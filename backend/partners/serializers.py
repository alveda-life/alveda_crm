from datetime import date, timedelta
from rest_framework import serializers
from accounts.serializers import UserSerializer
from .models import Partner


class PartnerListSerializer(serializers.ModelSerializer):
    assigned_to_detail = UserSerializer(source='assigned_to', read_only=True)
    contacts_count = serializers.ReadOnlyField()
    missed_calls_count = serializers.ReadOnlyField()
    last_contact_date = serializers.ReadOnlyField()
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    gender_display = serializers.CharField(source='get_gender_display', read_only=True)

    class Meta:
        model = Partner
        fields = [
            'id', 'name', 'phone', 'user_id', 'type', 'type_display',
            'category', 'category_display', 'gender', 'gender_display',
            'experience_years', 'state', 'city',
            'referred_by', 'stage', 'stage_display',
            'status', 'status_display', 'control_date',
            'medical_sets_count', 'orders_count', 'paid_orders_count',
            'paid_orders_sum', 'unpaid_orders_sum', 'referrals_count',
            'assigned_to', 'assigned_to_detail', 'notes',
            'whatsapp_added',
            'contacts_count', 'missed_calls_count', 'last_contact_date',
            'created_at', 'updated_at',
        ]


class PartnerWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = [
            'name', 'phone', 'user_id', 'type', 'category',
            'gender', 'experience_years', 'state', 'city',
            'referred_by', 'stage', 'status', 'control_date',
            'medical_sets_count', 'orders_count', 'paid_orders_count',
            'paid_orders_sum', 'unpaid_orders_sum', 'referrals_count',
            'assigned_to', 'notes', 'whatsapp_added',
        ]

    def validate_control_date(self, value):
        if value is None:
            raise serializers.ValidationError('Control date is required.')
        max_date = date.today() + timedelta(days=14)
        if value > max_date:
            raise serializers.ValidationError('Control date cannot be more than 14 days in the future.')
        return value
