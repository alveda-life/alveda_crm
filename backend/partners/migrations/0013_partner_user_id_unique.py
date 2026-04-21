from django.db import migrations, models


class Migration(migrations.Migration):
    """Prevent duplicate partner rows for the same external CRM user_id.

    The constraint is partial: only enforced when user_id is non-empty, so legacy
    rows that were created manually (without a CRM origin) are still allowed to
    share an empty string. Dedup of existing data should be done BEFORE running
    this migration on prod (e.g. `manage.py import_crm_contacts --clear` or
    `manage.py dedupe_partners`).
    """

    dependencies = [
        ('partners', '0012_alter_partner_category_alter_partner_status_and_more'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='partner',
            constraint=models.UniqueConstraint(
                fields=['user_id'],
                condition=~models.Q(user_id=''),
                name='partners_partner_user_id_unique_when_set',
            ),
        ),
    ]
