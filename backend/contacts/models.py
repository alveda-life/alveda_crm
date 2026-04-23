from django.db import models
from partners.models import Partner
from accounts.models import User


class Contact(models.Model):
    partner = models.ForeignKey(Partner, on_delete=models.CASCADE, related_name='contacts')
    date = models.DateTimeField(db_index=True)
    audio_file = models.FileField(upload_to='contacts/audio/%Y/%m/', null=True, blank=True)
    transcription = models.TextField(blank=True)
    transcript_file = models.FileField(upload_to='contacts/transcripts/%Y/%m/', null=True, blank=True)
    TRANSCRIPTION_PENDING = 'pending'
    TRANSCRIPTION_PROCESSING = 'processing'
    TRANSCRIPTION_DONE = 'done'
    TRANSCRIPTION_FAILED = 'failed'
    TRANSCRIPTION_NONE = ''
    TRANSCRIPTION_STATUS_CHOICES = [
        (TRANSCRIPTION_NONE, 'None'),
        (TRANSCRIPTION_PENDING, 'Pending'),
        (TRANSCRIPTION_PROCESSING, 'Processing'),
        (TRANSCRIPTION_DONE, 'Done'),
        (TRANSCRIPTION_FAILED, 'Failed'),
    ]
    transcription_status = models.CharField(
        max_length=20, choices=TRANSCRIPTION_STATUS_CHOICES, default='', blank=True, db_index=True
    )
    transcription_retries        = models.PositiveSmallIntegerField(default=0)
    transcription_last_error     = models.TextField(blank=True)
    transcription_last_attempt_at = models.DateTimeField(null=True, blank=True)
    summary = models.TextField(blank=True)
    summary_status = models.CharField(
        max_length=20, choices=TRANSCRIPTION_STATUS_CHOICES, default='', blank=True, db_index=True
    )
    summary_retries        = models.PositiveSmallIntegerField(default=0)
    summary_last_error     = models.TextField(blank=True)
    summary_last_attempt_at = models.DateTimeField(null=True, blank=True)
    # Diarized transcript — plain text with **Operator:** / **Partner:** labels
    diarized_transcript = models.TextField(blank=True)
    # Call duration in seconds (from Whisper verbose response)
    call_duration = models.PositiveIntegerField(null=True, blank=True)
    # AI quality scores (1–10), populated by Claude during summarization
    quality_survey      = models.PositiveSmallIntegerField(null=True, blank=True)
    quality_explanation = models.PositiveSmallIntegerField(null=True, blank=True)
    quality_overall     = models.PositiveSmallIntegerField(null=True, blank=True)
    # Short AI comments per dimension
    quality_survey_comment      = models.TextField(blank=True)
    quality_explanation_comment = models.TextField(blank=True)
    quality_overall_comment     = models.TextField(blank=True)
    # Detailed AI analysis per dimension (Markdown with quotes, examples, recommendations)
    quality_survey_detail       = models.TextField(blank=True)
    quality_explanation_detail  = models.TextField(blank=True)
    quality_overall_detail      = models.TextField(blank=True)
    # Operator coaching recommendations (Markdown)
    quality_recommendations     = models.TextField(blank=True)
    # Detailed AI feedback with specific quotes and recommendations (legacy/combined)
    quality_feedback            = models.TextField(blank=True)
    # Concise numbered list of mistakes the operator made (Markdown)
    quality_errors_found        = models.TextField(blank=True)
    # Actionable improvement plan for the operator (Markdown)
    quality_improvement_plan    = models.TextField(blank=True)
    notes = models.TextField(blank=True, help_text='Internal notes from the operator')
    is_missed_call = models.BooleanField(default=False, db_index=True, help_text='Operator did not reach the partner')
    callback_later = models.BooleanField(default=False, db_index=True, help_text='Need to call back later')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_contacts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Call with {self.partner.name} on {self.date.strftime('%Y-%m-%d')}"

    @property
    def audio_url(self):
        if self.audio_file:
            return self.audio_file.url
        return None

    @property
    def transcript_url(self):
        if self.transcript_file:
            return self.transcript_file.url
        return None


