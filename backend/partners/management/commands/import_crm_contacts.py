"""
Import / sync partners from the external CRM API.

Usage:
  python manage.py import_crm_contacts            # upsert, keep existing stage/notes
  python manage.py import_crm_contacts --clear    # delete ALL existing partners first
  python manage.py import_crm_contacts --dry-run  # show counts, do nothing
"""

import os
import requests
from django.core.management.base import BaseCommand
from django.db import transaction

API_BASE = os.environ.get('CRM_API_BASE', 'https://ask-ayurveda.com/_crm/api/contacts/')
# Read from env so the key never lives in source. Falls back to the legacy literal
# only when the env variable is not set, so existing dev environments keep working.
API_KEY  = os.environ.get('CRM_API_KEY', 'FsOTsYR7TFFaSzRn9x1R0npTsD3NsopqvvaX20Cz')

SEGMENT_TO_CATEGORY = {
    'doctor':          'doctor',
    'fitness':         'fitness_trainer',
    'fitness_trainer': 'fitness_trainer',
    'blogger':         'blogger',
    'other':           'other',
}


def fetch_all():
    """Paginate through all contacts and return a flat list."""
    contacts = []
    url = API_BASE
    headers = {'X-API-Key': API_KEY}
    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        contacts.extend(data['results'])
        url = data.get('next')
    return contacts


# Ordered low → high. Used to decide whether an incoming auto-derived stage
# is an upgrade over the partner's current stage. Manager-set stages further
# down the pipeline (e.g. STAGE_TRAINED set by a human) are never downgraded
# back to STAGE_NEW just because the API stats happen to be zero.
def _derive_stage_from_stats(stats: dict) -> str:
    """Map external CRM stats to our funnel stage.

    Rules (ordered, first match wins):
      paid_orders_count > 0 → 'has_sale'
      medical_sets_count > 0 → 'set_created'
      otherwise              → 'new'
    """
    from partners.models import Partner
    if (stats.get('paid_orders_count') or 0) > 0:
        return Partner.STAGE_HAS_SALE
    if (stats.get('medical_sets_count') or 0) > 0:
        return Partner.STAGE_SET_CREATED
    return Partner.STAGE_NEW


# Strict ordering for auto-derived stages: higher index = further along.
# Stages NOT in this list (TRAINED, NO_ANSWER, DECLINED, NO_SALES) are
# considered "manager-managed" and the API never overwrites them.
_AUTO_STAGE_RANK = {
    'new': 0,
    'set_created': 1,
    'has_sale': 2,
}


class Command(BaseCommand):
    help = 'Import/sync partners from the external CRM API'

    def add_arguments(self, parser):
        parser.add_argument('--clear',   action='store_true', help='Delete all existing partners before import')
        parser.add_argument('--dry-run', action='store_true', help='Show what would happen, do nothing')

    def handle(self, *args, **options):
        from partners.models import Partner

        dry_run = options['dry_run']
        clear   = options['clear']

        self.stdout.write('Fetching contacts from CRM API…')
        contacts = fetch_all()
        self.stdout.write(f'  Fetched {len(contacts)} contacts total')

        if dry_run:
            types = {}
            segments = {}
            for c in contacts:
                types[c['type']] = types.get(c['type'], 0) + 1
                seg = c.get('audience_segment', '<missing>')
                segments[seg] = segments.get(seg, 0) + 1
            self.stdout.write(f'  Types: {types}')
            self.stdout.write(f'  Audience segments: {segments}')
            self.stdout.write('Dry run — no changes made.')
            return

        with transaction.atomic():
            if clear:
                deleted, _ = Partner.objects.all().delete()
                self.stdout.write(self.style.WARNING(f'Deleted {deleted} existing partners'))

            created_count = 0
            updated_count = 0

            # Build lookup of existing partners by user_id
            existing = {p.user_id: p for p in Partner.objects.exclude(user_id='')}

            for c in contacts:
                uid      = str(c['user_id'])
                category = SEGMENT_TO_CATEGORY.get(c.get('audience_segment', ''), 'other')

                # Stats fields — always overwrite from API
                stats = dict(
                    medical_sets_count = c.get('product_sets_count') or 0,
                    orders_count       = c.get('orders_count')       or 0,
                    paid_orders_count  = c.get('paid_orders_count')  or 0,
                    paid_orders_sum    = c.get('paid_orders_sum')    or 0,
                    unpaid_orders_sum  = c.get('unpaid_orders_sum')  or 0,
                    referrals_count    = c.get('referrals_count')    or 0,
                )

                derived_stage = _derive_stage_from_stats(stats)

                if uid in existing:
                    # Update: refresh stats + basic info. Stage is auto-upgraded
                    # only when the API-derived stage is strictly higher than the
                    # current one AND the current stage is in the auto-managed set
                    # (new / set_created / has_sale). Manager-set stages (trained,
                    # no_answer, declined, no_sales) are never overwritten here.
                    p = existing[uid]
                    p.name     = c['name']
                    p.phone    = c.get('phone') or ''
                    p.type     = c.get('type', 'partner')
                    p.category = category
                    p.referred_by = c.get('referred_by_name') or ''
                    for k, v in stats.items():
                        setattr(p, k, v)

                    update_fields = [
                        'name', 'phone', 'type', 'category', 'referred_by',
                        'medical_sets_count', 'orders_count', 'paid_orders_count',
                        'paid_orders_sum', 'unpaid_orders_sum', 'referrals_count',
                    ]

                    current_rank = _AUTO_STAGE_RANK.get(p.stage)
                    derived_rank = _AUTO_STAGE_RANK.get(derived_stage, 0)
                    if current_rank is not None and derived_rank > current_rank:
                        p.stage = derived_stage
                        update_fields.append('stage')

                    p.save(update_fields=update_fields)
                    updated_count += 1
                else:
                    # Create new — stage derived from stats so a partner who
                    # already has paid orders lands directly in "Has Sale", not "New".
                    Partner.objects.create(
                        user_id   = uid,
                        name      = c['name'],
                        phone     = c.get('phone') or '',
                        type      = c.get('type', 'partner'),
                        category  = category,
                        referred_by = c.get('referred_by_name') or '',
                        stage     = derived_stage,
                        **stats,
                    )
                    created_count += 1

            self.stdout.write(self.style.SUCCESS(
                f'Done: {created_count} created, {updated_count} updated'
            ))
