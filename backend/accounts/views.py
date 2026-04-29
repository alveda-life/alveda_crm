from django.utils import timezone
from datetime import timedelta, date as date_cls, datetime as dt_cls, time as time_cls
from django.db.models import Avg, Count, Min, Q, Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import status
from .serializers import (
    CustomTokenObtainPairSerializer, UserSerializer, MeSerializer,
    RolePermissionSerializer, UserCreateSerializer, UserUpdateSerializer,
    CRMSettingsSerializer,
)
from .models import User, RolePermission, CRMSettings
from .permissions_config import SECTIONS, get_role_defaults


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(MeSerializer(request.user).data)


class UserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = User.objects.all().order_by('username')
        return Response(UserSerializer(users, many=True).data)

    def post(self, request):
        """Create a new user. Admin only."""
        if not (request.user.is_staff or getattr(request.user, 'role', '') == 'admin'):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        s = UserCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _require_admin(self, request):
        if not (request.user.is_staff or getattr(request.user, 'role', '') == 'admin'):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        return None

    def get_object(self, pk):
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist:
            return None

    def patch(self, request, pk):
        err = self._require_admin(request)
        if err:
            return err
        user = self.get_object(pk)
        if not user:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        s = UserUpdateSerializer(user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        user = s.save()
        return Response(UserSerializer(user).data)

    def delete(self, request, pk):
        err = self._require_admin(request)
        if err:
            return err
        user = self.get_object(pk)
        if not user:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if user.pk == request.user.pk:
            return Response({'detail': 'Cannot delete yourself.'}, status=status.HTTP_400_BAD_REQUEST)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CRMSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CRMSettingsSerializer(CRMSettings.get()).data)

    def patch(self, request):
        if not (request.user.is_staff or getattr(request.user, 'role', '') == 'admin'):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        s = CRMSettingsSerializer(CRMSettings.get(), data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        obj = s.save()
        return Response(CRMSettingsSerializer(obj).data)


class RolePermissionView(APIView):
    """
    GET  /api/role-permissions/         — list all role permissions
    PUT  /api/role-permissions/{role}/  — update a role's permissions
    POST /api/role-permissions/{role}/reset/ — reset to defaults
    """
    permission_classes = [IsAuthenticated]

    def _require_admin(self, request):
        u = request.user
        if not (u.is_staff or getattr(u, 'role', '') == 'admin'):
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        return None

    def get(self, request, role=None):
        if role:
            perms = RolePermission.get_for_role(role)
            return Response({'role': role, 'permissions': perms})
        # Return all roles
        result = {}
        for r, _ in User.ROLE_CHOICES:
            result[r] = RolePermission.get_for_role(r)
        return Response(result)

    def put(self, request, role=None):
        err = self._require_admin(request)
        if err:
            return err
        if not role:
            return Response({'detail': 'Role required.'}, status=400)
        # Validate role exists
        valid_roles = [r for r, _ in User.ROLE_CHOICES]
        if role not in valid_roles:
            return Response({'detail': 'Invalid role.'}, status=400)
        permissions = request.data.get('permissions', {})
        obj, _ = RolePermission.objects.update_or_create(
            role=role,
            defaults={'permissions': permissions},
        )
        return Response(RolePermissionSerializer(obj).data)

    def post(self, request, role=None):
        """Reset role to defaults."""
        err = self._require_admin(request)
        if err:
            return err
        if not role:
            return Response({'detail': 'Role required.'}, status=400)
        defaults = get_role_defaults(role)
        obj, _ = RolePermission.objects.update_or_create(
            role=role,
            defaults={'permissions': defaults},
        )
        return Response(RolePermissionSerializer(obj).data)


class SectionsMetaView(APIView):
    """Returns available sections and their actions — used by frontend constructor."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(SECTIONS)


class OperatorStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from contacts.models import Contact
        from partners.models import Partner

        period = request.query_params.get('period', 'week')
        now = timezone.now()

        if period == 'today':
            since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            since = now - timedelta(days=7)
        elif period == 'month':
            since = now - timedelta(days=30)
        else:
            since = None

        users = User.objects.filter(role=User.ROLE_OPERATOR).order_by('first_name', 'username')
        result = []

        for user in users:
            contact_qs = Contact.objects.filter(created_by=user)
            if since:
                contact_qs = contact_qs.filter(created_at__gte=since)

            stats = contact_qs.aggregate(
                total_calls=Count('id', filter=Q(is_missed_call=False) & Q(callback_later=False)),
                missed_calls=Count('id', filter=Q(is_missed_call=True)),
                callbacks=Count('id', filter=Q(callback_later=True)),
                audio_uploads=Count(
                    'id',
                    filter=Q(audio_file__isnull=False) & ~Q(audio_file=''),
                ),
            )

            last_contact = Contact.objects.filter(created_by=user).order_by('-created_at').first()
            assigned_qs = Partner.objects.filter(assigned_to=user)
            partners_total = assigned_qs.count()
            active_stages = ['new', 'trained', 'set_created', 'has_sale']
            dead_stages = ['no_answer', 'declined', 'no_sales']
            by_stage = {}
            for s, _ in Partner.STAGE_CHOICES:
                by_stage[s] = assigned_qs.filter(stage=s).count()
            active_count = sum(by_stage.get(s, 0) for s in active_stages)
            dead_count = sum(by_stage.get(s, 0) for s in dead_stages)
            overdue = assigned_qs.filter(
                stage__in=active_stages,
                control_date__lte=date_cls.today(),
            ).count()

            result.append({
                'id': user.id,
                'name': user.get_full_name() or user.username,
                'username': user.username,
                'total_calls': stats['total_calls'] or 0,
                'missed_calls': stats['missed_calls'] or 0,
                'callbacks': stats['callbacks'] or 0,
                'audio_uploads': stats['audio_uploads'] or 0,
                'assigned_partners': partners_total,
                'active_partners': active_count,
                'dead_partners': dead_count,
                'overdue_partners': overdue,
                'partners_by_stage': by_stage,
                'last_activity': last_contact.created_at.isoformat() if last_contact else None,
            })

        result.sort(
            key=lambda x: x['total_calls'] + x['missed_calls'] + x['callbacks'],
            reverse=True,
        )
        return Response(result)


class AnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from contacts.models import Contact
        from partners.models import Partner
        from django.db.models.functions import TruncDate, TruncHour

        period = request.query_params.get('period', 'week')
        now = timezone.now()
        today = now.date()

        # ------------------------------------------------------------------ #
        # Time-series buckets
        # ------------------------------------------------------------------ #
        until = None  # upper bound used only for 'custom' period

        if period == 'today':
            since = now.replace(hour=0, minute=0, second=0, microsecond=0)
            labels = [f'{h:02d}:00' for h in range(24)]

            c_raw = (
                Contact.objects.filter(created_at__gte=since)
                .annotate(bucket=TruncHour('created_at'))
                .values('bucket')
                .annotate(
                    calls=Count('id', filter=Q(is_missed_call=False, callback_later=False)),
                    missed=Count('id', filter=Q(is_missed_call=True)),
                    callbacks=Count('id', filter=Q(callback_later=True)),
                )
                .order_by('bucket')
            )
            p_raw = (
                Partner.objects.filter(created_at__gte=since)
                .annotate(bucket=TruncHour('created_at'))
                .values('bucket').annotate(cnt=Count('id')).order_by('bucket')
            )
            c_map = {r['bucket'].hour: r for r in c_raw}
            p_map = {r['bucket'].hour: r['cnt'] for r in p_raw}
            time_series = {
                'labels': labels,
                'partners_new': [p_map.get(h, 0) for h in range(24)],
                'calls': [c_map.get(h, {}).get('calls', 0) for h in range(24)],
                'missed': [c_map.get(h, {}).get('missed', 0) for h in range(24)],
                'callbacks': [c_map.get(h, {}).get('callbacks', 0) for h in range(24)],
            }
            # Task time series (today branch)
            from tasks.models import Task as TaskModel
            t_raw = TaskModel.objects.filter(created_at__gte=since).annotate(bucket=TruncHour('created_at')).values('bucket').annotate(cnt=Count('id')).order_by('bucket')
            tc_raw = TaskModel.objects.filter(completed_at__gte=since, completed_at__isnull=False).annotate(bucket=TruncHour('completed_at')).values('bucket').annotate(cnt=Count('id')).order_by('bucket')
            t_map = {r['bucket'].hour: r['cnt'] for r in t_raw}
            tc_map = {r['bucket'].hour: r['cnt'] for r in tc_raw}
            time_series['tasks_created']   = [t_map.get(h, 0) for h in range(24)]
            time_series['tasks_completed'] = [tc_map.get(h, 0) for h in range(24)]

        elif period in ('week', 'month'):
            num_days = 7 if period == 'week' else 30
            start = today - timedelta(days=num_days - 1)
            since = now - timedelta(days=num_days - 1)
            since = since.replace(hour=0, minute=0, second=0, microsecond=0)
            date_list = [start + timedelta(days=i) for i in range(num_days)]
            labels = [d.strftime('%b %d') for d in date_list]

            c_raw = (
                Contact.objects.filter(created_at__gte=since)
                .annotate(bucket=TruncDate('created_at'))
                .values('bucket')
                .annotate(
                    calls=Count('id', filter=Q(is_missed_call=False, callback_later=False)),
                    missed=Count('id', filter=Q(is_missed_call=True)),
                    callbacks=Count('id', filter=Q(callback_later=True)),
                )
                .order_by('bucket')
            )
            p_raw = (
                Partner.objects.filter(created_at__gte=since)
                .annotate(bucket=TruncDate('created_at'))
                .values('bucket').annotate(cnt=Count('id')).order_by('bucket')
            )
            c_map = {str(r['bucket']): r for r in c_raw}
            p_map = {str(r['bucket']): r['cnt'] for r in p_raw}
            time_series = {
                'labels': labels,
                'partners_new': [p_map.get(str(d), 0) for d in date_list],
                'calls': [c_map.get(str(d), {}).get('calls', 0) for d in date_list],
                'missed': [c_map.get(str(d), {}).get('missed', 0) for d in date_list],
                'callbacks': [c_map.get(str(d), {}).get('callbacks', 0) for d in date_list],
            }
            # Task time series (week/month branch)
            from tasks.models import Task as TaskModel
            t_raw = TaskModel.objects.filter(created_at__gte=since).annotate(bucket=TruncDate('created_at')).values('bucket').annotate(cnt=Count('id')).order_by('bucket')
            tc_raw = TaskModel.objects.filter(completed_at__gte=since, completed_at__isnull=False).annotate(bucket=TruncDate('completed_at')).values('bucket').annotate(cnt=Count('id')).order_by('bucket')
            t_map = {str(r['bucket']): r['cnt'] for r in t_raw}
            tc_map = {str(r['bucket']): r['cnt'] for r in tc_raw}
            time_series['tasks_created']   = [t_map.get(str(d), 0) for d in date_list]
            time_series['tasks_completed'] = [tc_map.get(str(d), 0) for d in date_list]

        elif period == 'custom':
            date_from_str = request.query_params.get('date_from', '')
            date_to_str   = request.query_params.get('date_to', '')
            try:
                date_from = dt_cls.strptime(date_from_str, '%Y-%m-%d').date()
                date_to   = dt_cls.strptime(date_to_str,   '%Y-%m-%d').date()
            except (ValueError, TypeError):
                date_from = today - timedelta(days=7)
                date_to   = today
            if date_to > today:    date_to   = today
            if date_from > date_to: date_from = date_to - timedelta(days=7)

            since = timezone.make_aware(dt_cls.combine(date_from, time_cls.min))
            until = timezone.make_aware(dt_cls.combine(date_to + timedelta(days=1), time_cls.min))

            diff_days = (date_to - date_from).days + 1
            date_list = [date_from + timedelta(days=i) for i in range(diff_days)]
            labels = [d.strftime('%b %d') for d in date_list]

            c_raw = (
                Contact.objects.filter(created_at__gte=since, created_at__lt=until)
                .annotate(bucket=TruncDate('created_at'))
                .values('bucket')
                .annotate(
                    calls=Count('id', filter=Q(is_missed_call=False, callback_later=False)),
                    missed=Count('id', filter=Q(is_missed_call=True)),
                    callbacks=Count('id', filter=Q(callback_later=True)),
                )
                .order_by('bucket')
            )
            p_raw = (
                Partner.objects.filter(created_at__gte=since, created_at__lt=until)
                .annotate(bucket=TruncDate('created_at'))
                .values('bucket').annotate(cnt=Count('id')).order_by('bucket')
            )
            c_map = {str(r['bucket']): r for r in c_raw}
            p_map = {str(r['bucket']): r['cnt'] for r in p_raw}
            time_series = {
                'labels': labels,
                'partners_new': [p_map.get(str(d), 0) for d in date_list],
                'calls':     [c_map.get(str(d), {}).get('calls',     0) for d in date_list],
                'missed':    [c_map.get(str(d), {}).get('missed',    0) for d in date_list],
                'callbacks': [c_map.get(str(d), {}).get('callbacks', 0) for d in date_list],
            }
            # Task time series (custom branch)
            from tasks.models import Task as TaskModel
            t_raw = TaskModel.objects.filter(created_at__gte=since, created_at__lt=until).annotate(bucket=TruncDate('created_at')).values('bucket').annotate(cnt=Count('id')).order_by('bucket')
            tc_raw = TaskModel.objects.filter(completed_at__gte=since, completed_at__lt=until, completed_at__isnull=False).annotate(bucket=TruncDate('completed_at')).values('bucket').annotate(cnt=Count('id')).order_by('bucket')
            t_map = {str(r['bucket']): r['cnt'] for r in t_raw}
            tc_map = {str(r['bucket']): r['cnt'] for r in tc_raw}
            time_series['tasks_created']   = [t_map.get(str(d), 0) for d in date_list]
            time_series['tasks_completed'] = [tc_map.get(str(d), 0) for d in date_list]

        else:  # all — last 12 weeks
            from django.db.models.functions import TruncWeek
            from tasks.models import Task as TaskModel
            since = None
            until = None
            monday_offset = today.weekday()
            week0 = today - timedelta(days=monday_offset + 11 * 7)
            weeks = [week0 + timedelta(weeks=i) for i in range(12)]
            def _week_label(w, ongoing=False):
                end = w + timedelta(days=6)
                suffix = ' →' if ongoing else ''
                return f"{w.day}–{end.day} {end.strftime('%b')}{suffix}"
            labels = [_week_label(w) for w in weeks]
            labels[-1] = _week_label(weeks[-1], ongoing=True)

            # Single query per model — annotate by ISO week start, bucket in Python
            p_raw = (
                Partner.objects.filter(created_at__date__gte=week0)
                .annotate(bucket=TruncWeek('created_at'))
                .values('bucket').annotate(cnt=Count('id')).order_by('bucket')
            )
            c_raw = (
                Contact.objects.filter(created_at__date__gte=week0)
                .annotate(bucket=TruncWeek('created_at'))
                .values('bucket')
                .annotate(
                    calls=Count('id', filter=Q(is_missed_call=False, callback_later=False)),
                    missed=Count('id', filter=Q(is_missed_call=True)),
                    callbacks=Count('id', filter=Q(callback_later=True)),
                ).order_by('bucket')
            )
            t_raw = (
                TaskModel.objects.filter(created_at__date__gte=week0)
                .annotate(bucket=TruncWeek('created_at'))
                .values('bucket').annotate(cnt=Count('id')).order_by('bucket')
            )
            tc_raw = (
                TaskModel.objects.filter(completed_at__date__gte=week0, completed_at__isnull=False)
                .annotate(bucket=TruncWeek('completed_at'))
                .values('bucket').annotate(cnt=Count('id')).order_by('bucket')
            )

            def _week_key(w):
                return str(w.date()) if hasattr(w, 'date') else str(w)

            p_map  = {_week_key(r['bucket']): r['cnt'] for r in p_raw}
            c_map  = {_week_key(r['bucket']): r for r in c_raw}
            t_map  = {_week_key(r['bucket']): r['cnt'] for r in t_raw}
            tc_map = {_week_key(r['bucket']): r['cnt'] for r in tc_raw}

            time_series = {
                'labels':      labels,
                'partners_new': [p_map.get(str(w), 0) for w in weeks],
                'calls':        [c_map.get(str(w), {}).get('calls', 0) for w in weeks],
                'missed':       [c_map.get(str(w), {}).get('missed', 0) for w in weeks],
                'callbacks':    [c_map.get(str(w), {}).get('callbacks', 0) for w in weeks],
                'tasks_created':   [t_map.get(str(w), 0) for w in weeks],
                'tasks_completed': [tc_map.get(str(w), 0) for w in weeks],
            }

        # ------------------------------------------------------------------ #
        # Operator daily trends and CRM contact coverage
        # ------------------------------------------------------------------ #
        if period == 'today':
            trend_dates = [today]
        elif period in ('week', 'month', 'custom'):
            trend_dates = date_list
        else:
            trend_start = today - timedelta(days=89)
            trend_dates = [trend_start + timedelta(days=i) for i in range(90)]

        trend_labels = [d.strftime('%b %d') for d in trend_dates]
        trend_start_dt = timezone.make_aware(dt_cls.combine(trend_dates[0], time_cls.min))
        trend_end_dt = timezone.make_aware(dt_cls.combine(trend_dates[-1] + timedelta(days=1), time_cls.min))

        from contacts.models import CallInsight

        operators_for_trends = list(User.objects.filter(role=User.ROLE_OPERATOR, is_active=True).order_by('first_name', 'username'))
        operator_ids_for_trends = [u.id for u in operators_for_trends]

        op_contact_rows = (
            Contact.objects
            .filter(created_by_id__in=operator_ids_for_trends, date__gte=trend_start_dt, date__lt=trend_end_dt)
            .annotate(bucket=TruncDate('date'))
            .values('created_by_id', 'bucket')
            .annotate(
                calls_count=Count('id', filter=Q(is_missed_call=False, callback_later=False)),
                missed_calls_count=Count('id', filter=Q(is_missed_call=True)),
                total_call_seconds=Sum('call_duration', filter=Q(is_missed_call=False, callback_later=False)),
                avg_call_seconds=Avg(
                    'call_duration',
                    filter=Q(is_missed_call=False, callback_later=False, call_duration__isnull=False),
                ),
            )
        )
        op_contact_map = {
            (row['created_by_id'], row['bucket']): row
            for row in op_contact_rows
        }

        op_insight_rows = (
            CallInsight.objects
            .filter(
                created_by_id__in=operator_ids_for_trends,
                call_date__gte=trend_start_dt,
                call_date__lt=trend_end_dt,
                status=CallInsight.STATUS_DONE,
            )
            .annotate(bucket=TruncDate('call_date'))
            .values('created_by_id', 'bucket')
            .annotate(insights_count=Sum('insight_count'))
        )
        op_insight_map = {
            (row['created_by_id'], row['bucket']): row['insights_count'] or 0
            for row in op_insight_rows
        }

        operator_daily_trends = {
            'labels': trend_labels,
            'dates': [str(d) for d in trend_dates],
            'operators': [],
        }
        for op in operators_for_trends:
            calls = []
            missed = []
            total_minutes = []
            avg_minutes = []
            insights = []
            for d in trend_dates:
                contact_row = op_contact_map.get((op.id, d), {})
                total_seconds = contact_row.get('total_call_seconds') or 0
                avg_seconds = contact_row.get('avg_call_seconds')
                calls.append(contact_row.get('calls_count') or 0)
                missed.append(contact_row.get('missed_calls_count') or 0)
                total_minutes.append(round(total_seconds / 60.0, 1))
                avg_minutes.append(round(avg_seconds / 60.0, 1) if avg_seconds else 0)
                insights.append(op_insight_map.get((op.id, d), 0))

            operator_daily_trends['operators'].append({
                'id': op.id,
                'name': op.get_full_name() or op.username,
                'username': op.username,
                'calls_count': calls,
                'missed_calls_count': missed,
                'total_call_minutes': total_minutes,
                'avg_call_minutes': avg_minutes,
                'insights_count': insights,
            })

        partner_created_dates = [
            timezone.localtime(created_at).date()
            for created_at in Partner.objects.values_list('created_at', flat=True)
            if created_at
        ]
        first_audio_call_dates = [
            timezone.localtime(row['first_call']).date()
            for row in (
                Contact.objects
                .filter(
                    audio_file__isnull=False,
                    transcription_status=Contact.TRANSCRIPTION_DONE,
                )
                .exclude(audio_file='')
                .values('partner_id')
                .annotate(first_call=Min('date'))
            )
            if row['first_call']
        ]
        partner_contact_coverage = {
            'labels': trend_labels,
            'dates': [str(d) for d in trend_dates],
            'partners_with_transcribed_audio_call': [],
            'partners_never_contacted': [],
        }
        for d in trend_dates:
            partner_total = sum(1 for created_date in partner_created_dates if created_date <= d)
            contacted_total = sum(1 for first_call_date in first_audio_call_dates if first_call_date <= d)
            partner_contact_coverage['partners_with_transcribed_audio_call'].append(contacted_total)
            partner_contact_coverage['partners_never_contacted'].append(max(partner_total - contacted_total, 0))

        # ------------------------------------------------------------------ #
        # Overview KPIs
        # ------------------------------------------------------------------ #
        all_partners = Partner.objects.all()
        active_stages = ['new', 'trained', 'set_created', 'has_sale']
        dead_stages = ['no_answer', 'declined', 'no_sales']

        def period_qs(qs):
            if since:
                qs = qs.filter(created_at__gte=since)
            if until:
                qs = qs.filter(created_at__lt=until)
            return qs

        period_partners = period_qs(all_partners)
        period_contacts = period_qs(Contact.objects.all())

        total = all_partners.count()
        active_cnt = all_partners.filter(stage__in=active_stages).count()
        dead_cnt = all_partners.filter(stage__in=dead_stages).count()

        c_agg = period_contacts.aggregate(
            calls=Count('id', filter=Q(is_missed_call=False, callback_later=False)),
            missed=Count('id', filter=Q(is_missed_call=True)),
            callbacks=Count('id', filter=Q(callback_later=True)),
            audio=Count('id', filter=Q(audio_file__isnull=False) & ~Q(audio_file='')),
        )
        calls_total = c_agg['calls'] or 0
        missed_total = c_agg['missed'] or 0
        miss_rate = round(missed_total / (calls_total + missed_total) * 100, 1) if (calls_total + missed_total) else 0

        unassigned = all_partners.filter(assigned_to__isnull=True, stage__in=active_stages).count()
        # Partners in active pipeline that have never had any contact
        active_partner_ids = list(all_partners.filter(stage__in=active_stages).values_list('id', flat=True))
        contacted_ids = set(
            Contact.objects.filter(partner_id__in=active_partner_ids)
            .values_list('partner_id', flat=True).distinct()
        )
        never_contacted = len([pid for pid in active_partner_ids if pid not in contacted_ids])

        # Stagnant: active partners with no contact in 21+ days
        three_weeks_ago = now - timedelta(days=21)
        recent_any_ids = set(
            Contact.objects.filter(
                partner_id__in=active_partner_ids, created_at__gte=three_weeks_ago
            ).values_list('partner_id', flat=True).distinct()
        )
        stagnant = len([pid for pid in active_partner_ids if pid not in recent_any_ids])

        overview = {
            'total_partners': total,
            'new_in_period': period_partners.count(),
            'active_partners': active_cnt,
            'dead_partners': dead_cnt,
            'dead_rate': round(dead_cnt / total * 100, 1) if total else 0,
            'total_calls': calls_total,
            'missed_calls': missed_total,
            'miss_rate': miss_rate,
            'callbacks': c_agg['callbacks'] or 0,
            'audio_uploads': c_agg['audio'] or 0,
            'overdue_partners': all_partners.filter(
                stage__in=active_stages, control_date__lt=today
            ).count(),
            'due_today': all_partners.filter(
                stage__in=active_stages, control_date=today
            ).count(),
            'unassigned_partners': unassigned,
            'never_contacted': never_contacted,
            'stagnant_partners': stagnant,
        }

        # ------------------------------------------------------------------ #
        # Funnel snapshot
        # ------------------------------------------------------------------ #
        stage_meta = [
            ('new',         'New',              '#EF5350'),
            ('trained',     'Agreed to Create First Set', '#FFB300'),
            ('set_created', 'Set Created',       '#29B6F6'),
            ('has_sale',    'Has Sale',          '#43A047'),
            ('no_answer',   'Dead — No Answer', '#546E7A'),
            ('declined',    'Dead — Declined',  '#B71C1C'),
            ('no_sales',    'Dead — No Sales',  '#E65100'),
        ]
        funnel = [
            {'stage': k, 'label': lbl, 'color': clr, 'count': all_partners.filter(stage=k).count()}
            for k, lbl, clr in stage_meta
        ]

        # ------------------------------------------------------------------ #
        # Conversion rates (cumulative from New)
        # ------------------------------------------------------------------ #
        reached_trained = all_partners.filter(stage__in=['trained', 'set_created', 'has_sale']).count()
        reached_set = all_partners.filter(stage__in=['set_created', 'has_sale']).count()
        reached_sale = all_partners.filter(stage='has_sale').count()
        conversion = {
            'to_trained':     round(reached_trained / total * 100, 1) if total else 0,
            'to_set_created': round(reached_set / total * 100, 1) if total else 0,
            'to_sale':        round(reached_sale / total * 100, 1) if total else 0,
        }

        # ------------------------------------------------------------------ #
        # Pipeline velocity — avg time at current stage + stuck count
        # Uses stage_changed_at; falls back to created_at for old records
        # ------------------------------------------------------------------ #
        stage_stuck_threshold = {'new': 14, 'trained': 30, 'set_created': 45}
        stage_labels = {'new': 'New', 'trained': 'Agreed to Create First Set', 'set_created': 'Set Created', 'has_sale': 'Has Sale'}
        pipeline_velocity = []
        for stage in active_stages:
            rows = list(all_partners.filter(stage=stage).values_list('stage_changed_at', 'created_at'))
            cnt = len(rows)
            ages = [(now - (sc or ca)).days for sc, ca in rows]
            avg_age = round(sum(ages) / cnt) if cnt else 0
            threshold = stage_stuck_threshold.get(stage)
            stuck = sum(1 for a in ages if threshold and a > threshold) if threshold else 0
            pipeline_velocity.append({
                'stage': stage,
                'label': stage_labels[stage],
                'count': cnt,
                'avg_age_days': avg_age,
                'stuck': stuck,
                'stuck_threshold': threshold,
            })

        # ------------------------------------------------------------------ #
        # Category / type breakdown  (with conversion rates)
        # ------------------------------------------------------------------ #
        by_category = []
        for k, lbl in Partner.CATEGORY_CHOICES:
            qs = all_partners.filter(category=k)
            cnt = qs.count()
            sale = qs.filter(stage='has_sale').count()
            dead = qs.filter(stage__in=dead_stages).count()
            rev  = float(qs.aggregate(r=Sum('paid_orders_sum'))['r'] or 0)
            by_category.append({
                'key': k, 'label': lbl, 'count': cnt,
                'sale': sale, 'dead': dead, 'revenue': rev,
                'conv_sale': round(sale / cnt * 100, 1) if cnt else 0,
                'dead_rate': round(dead / cnt * 100, 1) if cnt else 0,
            })

        by_type = []
        for k, lbl in Partner.TYPE_CHOICES:
            qs = all_partners.filter(type=k)
            cnt = qs.count()
            sale = qs.filter(stage='has_sale').count()
            dead = qs.filter(stage__in=dead_stages).count()
            rev  = float(qs.aggregate(r=Sum('paid_orders_sum'))['r'] or 0)
            by_type.append({
                'key': k, 'label': lbl, 'count': cnt,
                'sale': sale, 'dead': dead, 'revenue': rev,
                'conv_sale': round(sale / cnt * 100, 1) if cnt else 0,
                'dead_rate': round(dead / cnt * 100, 1) if cnt else 0,
            })

        # Gender breakdown
        by_gender = []
        for k, lbl in Partner.GENDER_CHOICES:
            qs = all_partners.filter(gender=k)
            cnt = qs.count()
            sale = qs.filter(stage='has_sale').count()
            rev  = float(qs.aggregate(r=Sum('paid_orders_sum'))['r'] or 0)
            by_gender.append({
                'key': k, 'label': lbl, 'count': cnt,
                'sale': sale, 'revenue': rev,
                'conv_sale': round(sale / cnt * 100, 1) if cnt else 0,
            })

        # Top states by partner count + conversion
        from django.db.models import Count as DjCount
        state_rows = list(
            all_partners.filter(state__gt='')
            .values('state')
            .annotate(
                count=DjCount('id'),
                sale=DjCount('id', filter=Q(stage='has_sale')),
                dead=DjCount('id', filter=Q(stage__in=dead_stages)),
            )
            .order_by('-count')[:12]
        )
        for r in state_rows:
            r['conv_sale'] = round(r['sale'] / r['count'] * 100, 1) if r['count'] else 0

        # Top referral sources
        referral_rows = list(
            all_partners.filter(referred_by__gt='')
            .values('referred_by')
            .annotate(
                count=DjCount('id'),
                sale=DjCount('id', filter=Q(stage='has_sale')),
            )
            .order_by('-count')[:10]
        )
        for r in referral_rows:
            r['conv_sale'] = round(r['sale'] / r['count'] * 100, 1) if r['count'] else 0

        # ------------------------------------------------------------------ #
        # Sales depth — weekly cumulative time series (always 16 weeks back,
        # independent of the selected period).
        # Y = "how many partners (ever created up to that week) NOW have ≥N
        #       paid orders" — gives rising adoption curves.
        # One query: fetch all partners' creation date + paid_orders_count,
        # then compute cumulative thresholds in Python.
        # ------------------------------------------------------------------ #
        monday_offset = today.weekday()
        sd_week0 = today - timedelta(days=monday_offset + 15 * 7)  # 16 weeks back
        sd_weeks = [sd_week0 + timedelta(weeks=i) for i in range(16)]
        def _sd_week_label(w):
            end = w + timedelta(days=6)
            return f"{w.day}–{end.day} {end.strftime('%b')}"
        sd_labels = [_sd_week_label(w) for w in sd_weeks]

        # Single DB fetch: (created_at timezone-aware datetime, paid_orders_count, type)
        ap_raw = list(all_partners.values_list('created_at', 'paid_orders_count', 'type'))

        def _sd_series(min_orders, type_filter=None):
            row = []
            for w in sd_weeks:
                w_end = w + timedelta(days=7)
                w_end_aware = timezone.make_aware(dt_cls.combine(w_end, time_cls.min))
                count = sum(
                    1 for ca, poc, pt in ap_raw
                    if ca < w_end_aware
                    and poc >= min_orders
                    and (type_filter is None or pt == type_filter)
                )
                row.append(count)
            return row

        sales_depth_ts = {
            'labels':  sd_labels,
            '1plus':   _sd_series(1),
            '3plus':   _sd_series(3),
            '5plus':   _sd_series(5),
            '10plus':  _sd_series(10),
            # split by type for context
            '1plus_partner':  _sd_series(1, 'partner'),
            '1plus_medic':    _sd_series(1, 'medic'),
        }

        # ------------------------------------------------------------------ #
        # Financial KPIs  (aggregate over ALL partners, not period-filtered —
        # these are lifetime stats synced from the platform)
        # ------------------------------------------------------------------ #
        fin = all_partners.aggregate(
            total_revenue=Sum('paid_orders_sum'),
            total_unpaid=Sum('unpaid_orders_sum'),
            total_orders=Sum('orders_count'),
            total_paid_orders=Sum('paid_orders_count'),
            total_sets=Sum('medical_sets_count'),
            total_referrals=Sum('referrals_count'),
        )
        total_rev = float(fin['total_revenue'] or 0)
        total_unp = float(fin['total_unpaid'] or 0)
        total_ord = fin['total_orders'] or 0
        total_paid_ord = fin['total_paid_orders'] or 0
        partners_with_rev = all_partners.filter(paid_orders_sum__gt=0).count()
        avg_rev = round(total_rev / partners_with_rev, 2) if partners_with_rev else 0
        paid_ord_rate = round(total_paid_ord / total_ord * 100, 1) if total_ord else 0

        financials = {
            'total_revenue': total_rev,
            'total_unpaid': total_unp,
            'total_orders': total_ord,
            'total_paid_orders': total_paid_ord,
            'paid_order_rate': paid_ord_rate,
            'total_sets': fin['total_sets'] or 0,
            'total_referrals': fin['total_referrals'] or 0,
            'partners_with_revenue': partners_with_rev,
            'avg_revenue_per_partner': avg_rev,
        }

        # ------------------------------------------------------------------ #
        # Operator performance
        # Pre-fetch contact/partner data for all operators in bulk
        # ------------------------------------------------------------------ #
        users = User.objects.filter(role=User.ROLE_OPERATOR).order_by('first_name', 'username')

        # Active assigned partners per operator (2 queries total)
        two_weeks_ago = now - timedelta(days=14)
        all_active_assigned = list(
            all_partners.filter(stage__in=active_stages, assigned_to__in=users)
            .values_list('id', 'assigned_to_id')
        )
        op_active_pids = {}
        for pid, uid in all_active_assigned:
            op_active_pids.setdefault(uid, set()).add(pid)
        all_active_pids_set = set(p[0] for p in all_active_assigned)

        ever_contacted_set = set(
            Contact.objects.filter(partner_id__in=all_active_pids_set)
            .values_list('partner_id', flat=True).distinct()
        ) if all_active_pids_set else set()
        recent_contacted_set = set(
            Contact.objects.filter(
                partner_id__in=all_active_pids_set, created_at__gte=two_weeks_ago
            ).values_list('partner_id', flat=True).distinct()
        ) if all_active_pids_set else set()

        # Revenue per operator (1 query)
        op_rev_map = dict(
            all_partners.filter(assigned_to__in=users)
            .values('assigned_to_id')
            .annotate(rev=Sum('paid_orders_sum'))
            .values_list('assigned_to_id', 'rev')
        )

        operators = []
        for user in users:
            c_all = Contact.objects.filter(created_by=user)
            c_period = c_all
            if since:
                c_period = c_period.filter(created_at__gte=since)
            if until:
                c_period = c_period.filter(created_at__lt=until)
            cs = c_period.aggregate(
                calls=Count('id', filter=Q(is_missed_call=False, callback_later=False)),
                missed=Count('id', filter=Q(is_missed_call=True)),
                callbacks=Count('id', filter=Q(callback_later=True)),
                audio=Count('id', filter=Q(audio_file__isnull=False) & ~Q(audio_file='')),
            )
            asgn = Partner.objects.filter(assigned_to=user)
            last = c_all.order_by('-created_at').first()
            op_calls   = cs['calls'] or 0
            op_missed  = cs['missed'] or 0
            op_callbacks = cs['callbacks'] or 0
            op_rate    = round(op_missed / (op_calls + op_missed) * 100, 1) if (op_calls + op_missed) else 0
            asgn_total   = asgn.count()
            asgn_active  = asgn.filter(stage__in=active_stages).count()
            asgn_dead    = asgn.filter(stage__in=dead_stages).count()
            asgn_trained = asgn.filter(stage__in=['trained', 'set_created', 'has_sale']).count()
            asgn_set     = asgn.filter(stage__in=['set_created', 'has_sale']).count()
            asgn_sale    = asgn.filter(stage='has_sale').count()
            partners_1sale  = asgn.filter(paid_orders_count__gte=1).count()
            partners_10sale = asgn.filter(paid_orders_count__gte=10).count()

            def pct(n):
                return round(n / asgn_total * 100, 1) if asgn_total else 0

            # Efficiency from pre-fetched maps
            op_pids = op_active_pids.get(user.id, set())
            never_contacted_op = len(op_pids - ever_contacted_set)
            inactive_op = len(op_pids - recent_contacted_set)
            contact_rate = round(len(op_pids & ever_contacted_set) / len(op_pids) * 100, 1) if op_pids else 0

            total_activity = op_calls + op_missed + op_callbacks
            calls_per_sale = round(total_activity / asgn_sale, 1) if asgn_sale else None

            op_revenue = float(op_rev_map.get(user.id) or 0)
            dead_rate = round(asgn_dead / asgn_total * 100, 1) if asgn_total else 0

            operators.append({
                'id': user.id,
                'name': user.get_full_name() or user.username,
                'username': user.username,
                # activity
                'calls': op_calls,
                'missed': op_missed,
                'miss_rate': op_rate,
                'callbacks': op_callbacks,
                'audio': cs['audio'] or 0,
                'total_activity': total_activity,
                # portfolio
                'assigned': asgn_total,
                'active': asgn_active,
                'dead': asgn_dead,
                'overdue': asgn.filter(stage__in=active_stages, control_date__lt=today).count(),
                'last_activity': last.created_at.isoformat() if last else None,
                # conversion
                'conv_trained': pct(asgn_trained),
                'conv_set': pct(asgn_set),
                'conv_sale': pct(asgn_sale),
                'sale_count': asgn_sale,
                'dead_rate': dead_rate,
                # sales depth
                'partners_1sale': partners_1sale,
                'partners_10sale': partners_10sale,
                # efficiency
                'never_contacted': never_contacted_op,
                'inactive': inactive_op,
                'contact_rate': contact_rate,
                'calls_per_sale': calls_per_sale,
                # revenue
                'revenue': op_revenue,
            })
        operators.sort(key=lambda x: x['conv_sale'], reverse=True)

        # ------------------------------------------------------------------ #
        # Call quality per operator (AI-scored calls)
        # ------------------------------------------------------------------ #
        from contacts.models import Contact as ContactModel
        from django.db.models import Avg as DjAvg2
        for op_dict in operators:
            q = ContactModel.objects.filter(
                created_by_id=op_dict['id'],
                quality_survey__isnull=False,
            ).aggregate(
                avg_survey=DjAvg2('quality_survey'),
                avg_explanation=DjAvg2('quality_explanation'),
                avg_overall=DjAvg2('quality_overall'),
                scored_calls=Count('id'),
                avg_duration=DjAvg2('call_duration'),
            )
            op_dict['avg_survey']     = round(q['avg_survey'], 1) if q['avg_survey'] else None
            op_dict['avg_explanation']= round(q['avg_explanation'], 1) if q['avg_explanation'] else None
            op_dict['avg_overall']    = round(q['avg_overall'], 1) if q['avg_overall'] else None
            op_dict['scored_calls']   = q['scored_calls'] or 0
            op_dict['avg_duration']   = round(q['avg_duration'], 1) if q['avg_duration'] else None

        # ------------------------------------------------------------------ #
        # WhatsApp adoption stats
        # ------------------------------------------------------------------ #
        active_partners_qs = all_partners.filter(stage__in=active_stages)
        wa_total = active_partners_qs.count()
        wa_added = active_partners_qs.filter(whatsapp_added=True).count()
        by_stage_wa = {}
        for stage in active_stages:
            stage_qs = active_partners_qs.filter(stage=stage)
            cnt  = stage_qs.count()
            added = stage_qs.filter(whatsapp_added=True).count()
            by_stage_wa[stage] = {
                'total': cnt,
                'added': added,
                'pct':   round(added / cnt * 100, 1) if cnt else 0,
            }
        whatsapp_stats = {
            'total_active': wa_total,
            'added':     wa_added,
            'not_added': wa_total - wa_added,
            'pct':       round(wa_added / wa_total * 100, 1) if wa_total else 0,
            'by_stage':  by_stage_wa,
        }

        # ------------------------------------------------------------------ #
        # Top 10 partners by paid_orders_sum
        # ------------------------------------------------------------------ #
        top_10 = list(
            all_partners.filter(paid_orders_sum__gt=0)
            .select_related('assigned_to')
            .order_by('-paid_orders_sum')[:10]
            .values('id', 'name', 'stage', 'paid_orders_sum', 'paid_orders_count',
                    'medical_sets_count', 'assigned_to__first_name', 'assigned_to__last_name',
                    'assigned_to__username')
        )
        for p in top_10:
            fn = p.pop('assigned_to__first_name') or ''
            ln = p.pop('assigned_to__last_name') or ''
            un = p.pop('assigned_to__username') or ''
            p['operator'] = f'{fn} {ln}'.strip() or un
            p['paid_orders_sum'] = float(p['paid_orders_sum'])

        # ------------------------------------------------------------------ #
        # TASK ANALYTICS
        # ------------------------------------------------------------------ #
        from tasks.models import Task as TaskModel
        from django.db.models import ExpressionWrapper as EW, DurationField as DF, F as Fld, Avg as DjAvg

        task_all = TaskModel.objects.all()

        def period_qs_field(qs, field):
            """Filter by period using a specific date field."""
            if since:
                qs = qs.filter(**{f'{field}__gte': since})
            if until:
                qs = qs.filter(**{f'{field}__lt': until})
            return qs

        task_total = task_all.count()
        task_done  = task_all.filter(status='done').count()

        task_overview = {
            'total':             task_total,
            'open':              task_all.filter(status='open').count(),
            'in_progress':       task_all.filter(status='in_progress').count(),
            'done':              task_done,
            'cancelled':         task_all.filter(status='cancelled').count(),
            'overdue':           task_all.filter(status__in=['open', 'in_progress'], due_date__lt=today).count(),
            'no_due_date':       task_all.filter(status__in=['open', 'in_progress'], due_date__isnull=True).count(),
            'created_in_period': period_qs_field(task_all, 'created_at').count(),
            'completed_in_period': period_qs_field(task_all.filter(completed_at__isnull=False), 'completed_at').count(),
            'completion_rate':   round(task_done / task_total * 100, 1) if task_total else 0,
        }

        # Avg completion time in hours
        done_qs = task_all.filter(status='done', completed_at__isnull=False)
        avg_dur = done_qs.aggregate(avg=DjAvg(EW(Fld('completed_at') - Fld('created_at'), output_field=DF())))['avg']
        avg_completion_hours = round(avg_dur.total_seconds() / 3600, 1) if avg_dur else None

        task_by_priority = []
        for p_key, p_lbl in [('high', 'High'), ('medium', 'Medium'), ('low', 'Low')]:
            pqs = task_all.filter(priority=p_key)
            cnt = pqs.count()
            done_p = pqs.filter(status='done').count()
            task_by_priority.append({
                'key': p_key, 'label': p_lbl, 'count': cnt, 'done': done_p,
                'overdue': pqs.filter(status__in=['open', 'in_progress'], due_date__lt=today).count(),
                'completion_rate': round(done_p / cnt * 100, 1) if cnt else 0,
            })

        task_by_operator = []
        for op in operators:
            opqs = task_all.filter(assigned_to_id=op['id'])
            cnt = opqs.count()
            done_o = opqs.filter(status='done').count()
            task_by_operator.append({
                'id': op['id'], 'name': op['name'], 'username': op['username'],
                'total': cnt,
                'open':        opqs.filter(status='open').count(),
                'in_progress': opqs.filter(status='in_progress').count(),
                'done':        done_o,
                'overdue':     opqs.filter(status__in=['open', 'in_progress'], due_date__lt=today).count(),
                'completion_rate': round(done_o / cnt * 100, 1) if cnt else 0,
            })
        task_by_operator.sort(key=lambda x: x['total'], reverse=True)

        return Response({
            'period': period,
            'overview': overview,
            'funnel': funnel,
            'conversion': conversion,
            'pipeline_velocity': pipeline_velocity,
            'financials': financials,
            'sales_depth_ts': sales_depth_ts,
            'by_category': by_category,
            'by_type': by_type,
            'by_gender': by_gender,
            'by_state': state_rows,
            'by_referral': referral_rows,
            'time_series': time_series,
            'operator_daily_trends': operator_daily_trends,
            'partner_contact_coverage': partner_contact_coverage,
            'operators': operators,
            'task_overview':        task_overview,
            'task_by_priority':     task_by_priority,
            'task_by_operator':     task_by_operator,
            'avg_completion_hours': avg_completion_hours,
            'whatsapp_stats':       whatsapp_stats,
            'top_partners':         top_10,
        })


class AnalyticsAIChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from openai import OpenAI
        import json
        question     = request.data.get('question', '').strip()
        context_data = request.data.get('context', {})
        section      = request.data.get('section', 'partners')

        if not question:
            return Response({'error': 'Question required'}, status=400)

        if section == 'producers':
            system = (
                "You are an expert business analyst for an Ayurveda product CRM. "
                "You analyze producer onboarding and support pipeline data. "
                "Give concise, actionable insights based on the data. Use specific numbers. "
                "Answer in the same language the question is asked (Russian or English)."
            )
        else:
            system = (
                "You are an expert business analyst for an Ayurveda product CRM. "
                "You analyze partner sales performance, operator efficiency, and revenue metrics. "
                "Give concise, actionable insights. Use specific numbers from the data. "
                "Answer in the same language the question is asked (Russian or English)."
            )

        user_msg = f"Analytics data:\n{json.dumps(context_data, ensure_ascii=False, indent=2)}\n\nQuestion: {question}"

        try:
            ai   = OpenAI()
            resp = ai.chat.completions.create(
                model='gpt-4o-mini',
                max_tokens=1500,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user_msg},
                ],
            )
            return Response({'answer': resp.choices[0].message.content})
        except Exception as e:
            return Response({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# Operator Utilization analytics
# ─────────────────────────────────────────────────────────────────────────────
class OperatorUtilizationView(APIView):
    """
    Per-operator utilization & quality dashboard.

    The point of this endpoint is NOT raw call counts ("hit 100 calls of 1
    minute and win") — it's the combination of *quantity*, *call duration*
    and *AI-graded quality*, surfaced via composite metrics so half-arsed
    work is immediately visible:

      • effective_effort_score = avg_call_min × (avg_quality_overall / 10) × 10
        — penalises both short calls and low quality calls.
      • quality_minutes = sum(call_min × quality_overall) — total "useful work"
      • talk_min_per_active_day, calls_per_active_day — Mon-Fri density
      • days_active counts only Mon–Fri days with at least one logged call

    Period semantics:
      ?period = today | week | month | quarter | all | custom
      For custom: also pass date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from contacts.models import Contact

        period = request.query_params.get('period', 'week')
        now = timezone.now()
        today = now.date()

        # ── Resolve [since, until) ─────────────────────────────────────────
        until = None
        if period == 'today':
            since = now.replace(hour=0, minute=0, second=0, microsecond=0)
            day_count = 1
        elif period == 'week':
            since = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_count = 7
        elif period == 'month':
            since = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_count = 30
        elif period == 'quarter':
            since = (now - timedelta(days=89)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_count = 90
        elif period == 'custom':
            df = request.query_params.get('date_from', '')
            dt = request.query_params.get('date_to', '')
            try:
                date_from = dt_cls.strptime(df, '%Y-%m-%d').date()
                date_to   = dt_cls.strptime(dt, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                date_from = today - timedelta(days=6)
                date_to   = today
            if date_to > today:    date_to   = today
            if date_from > date_to: date_from = date_to - timedelta(days=6)
            since = timezone.make_aware(dt_cls.combine(date_from, time_cls.min))
            until = timezone.make_aware(dt_cls.combine(date_to + timedelta(days=1), time_cls.min))
            day_count = (date_to - date_from).days + 1
        else:  # all
            since = (now - timedelta(days=365)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_count = 365

        # Previous comparable period of same length
        if period == 'all':
            prev_since = None
            prev_until = None
        else:
            window = until or now
            prev_until = since
            prev_since = since - (window - since)

        # ── Build per-operator metrics ─────────────────────────────────────
        operators = list(User.objects.filter(role=User.ROLE_OPERATOR, is_active=True))

        # Pre-fetch period contacts so we don't hit DB N times per operator
        period_qs = Contact.objects.filter(created_at__gte=since)
        if until:
            period_qs = period_qs.filter(created_at__lt=until)
        period_qs = period_qs.select_related('partner', 'created_by')

        prev_qs = None
        if prev_since is not None:
            prev_qs = Contact.objects.filter(
                created_at__gte=prev_since, created_at__lt=prev_until
            )

        # Index by operator
        from collections import defaultdict
        by_op = defaultdict(list)
        for c in period_qs:
            if c.created_by_id:
                by_op[c.created_by_id].append(c)

        prev_by_op = defaultdict(list)
        if prev_qs is not None:
            for c in prev_qs:
                if c.created_by_id:
                    prev_by_op[c.created_by_id].append(c)

        def _avg(seq):
            seq = [x for x in seq if x is not None]
            return round(sum(seq) / len(seq), 1) if seq else None

        def _summarise(contacts):
            real_calls = [c for c in contacts if not c.is_missed_call and not c.callback_later]
            missed     = [c for c in contacts if c.is_missed_call]
            callbacks  = [c for c in contacts if c.callback_later]
            durations  = [(c.call_duration or 0) / 60.0 for c in real_calls if c.call_duration]
            quality_calls = [c for c in real_calls
                             if c.quality_overall is not None
                             or c.quality_survey is not None
                             or c.quality_explanation is not None]
            avg_q_survey      = _avg([c.quality_survey      for c in quality_calls])
            avg_q_explanation = _avg([c.quality_explanation for c in quality_calls])
            avg_q_overall     = _avg([c.quality_overall     for c in quality_calls])
            avg_q_mean        = _avg([v for v in (avg_q_survey, avg_q_explanation, avg_q_overall) if v is not None])

            avg_call_min = round(sum(durations) / len(durations), 1) if durations else None
            talk_min     = round(sum(durations), 1) if durations else 0.0

            # Composite "Effective Effort": penalise both short calls and low quality.
            # Scale × 10 so a "5 min × 7/10 quality" call ≈ 35 (easier to read than 3.5).
            if avg_call_min and avg_q_overall:
                effective_effort = round(avg_call_min * (avg_q_overall / 10.0) * 10.0, 1)
            else:
                effective_effort = None

            quality_minutes = round(
                sum(((c.call_duration or 0) / 60.0) * (c.quality_overall or 0)
                    for c in quality_calls if c.call_duration), 1
            )

            # Mon–Fri active days (only days with at least one *real* call)
            workday_dates = {
                c.created_at.astimezone(timezone.get_current_timezone()).date()
                for c in real_calls
                if c.created_at.astimezone(timezone.get_current_timezone()).weekday() < 5
            }
            days_active = len(workday_dates)

            unique_partners = len({c.partner_id for c in contacts if c.partner_id})

            miss_rate_pct = round(100.0 * len(missed) / len(contacts), 1) if contacts else 0.0

            calls_per_day      = round(len(real_calls) / days_active, 1) if days_active else None
            talk_min_per_day   = round(talk_min      / days_active, 1) if days_active else None

            last_activity = max((c.created_at for c in contacts), default=None)

            return {
                'calls':            len(contacts),
                'real_calls':       len(real_calls),
                'missed_calls':     len(missed),
                'callbacks':        len(callbacks),
                'unique_partners':  unique_partners,
                'talk_min':         talk_min,
                'avg_call_min':     avg_call_min,
                'quality_calls':    len(quality_calls),
                'avg_q_survey':      avg_q_survey,
                'avg_q_explanation': avg_q_explanation,
                'avg_q_overall':     avg_q_overall,
                'avg_q_mean':        avg_q_mean,
                'effective_effort_score': effective_effort,
                'quality_minutes':   quality_minutes,
                'miss_rate_pct':     miss_rate_pct,
                'days_active':       days_active,
                'calls_per_active_day': calls_per_day,
                'talk_min_per_active_day': talk_min_per_day,
                'last_activity':     last_activity.isoformat() if last_activity else None,
            }

        # Build daily trend series within current period
        # Build a sorted list of date keys for the period
        if period == 'today':
            buckets = [now.replace(hour=h, minute=0, second=0, microsecond=0) for h in range(24)]
            bucket_labels = [f'{h:02d}:00' for h in range(24)]
            def _bucket_of(c):
                return c.created_at.astimezone(timezone.get_current_timezone()).hour
            num_buckets = 24
        else:
            start_date = since.date()
            end_date   = (until.date() - timedelta(days=1)) if until else today
            num_buckets = (end_date - start_date).days + 1
            bucket_labels = [(start_date + timedelta(days=i)).strftime('%b %d')
                             for i in range(num_buckets)]
            def _bucket_of(c):
                return (c.created_at.astimezone(timezone.get_current_timezone()).date()
                        - start_date).days

        operators_payload = []
        for op in operators:
            cur = _summarise(by_op.get(op.id, []))
            prev = _summarise(prev_by_op.get(op.id, [])) if prev_qs is not None else None

            # Build trend arrays (calls / talk min / avg quality per bucket)
            trend_calls   = [0] * num_buckets
            trend_minutes = [0.0] * num_buckets
            quality_buckets = [[] for _ in range(num_buckets)]
            for c in by_op.get(op.id, []):
                idx = _bucket_of(c)
                if 0 <= idx < num_buckets:
                    if not c.is_missed_call and not c.callback_later:
                        trend_calls[idx] += 1
                        if c.call_duration:
                            trend_minutes[idx] += (c.call_duration or 0) / 60.0
                        if c.quality_overall is not None:
                            quality_buckets[idx].append(c.quality_overall)
            trend_quality = [
                round(sum(b) / len(b), 1) if b else None for b in quality_buckets
            ]
            trend_minutes = [round(m, 1) for m in trend_minutes]

            operators_payload.append({
                'id':       op.id,
                'username': op.username,
                'name':     (op.get_full_name() or op.username),
                'role':     op.role,
                **cur,
                'prev': {
                    'calls':                  prev['calls'],
                    'avg_call_min':           prev['avg_call_min'],
                    'avg_q_overall':          prev['avg_q_overall'],
                    'effective_effort_score': prev['effective_effort_score'],
                    'talk_min':               prev['talk_min'],
                } if prev else None,
                'trend': {
                    'labels':  bucket_labels,
                    'calls':   trend_calls,
                    'minutes': trend_minutes,
                    'quality': trend_quality,
                },
            })

        # ── Team aggregates ────────────────────────────────────────────────
        all_period_contacts = list(period_qs)
        team = _summarise(all_period_contacts)
        team['operators_active'] = sum(1 for o in operators_payload if o['real_calls'] > 0)
        team['operators_total']  = len(operators)

        # Period labels for the UI
        period_labels = {
            'today':   'Today',
            'week':    'Last 7 days',
            'month':   'Last 30 days',
            'quarter': 'Last 90 days',
            'custom':  f"{since.date()} → {(until.date() - timedelta(days=1)) if until else today}",
            'all':     'Last 12 months',
        }

        return Response({
            'period':        period,
            'period_label':  period_labels.get(period, period),
            'since':         since.isoformat(),
            'until':         until.isoformat() if until else None,
            'day_count':     day_count,
            'team':          team,
            'operators':     operators_payload,
        })
