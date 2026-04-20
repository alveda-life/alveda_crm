import os
import threading
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ContactsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'contacts'

    def ready(self):
        if os.environ.get('RUN_MAIN') == 'true':
            threading.Thread(target=_startup_retry_kickoff, daemon=True).start()


def _startup_retry_kickoff():
    """
    Kick off the startup retry job after a short delay so the web server has
    time to come up. The actual work is done by the registered job runner so
    every startup retry is recorded in AiJobRun and visible in the
    Background Operations admin panel.
    """
    import time
    time.sleep(10)
    try:
        from reports.sync_runners import run_contacts_startup_retry
        run_contacts_startup_retry()
    except Exception as exc:
        logger.error('Startup retry job failed to launch: %s', exc)


def _retry_failed_transcriptions():
    from .models import Contact
    from .transcription import transcribe_audio

    stuck = Contact.objects.filter(
        transcription_status__in=['failed', 'processing'],
    ).exclude(audio_file='').exclude(audio_file__isnull=True)

    if not stuck.exists():
        return

    logger.info(f'Auto-retrying transcription for {stuck.count()} contacts...')
    for contact in stuck.iterator():
        try:
            logger.info(f'Auto-retrying transcription for contact {contact.id}')
            transcribe_audio(contact)
        except Exception as e:
            logger.error(f'Auto-retry transcription failed for contact {contact.id}: {e}')


def _retry_failed_summaries():
    from .models import Contact
    from .summarization import summarize_transcription

    stuck = Contact.objects.filter(
        summary_status__in=['failed', 'processing'],
    ).exclude(transcription='').exclude(transcription__isnull=True)

    if not stuck.exists():
        return

    logger.info(f'Auto-retrying summarization for {stuck.count()} contacts...')
    for contact in stuck.iterator():
        try:
            logger.info(f'Auto-retrying summarization for contact {contact.id}')
            summarize_transcription(contact)
        except Exception as e:
            logger.error(f'Auto-retry summarization failed for contact {contact.id}: {e}')


def _retry_failed_feedback():
    from .models import OperatorFeedback
    from .feedback_generator import generate_daily_feedback, generate_weekly_feedback

    stuck = OperatorFeedback.objects.filter(
        status__in=['failed', 'generating']
    ).select_related('operator')

    if not stuck.exists():
        return

    logger.info(f'Auto-retrying feedback generation for {stuck.count()} items...')
    for fb in stuck.iterator():
        try:
            logger.info(f'Auto-retrying feedback for {fb.operator} ({fb.feedback_type}, {fb.period_start})')
            fb.delete()
            if fb.feedback_type == 'daily':
                generate_daily_feedback(fb.operator, target_date=fb.period_start)
            else:
                generate_weekly_feedback(fb.operator, week_end=fb.period_end)
        except Exception as e:
            logger.error(f'Auto-retry feedback failed for feedback {fb.id}: {e}')
