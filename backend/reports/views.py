import os, json, threading
from django.utils import timezone
from django.db import close_old_connections
from datetime import timedelta
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Sum, Q
from .models import AiReport, ProducerUpdateReport, BrandSituationReport
from .serializers import (
    AiReportSerializer, ProducerUpdateReportSerializer, BrandSituationReportSerializer,
)


def gather_partners_snapshot():
    """Partners + operators + tasks data for AI context."""
    from partners.models import Partner
    from contacts.models import Contact
    from tasks.models import Task
    from accounts.models import User

    now = timezone.now()
    today = now.date()
    last_30 = now - timedelta(days=30)
    last_7  = now - timedelta(days=7)

    partners = Partner.objects.all()
    active_stages = ['new', 'trained', 'set_created', 'has_sale']
    dead_stages   = ['no_answer', 'declined', 'no_sales']

    # Financial
    fin = partners.aggregate(
        revenue=Sum('paid_orders_sum'),
        unpaid=Sum('unpaid_orders_sum'),
        orders=Sum('orders_count'),
        paid_orders=Sum('paid_orders_count'),
        sets=Sum('medical_sets_count'),
        referrals=Sum('referrals_count'),
    )

    # Operators
    operators = User.objects.filter(role='operator').order_by('first_name', 'username')
    op_rows = []
    for op in operators:
        asgn = partners.filter(assigned_to=op)
        total = asgn.count()
        sale  = asgn.filter(stage='has_sale').count()
        c30   = Contact.objects.filter(created_by=op, created_at__gte=last_30)
        c7    = Contact.objects.filter(created_by=op, created_at__gte=last_7)
        c30_agg = c30.aggregate(
            calls=Count('id', filter=Q(is_missed_call=False, callback_later=False)),
            missed=Count('id', filter=Q(is_missed_call=True)),
            callbacks=Count('id', filter=Q(callback_later=True)),
        )
        c7_agg = c7.aggregate(
            calls=Count('id', filter=Q(is_missed_call=False, callback_later=False)),
            missed=Count('id', filter=Q(is_missed_call=True)),
        )
        overdue = asgn.filter(stage__in=active_stages, control_date__lt=today).count()
        last_c  = Contact.objects.filter(created_by=op).order_by('-created_at').first()
        op_rows.append({
            'name':            op.get_full_name() or op.username,
            'assigned':        total,
            'active':          asgn.filter(stage__in=active_stages).count(),
            'dead':            asgn.filter(stage__in=dead_stages).count(),
            'overdue':         overdue,
            'partners_sale':   sale,
            'conv_to_sale_pct': round(sale / total * 100, 1) if total else 0,
            'revenue':         float(asgn.aggregate(r=Sum('paid_orders_sum'))['r'] or 0),
            'calls_30d':       c30_agg['calls'] or 0,
            'missed_30d':      c30_agg['missed'] or 0,
            'callbacks_30d':   c30_agg['callbacks'] or 0,
            'calls_7d':        c7_agg['calls'] or 0,
            'missed_7d':       c7_agg['missed'] or 0,
            'last_activity':   last_c.created_at.strftime('%Y-%m-%d') if last_c else 'never',
        })

    # Tasks
    tasks = Task.objects.all()
    task_snap = {
        'total':       tasks.count(),
        'open':        tasks.filter(status='open').count(),
        'in_progress': tasks.filter(status='in_progress').count(),
        'done':        tasks.filter(status='done').count(),
        'overdue':     tasks.filter(status__in=['open','in_progress'], due_date__lt=today).count(),
    }

    # Contact activity
    c_all = Contact.objects.all()
    c30_team = c_all.filter(created_at__gte=last_30).aggregate(
        calls=Count('id', filter=Q(is_missed_call=False, callback_later=False)),
        missed=Count('id', filter=Q(is_missed_call=True)),
        callbacks=Count('id', filter=Q(callback_later=True)),
    )
    transcribed = c_all.filter(transcription_status=Contact.TRANSCRIPTION_DONE)
    transcript_stats = transcribed.aggregate(
        done_total=Count('id'),
        done_last_30d=Count('id', filter=Q(date__gte=last_30)),
        with_summary=Count('id', filter=~Q(summary='')),
        with_any_text=Count('id', filter=(~Q(diarized_transcript='') | ~Q(transcription=''))),
    )
    transcript_rows = []
    for c in transcribed.select_related('partner', 'created_by').order_by('-date')[:20]:
        text = (c.diarized_transcript or c.transcription or '').strip()
        if not text:
            continue
        excerpt = ' '.join(text.split())
        if len(excerpt) > 900:
            excerpt = excerpt[:897] + '...'
        transcript_rows.append({
            'contact_id': c.id,
            'date': c.date.isoformat() if c.date else None,
            'partner': c.partner.name if c.partner_id else 'Unknown',
            'operator': (c.created_by.get_full_name() or c.created_by.username) if c.created_by_id else 'Unknown',
            'transcript_excerpt': excerpt,
            'summary': (c.summary or '').strip()[:500],
        })

    return {
        'snapshot_date': now.strftime('%Y-%m-%d %H:%M UTC'),
        'partners': {
            'total':         partners.count(),
            'active':        partners.filter(stage__in=active_stages).count(),
            'dead':          partners.filter(stage__in=dead_stages).count(),
            'new_last_30d':  partners.filter(created_at__gte=last_30).count(),
            'by_stage': {k: partners.filter(stage=k).count() for k, _ in Partner.STAGE_CHOICES},
            'by_type':  {k: partners.filter(type=k).count()  for k, _ in Partner.TYPE_CHOICES},
            'by_category': {k: partners.filter(category=k).count() for k, _ in Partner.CATEGORY_CHOICES},
            'financials': {
                'total_revenue':   float(fin['revenue'] or 0),
                'unpaid_pipeline': float(fin['unpaid']  or 0),
                'total_orders':    fin['orders']      or 0,
                'paid_orders':     fin['paid_orders'] or 0,
                'medical_sets':    fin['sets']        or 0,
                'referrals':       fin['referrals']   or 0,
            },
        },
        'team_calls_last_30d': {
            'calls':     c30_team['calls']     or 0,
            'missed':    c30_team['missed']    or 0,
            'callbacks': c30_team['callbacks'] or 0,
        },
        'transcriptions': {
            'done_total': transcript_stats['done_total'] or 0,
            'done_last_30d': transcript_stats['done_last_30d'] or 0,
            'with_summary': transcript_stats['with_summary'] or 0,
            'with_any_text': transcript_stats['with_any_text'] or 0,
            'recent_call_excerpts': transcript_rows,
        },
        'tasks': task_snap,
        'operators': op_rows,
    }


