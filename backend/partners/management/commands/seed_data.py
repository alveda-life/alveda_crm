import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from partners.models import Partner
from contacts.models import Contact
from accounts.models import User


NAMES = [
    'Dr. Priya Sharma', 'Alexei Volkov', 'Maria Gonzalez', 'James Okonkwo',
    'Sofia Petersen', 'Ravi Kumar', 'Emily Chen', 'Hassan Al-Rashid',
    'Natasha Ivanova', 'Carlos Mendez', 'Yuki Tanaka', 'Amara Diallo',
    'Lucas Silva', 'Ingrid Larsen', 'Tariq Mahmoud', 'Isabelle Fontaine',
    'Dmitri Kozlov', 'Aisha Osei', 'Marco Rossi', 'Leila Nouri',
]

TRANSCRIPTIONS = [
    "Partner showed strong interest in the Medical Set program. Explained commission structure (15%). Will create their first set within a week. Follow up scheduled.",
    "Discussed platform features and onboarding process. Partner has 2,000 Instagram followers in the wellness niche. Very motivated to start. Sent welcome email.",
    "First call went well. Partner is a licensed Ayurvedic doctor with 10 years experience. Concerned about product quality - shared certificates. Will review and decide.",
    "Partner already created 3 Medical Sets. Shared best practices for promotion. Discussed social media strategy. Revenue growing steadily.",
    "Cold call - partner was not expecting it. Rescheduled for next Tuesday at 14:00. Brief intro given about the platform.",
    "Partner has started seeing first sales from their referral link. Discussed upsell opportunities. Very happy with the commission received. Potential ambassador.",
    "Technical question about the partner dashboard. Walked through the reporting features. Partner now confident in tracking their sales.",
]


class Command(BaseCommand):
    help = 'Seed test partner data'

    def handle(self, *args, **options):
        if Partner.objects.exists():
            self.stdout.write('Data already exists, skipping seed.')
            return

        operator = User.objects.filter(role='operator').first()
        admin = User.objects.filter(role='admin').first()

        stages = [Partner.STAGE_NEW, Partner.STAGE_TRAINED, Partner.STAGE_SET_CREATED, Partner.STAGE_HAS_SALE]
        stage_weights = [6, 5, 5, 4]
        categories = [Partner.CAT_DOCTOR, Partner.CAT_TRAINER, Partner.CAT_BLOGGER, Partner.CAT_OTHER]
        types = [Partner.TYPE_PARTNER, Partner.TYPE_MEDIC]

        created = []
        for i, name in enumerate(NAMES):
            stage = random.choices(stages, weights=stage_weights)[0]
            category = random.choice(categories)
            p_type = random.choices(types, weights=[8, 2])[0]

            medical_sets = 0
            orders = 0
            paid = 0
            paid_sum = Decimal('0')
            unpaid_sum = Decimal('0')
            refs = 0

            if stage in [Partner.STAGE_SET_CREATED, Partner.STAGE_HAS_SALE]:
                medical_sets = random.randint(1, 5)
            if stage == Partner.STAGE_HAS_SALE:
                orders = random.randint(3, 30)
                paid = random.randint(1, orders)
                paid_sum = Decimal(str(round(random.uniform(50, 3000), 2)))
                unpaid_sum = Decimal(str(round(random.uniform(0, 500), 2)))
                refs = random.randint(0, 8)

            partner = Partner.objects.create(
                name=name,
                phone=f'+7 9{random.randint(10, 99)} {random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}',
                user_id=f'USR{1000 + i}',
                type=p_type,
                category=category,
                stage=stage,
                medical_sets_count=medical_sets,
                orders_count=orders,
                paid_orders_count=paid,
                paid_orders_sum=paid_sum,
                unpaid_orders_sum=unpaid_sum,
                referrals_count=refs,
                assigned_to=operator if i % 3 != 0 else admin,
                referred_by=random.choice(['', 'organicreach', 'USR1001', 'USR1005', '']),
                notes='' if random.random() > 0.4 else 'VIP client - prioritize.',
            )
            created.append(partner)

        # Add contacts to trained/set_created/has_sale partners
        creator = operator or admin
        for partner in created:
            if partner.stage == Partner.STAGE_NEW:
                continue
            n_contacts = {
                Partner.STAGE_TRAINED: 1,
                Partner.STAGE_SET_CREATED: random.randint(1, 3),
                Partner.STAGE_HAS_SALE: random.randint(2, 5),
            }.get(partner.stage, 0)

            for j in range(n_contacts):
                days_ago = random.randint(1, 60)
                Contact.objects.create(
                    partner=partner,
                    date=timezone.now() - timedelta(days=days_ago - j * 7),
                    transcription=random.choice(TRANSCRIPTIONS),
                    notes='Good call.' if random.random() > 0.5 else '',
                    created_by=creator,
                )

        self.stdout.write(self.style.SUCCESS(f'Seeded {len(created)} partners with contacts.'))
