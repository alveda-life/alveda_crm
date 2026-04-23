import threading
from django.db import close_old_connections
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, serializers as drf_serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from accounts.serializers import UserSerializer
from accounts.models import RolePermission
from .models import Contact, OperatorFeedback, CallInsight, InsightAggregate
from .serializers import (
    ContactSerializer, CallInsightListSerializer, CallInsightDetailSerializer,
    InsightAggregateListSerializer, InsightAggregateDetailSerializer,
    InsightAggregateCreateSerializer,
)
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


def _is_admin_user(user):
    return bool(user and user.is_authenticated and (user.is_staff or getattr(user, 'role', '') == 'admin'))


class CallInsightViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin-only list/detail of per-call partner insights."""
    permission_classes = [IsAuthenticated]
    queryset = CallInsight.objects.all()

    def get_queryset(self):
        if not _is_admin_user(self.request.user):
            return CallInsight.objects.none()

        qs = CallInsight.objects.select_related('partner', 'created_by', 'contact')
        partner = self.request.query_params.get('partner')
        if partner:
            qs = qs.filter(partner_id=partner)
        contact = self.request.query_params.get('contact')
        if contact:
            qs = qs.filter(contact_id=contact)
        date_after = self.request.query_params.get('date_after')
        if date_after:
            qs = qs.filter(call_date__date__gte=date_after)
        date_before = self.request.query_params.get('date_before')
        if date_before:
            qs = qs.filter(call_date__date__lte=date_before)
        bucket = self.request.query_params.get('density_bucket')
        if bucket in ('low', 'medium', 'high'):
            qs = qs.filter(density_bucket=bucket)
        st = self.request.query_params.get('status')
        if st in ('pending', 'processing', 'done', 'failed'):
            qs = qs.filter(status=st)
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(insights_markdown__icontains=search)
                | Q(partner__name__icontains=search),
            )
        ordering = self.request.query_params.get('ordering')
        if ordering in ('call_date', '-call_date', 'created_at', '-created_at', 'insight_count', '-insight_count'):
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by('-call_date', '-id')
        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CallInsightDetailSerializer
        return CallInsightListSerializer


class InsightAggregateViewSet(viewsets.ModelViewSet):
    """
    Admin-only cross-call aggregate reports.

    POST creates a job (date_from, date_to) and kicks off background generation.
    GET list / retrieve return aggregated themes ranked by unique partner count.
    """
    permission_classes = [IsAuthenticated]
    queryset = InsightAggregate.objects.all()
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        if not _is_admin_user(self.request.user):
            return InsightAggregate.objects.none()
        qs = InsightAggregate.objects.select_related('created_by')
        # By default, the admin "Aggregate report" tab only shows manual
        # ad-hoc reports. Rolling general-insight rows live in their own page
        # and would just create noise here. Pass ?include_rolling=1 to opt in.
        if not self.request.query_params.get('include_rolling'):
            qs = qs.filter(kind=InsightAggregate.KIND_MANUAL)
        st = self.request.query_params.get('status')
        if st in ('pending', 'processing', 'done', 'failed'):
            qs = qs.filter(status=st)
        return qs.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return InsightAggregateCreateSerializer
        if self.action == 'retrieve':
            return InsightAggregateDetailSerializer
        return InsightAggregateListSerializer

    def create(self, request, *args, **kwargs):
        if not _is_admin_user(request.user):
            return Response({'detail': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        agg = serializer.save()
        from .aggregation import enqueue_aggregate
        enqueue_aggregate(agg.pk)
        return Response(InsightAggregateDetailSerializer(agg).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        if not _is_admin_user(request.user):
            return Response({'detail': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='retry')
    def retry(self, request, pk=None):
        if not _is_admin_user(request.user):
            return Response({'detail': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        agg = self.get_object()
        agg.status = InsightAggregate.STATUS_PENDING
        agg.last_error = ''
        agg.last_attempt_at = timezone.now()
        agg.save(update_fields=['status', 'last_error', 'last_attempt_at', 'updated_at'])
        from .aggregation import enqueue_aggregate
        enqueue_aggregate(agg.pk)
        return Response(InsightAggregateDetailSerializer(agg).data)

    @action(detail=False, methods=['get', 'post'], url_path='general')
    def general(self, request):
        """
        General Insights — always-on rolling top-15 view.

        GET  ?period=30d|60d|180d|all   → returns the cached InsightAggregate
                                          row for that bucket. Builds it in
                                          background if missing or stale (>6h).
        POST ?period=30d|60d|180d|all   → forces a fresh rebuild.
        """
        if not _is_admin_user(request.user):
            return Response({'detail': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        period = (request.query_params.get('period') or '30d').lower()
        kind_map = {
            '30d': InsightAggregate.KIND_ROLLING_30D,
            '60d': InsightAggregate.KIND_ROLLING_60D,
            '180d': InsightAggregate.KIND_ROLLING_180D,
            'all': InsightAggregate.KIND_ROLLING_ALL,
        }
        if period not in kind_map:
            return Response(
                {'detail': 'period must be one of: 30d, 60d, 180d, all'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .aggregation import find_or_create_rolling
        try:
            row = find_or_create_rolling(
                kind_map[period],
                force_refresh=(request.method == 'POST'),
            )
        except Exception as e:
            return Response({'detail': 'Build failed: %s' % e}, status=500)
        return Response(InsightAggregateDetailSerializer(row).data)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        from django.http import HttpResponse
        if not _is_admin_user(request.user):
            return Response({'detail': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        agg = self.get_object()
        if agg.status != InsightAggregate.STATUS_DONE:
            return Response(
                {'detail': 'Aggregate is not ready (status=%s)' % agg.status},
                status=status.HTTP_409_CONFLICT,
            )
        from .aggregate_pdf import render_aggregate_pdf
        try:
            data = render_aggregate_pdf(agg)
        except Exception as e:
            return Response({'detail': 'PDF render failed: %s' % e}, status=500)
        filename = f'aggregate-insights-{agg.date_from}-to-{agg.date_to}.pdf'
        resp = HttpResponse(data, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        resp['Content-Length'] = str(len(data))
        return resp


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
        CallInsight.objects.filter(contact=contact).delete()
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

    @action(detail=True, methods=['post'], url_path='retry-insights')
    def retry_insights(self, request, pk=None):
        """Admin-only: re-run partner insight extraction for this call."""
        if not _is_admin_user(request.user):
            return Response({'error': 'Admin only'}, status=403)
        contact = self.get_object()
        if contact.transcription_status != Contact.TRANSCRIPTION_DONE:
            return Response({'error': 'Transcription must be done first.'}, status=400)
        if not (contact.transcription or contact.diarized_transcript):
            return Response({'error': 'No transcript text.'}, status=400)

        def _bg(cid):
            close_old_connections()
            try:
                from .insights import extract_call_insights
                extract_call_insights(cid, force=True)
            finally:
                close_old_connections()

        threading.Thread(target=_bg, args=(contact.id,), daemon=True).start()
        return Response({'queued': True})

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
