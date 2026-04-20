from django.db import migrations, models


def merge_prompts_forward(apps, schema_editor):
    CRMSettings = apps.get_model('accounts', 'CRMSettings')
    for s in CRMSettings.objects.all():
        parts = []
        for label, value in (
            ('Survey / Discovery',     (s.prompt_survey or '').strip()),
            ('Product Explanation',    (s.prompt_explanation or '').strip()),
            ('Overall Call Quality',   (s.prompt_overall or '').strip()),
        ):
            if value:
                parts.append(f'### {label}\n{value}')
        if parts and not (s.evaluation_prompt or '').strip():
            s.evaluation_prompt = '\n\n'.join(parts)
            s.save(update_fields=['evaluation_prompt'])


def merge_prompts_backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_add_crmsettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmsettings',
            name='evaluation_prompt',
            field=models.TextField(
                blank=True,
                help_text=(
                    'Single set of evaluation criteria the AI uses to score every '
                    'call (survey, explanation and overall dimensions). Leave blank '
                    'for defaults.'
                ),
            ),
        ),
        migrations.RunPython(merge_prompts_forward, merge_prompts_backward),
        migrations.RemoveField(model_name='crmsettings', name='prompt_survey'),
        migrations.RemoveField(model_name='crmsettings', name='prompt_explanation'),
        migrations.RemoveField(model_name='crmsettings', name='prompt_overall'),
    ]
