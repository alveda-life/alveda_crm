from django.db import models
from accounts.models import User


class ProducerUpdateReport(models.Model):
    TYPE_DAILY  = 'daily'
    TYPE_WEEKLY = 'weekly'
    TYPE_CHOICES = [(TYPE_DAILY, 'Daily'), (TYPE_WEEKLY, 'Weekly')]

    STATUS_PENDING    = 'pending'
    STATUS_GENERATING = 'generating'
    STATUS_DONE       = 'done'
    STATUS_ERROR      = 'error'
    STATUS_CHOICES = [
        (STATUS_PENDING,    'Pending'),
        (STATUS_GENERATING, 'Generating'),
        (STATUS_DONE,       'Done'),
        (STATUS_ERROR,      'Error'),
    ]

    report_type   = models.CharField(max_length=10, choices=TYPE_CHOICES, db_index=True)
    period_start  = models.DateTimeField()
    period_end    = models.DateTimeField()
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    title         = models.CharField(max_length=250, default='Generating…')
    content       = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.report_type} — {self.created_at.date()}'


class AiReport(models.Model):
    STATUS_PENDING    = 'pending'
    STATUS_GENERATING = 'generating'
    STATUS_DONE       = 'done'
    STATUS_ERROR      = 'error'
    STATUS_CHOICES = [
        (STATUS_PENDING,    'Pending'),
        (STATUS_GENERATING, 'Generating'),
        (STATUS_DONE,       'Done'),
        (STATUS_ERROR,      'Error'),
    ]

    TYPE_PARTNERS  = 'partners'
    TYPE_PRODUCERS = 'producers'
    TYPE_CHOICES = [
        (TYPE_PARTNERS,  'Partners'),
        (TYPE_PRODUCERS, 'Producers'),
    ]

    title       = models.CharField(max_length=250, default='Generating report…')
    prompt      = models.TextField()
    content     = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    report_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_PARTNERS, db_index=True)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ai_reports')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class BrandSituationReport(models.Model):
    """
    Weekly snapshot of all active brands (In Communication / Negotiation / Contract Signed).
    Generated every Friday 15:00 IST.
    Per brand stores AI analysis: was there a real fundamental change this week vs prior weeks?
    Frontend renders this as a per-brand timeline (dot per week, green = real change, grey = no change).
    """
    STATUS_PENDING    = 'pending'
    STATUS_GENERATING = 'generating'
    STATUS_DONE       = 'done'
    STATUS_ERROR      = 'error'
    STATUS_CHOICES = [
        (STATUS_PENDING,    'Pending'),
        (STATUS_GENERATING, 'Generating'),
        (STATUS_DONE,       'Done'),
        (STATUS_ERROR,      'Error'),
    ]

    week_start    = models.DateField(db_index=True, help_text='Monday of the week (IST)')
    week_end      = models.DateField(help_text='Sunday of the week (IST)')
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    error_message = models.TextField(blank=True)
    # JSON: { producer_id: { name, stage, has_real_change: bool, change_summary: str, current_status: str } }
    brand_data    = models.JSONField(default=dict, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-week_start']
        unique_together = ('week_start',)

    def __str__(self):
        return f'BrandSituation week {self.week_start}'


class AiJobRun(models.Model):
    """
    Audit log for every AI / auto-generation job execution
    (scheduled or manually triggered). Powers the AI Operations admin panel.
    """
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_ERROR   = 'error'
    STATUS_CHOICES = [
        (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_ERROR,   'Error'),
    ]

    TRIGGER_SCHEDULE = 'schedule'
    TRIGGER_STARTUP  = 'startup'
    TRIGGER_MANUAL   = 'manual'
    TRIGGER_CHOICES = [
        (TRIGGER_SCHEDULE, 'Schedule'),
        (TRIGGER_STARTUP,  'Startup'),
        (TRIGGER_MANUAL,   'Manual'),
    ]

    job_id        = models.CharField(max_length=64, db_index=True,
                                     help_text='Identifier from JOB_REGISTRY')
    trigger       = models.CharField(max_length=16, choices=TRIGGER_CHOICES,
                                     default=TRIGGER_SCHEDULE)
    status        = models.CharField(max_length=16, choices=STATUS_CHOICES,
                                     default=STATUS_RUNNING, db_index=True)
    started_at    = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at   = models.DateTimeField(null=True, blank=True)
    duration_ms   = models.PositiveIntegerField(default=0)
    summary       = models.CharField(max_length=500, blank=True,
                                     help_text='Short result message')
    error_message = models.TextField(blank=True)
    triggered_by  = models.ForeignKey(User, on_delete=models.SET_NULL,
                                      null=True, blank=True,
                                      related_name='ai_job_runs')

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['job_id', '-started_at']),
        ]

    def __str__(self):
        return f'{self.job_id} @ {self.started_at:%Y-%m-%d %H:%M} → {self.status}'
