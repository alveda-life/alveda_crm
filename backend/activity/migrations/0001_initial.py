from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserActivityEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(
                    choices=[
                        ('page_view',      'Page view'),
                        ('partner_open',   'Partner card opened'),
                        ('partner_close',  'Partner card closed'),
                        ('contact_create', 'Contact created'),
                        ('task_create',    'Task created'),
                        ('task_complete',  'Task completed'),
                        ('note_create',    'Note created'),
                        ('status_change',  'Status changed'),
                        ('call_log',       'Call logged'),
                        ('heartbeat',      'Heartbeat'),
                        ('login',          'Login'),
                        ('logout',         'Logout'),
                        ('other',          'Other'),
                    ],
                    db_index=True, max_length=32,
                )),
                ('object_type', models.CharField(blank=True, default='', max_length=32)),
                ('object_id',   models.BigIntegerField(blank=True, null=True)),
                ('path',        models.CharField(blank=True, default='', max_length=500)),
                ('metadata',    models.JSONField(blank=True, default=dict)),
                ('session_key', models.UUIDField(blank=True, db_index=True, null=True)),
                ('client_ts',   models.DateTimeField(blank=True, null=True)),
                ('created_at',  models.DateTimeField(auto_now_add=True, db_index=True)),
                ('ip',          models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent',  models.CharField(blank=True, default='', max_length=500)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='activity_events',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='useractivityevent',
            index=models.Index(fields=['user', 'created_at'], name='activity_us_user_id_ca_idx'),
        ),
        migrations.AddIndex(
            model_name='useractivityevent',
            index=models.Index(fields=['user', 'event_type', 'created_at'], name='activity_us_user_ev_ca_idx'),
        ),
    ]
