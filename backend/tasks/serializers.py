from rest_framework import serializers
from accounts.serializers import UserSerializer
from .models import Task, TaskComment


class TaskCommentSerializer(serializers.ModelSerializer):
    author_detail = UserSerializer(source='author', read_only=True)

    class Meta:
        model  = TaskComment
        fields = ['id', 'task', 'author', 'author_detail', 'text', 'created_at']
        read_only_fields = ['author', 'created_at']


class TaskSerializer(serializers.ModelSerializer):
    assigned_to_detail  = UserSerializer(source='assigned_to',  read_only=True)
    created_by_detail   = UserSerializer(source='created_by',   read_only=True)
    completed_by_detail = UserSerializer(source='completed_by', read_only=True)
    partner_name        = serializers.CharField(source='partner.name', read_only=True)
    priority_display    = serializers.CharField(source='get_priority_display', read_only=True)
    status_display      = serializers.CharField(source='get_status_display',   read_only=True)
    is_overdue          = serializers.ReadOnlyField()
    comments            = TaskCommentSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'partner', 'partner_name',
            'title', 'description',
            'assigned_to', 'assigned_to_detail',
            'created_by', 'created_by_detail',
            'due_date', 'priority', 'priority_display',
            'status', 'status_display', 'is_overdue',
            'completed_by', 'completed_by_detail', 'completed_at',
            'created_at', 'updated_at',
            'comments',
        ]
        read_only_fields = ['created_by', 'completed_by', 'completed_at', 'created_at', 'updated_at']
