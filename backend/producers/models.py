from django.db import models
from django.utils import timezone
from accounts.models import User


class Producer(models.Model):
    # ── Funnels ──────────────────────────────────────────────────────────────
    FUNNEL_ONBOARDING = 'onboarding'
    FUNNEL_SUPPORT    = 'support'
    FUNNEL_CHOICES = [
        (FUNNEL_ONBOARDING, 'Onboarding'),
        (FUNNEL_SUPPORT,    'Support'),
    ]

    # ── Onboarding stages ───────────────────────────────────────────────────
    STAGE_INTEREST           = 'interest'
    STAGE_IN_COMMUNICATION   = 'in_communication'
    STAGE_TERMS_NEGOTIATION  = 'terms_negotiation'
    STAGE_NEGOTIATION        = 'negotiation'
    STAGE_CONTRACT_SIGNED    = 'contract_signed'
    STAGE_ON_PLATFORM        = 'on_platform'
    STAGE_STOPPED            = 'stopped'

    ONBOARDING_STAGE_CHOICES = [
        (STAGE_INTEREST,          'Interest'),
        (STAGE_IN_COMMUNICATION,  'In Communication'),
        (STAGE_TERMS_NEGOTIATION, 'Negotiation'),
        (STAGE_NEGOTIATION,       'Signing Contract'),
        (STAGE_CONTRACT_SIGNED,   'Contract Signed'),
        (STAGE_ON_PLATFORM,       'On the Platform'),
        (STAGE_STOPPED,           'Stopped'),
    ]

    # ── Support stages ──────────────────────────────────────────────────────
    STAGE_AGREED   = 'agreed'
    STAGE_SIGNED   = 'signed'
    STAGE_PRODUCTS = 'products_received'
    STAGE_READY    = 'ready_to_sell'
    STAGE_IN_STORE = 'in_store'

    SUPPORT_STAGE_CHOICES = [
        (STAGE_AGREED,   'Agreed'),
        (STAGE_SIGNED,   'Signed'),
        (STAGE_PRODUCTS, 'Products Received'),
        (STAGE_READY,    'Ready to Sell'),
        (STAGE_IN_STORE, 'In Store'),
    ]

    ALL_STAGE_CHOICES = ONBOARDING_STAGE_CHOICES + SUPPORT_STAGE_CHOICES

    ONBOARDING_STAGES = [c[0] for c in ONBOARDING_STAGE_CHOICES]
    SUPPORT_STAGES    = [c[0] for c in SUPPORT_STAGE_CHOICES]

    # ── Priority ─────────────────────────────────────────────────────────────
    PRIORITY_HIGH   = 'high'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_LOW    = 'low'
    PRIORITY_CHOICES = [
        (PRIORITY_HIGH,   'High'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_LOW,    'Low'),
    ]

    # ── Cooperation potential ─────────────────────────────────────────────────
    COOP_STRONG      = 'strong'
    COOP_MEDIUM      = 'medium'
    COOP_WEAK        = 'weak'
    COOP_NO_RESPONSE = 'no_response'
    COOP_CHOICES = [
        (COOP_STRONG,      'Strong'),
        (COOP_MEDIUM,      'Medium'),
        (COOP_WEAK,        'Weak'),
        (COOP_NO_RESPONSE, 'No Response Yet'),
    ]

    # ── Basic info ───────────────────────────────────────────────────────────
    name           = models.CharField(max_length=255)
    asana_task_gid = models.CharField(max_length=64, blank=True, db_index=True,
        help_text='Asana task gid — used for syncing comments back from Asana')
    company        = models.CharField(max_length=255, blank=True)
    phone        = models.CharField(max_length=50, blank=True)
    email        = models.EmailField(blank=True)
    website      = models.CharField(max_length=255, blank=True)
    city         = models.CharField(max_length=100, blank=True)
    country      = models.CharField(max_length=100, blank=True)
    product_type = models.CharField(max_length=255, blank=True, help_text='Type / category of products')
    notes        = models.TextField(blank=True)

    # ── Extended Pharma fields ────────────────────────────────────────────────
    priority              = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM, db_index=True)
    product_count         = models.PositiveIntegerField(null=True, blank=True, help_text='Number of SKUs / catalog size')
    cooperation_potential = models.CharField(max_length=15, choices=COOP_CHOICES, default=COOP_MEDIUM, db_index=True)
    certifications        = models.TextField(blank=True, help_text='Comma-separated: GMP, ISO, FSSAI, etc.')
    communication_status  = models.TextField(blank=True, help_text='Comma-separated communication status tags')
    next_step             = models.CharField(max_length=100, blank=True)
    contact_info          = models.TextField(blank=True, help_text='Key contacts, emails, phones')
    control_date          = models.DateField(null=True, blank=True, db_index=True, help_text='Next follow-up date')
    last_contact          = models.DateField(null=True, blank=True, db_index=True, help_text='Date of last contact')
    planned_connection_date = models.DateField(null=True, blank=True, help_text='Planned onboarding / connection date')

    # ── Funnel state ─────────────────────────────────────────────────────────
    funnel          = models.CharField(max_length=20, choices=FUNNEL_CHOICES, default=FUNNEL_ONBOARDING, db_index=True)
    stage           = models.CharField(max_length=30, choices=ALL_STAGE_CHOICES, default=STAGE_INTEREST, db_index=True)
    stage_changed_at = models.DateTimeField(null=True, blank=True)

    # ── CRM ──────────────────────────────────────────────────────────────────
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_producers'
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_producers'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} [{self.get_stage_display()}]"

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old = Producer.objects.only('stage', 'funnel').get(pk=self.pk)
                if old.stage != self.stage:
                    self.stage_changed_at = timezone.now()
            except Producer.DoesNotExist:
                pass
        else:
            self.stage_changed_at = timezone.now()
        super().save(*args, **kwargs)


