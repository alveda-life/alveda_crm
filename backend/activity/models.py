from django.conf import settings
from django.db import models


class UserActivityEvent(models.Model):
    """Append-only log of user actions in the CRM.

    Populated by the frontend tracker (router navigations, explicit `track()`
    calls in pages/stores, and periodic heartbeat pings while the tab is
    visible). Used to render the operator activity timeline / heatmap.
    """

    EVENT_PAGE_VIEW      = 'page_view'
    EVENT_PARTNER_OPEN   = 'partner_open'
    EVENT_PARTNER_CLOSE  = 'partner_close'
    EVENT_CONTACT_CREATE = 'contact_create'
    EVENT_TASK_CREATE    = 'task_create'
    EVENT_TASK_COMPLETE  = 'task_complete'
    EVENT_NOTE_CREATE    = 'note_create'
    EVENT_STATUS_CHANGE  = 'status_change'
    EVENT_CALL_LOG       = 'call_log'
    EVENT_HEARTBEAT      = 'heartbeat'
    EVENT_LOGIN          = 'login'
    EVENT_LOGOUT         = 'logout'
    EVENT_OTHER          = 'other'

    EVENT_CHOICES = [
        (EVENT_PAGE_VIEW,      'Page view'),
        (EVENT_PARTNER_OPEN,   'Partner card opened'),
        (EVENT_PARTNER_CLOSE,  'Partner card closed'),
        (EVENT_CONTACT_CREATE, 'Contact created'),
        (EVENT_TASK_CREATE,    'Task created'),
        (EVENT_TASK_COMPLETE,  'Task completed'),
        (EVENT_NOTE_CREATE,    'Note created'),
        (EVENT_STATUS_CHANGE,  'Status changed'),
        (EVENT_CALL_LOG,       'Call logged'),
        (EVENT_HEARTBEAT,      'Heartbeat'),
        (EVENT_LOGIN,          'Login'),
        (EVENT_LOGOUT,         'Logout'),
        (EVENT_OTHER,          'Other'),
    ]

    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='activity_events',
    )
    event_type  = models.CharField(max_length=32, choices=EVENT_CHOICES, db_index=True)
    object_type = models.CharField(max_length=32, blank=True, default='')
    object_id   = models.BigIntegerField(null=True, blank=True)
    path        = models.CharField(max_length=500, blank=True, default='')
    metadata    = models.JSONField(default=dict, blank=True)
    session_key = models.UUIDField(null=True, blank=True, db_index=True)
    client_ts   = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)
    ip          = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['user', 'event_type', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user_id}:{self.event_type}@{self.created_at:%Y-%m-%d %H:%M:%S}'
