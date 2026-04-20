from rest_framework import serializers
from accounts.serializers import UserSerializer
from .models import Contact


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
