from datetime import date
from django.db import models
from django.utils import timezone
from accounts.models import User


class Partner(models.Model):
    # Funnel stages
    STAGE_NEW = 'new'
    STAGE_TRAINED = 'trained'
    STAGE_SET_CREATED = 'set_created'
    STAGE_HAS_SALE = 'has_sale'
    STAGE_NO_ANSWER = 'no_answer'
    STAGE_DECLINED = 'declined'
    STAGE_NO_SALES = 'no_sales'
    STAGE_CHOICES = [
        (STAGE_NEW, 'New'),
        (STAGE_TRAINED, 'Agreed to Create First Set'),
        (STAGE_SET_CREATED, 'Medical Set Created'),
        (STAGE_HAS_SALE, 'Has Sale'),
        (STAGE_NO_ANSWER, 'Dead (No Answer)'),
        (STAGE_DECLINED, 'Dead (Declined)'),
        (STAGE_NO_SALES, 'Dead (No Sales)'),
    ]

    TYPE_PARTNER = 'partner'
    TYPE_MEDIC = 'medic'
    TYPE_CHOICES = [
        (TYPE_PARTNER, 'Partner'),
        (TYPE_MEDIC, 'Medic'),
    ]

    CAT_DOCTOR = 'doctor'
    CAT_TRAINER = 'fitness_trainer'
    CAT_BLOGGER = 'blogger'
    CAT_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CAT_DOCTOR, 'Doctor'),
        (CAT_TRAINER, 'Fitness Trainer'),
        (CAT_BLOGGER, 'Blogger'),
        (CAT_OTHER, 'Other'),
    ]

    GENDER_MALE = 'male'
    GENDER_FEMALE = 'female'
    GENDER_CHOICES = [
        (GENDER_MALE, 'Male'),
        (GENDER_FEMALE, 'Female'),
    ]

    # Identity
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True)
    user_id = models.CharField(max_length=100, blank=True, help_text='ID from the platform')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_PARTNER, db_index=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CAT_OTHER, db_index=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, default='')
    experience_years = models.PositiveSmallIntegerField(null=True, blank=True)
    state = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    referred_by = models.CharField(max_length=255, blank=True)

    # Card status
    STATUS_NEW = 'new'
    STATUS_IN_SUPPORT = 'in_support'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_IN_SUPPORT, 'In Support'),
        (STATUS_CLOSED, 'Closed'),
    ]

    # Funnel
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default=STAGE_NEW, db_index=True)

    # Card status & control date
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True)
    control_date = models.DateField(default=date.today, db_index=True)

    # Stats (synced from platform API)
    medical_sets_count = models.PositiveIntegerField(default=0)
    orders_count = models.PositiveIntegerField(default=0)
    paid_orders_count = models.PositiveIntegerField(default=0)
    paid_orders_sum = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    unpaid_orders_sum = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    referrals_count = models.PositiveIntegerField(default=0)

    # WhatsApp channel membership
    whatsapp_added = models.BooleanField(default=False, db_index=True,
        help_text='Partner has been added to our WhatsApp channel')

    # CRM
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_partners'
    )
    notes = models.TextField(blank=True)

    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    stage_changed_at = models.DateTimeField(null=True, blank=True, help_text='When the stage was last changed')

    class Meta:
        ordering = ['-created_at']

    DEAD_STAGES = {STAGE_NO_ANSWER, STAGE_DECLINED, STAGE_NO_SALES}

    def _auto_status(self):
        """Derive status from stage automatically."""
        if self.stage == self.STAGE_NEW:
            return self.STATUS_NEW
        if self.stage in self.DEAD_STAGES:
            return self.STATUS_CLOSED
        return self.STATUS_IN_SUPPORT

    def save(self, *args, **kwargs):
        # Track when stage changes + auto-derive status
        if self.pk:
            try:
                old = Partner.objects.only('stage', 'status').get(pk=self.pk)
                if old.stage != self.stage:
                    self.stage_changed_at = timezone.now()
                    self.status = self._auto_status()
            except Partner.DoesNotExist:
                pass
        else:
            if not self.stage_changed_at:
                self.stage_changed_at = timezone.now()
            self.status = self._auto_status()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} [{self.get_stage_display()}]"
