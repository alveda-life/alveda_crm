"""
Wrappers around feedback_generator that are registered with the global
APScheduler instance and instrumented via reports.job_runner.logged_job
so every run is visible in the AI Operations admin panel.
"""
import logging
from datetime import date, timedelta

from reports.job_runner import logged_job

logger = logging.getLogger(__name__)


def _active_operators():
    """Operators we want feedback for: any non-admin active user that has
    or could have call activity."""
    from accounts.models import User
    return User.objects.filter(is_active=True).exclude(role='admin')


@logged_job('operator_daily_feedback')
def run_daily_feedback_for_yesterday():
    from .feedback_generator import generate_daily_feedback

    target = date.today() - timedelta(days=1)
    ops = list(_active_operators())
    ok = err = skipped = 0
    for op in ops:
        try:
            fb = generate_daily_feedback(op, target_date=target)
            if fb is None:
                skipped += 1
            else:
                ok += 1
        except Exception as exc:
            err += 1
            logger.error('Daily feedback failed for %s: %s', op, exc)
    return f'{target}: generated={ok}, no-calls={skipped}, errors={err}, operators={len(ops)}'


@logged_job('operator_weekly_feedback')
def run_weekly_feedback_for_last_week():
    from .feedback_generator import generate_weekly_feedback

    today = date.today()
    last_sunday = today - timedelta(days=today.weekday() + 1)
    ops = list(_active_operators())
    ok = err = skipped = 0
    for op in ops:
        try:
            fb = generate_weekly_feedback(op, week_end=last_sunday)
            if fb is None:
                skipped += 1
            else:
                ok += 1
        except Exception as exc:
            err += 1
            logger.error('Weekly feedback failed for %s: %s', op, exc)
    return f'week ending {last_sunday}: generated={ok}, no-calls={skipped}, errors={err}, operators={len(ops)}'
