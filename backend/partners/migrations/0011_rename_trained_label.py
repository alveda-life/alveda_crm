from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partners', '0010_add_whatsapp_added'),
    ]

    operations = [
        migrations.AlterField(
            model_name='partner',
            name='stage',
            field=models.CharField(
                choices=[
                    ('new', 'New'),
                    ('trained', 'Agreed to Create First Set'),
                    ('set_created', 'Medical Set Created'),
                    ('has_sale', 'Has Sale'),
                    ('no_answer', 'Dead (No Answer)'),
                    ('declined', 'Dead (Declined)'),
                    ('no_sales', 'Dead (No Sales)'),
                ],
                db_index=True,
                default='new',
                max_length=20,
            ),
        ),
    ]
