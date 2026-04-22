from rest_framework import serializers

from .models import UserActivityEvent


class UserActivityEventInSerializer(serializers.Serializer):
    """Payload sent by the frontend tracker (one element per event)."""

    event_type  = serializers.ChoiceField(
        choices=[c[0] for c in UserActivityEvent.EVENT_CHOICES],
    )
    object_type = serializers.CharField(max_length=32, required=False, allow_blank=True, default='')
    object_id   = serializers.IntegerField(required=False, allow_null=True)
    path        = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
    metadata    = serializers.JSONField(required=False, default=dict)
    session_key = serializers.UUIDField(required=False, allow_null=True)
    client_ts   = serializers.DateTimeField(required=False, allow_null=True)


class UserActivityEventOutSerializer(serializers.ModelSerializer):
    user_full_name = serializers.SerializerMethodField()
    username       = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = UserActivityEvent
        fields = (
            'id', 'user', 'username', 'user_full_name',
            'event_type', 'object_type', 'object_id',
            'path', 'metadata', 'session_key',
            'client_ts', 'created_at',
        )

    def get_user_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
