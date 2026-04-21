import threading
from django.db import close_old_connections
from django.utils import timezone
from rest_framework import viewsets, serializers as drf_serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from accounts.serializers import UserSerializer
from accounts.models import RolePermission
from .models import Contact, OperatorFeedback
from .serializers import ContactSerializer
from .transcription import transcribe_audio
from .summarization import summarize_transcription


def _summarize_in_background(contact_id):
    close_old_connections()
    try:
        contact = Contact.objects.get(pk=contact_id)
        summarize_transcription(contact)
    except Contact.DoesNotExist:
        pass
    finally:
        close_old_connections()


def _transcribe_in_background(contact_id):
    """Run transcription in a background thread so the API responds immediately."""
    close_old_connections()
    try:
        contact = Contact.objects.get(pk=contact_id)
        transcribe_audio(contact)
    except Contact.DoesNotExist:
        pass
    finally:
        close_old_connections()


def _is_operator(user):
    return getattr(user, 'role', '') == 'operator' and not user.is_staff


class ContactViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ContactSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if _is_operator(request.user):
            if instance.created_by_id != request.user.id:
                return Response(
                    {'detail': 'Operators can only delete their own activity records.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        elif not RolePermission.has_perm(request.user, 'partners', 'delete'):
            return Response({'detail': 'You do not have permission to delete.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if _is_operator(request.user) and instance.created_by_id != request.user.id:
            return Response(
                {'detail': 'Operators can only edit their own activity records.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def get_queryset(self):
        from django.db.models import Count, Q, OuterRef, Subquery, IntegerField
        # Annotate per-partner call_number once at query level instead of running
        # one COUNT(*) per row inside ContactSerializer (was the main N+1 hot spot).
        call_number_sq = (
            Contact.objects
            .filter(partner_id=OuterRef('partner_id'), date__lte=OuterRef('date'))
            .order_by()
            .values('partner_id')
            .annotate(c=Count('id'))
            .values('c')
        )
        qs = (
            Contact.objects
            .select_related('created_by', 'partner')
            .annotate(call_number_annotated=Subquery(call_number_sq, output_field=IntegerField()))
        )
        partner_id = self.request.query_params.get('partner')
        if partner_id:
            qs = qs.filter(partner_id=partner_id)
        if self.request.query_params.get('has_audio') == 'true':
            qs = qs.exclude(audio_file='').exclude(audio_file__isnull=True)
        created_by = self.request.query_params.get('created_by')
        if created_by:
            qs = qs.filter(created_by_id=created_by)
        date_after = self.request.query_params.get('date_after')
        if date_after:
            qs = qs.filter(date__date__gte=date_after)
        date_before = self.request.query_params.get('date_before')
        if date_before:
            qs = qs.filter(date__date__lte=date_before)
        ordering = self.request.query_params.get('ordering')
        if ordering in ('-date', 'date', '-quality_overall', 'quality_overall'):
            qs = qs.order_by(ordering)
        return qs

    def perform_create(self, serializer):
        contact = serializer.save(created_by=self.request.user)
        if contact.audio_file:
            contact.transcription_status = 'pending'
            contact.save(update_fields=['transcription_status'])
            t = threading.Thread(target=_transcribe_in_background, args=(contact.id,), daemon=True)
            t.start()

    @action(detail=True, methods=['post'], url_path='retry-transcription')
    def retry_transcription(self, request, pk=None):
        contact = self.get_object()
        if _is_operator(request.user) and contact.created_by_id != request.user.id:
            return Response({'error': 'Forbidden'}, status=403)
        if not contact.audio_file:
            return Response({'error': 'No audio file attached.'}, status=400)
        contact.transcription_status = 'pending'
        contact.transcription = ''
        contact.summary = ''
        contact.summary_status = ''
        contact.save(update_fields=['transcription_status', 'transcription', 'summary', 'summary_status'])
        t = threading.Thread(target=_transcribe_in_background, args=(contact.id,), daemon=True)
        t.start()
        return Response(ContactSerializer(contact).data)

    @action(detail=True, methods=['post'], url_path='retry-summary')
    def retry_summary(self, request, pk=None):
        contact = self.get_object()
        if _is_operator(request.user) and contact.created_by_id != request.user.id:
            return Response({'error': 'Forbidden'}, status=403)
        if not contact.transcription:
            return Response({'error': 'No transcription available.'}, status=400)
        contact.summary_status = 'pending'
        contact.summary = ''
        contact.save(update_fields=['summary_status', 'summary'])
        t = threading.Thread(target=_summarize_in_background, args=(contact.id,), daemon=True)
        t.start()
        return Response(ContactSerializer(contact).data)

    @action(detail=True, methods=['post'], url_path='rediarize')
    def rediarize(self, request, pk=None):
        """Re-run translation + speaker diarization on the existing raw transcript
        without re-transcribing the audio. Admin or owner only.

        Runs in a background thread because the OpenAI call can take 30s+.
        """
        contact = self.get_object()
        if not contact.transcription:
            return Response({'error': 'No raw transcription available — run transcription first.'}, status=400)
        user = request.user
        if not (user.is_staff or getattr(user, 'role', '') == 'admin' or contact.created_by_id == user.id):
            return Response({'error': 'Forbidden'}, status=403)

        def _rediarize_background(cid):
            from .transcription import _diarize_with_openai
            close_old_connections()
            try:
                c = Contact.objects.get(pk=cid)
                new_diar = _diarize_with_openai(c.transcription)
                c.diarized_transcript = new_diar
                c.save(update_fields=['diarized_transcript'])
            except Exception:
                pass
            finally:
                close_old_connections()

        threading.Thread(target=_rediarize_background, args=(contact.id,), daemon=True).start()
        return Response({'queued': True, 'detail': 'Rediarization started in background.'})

    def perform_update(self, serializer):
        old_audio = serializer.instance.audio_file.name if serializer.instance.audio_file else None
        contact = serializer.save()
        new_audio = contact.audio_file.name if contact.audio_file else None
        if new_audio and new_audio != old_audio:
            contact.transcription_status = 'pending'
            contact.save(update_fields=['transcription_status'])
            t = threading.Thread(target=_transcribe_in_background, args=(contact.id,), daemon=True)
            t.start()


class OperatorFeedbackSerializer(drf_serializers.ModelSerializer):
    operator_detail = UserSerializer(source='operator', read_only=True)

    class Meta:
        model = OperatorFeedback
        fields = [
            'id', 'operator', 'operator_detail', 'feedback_type',
            'period_start', 'period_end', 'calls_analyzed', 'avg_score',
            'content', 'status', 'acknowledged', 'acknowledged_at', 'created_at',
        ]
        read_only_fields = fields


class OperatorFeedbackView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = OperatorFeedback.objects.select_related('operator').filter(status='done')

        if request.user.role != 'admin':
            qs = qs.filter(operator=request.user)

        operator_id = request.query_params.get('operator')
        if operator_id and request.user.role == 'admin':
            qs = qs.filter(operator_id=operator_id)

        fb_type = request.query_params.get('type')
        if fb_type in ('daily', 'weekly'):
            qs = qs.filter(feedback_type=fb_type)

        data = OperatorFeedbackSerializer(qs[:100], many=True).data
        return Response(data)


class OperatorFeedbackAcknowledgeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            fb = OperatorFeedback.objects.get(pk=pk)
        except OperatorFeedback.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        if request.user.role != 'admin' and fb.operator_id != request.user.id:
            return Response({'error': 'Forbidden'}, status=403)

        fb.acknowledged = True
        fb.acknowledged_at = timezone.now()
        fb.save(update_fields=['acknowledged', 'acknowledged_at'])
        return Response(OperatorFeedbackSerializer(fb).data)


class GenerateFeedbackView(APIView):
    """Admin-only: trigger feedback generation for a specific operator or all."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'admin':
            return Response({'error': 'Admin only'}, status=403)

        from .feedback_generator import generate_daily_feedback, generate_weekly_feedback
        from accounts.models import User
        from datetime import date, timedelta

        target_date = request.data.get('date')
        fb_type = request.data.get('type', 'daily')
        operator_id = request.data.get('operator_id')

        if target_date:
            from datetime import datetime
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        else:
            target_date = date.today()

        if operator_id:
            operator_ids = list(User.objects.filter(pk=operator_id).values_list('pk', flat=True))
        else:
            operator_ids = list(User.objects.filter(is_active=True).values_list('pk', flat=True))

        # OpenAI feedback generation can take 30s+ per operator; never run in
        # the request thread or admin clicks would time out.
        def _run_in_background(ids, td, ftype):
            close_old_connections()
            try:
                for op in User.objects.filter(pk__in=ids):
                    try:
                        if ftype == 'weekly':
                            generate_weekly_feedback(op, td)
                        else:
                            generate_daily_feedback(op, td)
                    except Exception:
                        pass
            finally:
                close_old_connections()

        threading.Thread(
            target=_run_in_background,
            args=(operator_ids, target_date, fb_type),
            daemon=True,
        ).start()

        return Response({
            'queued': len(operator_ids),
            'type': fb_type,
            'date': target_date.isoformat(),
            'detail': 'Feedback generation started in background — refresh in a minute.',
        })
