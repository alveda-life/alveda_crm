from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0009_operatorfeedback'),
    ]

    operations = [
        migrations.AddField(
            model_name='contact',
            name='quality_errors_found',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='contact',
            name='quality_improvement_plan',
            field=models.TextField(blank=True),
        ),
    ]
