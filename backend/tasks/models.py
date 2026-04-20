from django.db import models
from django.utils import timezone
from accounts.models import User
from partners.models import Partner


class Task(models.Model):
    PRIORITY_LOW    = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH   = 'high'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW,    'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH,   'High'),
    ]

    STATUS_OPEN        = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_DONE        = 'done'
    STATUS_CANCELLED   = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_OPEN,        'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_DONE,        'Done'),
        (STATUS_CANCELLED,   'Cancelled'),
    ]

    partner     = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='tasks',
                                    null=True, blank=True)
    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='assigned_tasks')
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='created_tasks')
    due_date    = models.DateField(null=True, blank=True, db_index=True)
    priority    = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM, db_index=True)
    status      = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)

    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='completed_tasks')
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', '-priority', '-created_at']

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        if self.due_date and self.status not in (self.STATUS_DONE, self.STATUS_CANCELLED):
            return self.due_date < timezone.now().date()
        return False


class TaskComment(models.Model):
    task       = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='task_comments')
    text       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment by {self.author_id} on task {self.task_id}'
