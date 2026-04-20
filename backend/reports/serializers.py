from rest_framework import serializers
from .models import AiReport, ProducerUpdateReport, BrandSituationReport

class AiReportSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = AiReport
        fields = ['id', 'title', 'prompt', 'content', 'status', 'error_message', 'report_type', 'created_by_name', 'created_at']
        read_only_fields = ['created_by_name', 'created_at', 'status', 'error_message']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class ProducerUpdateReportSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ProducerUpdateReport
        fields = ['id', 'report_type', 'period_start', 'period_end',
                  'status', 'title', 'content', 'error_message', 'created_at']
        read_only_fields = fields


class BrandSituationReportSerializer(serializers.ModelSerializer):
    class Meta:
        model  = BrandSituationReport
        fields = ['id', 'week_start', 'week_end', 'status', 'error_message',
                  'brand_data', 'created_at']
        read_only_fields = fields
