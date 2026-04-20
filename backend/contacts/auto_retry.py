"""
Self-healing retry engine for the AI pipeline (transcription, summarization,
operator feedback).

Design goals:
  • Never lose a Contact transcription/summary or an OperatorFeedback row to
    a transient OpenAI / network / parsing error: the system retries
    automatically without operator intervention.
  • Never burn tokens on the same broken row forever: hard cap at MAX_RETRIES
    consecutive failures, then leave the row in 'failed' state with a clear
    `*_last_error` so a human can investigate.
  • Never hammer OpenAI: exponential backoff between attempts.

How it gets called:
  • The `ai_self_healing` job in JOB_REGISTRY runs `run_ai_self_healing()`
    every 10 minutes. The job is recorded in AiJobRun, so admins see
    every healing pass — what was attempted, what recovered, what is dead.
  • Single source of truth for retry policy lives here.

Status transitions tracked per row:
  failed (transient)            — retried until MAX_RETRIES is hit
  failed (dead-ended >= MAX)    — left alone, error_message preserved
  processing (stuck >30 min)    — treated as a transient failure, retried
  done                          — counters reset to 0
"""
import logging
from datetime import timedelta
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)

# Hard limits
MAX_RETRIES = 5

# Backoff (in minutes) BEFORE the next retry attempt N (1-indexed).
# After the 5th failure the row is considered dead-ended and skipped forever
# until a human resets `*_retries` to 0.
BACKOFF_MINUTES = [1, 5, 15, 60, 240]

# A row in 'processing' for longer than this is considered crashed.
STUCK_PROCESSING_MINUTES = 30


# ──────────────────────────────────────────────────────────────────────────
# Common helpers
# ──────────────────────────────────────────────────────────────────────────
def _next_attempt_due(retries: int, last_attempt_at) -> bool:
    """True if enough time has passed since the previous attempt."""
    if retries <= 0:
        return True
    if last_attempt_at is None:
        return True
    backoff_idx = min(retries - 1, len(BACKOFF_MINUTES) - 1)
    wait = timedelta(minutes=BACKOFF_MINUTES[backoff_idx])
    return (timezone.now() - last_attempt_at) >= wait


def _record_failure(obj, retry_field, attempt_field, error_field,
                    error: Exception, log_label: str):
    """Bump retry counter and persist last_error / last_attempt_at."""
    setattr(obj, retry_field, getattr(obj, retry_field, 0) + 1)
    setattr(obj, attempt_field, timezone.now())
    setattr(obj, error_field, repr(error)[:4000])
    obj.save(update_fields=[retry_field, attempt_field, error_field])
    logger.warning('%s retry %d failed: %s',
                   log_label, getattr(obj, retry_field), error)


def _record_success(obj, retry_field, attempt_field, error_field):
    """Reset retry counter and clear error trace on success."""
    setattr(obj, retry_field, 0)
    setattr(obj, attempt_field, timezone.now())
    setattr(obj, error_field, '')
    obj.save(update_fields=[retry_field, attempt_field, error_field])


# ──────────────────────────────────────────────────────────────────────────
# Pipeline 1 — Transcriptions
# ──────────────────────────────────────────────────────────────────────────
def _retry_transcriptions(stats):
    from .models import Contact
    from .transcription import transcribe_audio

    cutoff_stuck = timezone.now() - timedelta(minutes=STUCK_PROCESSING_MINUTES)

    candidates = Contact.objects.filter(
        transcription_status__in=[
            Contact.TRANSCRIPTION_FAILED,
            Contact.TRANSCRIPTION_PROCESSING,
        ],
        transcription_retries__lt=MAX_RETRIES,
    ).exclude(audio_file='').exclude(audio_file__isnull=True)
    # Don't re-touch rows still actively processing within the last 30 min
    candidates = candidates.exclude(
        transcription_status=Contact.TRANSCRIPTION_PROCESSING,
        transcription_last_attempt_at__gt=cutoff_stuck,
    )

    for c in candidates.iterator():
        if not _next_attempt_due(c.transcription_retries,
                                 c.transcription_last_attempt_at):
            stats['skipped_backoff'] += 1
            continue
        try:
            Contact.objects.filter(pk=c.pk).update(
                transcription_status=Contact.TRANSCRIPTION_PROCESSING,
                transcription_last_attempt_at=timezone.now(),
            )
            transcribe_audio(c)
            c.refresh_from_db(fields=['transcription_status'])
            if c.transcription_status == Contact.TRANSCRIPTION_DONE:
                _record_success(c, 'transcription_retries',
                                'transcription_last_attempt_at',
                                'transcription_last_error')
                stats['recovered'] += 1
            else:
                _record_failure(c, 'transcription_retries',
                                'transcription_last_attempt_at',
                                'transcription_last_error',
                                RuntimeError(f'transcribe_audio left status={c.transcription_status}'),
                                f'Contact {c.pk} transcription')
                stats['failed_again'] += 1
        except Exception as e:
            _record_failure(c, 'transcription_retries',
                            'transcription_last_attempt_at',
                            'transcription_last_error',
                            e, f'Contact {c.pk} transcription')
            stats['failed_again'] += 1

    # Count dead-ended rows (>= MAX_RETRIES) still in failed state
    stats['dead'] += Contact.objects.filter(
        transcription_status=Contact.TRANSCRIPTION_FAILED,
        transcription_retries__gte=MAX_RETRIES,
    ).count()


