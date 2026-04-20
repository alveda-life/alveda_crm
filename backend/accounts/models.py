from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_ADMIN                = 'admin'
    ROLE_OPERATOR             = 'operator'
    ROLE_PRODUCER_OPERATOR    = 'producer_operator'   # both producer funnels
    ROLE_PRODUCER_ONBOARDING  = 'producer_onboarding' # onboarding funnel only
    ROLE_PRODUCER_SUPPORT     = 'producer_support'    # support funnel only
    ROLE_CHOICES = [
        (ROLE_ADMIN,               'Admin'),
        (ROLE_OPERATOR,            'Operator'),
        (ROLE_PRODUCER_OPERATOR,   'Producer Manager'),
        (ROLE_PRODUCER_ONBOARDING, 'Producer Onboarding'),
        (ROLE_PRODUCER_SUPPORT,    'Producer Support'),
    ]

    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default=ROLE_OPERATOR, db_index=True)

    def is_admin_role(self):
        return self.role == self.ROLE_ADMIN

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"


class RolePermission(models.Model):
    """Configurable per-role permissions. One row per role, stored as JSON."""
    role        = models.CharField(max_length=30, unique=True)
    permissions = models.JSONField(default=dict)

    class Meta:
        ordering = ['role']

    def __str__(self):
        return f"RolePermission({self.role})"

    @classmethod
    def get_for_role(cls, role: str) -> dict:
        from .permissions_config import get_role_defaults
        try:
            return cls.objects.get(role=role).permissions
        except cls.DoesNotExist:
            return get_role_defaults(role)

    @classmethod
    def has_perm(cls, user, section: str, action: str) -> bool:
        if user.is_staff or getattr(user, 'role', '') == 'admin':
            return True
        perms = cls.get_for_role(user.role)
        return perms.get(section, {}).get(action, False)


class CRMSettings(models.Model):
    """Singleton — admin-editable settings used by AI evaluation."""
    product_info = models.TextField(
        blank=True,
        help_text='Product description and goals used by AI to evaluate operator calls',
    )
    evaluation_prompt = models.TextField(
        blank=True,
        help_text=(
            'Single set of evaluation criteria the AI uses to score every call '
            '(survey, explanation and overall dimensions). Leave blank for defaults.'
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'CRM Settings'

    def __str__(self):
        return 'CRM Settings'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
