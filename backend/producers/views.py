from datetime import timedelta, datetime
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Producer, ProducerTask, ProducerComment
from .serializers import (
    ProducerListSerializer, ProducerDetailSerializer, ProducerWriteSerializer,
    ProducerTaskSerializer, ProducerTaskGlobalSerializer, ProducerCommentSerializer,
)
from accounts.models import RolePermission


def _is_admin(user):
    return user.is_staff or getattr(user, 'role', '') == 'admin'


def _can(user, section, action):
    return RolePermission.has_perm(user, section, action)


def _producer_qs_annotated():
    from django.db.models import Max
    return (
        Producer.objects
        .select_related('assigned_to', 'created_by')
        .annotate(
            tasks_count=Count('tasks', distinct=True),
            open_tasks_count=Count('tasks', filter=Q(tasks__status__in=['open', 'in_progress']), distinct=True),
            comments_count=Count('comments', distinct=True),
            last_comment_at=Max('comments__created_at'),
        )
    )


def _funnel_section(funnel):
    return 'producers_onboarding' if funnel == Producer.FUNNEL_ONBOARDING else 'producers_support'


class ProducerViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields   = ['funnel', 'stage', 'assigned_to']
    search_fields      = ['name', 'company', 'phone', 'email']
    ordering_fields    = ['name', 'created_at', 'updated_at', 'stage']
    ordering           = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        qs = _producer_qs_annotated()
        if _is_admin(user):
            return qs
        # Filter to funnels the user can view
        allowed_funnels = []
        if _can(user, 'producers_onboarding', 'view'):
            allowed_funnels.append(Producer.FUNNEL_ONBOARDING)
        if _can(user, 'producers_support', 'view'):
            allowed_funnels.append(Producer.FUNNEL_SUPPORT)
        if not allowed_funnels:
            return Producer.objects.none()
        qs = qs.filter(funnel__in=allowed_funnels)
        return qs

    def _check_funnel_perm(self, funnel, action):
        section = _funnel_section(funnel)
        if not _can(self.request.user, section, action):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(f'No {action} permission for {section}.')

    def _annotated(self, pk):
        return _producer_qs_annotated().get(pk=pk)

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProducerWriteSerializer
        if self.action == 'retrieve':
            return ProducerDetailSerializer
        return ProducerListSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        funnel = request.data.get('funnel', Producer.FUNNEL_ONBOARDING)
        self._check_funnel_perm(funnel, 'create')
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            ProducerListSerializer(self._annotated(serializer.instance.pk)).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        partial  = kwargs.pop('partial', False)
        instance = self.get_object()
        self._check_funnel_perm(instance.funnel, 'edit')
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProducerListSerializer(self._annotated(serializer.instance.pk)).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self._check_funnel_perm(instance.funnel, 'delete')
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Kanban ───────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='kanban')
    def kanban(self, request):
        funnel = request.query_params.get('funnel', Producer.FUNNEL_ONBOARDING)
        qs = self.get_queryset().filter(funnel=funnel)

        # Optional filters
        assigned_to = request.query_params.get('assigned_to')
        if assigned_to:
            qs = qs.filter(assigned_to=assigned_to)
        search = request.query_params.get('search')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(company__icontains=search))

        stage_choices = (
            Producer.ONBOARDING_STAGE_CHOICES
            if funnel == Producer.FUNNEL_ONBOARDING
            else Producer.SUPPORT_STAGE_CHOICES
        )
        result = {}
        for stage_key, _ in stage_choices:
            result[stage_key] = ProducerListSerializer(
                qs.filter(stage=stage_key), many=True
            ).data
        return Response(result)

    # ── Stage change ─────────────────────────────────────────────────────────
    # ── Abandoned (AI analysis) ──────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='abandoned')
    def abandoned(self, request):
        """Start a background abandoned-analysis job. Returns {job_id, status}."""
        import threading
        from .models import ProducerAbandonedJob

        can_on  = _can(request.user, 'producers_onboarding', 'view')
        can_sup = _can(request.user, 'producers_support', 'view')
        if not _is_admin(request.user) and not can_on and not can_sup:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        funnel_filter = request.data.get('funnel', '')

        job = ProducerAbandonedJob.objects.create(
            created_by=request.user,
            funnel_filter=funnel_filter or '',
            status=ProducerAbandonedJob.STATUS_PENDING,
        )

        def run(job_id, user_id, is_admin, can_on, can_sup, funnel_filter):
            import json, django
            from openai import OpenAI
            django.db.close_old_connections()
            from producers.models import Producer, ProducerAbandonedJob
            from django.db.models import Max as _Max
            from django.utils import timezone

            job = ProducerAbandonedJob.objects.get(pk=job_id)
            job.status = ProducerAbandonedJob.STATUS_RUNNING
            job.save(update_fields=['status'])

            try:
                qs = Producer.objects.exclude(stage=Producer.STAGE_STOPPED)

                if not is_admin:
                    allowed_funnels = []
                    if can_on:  allowed_funnels.append(Producer.FUNNEL_ONBOARDING)
                    if can_sup: allowed_funnels.append(Producer.FUNNEL_SUPPORT)
                    qs = qs.filter(funnel__in=allowed_funnels)

                if funnel_filter:
                    qs = qs.filter(funnel=funnel_filter)

                qs = (
                    qs
                    .annotate(last_comment_at=_Max('comments__created_at'))
                    .prefetch_related('comments__author')
                    .select_related('assigned_to')
                )

                producers = list(qs.order_by('last_comment_at')[:60])

                if not producers:
                    job.status         = ProducerAbandonedJob.STATUS_DONE
                    job.results        = []
                    job.total_analyzed = 0
                    job.completed_at   = timezone.now()
                    job.save(update_fields=['status', 'results', 'total_analyzed', 'completed_at'])
                    return

                items = []
                for p in producers:
                    recent = list(p.comments.order_by('-created_at')[:8])
                    lines = []
                    for c in reversed(recent):
                        author = ''
                        if c.author:
                            author = f'{c.author.first_name} {c.author.last_name}'.strip() or c.author.username
                        else:
                            author = 'Unknown'
                        text = (c.text or '').strip()
                        if text:
                            lines.append(f'[{c.created_at.strftime("%Y-%m-%d")}] {author}: {text}')
                    items.append({
                        'id':          p.id,
                        'name':        p.name,
                        'company':     p.company or '',
                        'stage':       p.get_stage_display(),
                        'stage_since': p.stage_changed_at.strftime('%Y-%m-%d') if p.stage_changed_at else 'unknown',
                        'comments':    lines,
                    })

                prompt = (
                    'You analyze CRM producer cards for a business development team '
                    'that connects Ayurveda product manufacturers to a sales platform.\n\n'
                    'For each producer card, decide if it is "abandoned" — meaning recent activity '
                    'shows NO real business progress. Signs of abandonment: comments consist only of '
                    'passive waiting phrases ("waiting for a reply", "sent WhatsApp, no response", '
                    '"following up again", "no answer", "жду ответа", "написал письмо, жду", '
                    '"написал в WhatsApp, жду", "снова написал" etc.). '
                    'A card with NO comments that has been in the same stage for 7+ days is also abandoned.\n\n'
                    'A card is NOT abandoned if recent comments show real progress: '
                    'contract negotiations, actual agreements, documents exchanged, '
                    'pricing discussed, meeting scheduled, partnership confirmed, etc.\n\n'
                    'Return ONLY a valid JSON array (no markdown, no extra text). Each element:\n'
                    '{"id": <integer>, "abandoned": <true|false>, "reason": "<1-sentence reason>"}\n\n'
                    f'Producer cards:\n{json.dumps(items, ensure_ascii=False)}'
                )

                ai_client = OpenAI()
                resp = ai_client.chat.completions.create(
                    model='gpt-4o-mini',
                    max_tokens=3000,
                    messages=[{'role': 'user', 'content': prompt}],
                )
                text = resp.choices[0].message.content.strip()
                if text.startswith('```'):
                    text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
                classifications = json.loads(text)

                class_map = {c['id']: c for c in classifications if isinstance(c, dict)}
                results = []
                for p in producers:
                    cls = class_map.get(p.id, {})
                    if not cls.get('abandoned'):
                        continue
                    assigned = p.assigned_to
                    results.append({
                        'id':               p.id,
                        'name':             p.name,
                        'company':          p.company,
                        'funnel':           p.funnel,
                        'funnel_display':   p.get_funnel_display(),
                        'stage':            p.stage,
                        'stage_display':    p.get_stage_display(),
                        'stage_since':      p.stage_changed_at.isoformat() if p.stage_changed_at else None,
                        'last_comment_at':  p.last_comment_at.isoformat() if p.last_comment_at else None,
                        'assigned_to':      p.assigned_to_id,
                        'assigned_to_name': (
                            f'{assigned.first_name} {assigned.last_name}'.strip() or assigned.username
                            if assigned else None
                        ),
                        'ai_reason':        cls.get('reason', ''),
                    })

                results.sort(key=lambda x: x['last_comment_at'] or x['stage_since'] or '')

                job.status         = ProducerAbandonedJob.STATUS_DONE
                job.results        = results
                job.total_analyzed = len(producers)
                job.completed_at   = timezone.now()
                job.save(update_fields=['status', 'results', 'total_analyzed', 'completed_at'])

            except Exception as exc:
                job.status        = ProducerAbandonedJob.STATUS_ERROR
                job.error_message = str(exc)
                job.completed_at  = timezone.now()
                job.save(update_fields=['status', 'error_message', 'completed_at'])

        t = threading.Thread(
            target=run,
            args=(job.pk, request.user.pk, _is_admin(request.user), can_on, can_sup, funnel_filter),
            daemon=True,
        )
        t.start()

        return Response({'job_id': job.pk, 'status': job.status}, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=['get'], url_path='abandoned-status')
    def abandoned_status(self, request):
        """Poll status of an abandoned-analysis job."""
        from .models import ProducerAbandonedJob

        job_id = request.query_params.get('job_id')
        if not job_id:
            return Response({'detail': 'job_id required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            job = ProducerAbandonedJob.objects.get(pk=job_id, created_by=request.user)
        except ProducerAbandonedJob.DoesNotExist:
            return Response({'detail': 'Job not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = {
            'job_id':         job.pk,
            'status':         job.status,
            'total_analyzed': job.total_analyzed,
            'created_at':     job.created_at.isoformat(),
            'completed_at':   job.completed_at.isoformat() if job.completed_at else None,
        }
        if job.status == ProducerAbandonedJob.STATUS_DONE:
            data['results'] = job.results or []
        elif job.status == ProducerAbandonedJob.STATUS_ERROR:
            data['error'] = job.error_message
        return Response(data)

    @action(detail=False, methods=['get'], url_path='abandoned-history')
    def abandoned_history(self, request):
        """Return list of past abandoned-analysis jobs (summary only, no results payload)."""
        from .models import ProducerAbandonedJob

        qs = (
            ProducerAbandonedJob.objects
            .filter(created_by=request.user)
            .exclude(status=ProducerAbandonedJob.STATUS_PENDING)
            .exclude(status=ProducerAbandonedJob.STATUS_RUNNING)
            .order_by('-created_at')[:20]
        )

        items = []
        for job in qs:
            abandoned_count = len(job.results) if job.results else 0
            items.append({
                'job_id':           job.pk,
                'status':           job.status,
                'funnel_filter':    job.funnel_filter or None,
                'total_analyzed':   job.total_analyzed,
                'abandoned_count':  abandoned_count,
                'created_at':       job.created_at.isoformat(),
                'completed_at':     job.completed_at.isoformat() if job.completed_at else None,
                'error_message':    job.error_message if job.status == ProducerAbandonedJob.STATUS_ERROR else None,
            })

        return Response(items)

    @action(detail=True, methods=['patch'], url_path='stage')
    def update_stage(self, request, pk=None):
        producer = self.get_object()
        self._check_funnel_perm(producer.funnel, 'edit')
        stage  = request.data.get('stage')
        funnel = request.data.get('funnel', producer.funnel)

        all_stages = dict(Producer.ALL_STAGE_CHOICES)
        if stage not in all_stages:
            return Response({'error': 'Invalid stage'}, status=status.HTTP_400_BAD_REQUEST)

        producer.stage  = stage
        producer.funnel = funnel
        producer.save(update_fields=['stage', 'funnel', 'stage_changed_at', 'updated_at'])

        # Auto-create support record when producer reaches On the Platform in onboarding
        support_created = False
        if stage == Producer.STAGE_ON_PLATFORM and funnel == Producer.FUNNEL_ONBOARDING:
            already_in_support = Producer.objects.filter(
                funnel=Producer.FUNNEL_SUPPORT,
                name=producer.name,
                company=producer.company,
            ).exists()
            if not already_in_support:
                Producer.objects.create(
                    name=producer.name,
                    company=producer.company,
                    phone=producer.phone,
                    email=producer.email,
                    website=producer.website,
                    city=producer.city,
                    country=producer.country,
                    product_type=producer.product_type,
                    notes=producer.notes,
                    funnel=Producer.FUNNEL_SUPPORT,
                    stage=Producer.STAGE_AGREED,
                    assigned_to=producer.assigned_to,
                    created_by=producer.created_by,
                )
                support_created = True

        data = ProducerListSerializer(self._annotated(producer.pk)).data
        data['support_created'] = support_created
        return Response(data)

    # ── Tasks ─────────────────────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='tasks')
    def add_task(self, request, pk=None):
        producer = self.get_object()
        s = ProducerTaskSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save(producer=producer, created_by=request.user)
        return Response(
            ProducerDetailSerializer(self._annotated(producer.pk), context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['patch'], url_path=r'tasks/(?P<task_pk>\d+)')
    def update_task(self, request, pk=None, task_pk=None):
        producer = self.get_object()
        task = ProducerTask.objects.filter(pk=task_pk, producer=producer).first()
        if not task:
            return Response(status=status.HTTP_404_NOT_FOUND)
        s = ProducerTaskSerializer(task, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        new_status = s.validated_data.get('status', task.status)
        extra = {}
        if new_status == ProducerTask.STATUS_DONE and task.status != ProducerTask.STATUS_DONE:
            extra['completed_by'] = request.user
            extra['completed_at'] = timezone.now()
        elif new_status != ProducerTask.STATUS_DONE and task.status == ProducerTask.STATUS_DONE:
            extra['completed_by'] = None
            extra['completed_at'] = None
        s.save(**extra)
        return Response(
            ProducerDetailSerializer(self._annotated(producer.pk), context={'request': request}).data
        )

    @action(detail=True, methods=['delete'], url_path=r'tasks/(?P<task_pk>\d+)/delete')
    def delete_task(self, request, pk=None, task_pk=None):
        producer = self.get_object()
        task = ProducerTask.objects.filter(pk=task_pk, producer=producer).first()
        if not task:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if not _is_admin(request.user) and task.created_by_id != request.user.pk:
            return Response({'detail': 'Not allowed.'}, status=status.HTTP_403_FORBIDDEN)
        task.delete()
        return Response(ProducerDetailSerializer(self._annotated(producer.pk), context={'request': request}).data)

    # ── Comments ──────────────────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='comments',
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def add_comment(self, request, pk=None):
        producer = self.get_object()
        s = ProducerCommentSerializer(data=request.data, context={'request': request})
        s.is_valid(raise_exception=True)
        s.save(producer=producer, author=request.user)
        return Response(
            ProducerDetailSerializer(self._annotated(producer.pk), context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['delete'], url_path=r'comments/(?P<comment_pk>\d+)')
    def delete_comment(self, request, pk=None, comment_pk=None):
        producer = self.get_object()
        comment = ProducerComment.objects.filter(pk=comment_pk, producer=producer).first()
        if not comment:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if comment.author_id != request.user.pk and not _is_admin(request.user):
            return Response({'detail': 'Not allowed.'}, status=status.HTTP_403_FORBIDDEN)
        comment.delete()
        return Response(ProducerDetailSerializer(self._annotated(producer.pk), context={'request': request}).data)


class ProducerTaskViewSet(viewsets.ModelViewSet):
    """Global producer tasks endpoint — tasks across all producers."""
    permission_classes = [IsAuthenticated]
    serializer_class   = ProducerTaskGlobalSerializer
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields   = ['producer', 'assigned_to', 'status', 'priority']
    search_fields      = ['title', 'description']
    ordering_fields    = ['due_date', 'priority', 'status', 'created_at', 'updated_at']
    ordering           = ['due_date', '-created_at']

    def get_queryset(self):
        user = self.request.user
        qs = ProducerTask.objects.select_related(
            'producer', 'assigned_to', 'created_by', 'completed_by'
        )
        if _is_admin(user):
            return qs
        allowed_funnels = []
        if _can(user, 'producers_onboarding', 'view'):
            allowed_funnels.append(Producer.FUNNEL_ONBOARDING)
        if _can(user, 'producers_support', 'view'):
            allowed_funnels.append(Producer.FUNNEL_SUPPORT)
        if not allowed_funnels:
            return ProducerTask.objects.none()
        return qs.filter(producer__funnel__in=allowed_funnels)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        instance  = self.get_object()
        new_status = serializer.validated_data.get('status', instance.status)
        extra = {}
        if new_status == ProducerTask.STATUS_DONE and instance.status != ProducerTask.STATUS_DONE:
            extra['completed_by'] = self.request.user
            extra['completed_at'] = timezone.now()
        elif new_status != ProducerTask.STATUS_DONE and instance.status == ProducerTask.STATUS_DONE:
            extra['completed_by'] = None
            extra['completed_at'] = None
        serializer.save(**extra)

    @action(detail=False, methods=['get'], url_path='open-count')
    def open_count(self, request):
        qs = self.get_queryset().filter(status__in=['open', 'in_progress'])
        return Response({'count': qs.count()})


class ProducerStatsView(APIView):
    """Quick stats for sidebar badge and dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        qs   = Producer.objects.all()
        if not _is_admin(user):
            allowed = []
            if _can(user, 'producers_onboarding', 'view'):
                allowed.append(Producer.FUNNEL_ONBOARDING)
            if _can(user, 'producers_support', 'view'):
                allowed.append(Producer.FUNNEL_SUPPORT)
            qs = qs.filter(funnel__in=allowed)
        return Response({
            'total':      qs.count(),
            'onboarding': qs.filter(funnel=Producer.FUNNEL_ONBOARDING).count(),
            'support':    qs.filter(funnel=Producer.FUNNEL_SUPPORT).count(),
            'by_stage': {
                k: qs.filter(stage=k).count()
                for k, _ in Producer.ALL_STAGE_CHOICES
            },
        })


class ProducerAnalyticsView(APIView):
    """Onboarding funnel analytics: stage breakdown, operator performance."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not _is_admin(user) and not _can(user, 'producers_onboarding', 'view'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        period       = request.query_params.get('period', 'month')
        date_from_s  = request.query_params.get('date_from')
        date_to_s    = request.query_params.get('date_to')

        now = timezone.now()

        if period == 'today':
            since = now.replace(hour=0, minute=0, second=0, microsecond=0)
            until = now
        elif period == 'week':
            since = now - timedelta(days=7)
            until = now
        elif period == 'month':
            since = now - timedelta(days=30)
            until = now
        elif period == 'custom' and date_from_s and date_to_s:
            since = timezone.make_aware(datetime.strptime(date_from_s, '%Y-%m-%d'))
            until = timezone.make_aware(datetime.strptime(date_to_s, '%Y-%m-%d')) + timedelta(days=1)
        else:  # all
            since = None
            until = now

        ob  = Producer.objects.filter(funnel=Producer.FUNNEL_ONBOARDING)
        sup = Producer.objects.filter(funnel=Producer.FUNNEL_SUPPORT)

        # ── Stage breakdown ──────────────────────────────────────────────────
        total_ob = ob.count()
        max_count = max((ob.filter(stage=k).count() for k, _ in Producer.ONBOARDING_STAGE_CHOICES), default=1) or 1

        by_stage = []
        for key, label in Producer.ONBOARDING_STAGE_CHOICES:
            stage_qs = ob.filter(stage=key)
            count    = stage_qs.count()
            items    = list(stage_qs.filter(stage_changed_at__isnull=False).values_list('stage_changed_at', flat=True))
            avg_days = round(sum((now - dt).days for dt in items) / len(items), 1) if items else None
            by_stage.append({
                'key':      key,
                'label':    label,
                'count':    count,
                'pct':      round(count / total_ob * 100, 1) if total_ob else 0,
                'bar_pct':  round(count / max_count * 100) if max_count else 0,
                'avg_days': avg_days,
            })

        # ── Period stats ─────────────────────────────────────────────────────
        if since:
            new_period      = ob.filter(created_at__gte=since, created_at__lte=until).count()
            moved_to_support = sup.filter(stage_changed_at__gte=since, stage_changed_at__lte=until).count()
        else:
            new_period      = total_ob
            moved_to_support = sup.count()

        stopped = ob.filter(stage=Producer.STAGE_STOPPED).count()

        # ── Operator breakdown ───────────────────────────────────────────────
        from accounts.models import User as UserModel
        op_agg = (
            ob.filter(assigned_to__isnull=False)
              .values(
                  'assigned_to',
                  'assigned_to__username',
                  'assigned_to__first_name',
                  'assigned_to__last_name',
              )
              .annotate(
                  assigned  = Count('id'),
                  stopped   = Count('id', filter=Q(stage=Producer.STAGE_STOPPED)),
                  advanced  = Count('id', filter=Q(stage__in=[
                      Producer.STAGE_TERMS_NEGOTIATION,
                      Producer.STAGE_NEGOTIATION,
                      Producer.STAGE_CONTRACT_SIGNED,
                      Producer.STAGE_ON_PLATFORM,
                  ])),
              )
        )

        operators = []
        for row in op_agg:
            uid     = row['assigned_to']
            fname   = (row['assigned_to__first_name'] or '').strip()
            lname   = (row['assigned_to__last_name']  or '').strip()
            name    = f'{fname} {lname}'.strip() or row['assigned_to__username']
            support = sup.filter(assigned_to_id=uid).count()
            a       = row['assigned']
            operators.append({
                'name':             name,
                'assigned':         a,
                'stopped':          row['stopped'],
                'advanced':         row['advanced'],
                'moved_to_support': support,
                'conv_pct':         round(support / a * 100, 1) if a else 0,
            })

        operators.sort(key=lambda x: -x['assigned'])

        # ── Weekly new producers (last 10 weeks) ─────────────────────────────
        weeks = []
        for i in range(9, -1, -1):
            w_start = (now - timedelta(weeks=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            w_end   = w_start + timedelta(days=7)
            w_end_label = w_start + timedelta(days=6)
            suffix = ' →' if i == 0 else ''
            label  = f"{w_start.day}–{w_end_label.day} {w_end_label.strftime('%b')}{suffix}"
            weeks.append({
                'label': label,
                'count': ob.filter(created_at__gte=w_start, created_at__lt=w_end).count(),
            })

        # ── Support funnel breakdown ─────────────────────────────────────────
        sup_qs = Producer.objects.filter(funnel=Producer.FUNNEL_SUPPORT)
        support_stages = []
        for key, label in Producer.SUPPORT_STAGE_CHOICES:
            cnt  = sup_qs.filter(stage=key).count()
            rows = list(sup_qs.filter(stage=key, stage_changed_at__isnull=False).values_list('stage_changed_at', flat=True))
            avg_days = round(sum((now - dt).days for dt in rows) / len(rows), 1) if rows else None
            support_stages.append({'key': key, 'label': label, 'count': cnt, 'avg_days': avg_days})

        # ── Product categories (parse comma-separated) ───────────────────────
        from collections import Counter as _Counter
        cat_counter = _Counter()
        for pt in Producer.objects.filter(product_type__gt='').values_list('product_type', flat=True):
            for cat in pt.split(','):
                cat = cat.strip()
                if cat:
                    cat_counter[cat] += 1
        total_cats = sum(cat_counter.values()) or 1
        pt_rows = [
            {'product_type': k, 'count': v, 'pct': round(v / total_cats * 100, 1)}
            for k, v in cat_counter.most_common(15)
        ]

        # ── Top countries ────────────────────────────────────────────────────
        from django.db.models import Count as DjCount
        country_rows = list(
            Producer.objects.filter(country__gt='')
            .values('country')
            .annotate(count=DjCount('id'))
            .order_by('-count')[:12]
        )

        # ── Priority breakdown ───────────────────────────────────────────────
        all_producers = Producer.objects.all()
        total_all = all_producers.count() or 1
        by_priority = [
            {'label': 'High',   'value': 'high',   'color': '#C62828',
             'count': all_producers.filter(priority='high').count()},
            {'label': 'Medium', 'value': 'medium', 'color': '#E65100',
             'count': all_producers.filter(priority='medium').count()},
            {'label': 'Low',    'value': 'low',    'color': '#757575',
             'count': all_producers.filter(priority='low').count()},
        ]
        for r in by_priority:
            r['pct'] = round(r['count'] / total_all * 100, 1)

        # ── Cooperation potential breakdown ──────────────────────────────────
        by_coop = [
            {'label': 'Strong',      'value': 'strong',      'color': '#2E7D32',
             'count': all_producers.filter(cooperation_potential='strong').count()},
            {'label': 'Medium',      'value': 'medium',      'color': '#1565C0',
             'count': all_producers.filter(cooperation_potential='medium').count()},
            {'label': 'Weak',        'value': 'weak',        'color': '#E65100',
             'count': all_producers.filter(cooperation_potential='weak').count()},
            {'label': 'No Response', 'value': 'no_response', 'color': '#757575',
             'count': all_producers.filter(cooperation_potential='no_response').count()},
        ]
        for r in by_coop:
            r['pct'] = round(r['count'] / total_all * 100, 1)

        # ── Follow-up overdue ────────────────────────────────────────────────
        from datetime import date as _date
        overdue_followups = all_producers.filter(
            control_date__isnull=False,
            control_date__lt=_date.today()
        ).count()

        # ── Upcoming planned connection dates ────────────────────────────────
        from datetime import date as _date
        upcoming_connections = list(
            Producer.objects
            .filter(planned_connection_date__isnull=False)
            .exclude(stage=Producer.STAGE_STOPPED)
            .exclude(stage=Producer.STAGE_ON_PLATFORM)
            .order_by('planned_connection_date')
            .values('id', 'name', 'company', 'planned_connection_date', 'stage', 'funnel',
                    'priority', 'cooperation_potential')
        )
        for p in upcoming_connections:
            p['stage_display'] = dict(Producer.ALL_STAGE_CHOICES).get(p['stage'], p['stage'])
            p['is_overdue']    = p['planned_connection_date'] < _date.today()
            p['planned_connection_date'] = p['planned_connection_date'].isoformat()

        # ── Task stats ───────────────────────────────────────────────────────
        all_tasks = ProducerTask.objects.all()
        task_total = all_tasks.count()
        task_done  = all_tasks.filter(status='done').count()
        task_stats = {
            'total':           task_total,
            'open':            all_tasks.filter(status__in=['open', 'in_progress']).count(),
            'done':            task_done,
            'overdue':         all_tasks.filter(status__in=['open', 'in_progress'], due_date__lt=now.date()).count(),
            'completion_rate': round(task_done / task_total * 100, 1) if task_total else 0,
        }

        # ── Weekly comments (last 10 weeks) ──────────────────────────────────
        comment_weeks = []
        for i in range(9, -1, -1):
            w_start = (now - timedelta(weeks=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            w_end   = w_start + timedelta(days=7)
            w_end_label = w_start + timedelta(days=6)
            suffix = ' →' if i == 0 else ''
            label  = f"{w_start.day}–{w_end_label.day} {w_end_label.strftime('%b')}{suffix}"
            comment_weeks.append({
                'label': label,
                'count': ProducerComment.objects.filter(created_at__gte=w_start, created_at__lt=w_end).count(),
            })

        return Response({
            'totals': {
                'onboarding':       total_ob,
                'support':          sup.count(),
                'new_period':       new_period,
                'moved_to_support': moved_to_support,
                'stopped':          stopped,
            },
            'by_stage':       by_stage,
            'operators':      operators,
            'weekly_new':     weeks,
            'support_stages': support_stages,
            'by_product_type':   pt_rows,
            'by_country':        country_rows,
            'by_priority':       by_priority,
            'by_coop':           by_coop,
            'overdue_followups':      overdue_followups,
            'upcoming_connections':   upcoming_connections,
            'task_stats':             task_stats,
            'weekly_comments':        comment_weeks,
        })
