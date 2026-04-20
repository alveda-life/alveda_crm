"""
Helpers to log every AI / auto-generation job execution to AiJobRun.

Two ways to use:

1. Decorator for scheduler/manual entry-points:

    from .job_runner import logged_job

    @logged_job('brand_situation_weekly')
    def _run_brand_situation():
        ...                               # may return a str summary

2. Context manager for ad-hoc instrumentation:

    from .job_runner import job_run_context
    with job_run_context('my_job', trigger='manual', user=request.user) as run:
        do_work()
        run.set_summary('processed 12 items')

The decorator/context detect the trigger automatically: if called from an
APScheduler thread the trigger is 'schedule', if called via
`trigger_job_async` we pass trigger='manual', else 'startup'.
"""
import functools
import logging
import time
import threading
from contextlib import contextmanager
from django.utils import timezone
from django.db import close_old_connections

logger = logging.getLogger(__name__)

# Thread-local override for trigger source / user, set by the API "Run now"
# endpoint before invoking the actual job function.
_local = threading.local()


def _current_trigger_default():
    return getattr(_local, 'trigger', 'schedule')


def _current_user_default():
    return getattr(_local, 'user', None)


def set_trigger_context(trigger=None, user=None):
    """Used by the manual-run endpoint to tag the next job execution."""
    if trigger is not None:
        _local.trigger = trigger
    if user is not None:
        _local.user = user


def clear_trigger_context():
    _local.trigger = 'schedule'
    _local.user = None


class _RunHandle:
    def __init__(self, run_obj):
        self._run = run_obj

    def set_summary(self, text):
        self._run.summary = (text or '')[:500]


@contextmanager
def job_run_context(job_id, trigger=None, user=None):
    from .models import AiJobRun
    close_old_connections()
    eff_trigger = trigger or _current_trigger_default()
    eff_user = user if user is not None else _current_user_default()
    run = AiJobRun.objects.create(
        job_id=job_id,
        trigger=eff_trigger,
        triggered_by=eff_user if (eff_user and getattr(eff_user, 'pk', None)) else None,
        status=AiJobRun.STATUS_RUNNING,
    )
    handle = _RunHandle(run)
    started = time.monotonic()
    try:
        yield handle
        run.status = AiJobRun.STATUS_SUCCESS
    except Exception as exc:
        run.status = AiJobRun.STATUS_ERROR
        run.error_message = repr(exc)[:4000]
        logger.exception('AI job %s failed', job_id)
        raise
    finally:
        run.finished_at = timezone.now()
        run.duration_ms = int((time.monotonic() - started) * 1000)
        try:
            run.save(update_fields=['status', 'finished_at',
                                    'duration_ms', 'summary', 'error_message'])
        except Exception:
            logger.exception('Failed to persist AiJobRun %s', run.pk)
        finally:
            close_old_connections()


def logged_job(job_id):
    """Decorator that records every invocation of the wrapped function."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with job_run_context(job_id) as run:
                result = fn(*args, **kwargs)
                if isinstance(result, str) and result:
                    run.set_summary(result)
                return result
        return wrapper
    return deco
