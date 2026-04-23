"""
Central registry of EVERY background process in the system — AI generation,
data syncs from external APIs, maintenance jobs, etc.

Each entry describes ONE recurring or on-demand background job:
  - id               unique short identifier (used in URLs and AiJobRun.job_id)
  - category         grouping for the admin UI:
                     'ai_reports' | 'ai_feedback' | 'data_sync' | 'maintenance'
  - name             human label
  - description      what the job does and what artifact it produces
  - schedule_human   plain-language schedule (e.g. "Every Friday 15:00 IST")
  - cron             dict with kwargs for apscheduler.triggers.cron.CronTrigger
                     (used both to schedule and to compute next_run_time)
                     OR None for "manual / on-demand" jobs.
  - timezone         pytz tz name for the cron trigger
  - artifact         hint where the user can find generated content
  - run_now          dotted import path "module.function" — admin "Run now"
                     button calls this in a background thread

Adding a job here automatically:
  - exposes it in /api/ai-operations/ for the admin control panel
  - shows scheduling info in the related UI page
  - allows admins to trigger it on demand
"""
import importlib
import logging
import threading
import pytz

logger = logging.getLogger(__name__)

RIGA_TZ = 'Europe/Riga'
IST_TZ  = 'Asia/Kolkata'


JOB_REGISTRY = [
    # ─── AI Reports ─────────────────────────────────────────────────────────
    {
        'id': 'producer_daily_report',
        'category': 'ai_reports',
        'name': 'Producer Daily Update Report',
        'description': 'Aggregates the day\'s producer activity and writes a Daily Producer Update report for managers.',
        'schedule_human': 'Mon–Fri at 18:00 Europe/Riga',
        'cron': {'day_of_week': 'mon-fri', 'hour': 18, 'minute': 0},
        'timezone': RIGA_TZ,
        'artifact': 'Producers → Updates',
        'artifact_path': '/producers/updates',
        'run_now': 'reports.scheduler._run_daily',
    },
    {
        'id': 'producer_weekly_report',
        'category': 'ai_reports',
        'name': 'Producer Weekly Update Report',
        'description': 'Generates the weekly producer pipeline summary for managers.',
        'schedule_human': 'Every Friday at 14:00 Europe/Riga',
        'cron': {'day_of_week': 'fri', 'hour': 14, 'minute': 0},
        'timezone': RIGA_TZ,
        'artifact': 'Producers → Updates',
        'artifact_path': '/producers/updates',
        'run_now': 'reports.scheduler._run_weekly',
    },
    {
        'id': 'brand_situation_weekly',
        'category': 'ai_reports',
        'name': 'General Situation (per-brand timeline)',
        'description': 'Refreshes the General Situation snapshot of every active onboarding brand: stage, readiness %, "Now" status, the coloured weekly-dot history, and weeks-in-funnel. The same weekly slot is regenerated each weekday so the page always reflects the latest comments and stage moves.',
        'schedule_human': 'Mon–Fri at 15:00 Asia/Kolkata',
        'cron': {'day_of_week': 'mon-fri', 'hour': 15, 'minute': 0},
        'timezone': IST_TZ,
        'artifact': 'Producers → General Situation',
        'artifact_path': '/producers/general-situation',
        'run_now': 'reports.scheduler._run_brand_situation',
    },
    {
        'id': 'brand_situation_retry',
        'category': 'ai_reports',
        'name': 'General Situation — daily safety net',
        'description': 'Daily safety net: re-launches any General Situation report stuck in pending/generating/error and ensures a fresh report exists. Runs Mon–Fri only.',
        'schedule_human': 'Mon–Fri at 18:00 Asia/Kolkata',
        'cron': {'day_of_week': 'mon-fri', 'hour': 18, 'minute': 0},
        'timezone': IST_TZ,
        'artifact': 'Producers → General Situation',
        'artifact_path': '/producers/general-situation',
        'run_now': 'reports.scheduler._retry_brand_situation',
    },

    # ─── AI Feedback ────────────────────────────────────────────────────────
    {
        'id': 'operator_daily_feedback',
        'category': 'ai_feedback',
        'name': 'Operator Daily Feedback',
        'description': 'Generates personalized daily feedback for every operator based on yesterday\'s call transcripts (the "My Feedback → DAILY" tab). Runs Mon–Fri only.',
        'schedule_human': 'Mon–Fri at 09:00 Asia/Kolkata',
        'cron': {'day_of_week': 'mon-fri', 'hour': 9, 'minute': 0},
        'timezone': IST_TZ,
        'artifact': 'My Feedback (per operator)',
        'artifact_path': '/my-feedback',
        'run_now': 'contacts.feedback_scheduler.run_daily_feedback_for_yesterday',
    },
    {
        'id': 'operator_weekly_feedback',
        'category': 'ai_feedback',
        'name': 'Operator Weekly Feedback',
        'description': 'Generates personalized weekly feedback for every operator covering the previous Mon–Sun (the "My Feedback → WEEKLY" tab).',
        'schedule_human': 'Every Monday at 09:30 Asia/Kolkata',
        'cron': {'day_of_week': 'mon', 'hour': 9, 'minute': 30},
        'timezone': IST_TZ,
        'artifact': 'My Feedback (per operator)',
        'artifact_path': '/my-feedback',
        'run_now': 'contacts.feedback_scheduler.run_weekly_feedback_for_last_week',
    },

    # ─── Data Sync (external APIs) ──────────────────────────────────────────
    {
        'id': 'crm_partners_sync',
        'category': 'data_sync',
        'name': 'External CRM → Partners sync',
        'description': 'Imports partners (doctors, clinics, etc.) from the external Ask Ayurveda CRM HTTP API and upserts the local Partner table. A PostgreSQL advisory lock guarantees only one worker runs the import per tick — extra triggers exit immediately, so a faster cadence does not multiply load on the source site.',
        'schedule_human': 'Every 20 minutes, 24/7',
        'cron': {'minute': '5,25,45'},
        'timezone': IST_TZ,
        'artifact': 'Partners → All',
        'artifact_path': '/partners',
        'run_now': 'reports.sync_runners.run_crm_partners_sync',
    },

    # ─── AI Reports: Producer Weekly Report (onboarding funnel) ────────────
    {
        'id': 'producer_onboarding_weekly_report',
        'category': 'ai_reports',
        'name': 'Producer Onboarding Weekly Report',
        'description': 'AI-generated weekly snapshot of the producer onboarding funnel. Covers the period since the previous successful run (chained, not calendar-aligned). Lists newly added producers and existing producers with SIGNIFICANT changes — the LLM filters out trivial follow-up activity (reminders, "called again", contact requests). Visible to admins and Producer Managers.',
        'schedule_human': 'Friday at 16:00 IST',
        'cron': {'day_of_week': 'fri', 'hour': 16, 'minute': 0},
        'timezone': IST_TZ,
        'artifact': 'Producers → Weekly Report',
        'artifact_path': '/producers/weekly-report',
        'run_now': 'reports.sync_runners.run_producer_weekly_report',
    },

    # ─── AI Reports: General Insights rolling buckets ──────────────────────
    {
        'id': 'general_insights_refresh',
        'category': 'ai_reports',
        'name': 'General Insights rolling refresh',
        'description': 'Rebuilds the cross-call top-15 themes for the four rolling buckets (last 30 / 60 / 180 days, plus all-time) used by Partners → General Insights. Each bucket is regenerated by clustering every CallInsight item in its window, ranking themes by unique partners. Caching keeps the page instant; manual refresh from the UI also forces a rebuild.',
        'schedule_human': 'Mon–Fri at 17:00 IST',
        'cron': {'day_of_week': 'mon-fri', 'hour': 17, 'minute': 0},
        'timezone': IST_TZ,
        'artifact': 'Partners → General Insights',
        'artifact_path': '/admin/general-insights',
        'run_now': 'reports.sync_runners.run_general_insights_refresh',
    },

    # ─── Maintenance ────────────────────────────────────────────────────────
    {
        'id': 'ai_self_healing',
        'category': 'maintenance',
        'name': 'AI pipeline self-healing',
        'description': 'Continuously retries failed or stuck transcription / summarization / operator-feedback / call-insight / insight-telegram / aggregate-insight rows with exponential backoff (1m → 5m → 15m → 1h → 4h). Stops after 5 consecutive failures per row so we never burn OpenAI tokens on a permanently-broken item — those dead-ended rows surface here for a human to investigate.',
        'schedule_human': 'Every 10 minutes, 24/7',
        'cron': {'minute': '*/10'},
        'timezone': IST_TZ,
        'artifact': 'Transcriptions / Call Quality / My Feedback',
        'artifact_path': '/transcriptions',
        'run_now': 'reports.sync_runners.run_ai_self_healing_job',
    },
    {
        'id': 'contacts_startup_retry',
        'category': 'maintenance',
        'name': 'Stuck transcriptions / summaries / feedback retry (startup)',
        'description': 'Runs once on backend startup to immediately re-queue anything that was failed or stuck before the previous restart, without waiting for the next 10-min self-healing tick.',
        'schedule_human': 'On backend startup (and on demand)',
        'cron': None,
        'timezone': IST_TZ,
        'artifact': 'Transcriptions / My Feedback',
        'artifact_path': '/transcriptions',
        'run_now': 'reports.sync_runners.run_contacts_startup_retry',
    },
]


