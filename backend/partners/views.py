from django.db.models import Count, Q, Max, OuterRef, Subquery
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from accounts.models import RolePermission
from contacts.models import Contact
from .models import Partner
from .serializers import PartnerListSerializer, PartnerWriteSerializer


OPERATOR_ALLOWED_FIELDS = {
    'assigned_to',
    'whatsapp_added',
    'gender', 'experience_years', 'city', 'state',
    'status', 'control_date', 'notes',
}
OPERATOR_PROFILE_FIELDS = {'gender', 'experience_years', 'city', 'state'}
OPERATOR_ACTIVITY_GATED_FIELDS = {'status', 'control_date', 'notes'}


def _is_operator(user):
    return getattr(user, 'role', '') == 'operator' and not user.is_staff


def _operator_validate_partner_patch(user, instance, data):
    """Return (allowed: bool, message: str|None) for an operator partial update."""
    submitted = set(data.keys())

    extra = submitted - OPERATOR_ALLOWED_FIELDS
    if extra:
        return False, f"Operators cannot edit fields: {', '.join(sorted(extra))}."

    if 'assigned_to' in submitted:
        try:
            assigned_id = int(data['assigned_to']) if data['assigned_to'] is not None else None
        except (TypeError, ValueError):
            return False, 'Invalid assigned_to value.'
        if assigned_id != user.id:
            return False, 'Operators can only assign cards to themselves.'

    profile_changes = submitted & OPERATOR_PROFILE_FIELDS
    for field in profile_changes:
        current = getattr(instance, field, None)
        if field == 'experience_years':
            is_empty = current is None
        else:
            is_empty = not current
        if not is_empty:
            return False, f'Profile field "{field}" is already filled and cannot be changed.'

    if submitted & OPERATOR_ACTIVITY_GATED_FIELDS:
        has_own_activity = Contact.objects.filter(
            partner=instance, created_by=user
        ).exists()
        if not has_own_activity:
            return False, 'Add an Activity record before changing status, follow-up date or notes.'

    return True, None


class PartnerViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['stage', 'type', 'category', 'assigned_to']
    search_fields = ['name', 'phone', 'user_id', 'referred_by']
    ordering_fields = [
        'name', 'created_at', 'updated_at',
        'stage', 'status', 'control_date',
        'medical_sets_count', 'paid_orders_count', 'paid_orders_sum',
        'contacts_count', 'missed_calls_count',
    ]
    ordering = ['-created_at']

    def destroy(self, request, *args, **kwargs):
        if not RolePermission.has_perm(request.user, 'partners', 'delete'):
            return Response({'detail': 'You do not have permission to delete.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            Partner.objects
            .select_related('assigned_to')
            .annotate(
                contacts_count=Count(
                    'contacts',
                    filter=Q(contacts__is_missed_call=False) & Q(contacts__callback_later=False)
                ),
                missed_calls_count=Count(
                    'contacts',
                    filter=Q(contacts__is_missed_call=True)
                ),
                last_contact_date=Max('contacts__date'),
            )
        )
        min_paid = self.request.query_params.get('min_paid_orders')
        if min_paid:
            qs = qs.filter(paid_orders_count__gte=min_paid)
        return qs

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PartnerWriteSerializer
        return PartnerListSerializer

    def _annotated(self, pk):
        """Re-fetch a single partner through the annotated queryset."""
        return self.get_queryset().get(pk=pk)

    def _serialize(self, instance, request, **kwargs):
        return PartnerListSerializer(instance, context={'request': request}, **kwargs).data

    def create(self, request, *args, **kwargs):
        if _is_operator(request.user):
            return Response(
                {'detail': 'Operators cannot create partners.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        partner = serializer.save()
        return Response(self._serialize(self._annotated(partner.pk), request), status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if _is_operator(request.user):
            ok, msg = _operator_validate_partner_patch(request.user, instance, request.data)
            if not ok:
                return Response({'detail': msg}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        partner = serializer.save()
        return Response(self._serialize(self._annotated(partner.pk), request))

    @action(detail=True, methods=['patch'], url_path='stage')
    def update_stage(self, request, pk=None):
        if _is_operator(request.user):
            return Response(
                {'detail': 'Operators cannot change the funnel stage.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        partner = self.get_object()
        stage = request.data.get('stage')
        if stage not in dict(Partner.STAGE_CHOICES):
            return Response({'error': 'Invalid stage'}, status=status.HTTP_400_BAD_REQUEST)
        partner.stage = stage
        partner.save(update_fields=['stage', 'status', 'updated_at', 'stage_changed_at'])
        return Response(self._serialize(self._annotated(partner.pk), request))

    DEAD_STAGES_SET = {Partner.STAGE_NO_ANSWER, Partner.STAGE_DECLINED, Partner.STAGE_NO_SALES}
    KANBAN_LIMIT_ACTIVE = 50
    KANBAN_LIMIT_DEAD = 10

    def _kanban_base_qs(self, request):
        qs = self.get_queryset()
        for field in ['type', 'category', 'assigned_to']:
            val = request.query_params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        search = request.query_params.get('search')
        if search:
            from django.db.models import Q
            qs = qs.filter(Q(name__icontains=search) | Q(phone__icontains=search))
        return qs

    @action(detail=False, methods=['get'], url_path='kanban')
    def kanban(self, request):
        qs = self._kanban_base_qs(request)

        from django.db.models import F
        result = {}
        for stage_key, _ in Partner.STAGE_CHOICES:
            stage_qs = qs.filter(stage=stage_key)
            if stage_key == Partner.STAGE_NEW:
                stage_qs = stage_qs.order_by('-created_at')
            else:
                stage_qs = stage_qs.order_by(F('control_date').asc(nulls_last=True))

            total = stage_qs.count()
            limit = self.KANBAN_LIMIT_DEAD if stage_key in self.DEAD_STAGES_SET else self.KANBAN_LIMIT_ACTIVE
            result[stage_key] = {
                'items': PartnerListSerializer(stage_qs[:limit], many=True, context={'request': request}).data,
                'total': total,
                'has_more': total > limit,
            }
        return Response(result)

    @action(detail=False, methods=['get'], url_path='kanban-more')
    def kanban_more(self, request):
        stage = request.query_params.get('stage', '')
        if stage not in dict(Partner.STAGE_CHOICES):
            return Response({'error': 'Invalid stage'}, status=status.HTTP_400_BAD_REQUEST)

        offset = int(request.query_params.get('offset', 0))
        limit = int(request.query_params.get('limit', 50))
        limit = min(limit, 200)

        qs = self._kanban_base_qs(request).filter(stage=stage)

        from django.db.models import F
        if stage == Partner.STAGE_NEW:
            qs = qs.order_by('-created_at')
        else:
            qs = qs.order_by(F('control_date').asc(nulls_last=True))

        total = qs.count()
        items = PartnerListSerializer(qs[offset:offset + limit], many=True, context={'request': request}).data
        return Response({
            'items': items,
            'total': total,
            'has_more': (offset + limit) < total,
        })

    @action(detail=False, methods=['get'], url_path='abandoned')
    def abandoned(self, request):
        from contacts.models import Contact

        DEAD_STAGES = ['no_answer', 'declined', 'no_sales']
        THRESHOLD_DAYS = 15
        threshold_dt = timezone.now() - timedelta(days=THRESHOLD_DAYS)

        # Subquery: last contact date per partner
        last_contact_sq = (
            Contact.objects
            .filter(partner=OuterRef('pk'))
            .order_by('-date')
            .values('date')[:1]
        )

        qs = (
            Partner.objects
            .select_related('assigned_to')
            .annotate(last_contact=Subquery(last_contact_sq))
            .filter(Q(last_contact__lt=threshold_dt) | Q(last_contact__isnull=True))
            .order_by('last_contact')  # nulls first (never contacted come first)
        )

        # Operators see only their own abandoned partners
        if not request.user.is_staff and request.user.role != 'admin':
            qs = qs.filter(assigned_to=request.user)
        else:
            # Admin: optional filter by assigned_to
            assigned_to = request.query_params.get('assigned_to')
            if assigned_to:
                qs = qs.filter(assigned_to=assigned_to)

        # Optional stage filter
        stage = request.query_params.get('stage')
        if stage:
            qs = qs.filter(stage=stage)

        now = timezone.now()
        results = []
        for p in qs:
            if p.last_contact is None:
                days_silent = None
            else:
                days_silent = (now - p.last_contact).days
            results.append({
                'id': p.id,
                'name': p.name,
                'phone': p.phone,
                'stage': p.stage,
                'stage_display': p.get_stage_display(),
                'assigned_to': {
                    'id': p.assigned_to.id,
                    'name': f'{p.assigned_to.first_name} {p.assigned_to.last_name}'.strip() or p.assigned_to.username,
                    'username': p.assigned_to.username,
                } if p.assigned_to else None,
                'last_contact': p.last_contact,
                'days_silent': days_silent,
                'created_at': p.created_at,
            })

        return Response({
            'count': len(results),
            'results': results,
        })

    @action(detail=False, methods=['get'], url_path='abandoned-count')
    def abandoned_count(self, request):
        from contacts.models import Contact

        DEAD_STAGES = ['no_answer', 'declined', 'no_sales']
        threshold_dt = timezone.now() - timedelta(days=15)

        last_contact_sq = (
            Contact.objects
            .filter(partner=OuterRef('pk'))
            .order_by('-date')
            .values('date')[:1]
        )

        qs = (
            Partner.objects
            .annotate(last_contact=Subquery(last_contact_sq))
            .filter(Q(last_contact__lt=threshold_dt) | Q(last_contact__isnull=True))
        )

        if not request.user.is_staff and request.user.role != 'admin':
            qs = qs.filter(assigned_to=request.user)

        return Response({'count': qs.count()})

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        qs = Partner.objects.all()
        from django.db.models import Count, Sum
        total = qs.count()
        by_stage = {
            k: qs.filter(stage=k).count()
            for k, _ in Partner.STAGE_CHOICES
        }
        revenue = qs.aggregate(total=Sum('paid_orders_sum'))['total'] or 0
        return Response({
            'total': total,
            'by_stage': by_stage,
            'total_revenue': revenue,
        })