class ProducerTask(models.Model):
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

    producer    = models.ForeignKey(Producer, on_delete=models.CASCADE, related_name='tasks')
    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='assigned_producer_tasks')
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='created_producer_tasks')
    due_date    = models.DateField(null=True, blank=True, db_index=True)
    priority    = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM, db_index=True)
    status      = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='completed_producer_tasks')
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date', '-priority', '-created_at']

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.due_date and self.status not in (self.STATUS_DONE, self.STATUS_CANCELLED):
            return self.due_date < timezone.now().date()
        return False


class ProducerAbandonedJob(models.Model):
    STATUS_PENDING  = 'pending'
    STATUS_RUNNING  = 'running'
    STATUS_DONE     = 'done'
    STATUS_ERROR    = 'error'
    STATUS_CHOICES  = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_DONE,    'Done'),
        (STATUS_ERROR,   'Error'),
    ]

    created_by     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='abandoned_jobs')
    funnel_filter  = models.CharField(max_length=20, blank=True)
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    results        = models.JSONField(null=True, blank=True)
    total_analyzed = models.PositiveIntegerField(null=True, blank=True)
    error_message  = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    completed_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'AbandonedJob #{self.pk} [{self.status}]'


class ProducerComment(models.Model):
    producer    = models.ForeignKey(Producer, on_delete=models.CASCADE, related_name='comments')
    author      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='producer_comments')
    text        = models.TextField(blank=True)
    attachment  = models.FileField(upload_to='producers/attachments/%Y/%m/', null=True, blank=True)
    attachment_name = models.CharField(max_length=255, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    asana_story_id = models.CharField(max_length=64, blank=True, db_index=True,
        help_text='Asana story gid — set when comment was imported from Asana')

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment by {self.author_id} on {self.producer_id}'


class ProducerWeeklyReport(models.Model):
    """
    AI-generated weekly snapshot of the onboarding funnel.

    Period semantics:
      - period_from = period_to of the previous DONE report (chained, not aligned to a calendar week).
      - period_to   = the moment the build started.
      - First-ever run falls back to (period_to - 7 days) so we have something to summarise.

    Significance filter:
      - LLM is asked to drop trivial movements ("reminded", "called again",
        "asked for contact") and only surface meaningful onboarding-funnel
        changes (stage progression, terms, blockers, decisions, refusals).
    """
    STATUS_PENDING    = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE       = 'done'
    STATUS_FAILED     = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING,    'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE,       'Done'),
        (STATUS_FAILED,     'Failed'),
    ]

    TRIGGER_SCHEDULED = 'scheduled'
    TRIGGER_MANUAL    = 'manual'
    TRIGGER_CHOICES = [
        (TRIGGER_SCHEDULED, 'Scheduled (Fri 16:00 IST)'),
        (TRIGGER_MANUAL,    'Manual refresh'),
    ]

    period_from = models.DateTimeField(db_index=True)
    period_to   = models.DateTimeField(db_index=True)

    triggered_by = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default=TRIGGER_SCHEDULED)
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='producer_weekly_reports_created')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default=STATUS_PENDING, db_index=True)

    total_new_producers       = models.PositiveIntegerField(default=0)
    total_changed_producers   = models.PositiveIntegerField(default=0)
    total_comments_considered = models.PositiveIntegerField(default=0)

    summary_text       = models.TextField(blank=True, help_text='Executive summary in English.')
    new_producers_json = models.JSONField(default=list, blank=True,
                                          help_text='Array of new-producer cards.')
    changes_json       = models.JSONField(default=list, blank=True,
                                          help_text='Array of significant change cards (LLM-filtered).')
    rendered_markdown  = models.TextField(blank=True)

    last_error       = models.TextField(blank=True)
    retries          = models.PositiveSmallIntegerField(default=0)
    last_attempt_at  = models.DateTimeField(null=True, blank=True)
    completed_at     = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-period_to', '-created_at']
        indexes = [
            models.Index(fields=['-period_to']),
            models.Index(fields=['status', '-last_attempt_at']),
        ]

    def __str__(self):
        return f'ProducerWeeklyReport {self.period_from:%Y-%m-%d} → {self.period_to:%Y-%m-%d} [{self.status}]'