def get_job(job_id):
    for j in JOB_REGISTRY:
        if j['id'] == job_id:
            return j
    return None


def compute_next_run(job):
    """Return ISO-formatted next fire time for a registry entry, or None.

    Returns None for manual / on-demand jobs (cron is None).
    """
    if not job.get('cron'):
        return None
    try:
        from apscheduler.triggers.cron import CronTrigger
        tz = pytz.timezone(job['timezone'])
        trigger = CronTrigger(timezone=tz, **job['cron'])
        from datetime import datetime
        now = datetime.now(tz)
        nxt = trigger.get_next_fire_time(None, now)
        return nxt.isoformat() if nxt else None
    except Exception as exc:
        logger.warning('compute_next_run(%s) failed: %s', job.get('id'), exc)
        return None


def trigger_job_async(job_id, user=None):
    """
    Manually fire a registered job in a background thread.
    Logs the run via job_runner automatically because each runner is
    decorated, and propagates the manual trigger metadata into the worker.
    """
    from .job_runner import set_trigger_context, clear_trigger_context

    job = get_job(job_id)
    if not job:
        raise ValueError(f'Unknown job: {job_id}')
    dotted = job['run_now']
    module_path, func_name = dotted.rsplit('.', 1)
    module = importlib.import_module(module_path)
    fn = getattr(module, func_name)

    def _wrapper():
        try:
            set_trigger_context(trigger='manual', user=user)
            fn()
        except Exception as exc:
            logger.error('Manual job %s failed: %s', job_id, exc)
        finally:
            clear_trigger_context()

    t = threading.Thread(target=_wrapper, daemon=True)
    t.start()
    return t
