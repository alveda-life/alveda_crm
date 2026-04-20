"""
Wrappers around data-sync management commands and maintenance routines so
they can be:
  • scheduled via APScheduler
  • triggered on demand from the Background Operations admin panel
  • monitored via AiJobRun (last run, next run, success/error counts)

Each runner is decorated with @logged_job(<id>), captures the management
command's stdout, and returns a 1-line summary so the admin sees what
actually happened.
"""
import io
import logging
from contextlib import redirect_stdout, redirect_stderr
from django.core.management import call_command

from .job_runner import logged_job

logger = logging.getLogger(__name__)


def _row_counts():
    """Snapshot of the main entity tables for summary deltas."""
    from producers.models import Producer, ProducerComment
    from partners.models   import Partner
    return {
        'producers':         Producer.objects.count(),
        'producer_comments': ProducerComment.objects.count(),
        'partners':          Partner.objects.count(),
    }


def _delta(before, after, key):
    return after.get(key, 0) - before.get(key, 0)


# ── Asana: full producers sync ──────────────────────────────────────────────
@logged_job('asana_producers_sync')
def run_asana_producers_sync():
    """Re-import every producer from the Asana board (full sync)."""
    before = _row_counts()
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        call_command('import_asana_producers')
    after = _row_counts()
    added = _delta(before, after, 'producers')
    return f'Asana producers sync OK · total={after["producers"]} · new this run={added}'


# ── Asana: comments / stories sync ──────────────────────────────────────────
@logged_job('asana_comments_sync')
def run_asana_comments_sync():
    """Pull all task stories (comments) from Asana with original timestamps."""
    before = _row_counts()
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        call_command('sync_asana_comments')
    after = _row_counts()
    added = _delta(before, after, 'producer_comments')
    return f'Asana comments sync OK · total={after["producer_comments"]} · new this run={added}'


# ── External CRM: partners import ───────────────────────────────────────────
@logged_job('crm_partners_sync')
def run_crm_partners_sync():
    """Import partners from the external CRM API (incremental)."""
    before = _row_counts()
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        call_command('import_crm_contacts')
    after = _row_counts()
    added = _delta(before, after, 'partners')
    return f'CRM partners sync OK · total={after["partners"]} · new this run={added}'


# ── Maintenance: continuous self-healing of the AI pipeline ────────────────
@logged_job('ai_self_healing')
def run_ai_self_healing_job():
    """
    Continuous self-healing pass over all three AI pipelines:
      • Audio transcription (Whisper)
      • Summarization + quality scoring (GPT-4o)
      • Operator daily / weekly feedback (GPT-4o)
    Picks up rows in 'failed' or stuck-in-'processing' state, retries them
    with exponential backoff, gives up after MAX_RETRIES (5) consecutive
    failures so we don't burn tokens. The dead-ended rows surface in the
    Background Operations panel so a human can investigate.
    """
    from contacts.auto_retry import run_ai_self_healing, dead_ended_summary
    s = run_ai_self_healing()
    dead = dead_ended_summary()
    dead_total = sum(dead.values())
    parts = [
        f'recovered={s["recovered"]}',
        f'failed_again={s["failed_again"]}',
        f'backoff_wait={s["skipped_backoff"]}',
    ]
    if dead_total:
        parts.append(f'DEAD={dead_total} (t={dead["transcriptions"]}/s={dead["summaries"]}/f={dead["feedback"]})')
    return ' · '.join(parts)


# ── Maintenance: retry stuck transcriptions/summaries/feedback ──────────────
@logged_job('contacts_startup_retry')
def run_contacts_startup_retry():
    """
    Find any Contact rows whose transcription or summarization failed
    (status='failed' or stuck >30 min in 'processing') and re-queue them.
    Originally only ran once at backend startup — now also exposed as a
    monitored job so admins can trigger it manually if a batch got stuck.
    """
    from datetime import timedelta
    from django.utils import timezone
    from contacts.models import Contact, OperatorFeedback

    cutoff = timezone.now() - timedelta(minutes=30)

    stuck_transcriptions = list(Contact.objects.filter(
        transcription_status__in=['failed', 'processing'],
    ).exclude(
        transcription_status='processing',
        date__gte=cutoff,
    ).values_list('id', flat=True))

    stuck_summaries = list(Contact.objects.filter(
        summary_status__in=['failed', 'processing'],
    ).exclude(
        summary_status='processing',
        date__gte=cutoff,
    ).exclude(transcription='').values_list('id', flat=True))

    stuck_feedback = list(OperatorFeedback.objects.filter(
        status__in=['failed', 'generating'],
        created_at__lt=cutoff,
    ).values_list('id', flat=True))

    # Kick them off (best effort — don't crash the whole job if one fails)
    n_t = n_s = n_f = 0
    if stuck_transcriptions:
        try:
            from contacts.views import _transcribe_in_background
            import threading
            for cid in stuck_transcriptions:
                threading.Thread(
                    target=_transcribe_in_background, args=(cid,), daemon=True
                ).start()
                n_t += 1
        except Exception as e:
            logger.warning('Could not retry transcriptions: %s', e)
    if stuck_summaries:
        try:
            from contacts.views import _summarize_in_background
            import threading
            for cid in stuck_summaries:
                threading.Thread(
                    target=_summarize_in_background, args=(cid,), daemon=True
                ).start()
                n_s += 1
        except Exception as e:
            logger.warning('Could not retry summaries: %s', e)
    if stuck_feedback:
        try:
            from contacts.feedback_generator import (
                generate_daily_feedback,
                generate_weekly_feedback,
            )
            for fid in stuck_feedback:
                fb = OperatorFeedback.objects.filter(pk=fid).first()
                if not fb:
                    continue
                try:
                    if fb.feedback_type == 'daily':
                        generate_daily_feedback(fb.operator, fb.period_start)
                    else:
                        generate_weekly_feedback(fb.operator, fb.period_end)
                    n_f += 1
                except Exception as e:
                    logger.warning('Could not regenerate feedback %s: %s', fid, e)
        except Exception as e:
            logger.warning('Could not retry feedback: %s', e)

    return (
        f'Retried · transcriptions={n_t} · summaries={n_s} · feedback={n_f}'
        if (n_t + n_s + n_f) else 'Nothing stuck — all clean.'
    )