def gather_producers_snapshot():
    """Producers onboarding + support data for AI context."""
    from producers.models import Producer
    from accounts.models import User
    from django.db.models import Count, Q

    now    = timezone.now()
    last_30 = now - timedelta(days=30)
    last_7  = now - timedelta(days=7)

    ob  = Producer.objects.all().filter(funnel=Producer.FUNNEL_ONBOARDING)
    sup = Producer.objects.all().filter(funnel=Producer.FUNNEL_SUPPORT)

    # Per-operator breakdown
    op_rows = []
    operators = User.objects.filter(
        assigned_producers__isnull=False
    ).distinct().order_by('first_name', 'username')
    for op in operators:
        assigned_ob  = ob.filter(assigned_to=op).count()
        assigned_sup = sup.filter(assigned_to=op).count()
        if not assigned_ob and not assigned_sup:
            continue
        op_rows.append({
            'name':       op.get_full_name() or op.username,
            'onboarding': assigned_ob,
            'support':    assigned_sup,
            'stopped':    ob.filter(assigned_to=op, stage=Producer.STAGE_STOPPED).count(),
            'conv_pct':   round(assigned_sup / assigned_ob * 100, 1) if assigned_ob else 0,
        })

    return {
        'snapshot_date': now.strftime('%Y-%m-%d %H:%M UTC'),
        'onboarding_funnel': {
            'total':       ob.count(),
            'new_last_30d': ob.filter(created_at__gte=last_30).count(),
            'new_last_7d':  ob.filter(created_at__gte=last_7).count(),
            'stopped':     ob.filter(stage=Producer.STAGE_STOPPED).count(),
            'by_stage': {
                k: ob.filter(stage=k).count()
                for k, _ in Producer.ONBOARDING_STAGE_CHOICES
            },
        },
        'support_funnel': {
            'total':       sup.count(),
            'new_last_30d': sup.filter(stage_changed_at__gte=last_30).count(),
            'by_stage': {
                k: sup.filter(stage=k).count()
                for k, _ in Producer.SUPPORT_STAGE_CHOICES
            },
        },
        'operators': op_rows,
    }


