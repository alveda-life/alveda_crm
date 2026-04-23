"""APScheduler: auto-generates AI reports and feedback on schedule.

Every runner is wrapped with @logged_job(...) so each execution lands in
AiJobRun and the AI Operations admin panel can show last/next run + status.
"""
import logging
import pytz

from .job_runner import logged_job

logger = logging.getLogger(__name__)
RIGA_TZ = pytz.timezone('Europe/Riga')
IST_TZ  = pytz.timezone('Asia/Kolkata')
_started = False


@logged_job('producer_daily_report')
def _run_daily():
    from .producer_update_generator import generate_update_report
    rep = generate_update_report('daily')
    logger.info('Daily producer report generation started.')
    return f'Started daily report id={getattr(rep, "id", "?")}'


@logged_job('producer_weekly_report')
def _run_weekly():
    from .producer_update_generator import generate_update_report
    rep = generate_update_report('weekly')
    logger.info('Weekly producer report generation started.')
    return f'Started weekly report id={getattr(rep, "id", "?")}'


@logged_job('brand_situation_weekly')
def _run_brand_situation():
    from .brand_situation_generator import generate_brand_situation_report
    rep = generate_brand_situation_report(force=True)
    logger.info('Brand situation report generation started.')
    return f'Started brand-situation report id={getattr(rep, "id", "?")}'


@logged_job('brand_situation_retry')
def _retry_brand_situation():
    """Daily safety net (Mon-Fri 18:00 IST) — restart any General Situation
    report stuck in pending/generating/error and ensure today's report exists.
    """
    from .brand_situation_generator import retry_failed_situation_reports
    retry_failed_situation_reports()
    return 'Retried stuck brand-situation reports'


def start():
    global _started
    if _started:
        return
    _started = True

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler(timezone=RIGA_TZ)

        # ---- Producer Update reports ----
        scheduler.add_job(
            _run_daily,
            CronTrigger(day_of_week='mon-fri', hour=18, minute=0, timezone=RIGA_TZ),
            id='producer_daily_report',
            replace_existing=True,
        )
        scheduler.add_job(
            _run_weekly,
            CronTrigger(day_of_week='fri', hour=14, minute=0, timezone=RIGA_TZ),
            id='producer_weekly_report',
            replace_existing=True,
        )

        # ---- Brand Situation ----
        scheduler.add_job(
            _run_brand_situation,
            CronTrigger(day_of_week='mon-fri', hour=15, minute=0, timezone=IST_TZ),
            id='brand_situation_weekly',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            _retry_brand_situation,
            CronTrigger(day_of_week='mon-fri', hour=18, minute=0, timezone=IST_TZ),
            id='brand_situation_retry',
            replace_existing=True,
        )

        # ---- Operator Feedback (daily / weekly) ----
        try:
            from contacts.feedback_scheduler import (
                run_daily_feedback_for_yesterday,
                run_weekly_feedback_for_last_week,
            )
            scheduler.add_job(
                run_daily_feedback_for_yesterday,
                CronTrigger(day_of_week='mon-fri', hour=9, minute=0, timezone=IST_TZ),
                id='operator_daily_feedback',
                replace_existing=True,
            )
            scheduler.add_job(
                run_weekly_feedback_for_last_week,
                CronTrigger(day_of_week='mon', hour=9, minute=30, timezone=IST_TZ),
                id='operator_weekly_feedback',
                replace_existing=True,
            )
        except Exception as e:
            logger.error('Failed to register operator feedback schedule: %s', e)

        # ---- AI pipeline self-healing (every 10 min, 24/7) ----
        try:
            from .sync_runners import run_ai_self_healing_job
            scheduler.add_job(
                run_ai_self_healing_job,
                CronTrigger(minute='*/10', timezone=IST_TZ),
                id='ai_self_healing',
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
        except Exception as e:
            logger.error('Failed to register AI self-healing schedule: %s', e)

        # ---- Data Sync (external CRM) ----
        try:
            from .sync_runners import run_crm_partners_sync
            scheduler.add_job(
                run_crm_partners_sync,
                CronTrigger(minute='5,25,45', timezone=IST_TZ),
                id='crm_partners_sync',
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
        except Exception as e:
            logger.error('Failed to register data-sync schedule: %s', e)

        # ---- Producer Weekly Report (Fri 16:00 IST) ----
        try:
            from .sync_runners import run_producer_weekly_report
            scheduler.add_job(
                run_producer_weekly_report,
                CronTrigger(day_of_week='fri', hour=16, minute=0, timezone=IST_TZ),
                id='producer_onboarding_weekly_report',
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
        except Exception as e:
            logger.error('Failed to register producer-onboarding-weekly-report schedule: %s', e)

        # ---- General Insights rolling refresh (Mon-Fri 17:00 IST) ----
        try:
            from .sync_runners import run_general_insights_refresh
            scheduler.add_job(
                run_general_insights_refresh,
                CronTrigger(day_of_week='mon-fri', hour=17, minute=0, timezone=IST_TZ),
                id='general_insights_refresh',
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
        except Exception as e:
            logger.error('Failed to register general-insights refresh: %s', e)

        scheduler.start()
        logger.info(
            'Schedulers started: '
            'producer daily 18:00 Riga (Mon-Fri), producer weekly Fri 14:00 Riga, '
            'brand situation Fri 15:00 IST, brand-situation retry daily 18:00 IST (Mon-Fri), '
            'operator daily feedback 09:00 IST (Mon-Fri), weekly Mon 09:30 IST, '
            'CRM partners hourly :05 IST.'
        )
    except Exception as e:
        logger.error(f'Failed to start scheduler: {e}')
