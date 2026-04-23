from rest_framework import serializers
from accounts.serializers import UserSerializer
from .models import Contact, CallInsight, InsightAggregate


class ContactSerializer(serializers.ModelSerializer):
    created_by_detail = UserSerializer(source='created_by', read_only=True)
    audio_url         = serializers.ReadOnlyField()
    transcript_url    = serializers.ReadOnlyField()
    partner_name      = serializers.CharField(source='partner.name', read_only=True)
    partner_type      = serializers.CharField(source='partner.get_type_display', read_only=True)
    partner_category  = serializers.CharField(source='partner.get_category_display', read_only=True)
    partner_paid_orders = serializers.IntegerField(source='partner.paid_orders_count', read_only=True)
    partner_sets      = serializers.IntegerField(source='partner.medical_sets_count', read_only=True)
    partner_stage     = serializers.CharField(source='partner.get_stage_display', read_only=True)
    call_number       = serializers.SerializerMethodField()

    def get_call_number(self, obj):
        # Prefer the precomputed annotation (added by ContactViewSet.get_queryset)
        # to avoid an extra COUNT(*) query per row in list responses.
        n = getattr(obj, 'call_number_annotated', None)
        if n is not None:
            return n
        return Contact.objects.filter(partner_id=obj.partner_id, date__lte=obj.date).count()

    class Meta:
        model = Contact
        fields = [
            'id', 'partner', 'partner_name',
            'partner_type', 'partner_category', 'partner_paid_orders',
            'partner_sets', 'partner_stage', 'call_number',
            'date',
            'audio_file', 'audio_url',
            'transcription', 'diarized_transcript',
            'transcript_file', 'transcript_url', 'transcription_status',
            'call_duration',
            'summary', 'summary_status',
            'quality_survey', 'quality_survey_comment', 'quality_survey_detail',
            'quality_explanation', 'quality_explanation_comment', 'quality_explanation_detail',
            'quality_overall', 'quality_overall_comment', 'quality_overall_detail',
            'quality_recommendations', 'quality_feedback', 'quality_errors_found', 'quality_improvement_plan',
            'notes', 'is_missed_call', 'callback_later',
            'created_by', 'created_by_detail',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'created_by', 'created_at', 'updated_at',
            'transcription_status', 'transcript_file',
            'transcription', 'diarized_transcript', 'call_duration',
            'summary', 'summary_status',
            'quality_survey', 'quality_survey_comment', 'quality_survey_detail',
            'quality_explanation', 'quality_explanation_comment', 'quality_explanation_detail',
            'quality_overall', 'quality_overall_comment', 'quality_overall_detail',
            'quality_recommendations', 'quality_feedback', 'quality_errors_found', 'quality_improvement_plan',
        ]

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class CallInsightListSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source='partner.name', read_only=True)
    created_by_detail = UserSerializer(source='created_by', read_only=True)
    preview = serializers.SerializerMethodField()

    class Meta:
        model = CallInsight
        fields = [
            'id', 'contact', 'partner', 'partner_name', 'call_date',
            'created_by', 'created_by_detail',
            'status', 'insight_count', 'density_bucket',
            'preview', 'telegram_status', 'telegram_last_error',
            'transcript_fingerprint',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_preview(self, obj):
        md = (obj.insights_markdown or '').strip()
        if not md:
            return ''
        line = md.replace('\n', ' ').strip()
        return line[:220] + ('…' if len(line) > 220 else '')


class CallInsightDetailSerializer(serializers.ModelSerializer):
    partner_name = serializers.CharField(source='partner.name', read_only=True)
    created_by_detail = UserSerializer(source='created_by', read_only=True)

    class Meta:
        model = CallInsight
        fields = [
            'id', 'contact', 'partner', 'partner_name', 'call_date',
            'created_by', 'created_by_detail',
            'status', 'insight_count', 'density_bucket',
            'insights_json', 'insights_markdown',
            'transcript_fingerprint',
            'retries', 'last_error', 'last_attempt_at',
            'telegram_status', 'telegram_retries', 'telegram_last_error',
            'telegram_last_attempt_at', 'telegram_message_ids',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class InsightAggregateListSerializer(serializers.ModelSerializer):
    created_by_detail = UserSerializer(source='created_by', read_only=True)

    class Meta:
        model = InsightAggregate
        fields = [
            'id', 'kind', 'date_from', 'date_to', 'status',
            'total_calls', 'total_insights', 'unique_partners',
            'summary_text', 'last_error',
            'created_by', 'created_by_detail',
            'created_at', 'updated_at', 'completed_at',
        ]
        read_only_fields = fields


class InsightAggregateDetailSerializer(serializers.ModelSerializer):
    created_by_detail = UserSerializer(source='created_by', read_only=True)

    class Meta:
        model = InsightAggregate
        fields = [
            'id', 'kind', 'date_from', 'date_to', 'status',
            'total_calls', 'total_insights', 'unique_partners',
            'summary_text', 'clusters_json', 'rendered_markdown',
            'last_error', 'retries', 'last_attempt_at', 'completed_at',
            'created_by', 'created_by_detail',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class InsightAggregateCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsightAggregate
        fields = ['date_from', 'date_to']

    def validate(self, attrs):
        if attrs['date_from'] > attrs['date_to']:
            raise serializers.ValidationError('date_from must be on or before date_to')
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        return super().create(validated_data)
