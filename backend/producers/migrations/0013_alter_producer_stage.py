# Generated for the new "Negotiation" (terms_negotiation) onboarding stage.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('producers', '0012_alter_producer_cooperation_potential_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='producer',
            name='stage',
            field=models.CharField(
                choices=[
                    ('interest', 'Interest'),
                    ('in_communication', 'In Communication'),
                    ('terms_negotiation', 'Negotiation'),
                    ('negotiation', 'Signing Contract'),
                    ('contract_signed', 'Contract Signed'),
                    ('on_platform', 'On the Platform'),
                    ('stopped', 'Stopped'),
                    ('agreed', 'Agreed'),
                    ('signed', 'Signed'),
                    ('products_received', 'Products Received'),
                    ('ready_to_sell', 'Ready to Sell'),
                    ('in_store', 'In Store'),
                ],
                db_index=True,
                default='interest',
                max_length=30,
            ),
        ),
    ]
