# Generated manually for CallInsight model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contacts', '0012_alter_contact_date_alter_contact_summary_status_and_more'),
        ('partners', '0013_partner_user_id_unique'),
    ]

    operations = [
        migrations.CreateModel(
            name='CallInsight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('call_date', models.DateTimeField(db_index=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('done', 'Done'), ('failed', 'Failed')], db_index=True, default='pending', max_length=20)),
                ('insight_count', models.PositiveIntegerField(default=0)),
                ('density_bucket', models.CharField(blank=True, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], db_index=True, max_length=10)),
                ('insights_json', models.JSONField(blank=True, default=dict)),
                ('insights_markdown', models.TextField(blank=True)),
                ('transcript_fingerprint', models.CharField(blank=True, db_index=True, help_text='SHA256 of transcript text used for generation (re-transcribe detection)', max_length=64)),
                ('retries', models.PositiveSmallIntegerField(default=0)),
                ('last_error', models.TextField(blank=True)),
                ('last_attempt_at', models.DateTimeField(blank=True, null=True)),
                ('telegram_status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'), ('skipped', 'Skipped')], db_index=True, default='pending', max_length=16)),
                ('telegram_retries', models.PositiveSmallIntegerField(default=0)),
                ('telegram_last_error', models.TextField(blank=True)),
                ('telegram_last_attempt_at', models.DateTimeField(blank=True, null=True)),
                ('telegram_message_ids', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('contact', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='call_insight', to='contacts.contact')),
                ('created_by', models.ForeignKey(blank=True, help_text='Operator who logged the call', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='call_insights_created_for', to=settings.AUTH_USER_MODEL)),
                ('partner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='call_insights', to='partners.partner')),
            ],
            options={
                'ordering': ['-call_date', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='callinsight',
            index=models.Index(fields=['partner', '-call_date'], name='contacts_ca_partner_0f90_idx'),
        ),
        migrations.AddIndex(
            model_name='callinsight',
            index=models.Index(fields=['status', '-last_attempt_at'], name='contacts_ca_status_8b2a_idx'),
        ),
        migrations.AddIndex(
            model_name='callinsight',
            index=models.Index(fields=['telegram_status', '-telegram_last_attempt_at'], name='contacts_ca_telegra_3c1d_idx'),
        ),
    ]