class CallInsight(models.Model):
    """
    Partner-facing market/product insights extracted from a single call transcript.
    One row per Contact (call). Telegram delivery is tracked separately from AI generation.
    """
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    DENSITY_LOW = 'low'
    DENSITY_MEDIUM = 'medium'
    DENSITY_HIGH = 'high'
    DENSITY_CHOICES = [
        (DENSITY_LOW, 'Low'),
        (DENSITY_MEDIUM, 'Medium'),
        (DENSITY_HIGH, 'High'),
    ]

    TELEGRAM_PENDING = 'pending'
    TELEGRAM_SENT = 'sent'
    TELEGRAM_FAILED = 'failed'
    TELEGRAM_SKIPPED = 'skipped'
    TELEGRAM_CHOICES = [
        (TELEGRAM_PENDING, 'Pending'),
        (TELEGRAM_SENT, 'Sent'),
        (TELEGRAM_FAILED, 'Failed'),
        (TELEGRAM_SKIPPED, 'Skipped'),
    ]

    contact = models.OneToOneField(
        Contact, on_delete=models.CASCADE, related_name='call_insight',
    )
    partner = models.ForeignKey(
        Partner, on_delete=models.CASCADE, related_name='call_insights',
    )
    call_date = models.DateTimeField(db_index=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='call_insights_created_for',
        help_text='Operator who logged the call',
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True,
    )
    insight_count = models.PositiveIntegerField(default=0)
    density_bucket = models.CharField(
        max_length=10, choices=DENSITY_CHOICES, blank=True, db_index=True,
    )
    insights_json = models.JSONField(default=dict, blank=True)
    insights_markdown = models.TextField(blank=True)
    transcript_fingerprint = models.CharField(
        max_length=64, blank=True, db_index=True,
        help_text='SHA256 of transcript text used for generation (re-transcribe detection)',
    )

    retries = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    telegram_status = models.CharField(
        max_length=16, choices=TELEGRAM_CHOICES, default=TELEGRAM_PENDING, db_index=True,
    )
    telegram_retries = models.PositiveSmallIntegerField(default=0)
    telegram_last_error = models.TextField(blank=True)
    telegram_last_attempt_at = models.DateTimeField(null=True, blank=True)
    telegram_message_ids = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-call_date', '-id']
        indexes = [
            models.Index(fields=['partner', '-call_date']),
            models.Index(fields=['status', '-last_attempt_at']),
            models.Index(fields=['telegram_status', '-telegram_last_attempt_at']),
        ]

    def __str__(self):
        return f'Insights for contact {self.contact_id}'


class InsightAggregate(models.Model):
    """
    Aggregated cross-call report over a date range.

    Built by clustering individual CallInsight items, ranking themes by
    number of unique partners that voiced them, and producing one consolidated
    summary that lets the team see "how many doctors said X" instead of reading
    each call in isolation.
    """
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    KIND_MANUAL = 'manual'
    KIND_ROLLING_30D = 'rolling_30d'
    KIND_ROLLING_60D = 'rolling_60d'
    KIND_ROLLING_180D = 'rolling_180d'
    KIND_ROLLING_ALL = 'rolling_all'
    KIND_CHOICES = [
        (KIND_MANUAL, 'Manual ad-hoc report'),
        (KIND_ROLLING_30D, 'Rolling 30 days'),
        (KIND_ROLLING_60D, 'Rolling 60 days'),
        (KIND_ROLLING_180D, 'Rolling 180 days'),
        (KIND_ROLLING_ALL, 'All time'),
    ]

    date_from = models.DateField(db_index=True)
    date_to = models.DateField(db_index=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='insight_aggregates_created',
    )

    kind = models.CharField(
        max_length=20, choices=KIND_CHOICES, default=KIND_MANUAL, db_index=True,
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True,
    )

    total_calls = models.PositiveIntegerField(default=0)
    total_insights = models.PositiveIntegerField(default=0)
    unique_partners = models.PositiveIntegerField(default=0)

    summary_text = models.TextField(blank=True, help_text='Executive summary in English')
    clusters_json = models.JSONField(default=dict, blank=True)
    rendered_markdown = models.TextField(blank=True)

    last_error = models.TextField(blank=True)
    retries = models.PositiveSmallIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['date_from', 'date_to']),
            models.Index(fields=['status', '-last_attempt_at']),
        ]

    def __str__(self):
        return f'Insight aggregate {self.date_from}..{self.date_to}'


class OperatorFeedback(models.Model):
    TYPE_DAILY = 'daily'
    TYPE_WEEKLY = 'weekly'
    TYPE_CHOICES = [(TYPE_DAILY, 'Daily'), (TYPE_WEEKLY, 'Weekly')]

    STATUS_GENERATING = 'generating'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_GENERATING, 'Generating'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    operator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')
    feedback_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    period_start = models.DateField()
    period_end = models.DateField()
    calls_analyzed = models.PositiveIntegerField(default=0)
    avg_score = models.FloatField(null=True, blank=True)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_GENERATING, db_index=True)
    generation_retries  = models.PositiveSmallIntegerField(default=0)
    last_error          = models.TextField(blank=True)
    last_attempt_at     = models.DateTimeField(null=True, blank=True)
    acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-period_end', '-period_start']
        unique_together = ['operator', 'feedback_type', 'period_start']

    def __str__(self):
        return f"{self.operator.full_name} — {self.feedback_type} ({self.period_start})"
