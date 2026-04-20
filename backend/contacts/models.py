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