# ──────────────────────────────────────────────────────────────────────────
# Pipeline 2 — Summarization + quality scoring
# ──────────────────────────────────────────────────────────────────────────
def _retry_summaries(stats):
    from .models import Contact
    from .summarization import summarize_transcription

    cutoff_stuck = timezone.now() - timedelta(minutes=STUCK_PROCESSING_MINUTES)

    candidates = Contact.objects.filter(
        summary_status__in=[
            Contact.TRANSCRIPTION_FAILED,
            Contact.TRANSCRIPTION_PROCESSING,
        ],
        summary_retries__lt=MAX_RETRIES,
    ).exclude(transcription='').exclude(transcription__isnull=True)
    candidates = candidates.exclude(
        summary_status=Contact.TRANSCRIPTION_PROCESSING,
        summary_last_attempt_at__gt=cutoff_stuck,
    )

    for c in candidates.iterator():
        if not _next_attempt_due(c.summary_retries, c.summary_last_attempt_at):
            stats['skipped_backoff'] += 1
            continue
        try:
            Contact.objects.filter(pk=c.pk).update(
                summary_status=Contact.TRANSCRIPTION_PROCESSING,
                summary_last_attempt_at=timezone.now(),
            )
            summarize_transcription(c)
            c.refresh_from_db(fields=['summary_status'])
            if c.summary_status == Contact.TRANSCRIPTION_DONE:
                _record_success(c, 'summary_retries',
                                'summary_last_attempt_at',
                                'summary_last_error')
                stats['recovered'] += 1
            else:
                _record_failure(c, 'summary_retries',
                                'summary_last_attempt_at',
                                'summary_last_error',
                                RuntimeError(f'summarize_transcription left status={c.summary_status}'),
                                f'Contact {c.pk} summary')
                stats['failed_again'] += 1
        except Exception as e:
            _record_failure(c, 'summary_retries',
                            'summary_last_attempt_at',
                            'summary_last_error',
                            e, f'Contact {c.pk} summary')
            stats['failed_again'] += 1

    stats['dead'] += Contact.objects.filter(
        summary_status=Contact.TRANSCRIPTION_FAILED,
        summary_retries__gte=MAX_RETRIES,
    ).count()


