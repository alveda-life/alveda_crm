from django.contrib import admin

from .models import UserActivityEvent


@admin.register(UserActivityEvent)
class UserActivityEventAdmin(admin.ModelAdmin):
    list_display  = ('id', 'user', 'event_type', 'object_type', 'object_id', 'path', 'created_at')
    list_filter   = ('event_type', 'object_type')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'path')
    date_hierarchy = 'created_at'
    readonly_fields = (
        'user', 'event_type', 'object_type', 'object_id', 'path', 'metadata',
        'session_key', 'client_ts', 'created_at', 'ip', 'user_agent',
    )
