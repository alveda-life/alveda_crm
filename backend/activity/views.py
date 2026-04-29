from datetime import datetime, time as time_cls, timedelta
from collections import defaultdict

from django.db.models import Avg, Count, Max, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import RolePermission, User

from .models import UserActivityEvent
from .serializers import UserActivityEventInSerializer, UserActivityEventOutSerializer


# Heartbeats are throttled at the source (~30s interval). Drop ones that arrive
# closer than this for the same session — protects DB from spammy clients.
HEARTBEAT_DEDUP_SECONDS = 25


class ActivityEventsPagination(PageNumberPagination):
    page_size = 200
    page_size_query_param = 'page_size'
    max_page_size = 1000


def _has_activity_view(user) -> bool:
    return RolePermission.has_perm(user, 'operator_activity', 'view')


def _client_ip(request) -> str | None:
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def _parse_date_or(default, raw):
    if not raw:
        return default
    parsed = parse_date(raw)
    return parsed or default


def _day_range(d):
    """Return aware (start, end_exclusive) for the calendar day ``d``."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(d, time_cls.min), tz)
    end = start + timedelta(days=1)
    return start, end


def _empty_call_stats():
    return {
        'calls_count': 0,
        'missed_calls_count': 0,
        'total_call_seconds': 0,
        'avg_call_seconds': None,
        'insights_count': 0,
    }


def _operator_call_stats(user_ids, start, end):
    """Aggregate call and insight metrics keyed by operator user id."""
    if not user_ids:
        return {}

    from contacts.models import CallInsight, Contact

    stats = {uid: _empty_call_stats() for uid in user_ids}

    contact_rows = (
        Contact.objects
        .filter(created_by_id__in=user_ids, date__gte=start, date__lt=end)
        .values('created_by_id')
        .annotate(
            calls_count=Count('id', filter=Q(is_missed_call=False, callback_later=False)),
            missed_calls_count=Count('id', filter=Q(is_missed_call=True)),
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
    for row in contact_rows:
        uid = row['created_by_id']
        if uid not in stats:
            continue
        stats[uid].update({
            'calls_count': row['calls_count'] or 0,
            'missed_calls_count': row['missed_calls_count'] or 0,
            'total_call_seconds': int(row['total_call_seconds'] or 0),
            'avg_call_seconds': int(round(row['avg_call_seconds'])) if row['avg_call_seconds'] else None,
        })

    insight_rows = (
        CallInsight.objects
        .filter(
            created_by_id__in=user_ids,
            call_date__gte=start,
            call_date__lt=end,
            status=CallInsight.STATUS_DONE,
        )
        .values('created_by_id')
        .annotate(insights_count=Sum('insight_count'))
    )
    for row in insight_rows:
        uid = row['created_by_id']
        if uid in stats:
            stats[uid]['insights_count'] = row['insights_count'] or 0

    return stats


def _resolve_users(request):
    """Return queryset of users to include in admin views (operators by default)."""
    role_param = request.query_params.get('role', 'operator')
    user_ids_raw = request.query_params.get('user_ids', '')
    qs = User.objects.filter(is_active=True)
    if user_ids_raw:
        ids = [int(x) for x in user_ids_raw.split(',') if x.strip().isdigit()]
        if ids:
            qs = qs.filter(id__in=ids)
    elif role_param and role_param != 'all':
        qs = qs.filter(role=role_param)
    return qs.order_by('first_name', 'last_name', 'username')


class ActivityIngestView(APIView):
    """`POST /api/activity/events/` — accept a batch of events from any
    authenticated user (including operators). Each user can only log events
    for themselves; the current user is taken from the JWT.

    `GET /api/activity/events/?user_id=&date=&event_type=` — paginated raw
    event list (used by the scatter / events view).
    """

    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get(self, request):
        user_id_raw = request.query_params.get('user_id')
        if not user_id_raw or not user_id_raw.isdigit():
            return Response({'detail': 'user_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        user_id = int(user_id_raw)

        if user_id != request.user.id and not _has_activity_view(request.user):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        target_date = _parse_date_or(timezone.localdate(), request.query_params.get('date'))
        start, end = _day_range(target_date)
        call_stats = _operator_call_stats([user_id], start, end).get(user_id, _empty_call_stats())

        qs = (
            UserActivityEvent.objects
            .filter(user_id=user_id, created_at__gte=start, created_at__lt=end)
            .select_related('user')
            .order_by('created_at')
        )

        event_type = request.query_params.get('event_type')
        if event_type:
            qs = qs.filter(event_type=event_type)

        paginator = ActivityEventsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = UserActivityEventOutSerializer(page, many=True)
        response = paginator.get_paginated_response(serializer.data)
        response.data['call_stats'] = call_stats
        return response

    def post(self, request):
        payload = request.data
        if isinstance(payload, dict) and 'events' in payload:
            payload = payload['events']
        if not isinstance(payload, list):
            return Response(
                {'detail': 'Expected a list of events or {"events": [...]}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not payload:
            return Response({'created': 0})

        # Validate everything before insert — all-or-nothing keeps the client
        # logic simple (if an event is malformed it stays in the batch and we
        # surface the error so it can be discarded client-side).
        serializer = UserActivityEventInSerializer(data=payload, many=True)
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data

        ip = _client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '')[:500]

        # Heartbeat dedup against the most-recent heartbeat per session in DB.
        last_hb_by_session: dict = {}
        session_keys = {it.get('session_key') for it in items if it.get('session_key')}
        if session_keys:
            recent = (
                UserActivityEvent.objects
                .filter(
                    user=request.user,
                    event_type=UserActivityEvent.EVENT_HEARTBEAT,
                    session_key__in=session_keys,
                )
                .values('session_key')
                .annotate(last_at=Max('created_at'))
            )
            last_hb_by_session = {row['session_key']: row['last_at'] for row in recent}

        objs = []
        now = timezone.now()
        # Also dedup heartbeats inside the same batch.
        seen_hb_in_batch: dict = {}
        for it in items:
            event_type = it['event_type']
            session_key = it.get('session_key')
            client_ts = it.get('client_ts') or now

            if event_type == UserActivityEvent.EVENT_HEARTBEAT and session_key:
                last_at = seen_hb_in_batch.get(session_key) or last_hb_by_session.get(session_key)
                if last_at and (client_ts - last_at).total_seconds() < HEARTBEAT_DEDUP_SECONDS:
                    continue
                seen_hb_in_batch[session_key] = client_ts

            objs.append(UserActivityEvent(
                user=request.user,
                event_type=event_type,
                object_type=it.get('object_type', '') or '',
                object_id=it.get('object_id'),
                path=(it.get('path') or '')[:500],
                metadata=it.get('metadata') or {},
                session_key=session_key,
                client_ts=client_ts,
                ip=ip,
                user_agent=ua,
            ))

        if not objs:
            return Response({'created': 0})

        UserActivityEvent.objects.bulk_create(objs, batch_size=500)
        return Response({'created': len(objs)}, status=status.HTTP_201_CREATED)


class ActivitySummaryView(APIView):
    """`GET /api/activity/summary/?date=YYYY-MM-DD&role=operator` — for each
    user in the requested role compute first/last event times, total active
    minutes (5-min buckets that have at least one event) and longest gap
    between consecutive events during the working window.
    """

    permission_classes = [IsAuthenticated]
    BUCKET_MINUTES = 5
    GAP_MINUTES = 15

    def get(self, request):
        if not _has_activity_view(request.user):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        target_date = _parse_date_or(timezone.localdate(), request.query_params.get('date'))
        start, end = _day_range(target_date)
        users = list(_resolve_users(request))
        if not users:
            return Response({'date': str(target_date), 'operators': []})

        user_ids = [u.id for u in users]
        call_stats = _operator_call_stats(user_ids, start, end)
        events = (
            UserActivityEvent.objects
            .filter(user_id__in=user_ids, created_at__gte=start, created_at__lt=end)
            .values('user_id', 'created_at')
            .order_by('user_id', 'created_at')
        )

        per_user: dict = defaultdict(list)
        for row in events:
            per_user[row['user_id']].append(row['created_at'])

        gap_threshold = timedelta(minutes=self.GAP_MINUTES)

        result = []
        for u in users:
            ts_list = per_user.get(u.id, [])
            total_events = len(ts_list)
            if total_events == 0:
                result.append({
                    'user_id':       u.id,
                    'username':      u.username,
                    'full_name':     u.get_full_name() or u.username,
                    'role':          u.role,
                    'first_event':   None,
                    'last_event':    None,
                    'active_minutes': 0,
                    'total_events':  0,
                    'sessions_count': 0,
                    'longest_gap_minutes': 0,
                    **call_stats.get(u.id, _empty_call_stats()),
                })
                continue

            buckets = set()
            longest_gap = timedelta(0)
            sessions = 1
            prev = None
            for ts in ts_list:
                bucket_idx = int((ts - start).total_seconds() // (self.BUCKET_MINUTES * 60))
                buckets.add(bucket_idx)
                if prev is not None:
                    delta = ts - prev
                    if delta > longest_gap:
                        longest_gap = delta
                    if delta >= gap_threshold:
                        sessions += 1
                prev = ts

            result.append({
                'user_id':       u.id,
                'username':      u.username,
                'full_name':     u.get_full_name() or u.username,
                'role':          u.role,
                'first_event':   ts_list[0].isoformat(),
                'last_event':    ts_list[-1].isoformat(),
                'active_minutes': len(buckets) * self.BUCKET_MINUTES,
                'total_events':  total_events,
                'sessions_count': sessions,
                'longest_gap_minutes': int(longest_gap.total_seconds() // 60),
                **call_stats.get(u.id, _empty_call_stats()),
            })

        result.sort(key=lambda r: r['active_minutes'], reverse=True)

        return Response({
            'date':       str(target_date),
            'bucket_minutes': self.BUCKET_MINUTES,
            'gap_threshold_minutes': self.GAP_MINUTES,
            'operators':  result,
        })


class ActivityTimelineView(APIView):
    """`GET /api/activity/timeline/?user_id=&date=&bucket=5` — bucketed
    activity for one user/day. Returns the bucket array (sparse: only
    buckets with events) plus a sample of raw events for tooltips.
    """

    permission_classes = [IsAuthenticated]
    DEFAULT_BUCKET = 5

    def get(self, request):
        user_id_raw = request.query_params.get('user_id')
        if not user_id_raw or not user_id_raw.isdigit():
            return Response({'detail': 'user_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        user_id = int(user_id_raw)

        # Permission: admin/anyone with operator_activity:view sees anyone;
        # other users may only see their own timeline.
        if user_id != request.user.id and not _has_activity_view(request.user):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            bucket_minutes = int(request.query_params.get('bucket', self.DEFAULT_BUCKET))
        except ValueError:
            bucket_minutes = self.DEFAULT_BUCKET
        bucket_minutes = max(1, min(60, bucket_minutes))

        target_date = _parse_date_or(timezone.localdate(), request.query_params.get('date'))
        start, end = _day_range(target_date)

        qs = UserActivityEvent.objects.filter(
            user_id=user_id, created_at__gte=start, created_at__lt=end,
        )

        bucket_counts: dict = defaultdict(lambda: defaultdict(int))
        # Aggregate counts per bucket per event_type — we want total + breakdown.
        for row in qs.values('created_at', 'event_type'):
            bucket_idx = int((row['created_at'] - start).total_seconds() // (bucket_minutes * 60))
            bucket_counts[bucket_idx]['total'] += 1
            bucket_counts[bucket_idx][row['event_type']] += 1

        buckets = []
        for idx in sorted(bucket_counts.keys()):
            counts = bucket_counts[idx]
            ts = start + timedelta(minutes=idx * bucket_minutes)
            buckets.append({
                'index':  idx,
                'ts':     ts.isoformat(),
                'count':  counts.pop('total'),
                'by_type': dict(counts),
            })

        events = list(
            qs.order_by('created_at')
              .values('id', 'event_type', 'object_type', 'object_id',
                      'path', 'metadata', 'created_at', 'session_key')
        )
        for e in events:
            e['created_at'] = e['created_at'].isoformat()
            if e['session_key']:
                e['session_key'] = str(e['session_key'])

        return Response({
            'user_id':        user_id,
            'date':           str(target_date),
            'bucket_minutes': bucket_minutes,
            'buckets_per_day': int(24 * 60 / bucket_minutes),
            'buckets':        buckets,
            'events':         events,
        })


class ActivityHeatmapView(APIView):
    """`GET /api/activity/heatmap/?date_from=&date_to=&user_ids=&bucket=`
    Returns a sparse matrix of `(user_id, day, bucket_idx) -> count`.
    """

    permission_classes = [IsAuthenticated]
    DEFAULT_BUCKET = 30

    def get(self, request):
        if not _has_activity_view(request.user):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()
        date_to = _parse_date_or(today, request.query_params.get('date_to'))
        date_from = _parse_date_or(date_to - timedelta(days=6), request.query_params.get('date_from'))
        if date_from > date_to:
            date_from, date_to = date_to, date_from

        try:
            bucket_minutes = int(request.query_params.get('bucket', self.DEFAULT_BUCKET))
        except ValueError:
            bucket_minutes = self.DEFAULT_BUCKET
        bucket_minutes = max(5, min(60, bucket_minutes))

        users = list(_resolve_users(request))
        if not users:
            return Response({
                'date_from': str(date_from),
                'date_to':   str(date_to),
                'bucket_minutes': bucket_minutes,
                'users':     [],
                'cells':     [],
            })

        user_ids = [u.id for u in users]
        period_start, _ = _day_range(date_from)
        _, period_end = _day_range(date_to)
        call_stats = _operator_call_stats(user_ids, period_start, period_end)

        rows = (
            UserActivityEvent.objects
            .filter(user_id__in=user_ids, created_at__gte=period_start, created_at__lt=period_end)
            .values('user_id', 'created_at')
        )

        cell_counts: dict = defaultdict(int)
        for row in rows:
            ts = timezone.localtime(row['created_at'])
            day = ts.date()
            bucket_idx = (ts.hour * 60 + ts.minute) // bucket_minutes
            cell_counts[(row['user_id'], day, bucket_idx)] += 1

        cells = [
            {
                'user_id':    uid,
                'date':       str(d),
                'bucket_idx': idx,
                'count':      cnt,
            }
            for (uid, d, idx), cnt in cell_counts.items()
        ]

        return Response({
            'date_from':       str(date_from),
            'date_to':         str(date_to),
            'bucket_minutes':  bucket_minutes,
            'buckets_per_day': int(24 * 60 / bucket_minutes),
            'users': [
                {
                    'user_id':   u.id,
                    'username':  u.username,
                    'full_name': u.get_full_name() or u.username,
                    'role':      u.role,
                    **call_stats.get(u.id, _empty_call_stats()),
                }
                for u in users
            ],
            'cells': cells,
        })


