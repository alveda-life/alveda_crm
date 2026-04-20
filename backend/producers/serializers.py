from rest_framework import serializers
from accounts.serializers import UserSerializer
from .models import Producer, ProducerTask, ProducerComment


class ProducerCommentSerializer(serializers.ModelSerializer):
    author_detail = UserSerializer(source='author', read_only=True)
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model  = ProducerComment
        fields = ['id', 'producer', 'author', 'author_detail', 'text',
                  'attachment', 'attachment_url', 'attachment_name', 'created_at']
        read_only_fields = ['producer', 'author', 'created_at', 'attachment_url']

    def get_attachment_url(self, obj):
        if obj.attachment:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.attachment.url)
            return obj.attachment.url
        return None


class ProducerTaskSerializer(serializers.ModelSerializer):
    assigned_to_detail  = UserSerializer(source='assigned_to',  read_only=True)
    created_by_detail   = UserSerializer(source='created_by',   read_only=True)
    completed_by_detail = UserSerializer(source='completed_by', read_only=True)
    priority_display    = serializers.CharField(source='get_priority_display', read_only=True)
    status_display      = serializers.CharField(source='get_status_display',   read_only=True)
    is_overdue          = serializers.ReadOnlyField()

    class Meta:
        model = ProducerTask
        fields = [
            'id', 'producer',
            'title', 'description',
            'assigned_to', 'assigned_to_detail',
            'created_by', 'created_by_detail',
            'due_date', 'priority', 'priority_display',
            'status', 'status_display', 'is_overdue',
            'completed_by', 'completed_by_detail', 'completed_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['producer', 'created_by', 'completed_by', 'completed_at', 'created_at', 'updated_at']


class ProducerTaskGlobalSerializer(serializers.ModelSerializer):
    """Used by the global /producer-tasks/ endpoint where producer is writable."""
    assigned_to_detail  = UserSerializer(source='assigned_to',  read_only=True)
    created_by_detail   = UserSerializer(source='created_by',   read_only=True)
    completed_by_detail = UserSerializer(source='completed_by', read_only=True)
    priority_display    = serializers.CharField(source='get_priority_display', read_only=True)
    status_display      = serializers.CharField(source='get_status_display',   read_only=True)
    is_overdue          = serializers.ReadOnlyField()
    producer_name       = serializers.CharField(source='producer.name', read_only=True)

    class Meta:
        model = ProducerTask
        fields = [
            'id', 'producer', 'producer_name',
            'title', 'description',
            'assigned_to', 'assigned_to_detail',
            'created_by', 'created_by_detail',
            'due_date', 'priority', 'priority_display',
            'status', 'status_display', 'is_overdue',
            'completed_by', 'completed_by_detail', 'completed_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'completed_by', 'completed_at', 'created_at', 'updated_at']


class ProducerListSerializer(serializers.ModelSerializer):
    assigned_to_detail            = UserSerializer(source='assigned_to', read_only=True)
    created_by_detail             = UserSerializer(source='created_by',  read_only=True)
    stage_display                 = serializers.CharField(source='get_stage_display',                    read_only=True)
    funnel_display                = serializers.CharField(source='get_funnel_display',                   read_only=True)
    priority_display              = serializers.CharField(source='get_priority_display',                 read_only=True)
    cooperation_potential_display = serializers.CharField(source='get_cooperation_potential_display',    read_only=True)
    tasks_count                   = serializers.ReadOnlyField()
    open_tasks_count              = serializers.ReadOnlyField()
    comments_count                = serializers.ReadOnlyField()
    last_comment_at               = serializers.ReadOnlyField()

    class Meta:
        model  = Producer
        fields = [
            'id', 'name', 'company', 'phone', 'email', 'website',
            'city', 'country', 'product_type', 'notes',
            'funnel', 'funnel_display', 'stage', 'stage_display',
            'stage_changed_at',
            'priority', 'priority_display',
            'product_count', 'cooperation_potential', 'cooperation_potential_display',
            'certifications', 'communication_status', 'next_step', 'contact_info',
            'control_date', 'last_contact', 'planned_connection_date',
            'assigned_to', 'assigned_to_detail',
            'created_by', 'created_by_detail',
            'tasks_count', 'open_tasks_count', 'comments_count', 'last_comment_at',
            'created_at', 'updated_at',
        ]


class ProducerDetailSerializer(ProducerListSerializer):
    tasks    = ProducerTaskSerializer(many=True, read_only=True)
    comments = ProducerCommentSerializer(many=True, read_only=True)

    class Meta(ProducerListSerializer.Meta):
        fields = ProducerListSerializer.Meta.fields + ['tasks', 'comments']


class ProducerWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Producer
        fields = [
            'name', 'company', 'phone', 'email', 'website',
            'city', 'country', 'product_type', 'notes',
            'funnel', 'stage', 'assigned_to',
            'priority', 'product_count', 'cooperation_potential',
            'certifications', 'communication_status', 'next_step', 'contact_info',
            'control_date', 'last_contact', 'planned_connection_date',
        ]