# ──────────────────────────────────────────────────────────────────────────
# Pipeline 3 — Operator daily / weekly feedback
# ──────────────────────────────────────────────────────────────────────────
def _retry_feedback(stats):
    from .models import OperatorFeedback
    from .feedback_generator import (
        generate_daily_feedback,
        generate_weekly_feedback,
    )

    cutoff_stuck = timezone.now() - timedelta(minutes=STUCK_PROCESSING_MINUTES)

    candidates = OperatorFeedback.objects.filter(
        status__in=[OperatorFeedback.STATUS_FAILED,
                    OperatorFeedback.STATUS_GENERATING],
        generation_retries__lt=MAX_RETRIES,
    ).select_related('operator')
    candidates = candidates.exclude(
        status=OperatorFeedback.STATUS_GENERATING,
        last_attempt_at__gt=cutoff_stuck,
    )

    for fb in candidates.iterator():
        if not _next_attempt_due(fb.generation_retries, fb.last_attempt_at):
            stats['skipped_backoff'] += 1
            continue
        try:
            OperatorFeedback.objects.filter(pk=fb.pk).update(
                status=OperatorFeedback.STATUS_GENERATING,
                last_attempt_at=timezone.now(),
            )
            # The generator deletes & recreates the row, so we capture identity
            op_id = fb.operator_id
            ftype = fb.feedback_type
            pstart = fb.period_start
            pend = fb.period_end
            fb.delete()
            from accounts.models import User
            operator = User.objects.get(pk=op_id)
            if ftype == OperatorFeedback.TYPE_DAILY:
                generate_daily_feedback(operator, target_date=pstart)
            else:
                generate_weekly_feedback(operator, week_end=pend)
            new_fb = OperatorFeedback.objects.filter(
                operator_id=op_id, feedback_type=ftype, period_start=pstart,
            ).first()
            if new_fb and new_fb.status == OperatorFeedback.STATUS_DONE:
                # Carry over the success: zero retries, clear error
                OperatorFeedback.objects.filter(pk=new_fb.pk).update(
                    generation_retries=0,
                    last_error='',
                    last_attempt_at=timezone.now(),
                )
                stats['recovered'] += 1
            else:
                # Generator did not produce a done row — count as failure and
                # restore retry metadata on whatever row exists now.
                if new_fb:
                    OperatorFeedback.objects.filter(pk=new_fb.pk).update(
                        generation_retries=fb.generation_retries + 1,
                        last_attempt_at=timezone.now(),
                        last_error='Generator did not finish (no done status)',
                    )
                stats['failed_again'] += 1
        except Exception as e:
            # Re-create a placeholder failed row to track the retry counter
            from accounts.models import User
            try:
                operator = User.objects.get(pk=op_id)
                OperatorFeedback.objects.update_or_create(
                    operator=operator, feedback_type=ftype, period_start=pstart,
                    defaults=dict(
                        period_end=pend,
                        status=OperatorFeedback.STATUS_FAILED,
                        generation_retries=fb.generation_retries + 1,
                        last_attempt_at=timezone.now(),
                        last_error=repr(e)[:4000],
                    ),
                )
            except Exception as inner:
                logger.error('Could not record feedback retry failure: %s', inner)
            logger.warning('OperatorFeedback %s retry %d failed: %s',
                           fb.pk, fb.generation_retries + 1, e)
            stats['failed_again'] += 1

    stats['dead'] += OperatorFeedback.objects.filter(
        status=OperatorFeedback.STATUS_FAILED,
        generation_retries__gte=MAX_RETRIES,
    ).count()


# ──────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────
def run_ai_self_healing():
    """
    One full healing pass over all three pipelines.
    Returns a dict with totals so the caller can record a 1-line summary.
    """
    close_old_connections()
    stats = {
        'recovered': 0,
        'failed_again': 0,
        'skipped_backoff': 0,
        'dead': 0,
    }
    try:
        _retry_transcriptions(stats)
    except Exception as e:
        logger.exception('Self-healing transcriptions stage crashed: %s', e)
    try:
        _retry_summaries(stats)
    except Exception as e:
        logger.exception('Self-healing summaries stage crashed: %s', e)
    try:
        _retry_feedback(stats)
    except Exception as e:
        logger.exception('Self-healing feedback stage crashed: %s', e)
    finally:
        close_old_connections()
    return stats


def dead_ended_summary():
    """Return counts of rows that exhausted MAX_RETRIES — for the admin panel."""
    from .models import Contact, OperatorFeedback
    return {
        'transcriptions': Contact.objects.filter(
            transcription_status=Contact.TRANSCRIPTION_FAILED,
            transcription_retries__gte=MAX_RETRIES,
        ).count(),
        'summaries': Contact.objects.filter(
            summary_status=Contact.TRANSCRIPTION_FAILED,
            summary_retries__gte=MAX_RETRIES,
        ).count(),
        'feedback': OperatorFeedback.objects.filter(
            status=OperatorFeedback.STATUS_FAILED,
            generation_retries__gte=MAX_RETRIES,
        ).count(),
    }
