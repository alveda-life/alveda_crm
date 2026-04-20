from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0003_aireport_report_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProducerUpdateReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_type', models.CharField(choices=[('daily', 'Daily'), ('weekly', 'Weekly')], db_index=True, max_length=10)),
                ('period_start', models.DateTimeField()),
                ('period_end', models.DateTimeField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('generating', 'Generating'), ('done', 'Done'), ('error', 'Error')], default='pending', max_length=20)),
                ('title', models.CharField(default='Generating…', max_length=250)),
                ('content', models.TextField(blank=True)),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