PARTNERS_SYSTEM_PROMPT = """\
You are an AI analyst for "Ask Ayurveda" — a CRM system for managing Ayurveda product partners.

The CRM tracks:
• Partners (doctors, fitness trainers, bloggers, other) who sell Ayurveda products
• Funnel stages: New → Agreed to Create First Set → Set Created → Has Sale → (dead: No Answer / Declined / No Sales)
• Operators — CRM managers who call and support partners
• Calls/contacts recorded in the system
• Transcription excerpts and call summaries from processed calls
• Tasks for operators
• Financial metrics (revenue, orders, medical sets)

Rules for generating reports:
1. Always reply in the SAME LANGUAGE the user used in their request
2. Use Markdown formatting: ## for sections, ### for subsections, **bold** for key numbers
3. Use tables (Markdown table syntax) wherever data comparison makes sense
4. Use emojis for clarity: 📊 statistics, ✅ good/done, ⚠️ warning, 🔴 critical, 💰 revenue, 📞 calls
5. Always end with a "## Key Recommendations" section with 3-5 actionable points
6. Be specific — mention names, numbers, percentages from the data
7. If the user asks for a specific time period you don't have granular data for, use the available 30-day and 7-day windows and note the limitation
8. If transcription excerpts are provided and relevant, cite concrete phrases/patterns from them in your analysis
9. Never claim you lack access to call transcriptions or cannot see them when the JSON snapshot includes a `transcriptions` block with `done_total > 0` or any `recent_call_excerpts` entries — you MUST use that material for call-related questions.

Current Partners CRM snapshot ({snapshot_date}):
{crm_json}
"""

PRODUCERS_SYSTEM_PROMPT = """\
You are an AI analyst for "Ask Ayurveda" — a CRM system for managing Ayurveda producers (manufacturers/suppliers).

The CRM tracks producers across two funnels:
• Onboarding funnel — new producers being connected:
  Interest → In Communication → Negotiation → Contract Signed → On the Platform → Stopped
• Support funnel — active producers already signed:
  Agreed → Signed → Products Received → Ready to Sell → In Store

Key metrics:
• How many producers are at each stage
• Conversion rate from Onboarding to Support funnel
• Operator performance (who is handling which producers, conversion %)
• Time stuck in a stage (potential bottlenecks)

Rules for generating reports:
1. Always reply in the SAME LANGUAGE the user used in their request
2. Use Markdown formatting: ## for sections, ### for subsections, **bold** for key numbers
3. Use tables (Markdown table syntax) wherever data comparison makes sense
4. Use emojis for clarity: 📊 statistics, ✅ good/done, ⚠️ warning, 🔴 bottleneck, 🏭 producer
5. Always end with a "## Key Recommendations" section with 3-5 actionable points
6. Be specific — mention names, numbers, percentages from the data

Current Producers CRM snapshot ({snapshot_date}):
{crm_json}
"""


_REPORT_MAX_RETRIES = 3
_REPORT_RETRY_DELAYS = [5, 15, 30]


def _generate_in_background(report_id, prompt, api_key, system):
    import time
    close_old_connections()

    AiReport.objects.filter(pk=report_id).update(status=AiReport.STATUS_GENERATING)

    last_error = None
    for attempt in range(_REPORT_MAX_RETRIES):
        try:
            from openai import OpenAI
            client  = OpenAI(api_key=api_key)
            message = client.chat.completions.create(
                model='gpt-4o',
                max_tokens=4096,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': prompt},
                ],
            )
            content = message.choices[0].message.content
            title = next((l.lstrip('#').strip() for l in content.splitlines() if l.strip()), prompt[:80])
            if len(title) > 120:
                title = title[:117] + '…'
            AiReport.objects.filter(pk=report_id).update(
                status=AiReport.STATUS_DONE,
                title=title,
                content=content,
            )
            close_old_connections()
            return
        except Exception as e:
            last_error = e
            delay = _REPORT_RETRY_DELAYS[attempt] if attempt < len(_REPORT_RETRY_DELAYS) else _REPORT_RETRY_DELAYS[-1]
            time.sleep(delay)

    AiReport.objects.filter(pk=report_id).update(
        status=AiReport.STATUS_ERROR,
        error_message=str(last_error),
        title='Error generating report',
    )
    close_old_connections()


class GenerateReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        prompt      = (request.data.get('prompt') or '').strip()
        report_type = (request.data.get('report_type') or AiReport.TYPE_PARTNERS)
        if report_type not in (AiReport.TYPE_PARTNERS, AiReport.TYPE_PRODUCERS):
            report_type = AiReport.TYPE_PARTNERS

        if not prompt:
            return Response({'error': 'prompt is required'}, status=status.HTTP_400_BAD_REQUEST)

        api_key = os.environ.get('OPENAI_API_KEY', '')
        if not api_key:
            return Response({'error': 'OPENAI_API_KEY not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            if report_type == AiReport.TYPE_PRODUCERS:
                crm_data      = gather_producers_snapshot()
                system_tpl    = PRODUCERS_SYSTEM_PROMPT
            else:
                crm_data      = gather_partners_snapshot()
                system_tpl    = PARTNERS_SYSTEM_PROMPT

            system = system_tpl.format(
                snapshot_date=crm_data['snapshot_date'],
                crm_json=json.dumps(crm_data, ensure_ascii=False, indent=2),
            )

            report = AiReport.objects.create(
                prompt=prompt,
                report_type=report_type,
                created_by=request.user,
                status=AiReport.STATUS_PENDING,
            )

            t = threading.Thread(
                target=_generate_in_background,
                args=(report.pk, prompt, api_key, system),
                daemon=True,
            )
            t.start()

            return Response(AiReportSerializer(report).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AiReportViewSet(viewsets.ModelViewSet):
    permission_classes  = [IsAuthenticated]
    serializer_class    = AiReportSerializer
    http_method_names   = ['get', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = AiReport.objects.select_related('created_by')
        if not self.request.user.is_staff and getattr(self.request.user, 'role', '') != 'admin':
            qs = qs.filter(created_by=self.request.user)
        report_type = self.request.query_params.get('report_type')
        if report_type in (AiReport.TYPE_PARTNERS, AiReport.TYPE_PRODUCERS):
            qs = qs.filter(report_type=report_type)
        return qs


class ProducerUpdateReportViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve auto-generated producer update reports."""
    permission_classes = [IsAuthenticated]
    serializer_class   = ProducerUpdateReportSerializer

    def get_queryset(self):
        qs = ProducerUpdateReport.objects.all()
        report_type = self.request.query_params.get('type')
        if report_type in ('daily', 'weekly'):
            qs = qs.filter(report_type=report_type)
        return qs


class GenerateProducerUpdateView(APIView):
    """Manually trigger a daily or weekly producer update report. Admin only."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not (request.user.is_staff or getattr(request.user, 'role', '') == 'admin'):
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

        report_type = (request.data.get('type') or 'daily').strip()
        if report_type not in ('daily', 'weekly'):
            return Response({'error': 'type must be daily or weekly'}, status=status.HTTP_400_BAD_REQUEST)

        api_key = os.environ.get('OPENAI_API_KEY', '')
        if not api_key:
            return Response({'error': 'OPENAI_API_KEY not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            from .producer_update_generator import generate_update_report
            report = generate_update_report(report_type)
            return Response(ProducerUpdateReportSerializer(report).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BrandSituationReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Weekly brand situation snapshots — visible to producer-managers + admins.
    Any report stuck in pending/generating > 5 min, or in error, is auto-restarted.
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = BrandSituationReportSerializer

    def _auto_retry_stuck(self):
        from .brand_situation_generator import _run_generation
        cutoff = timezone.now() - timedelta(minutes=5)
        stuck = BrandSituationReport.objects.filter(
            status__in=[BrandSituationReport.STATUS_PENDING,
                        BrandSituationReport.STATUS_GENERATING,
                        BrandSituationReport.STATUS_ERROR],
            created_at__lt=cutoff,
        )
        for r in stuck:
            r.status = BrandSituationReport.STATUS_PENDING
            r.error_message = ''
            r.save(update_fields=['status', 'error_message'])
            t = threading.Thread(target=_run_generation, args=(r.pk,), daemon=True)
            t.start()

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, 'role', '')
        is_admin = user.is_staff or role == 'admin'
        is_producer_role = role in ('producer_operator', 'producer_onboarding', 'producer_support')
        if not (is_admin or is_producer_role):
            return BrandSituationReport.objects.none()
        try:
            self._auto_retry_stuck()
        except Exception:
            pass
        return BrandSituationReport.objects.all()


class GenerateBrandSituationView(APIView):
    """Manually trigger generation of the current week's brand situation report (admin only)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not (request.user.is_staff or getattr(request.user, 'role', '') == 'admin'):
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

        api_key = os.environ.get('OPENAI_API_KEY', '')
        if not api_key:
            return Response({'error': 'OPENAI_API_KEY not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            from .brand_situation_generator import generate_brand_situation_report
            report = generate_brand_situation_report(force=True)
            return Response(BrandSituationReportSerializer(report).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# AI Operations control panel
# ---------------------------------------------------------------------------

def _is_admin(user):
    return bool(user and (user.is_staff or getattr(user, 'role', '') == 'admin'))


def _serialize_run(run):
    return {
        'id':            run.id,
        'job_id':        run.job_id,
        'trigger':       run.trigger,
        'status':        run.status,
        'started_at':    run.started_at.isoformat() if run.started_at else None,
        'finished_at':   run.finished_at.isoformat() if run.finished_at else None,
        'duration_ms':   run.duration_ms,
        'summary':       run.summary,
        'error_message': run.error_message,
        'triggered_by':  (run.triggered_by.get_full_name() or run.triggered_by.username)
                          if run.triggered_by_id else None,
    }


def _job_payload(job, include_history=False):
    from .models import AiJobRun
    from .job_registry import compute_next_run

    runs_qs = AiJobRun.objects.filter(job_id=job['id'])
    last_run = runs_qs.first()
    last_success = runs_qs.filter(status=AiJobRun.STATUS_SUCCESS).first()
    last_error   = runs_qs.filter(status=AiJobRun.STATUS_ERROR).first()
    week_ago = timezone.now() - timedelta(days=7)
    recent = runs_qs.filter(started_at__gte=week_ago)
    counts = {
        'success': recent.filter(status=AiJobRun.STATUS_SUCCESS).count(),
        'error':   recent.filter(status=AiJobRun.STATUS_ERROR).count(),
        'running': runs_qs.filter(status=AiJobRun.STATUS_RUNNING).count(),
    }

    health = 'unknown'
    if counts['running']:
        health = 'running'
    elif last_run is None:
        health = 'never_ran'
    elif last_run.status == AiJobRun.STATUS_ERROR:
        health = 'error'
    elif last_run.status == AiJobRun.STATUS_SUCCESS:
        health = 'ok'

    payload = {
        'id':              job['id'],
        'category':        job.get('category', 'ai_reports'),
        'name':            job['name'],
        'description':     job['description'],
        'schedule_human':  job['schedule_human'],
        'timezone':        job['timezone'],
        'artifact':        job.get('artifact', ''),
        'artifact_path':   job.get('artifact_path', ''),
        'next_run':        compute_next_run(job),
        'health':          health,
        'last_run':        _serialize_run(last_run) if last_run else None,
        'last_success':    _serialize_run(last_success) if last_success else None,
        'last_error':      _serialize_run(last_error) if last_error else None,
        'last_7d_counts':  counts,
    }
    if include_history:
        payload['history'] = [_serialize_run(r) for r in runs_qs[:25]]
    return payload


class AiOperationsListView(APIView):
    """
    Admin control panel for every scheduled AI job.

    GET /api/ai-operations/                    list every job + status
    GET /api/ai-operations/<job_id>/           detail incl. last 25 runs
    POST /api/ai-operations/<job_id>/run-now/  fire the job in background
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_admin(request.user):
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        from .job_registry import JOB_REGISTRY
        from contacts.auto_retry import dead_ended_summary, MAX_RETRIES
        return Response({
            'jobs': [_job_payload(j) for j in JOB_REGISTRY],
            'dead_ended': dead_ended_summary(),
            'max_retries': MAX_RETRIES,
        })


class AiOperationsDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        if not _is_admin(request.user):
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        from .job_registry import get_job
        job = get_job(job_id)
        if not job:
            return Response({'error': 'Unknown job'}, status=status.HTTP_404_NOT_FOUND)
        return Response(_job_payload(job, include_history=True))


class AiOperationsRunNowView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        if not _is_admin(request.user):
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        from .job_registry import get_job, trigger_job_async
        job = get_job(job_id)
        if not job:
            return Response({'error': 'Unknown job'}, status=status.HTTP_404_NOT_FOUND)
        trigger_job_async(job_id, user=request.user)
        return Response({'queued': True, 'job_id': job_id}, status=status.HTTP_202_ACCEPTED)


class AiOperationsDeadEndedView(APIView):
    """
    GET  /api/ai-operations/dead-ended/  → admin list of rows that exhausted
                                           MAX_RETRIES so a human can investigate.
    POST /api/ai-operations/dead-ended/reset/ {kind, id} → reset retry counter
                                           and let the self-healer pick it up
                                           on the next pass.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_admin(request.user):
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        from contacts.models import Contact, OperatorFeedback, CallInsight, InsightAggregate
        from contacts.auto_retry import MAX_RETRIES

        def _short(s, n=240):
            s = s or ''
            return s if len(s) <= n else s[:n] + '…'

        transcriptions = [{
            'id': c.id,
            'partner': c.partner.name if c.partner_id else '—',
            'date': c.date.isoformat() if c.date else None,
            'retries': c.transcription_retries,
            'last_error': _short(c.transcription_last_error),
            'last_attempt_at': c.transcription_last_attempt_at.isoformat()
                                if c.transcription_last_attempt_at else None,
        } for c in Contact.objects.filter(
            transcription_status=Contact.TRANSCRIPTION_FAILED,
            transcription_retries__gte=MAX_RETRIES,
        ).select_related('partner').order_by('-transcription_last_attempt_at')[:100]]

        summaries = [{
            'id': c.id,
            'partner': c.partner.name if c.partner_id else '—',
            'date': c.date.isoformat() if c.date else None,
            'retries': c.summary_retries,
            'last_error': _short(c.summary_last_error),
            'last_attempt_at': c.summary_last_attempt_at.isoformat()
                                if c.summary_last_attempt_at else None,
        } for c in Contact.objects.filter(
            summary_status=Contact.TRANSCRIPTION_FAILED,
            summary_retries__gte=MAX_RETRIES,
        ).select_related('partner').order_by('-summary_last_attempt_at')[:100]]

        feedback = [{
            'id': fb.id,
            'operator': fb.operator.full_name or fb.operator.username if fb.operator_id else '—',
            'feedback_type': fb.feedback_type,
            'period_start': fb.period_start.isoformat() if fb.period_start else None,
            'retries': fb.generation_retries,
            'last_error': _short(fb.last_error),
            'last_attempt_at': fb.last_attempt_at.isoformat() if fb.last_attempt_at else None,
        } for fb in OperatorFeedback.objects.filter(
            status=OperatorFeedback.STATUS_FAILED,
            generation_retries__gte=MAX_RETRIES,
        ).select_related('operator').order_by('-last_attempt_at')[:100]]

        call_insights = [{
            'id': ci.id,
            'contact_id': ci.contact_id,
            'partner': ci.partner.name if ci.partner_id else '—',
            'date': ci.call_date.isoformat() if ci.call_date else None,
            'retries': ci.retries,
            'last_error': _short(ci.last_error),
            'last_attempt_at': ci.last_attempt_at.isoformat() if ci.last_attempt_at else None,
        } for ci in CallInsight.objects.filter(
            status=CallInsight.STATUS_FAILED,
            retries__gte=MAX_RETRIES,
        ).select_related('partner').order_by('-last_attempt_at')[:100]]

        insight_telegram = [{
            'id': ci.id,
            'contact_id': ci.contact_id,
            'partner': ci.partner.name if ci.partner_id else '—',
            'date': ci.call_date.isoformat() if ci.call_date else None,
            'retries': ci.telegram_retries,
            'last_error': _short(ci.telegram_last_error),
            'last_attempt_at': ci.telegram_last_attempt_at.isoformat()
                               if ci.telegram_last_attempt_at else None,
        } for ci in CallInsight.objects.filter(
            status=CallInsight.STATUS_DONE,
            telegram_status=CallInsight.TELEGRAM_FAILED,
            telegram_retries__gte=MAX_RETRIES,
        ).select_related('partner').order_by('-telegram_last_attempt_at')[:100]]

        insight_aggregates = [{
            'id': agg.id,
            'date_from': agg.date_from.isoformat() if agg.date_from else None,
            'date_to': agg.date_to.isoformat() if agg.date_to else None,
            'retries': agg.retries,
            'last_error': _short(agg.last_error),
            'last_attempt_at': agg.last_attempt_at.isoformat() if agg.last_attempt_at else None,
            'created_by': (
                agg.created_by.full_name or agg.created_by.username
                if agg.created_by_id else '—'
            ),
        } for agg in InsightAggregate.objects.filter(
            status=InsightAggregate.STATUS_FAILED,
            retries__gte=MAX_RETRIES,
        ).select_related('created_by').order_by('-last_attempt_at')[:100]]

        from producers.models import ProducerWeeklyReport
        producer_weekly_reports = [{
            'id': r.id,
            'period_from': r.period_from.isoformat() if r.period_from else None,
            'period_to': r.period_to.isoformat() if r.period_to else None,
            'retries': r.retries,
            'last_error': _short(r.last_error),
            'last_attempt_at': r.last_attempt_at.isoformat() if r.last_attempt_at else None,
            'created_by': (
                r.created_by.full_name or r.created_by.username
                if r.created_by_id else '—'
            ),
        } for r in ProducerWeeklyReport.objects.filter(
            status=ProducerWeeklyReport.STATUS_FAILED,
            retries__gte=MAX_RETRIES,
        ).select_related('created_by').order_by('-last_attempt_at')[:100]]

        return Response({
            'transcriptions': transcriptions,
            'summaries': summaries,
            'feedback': feedback,
            'call_insights': call_insights,
            'insight_telegram': insight_telegram,
            'insight_aggregates': insight_aggregates,
            'producer_weekly_reports': producer_weekly_reports,
        })

    def post(self, request):
        if not _is_admin(request.user):
            return Response({'error': 'Admin only'}, status=status.HTTP_403_FORBIDDEN)
        kind = request.data.get('kind')
        item_id = request.data.get('id')
        from contacts.models import Contact, OperatorFeedback, CallInsight, InsightAggregate
        if kind == 'transcription':
            updated = Contact.objects.filter(pk=item_id).update(
                transcription_retries=0, transcription_last_error='',
            )
        elif kind == 'summary':
            updated = Contact.objects.filter(pk=item_id).update(
                summary_retries=0, summary_last_error='',
            )
        elif kind == 'feedback':
            updated = OperatorFeedback.objects.filter(pk=item_id).update(
                generation_retries=0, last_error='',
            )
        elif kind == 'call_insight':
            updated = CallInsight.objects.filter(pk=item_id).update(
                retries=0, last_error='',
            )
        elif kind == 'insight_telegram':
            updated = CallInsight.objects.filter(pk=item_id).update(
                telegram_retries=0,
                telegram_last_error='',
                telegram_status=CallInsight.TELEGRAM_PENDING,
            )
        elif kind == 'insight_aggregate':
            updated = InsightAggregate.objects.filter(pk=item_id).update(
                retries=0, last_error='',
                status=InsightAggregate.STATUS_PENDING,
                last_attempt_at=timezone.now(),
            )
            if updated:
                from contacts.aggregation import enqueue_aggregate
                enqueue_aggregate(int(item_id))
        elif kind == 'producer_weekly_report':
            from producers.models import ProducerWeeklyReport
            updated = ProducerWeeklyReport.objects.filter(pk=item_id).update(
                retries=0, last_error='',
                status=ProducerWeeklyReport.STATUS_PENDING,
                last_attempt_at=timezone.now(),
            )
            if updated:
                from producers.weekly_report import enqueue_weekly_report
                enqueue_weekly_report(int(item_id))
        else:
            return Response({'error': 'Bad kind'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'reset': bool(updated)})


class AiOperationsPublicStatusView(APIView):
    """
    Lightweight, NON-admin endpoint used by the per-page status banner.
    Returns the same job payload (no history, no error stack) for ONE job id
    so the related UI page can show "next run / last run" to all users.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id):
        from .job_registry import get_job
        job = get_job(job_id)
        if not job:
            return Response({'error': 'Unknown job'}, status=status.HTTP_404_NOT_FOUND)
        payload = _job_payload(job)
        # strip raw error stacks for non-admins
        if not _is_admin(request.user):
            for k in ('last_run', 'last_error'):
                if payload.get(k):
                    payload[k] = {**payload[k], 'error_message': ''}
        return Response(payload)
