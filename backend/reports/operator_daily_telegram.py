"""Daily Telegram report with per-operator call/activity metrics."""
from datetime import datetime, time as time_cls, timedelta
from html import escape

import pytz
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.utils import timezone


IST_TZ = pytz.timezone('Asia/Kolkata')
KPI_DAILY_TALK_MINUTES = 300


def _h(value) -> str:
    return escape(str(value or ''), quote=False)


def _day_range_ist(target_date):
    start = IST_TZ.localize(datetime.combine(target_date, time_cls.min))
    end = start + timedelta(days=1)
    return start, end


def target_report_date(now=None):
    """Return the business day that should be reported at today's 10:00 IST run."""
    now_ist = (now or timezone.now()).astimezone(IST_TZ)
    if now_ist.weekday() == 0:  # Monday sends Friday's report.
        return now_ist.date() - timedelta(days=3)
    return now_ist.date() - timedelta(days=1)


def _format_minutes(minutes) -> str:
    minutes = float(minutes or 0)
    if minutes <= 0:
        return '0 min'
    if minutes < 60:
        return f'{minutes:.1f} min'
    hours = int(minutes // 60)
    rest = int(round(minutes % 60))
    return f'{hours}h {rest}m' if rest else f'{hours}h'


def _format_seconds(seconds) -> str:
    seconds = int(round(seconds or 0))
    if seconds <= 0:
        return '0 min'
    minutes = seconds // 60
    rest = seconds % 60
    if minutes < 60:
        return f'{minutes}m {rest}s' if rest else f'{minutes}m'
    hours = minutes // 60
    mins = minutes % 60
    return f'{hours}h {mins}m' if mins else f'{hours}h'


def _format_time(dt) -> str:
    if not dt:
        return '-'
    return timezone.localtime(dt, IST_TZ).strftime('%H:%M')


def _format_working_time(start, end) -> str:
    if not start or not end:
        return '-'
    delta = max((end - start).total_seconds(), 0)
    hours = int(delta // 3600)
    minutes = int((delta % 3600) // 60)
    return f'{hours}h {minutes}m'


def collect_operator_daily_stats(target_date):
    from accounts.models import User
    from activity.models import UserActivityEvent
    from contacts.models import CallInsight, Contact

    start, end = _day_range_ist(target_date)
    operators = list(
        User.objects
        .filter(role=User.ROLE_OPERATOR, is_active=True)
        .order_by('first_name', 'last_name', 'username')
    )
    operator_ids = [op.id for op in operators]

    contact_rows = (
        Contact.objects
        .filter(created_by_id__in=operator_ids, date__gte=start, date__lt=end)
        .values('created_by_id')
        .annotate(
            calls_count=Count('id', filter=Q(is_missed_call=False, callback_later=False)),
            total_call_seconds=Sum(
                'call_duration',
                filter=Q(is_missed_call=False, callback_later=False),
            ),
            avg_call_seconds=Avg(
                'call_duration',
                filter=Q(is_missed_call=False, callback_later=False, call_duration__isnull=False),
            ),
        )
    )
    contacts_by_operator = {row['created_by_id']: row for row in contact_rows}

    insight_rows = (
        CallInsight.objects
        .filter(
            created_by_id__in=operator_ids,
            call_date__gte=start,
            call_date__lt=end,
            status=CallInsight.STATUS_DONE,
        )
        .values('created_by_id')
        .annotate(insights_count=Sum('insight_count'))
    )
    insights_by_operator = {
        row['created_by_id']: row['insights_count'] or 0
        for row in insight_rows
    }

    activity_rows = (
        UserActivityEvent.objects
        .filter(user_id__in=operator_ids, created_at__gte=start, created_at__lt=end)
        .values('user_id')
        .annotate(start_time=Min('created_at'), end_time=Max('created_at'))
    )
    activity_by_operator = {row['user_id']: row for row in activity_rows}

    rows = []
    for op in operators:
        contact_row = contacts_by_operator.get(op.id, {})
        activity_row = activity_by_operator.get(op.id, {})
        total_seconds = int(contact_row.get('total_call_seconds') or 0)
        total_minutes = round(total_seconds / 60.0, 1)
        avg_seconds = contact_row.get('avg_call_seconds')
        start_time = activity_row.get('start_time')
        end_time = activity_row.get('end_time')
        rows.append({
            'operator_id': op.id,
            'operator_name': op.get_full_name() or op.username,
            'username': op.username,
            'calls_count': contact_row.get('calls_count') or 0,
            'total_call_seconds': total_seconds,
            'total_call_minutes': total_minutes,
            'avg_call_seconds': int(round(avg_seconds)) if avg_seconds else 0,
            'insights_count': insights_by_operator.get(op.id, 0),
            'kpi_percent': round((total_minutes / KPI_DAILY_TALK_MINUTES) * 100, 1),
            'start_time': start_time,
            'end_time': end_time,
            'working_seconds': int(max((end_time - start_time).total_seconds(), 0)) if start_time and end_time else 0,
        })
    return rows


def format_operator_daily_report_html(target_date, rows) -> str:
    lines = [
        f'<b>Operator Daily Stats</b>',
        f'For {_h(target_date.strftime("%d/%m/%Y"))}',
        '',
        f'KPI goal: {KPI_DAILY_TALK_MINUTES} minutes of talk time per day',
    ]

    if not rows:
        lines.extend(['', '<i>No active operators found.</i>'])
        return '\n'.join(lines)

    for row in rows:
        lines.extend([
            '',
            '━━━━━━━━━━━━━━━━━━━━━━',
            f'<b>{_h(row["operator_name"])}</b>',
            f'Total duration of all calls: <b>{_h(_format_minutes(row["total_call_minutes"]))}</b>',
            f'Average call duration: <b>{_h(_format_seconds(row["avg_call_seconds"]))}</b>',
            f'Number of insights: <b>{row["insights_count"]}</b>',
            f'KPI fulfillment: <b>{row["kpi_percent"]}%</b>',
            f'Operator start time: <b>{_h(_format_time(row["start_time"]))}</b>',
            f'Operator end time: <b>{_h(_format_time(row["end_time"]))}</b>',
            f'Operator working time: <b>{_h(_format_working_time(row["start_time"], row["end_time"]))}</b>',
        ])
    return '\n'.join(lines)


def send_operator_daily_report(target_date=None):
    """Build and send the operator daily report to the existing insights Telegram chat."""
    from contacts.telegram_insights import send_insight_html

    report_date = target_date or target_report_date()
    rows = collect_operator_daily_stats(report_date)
    body = format_operator_daily_report_html(report_date, rows)
    message_ids = send_insight_html(body)
    return {
        'date': report_date,
        'operators': len(rows),
        'message_ids': message_ids,
        'body': body,
    }
