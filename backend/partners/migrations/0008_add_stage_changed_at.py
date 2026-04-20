from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0007_alter_partner_stage'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='stage_changed_at',
            field=models.DateTimeField(blank=True, help_text='When the stage was last changed', null=True),
        ),
    ]
