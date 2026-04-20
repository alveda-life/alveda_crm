"""
Management command: import_asana_producers
Re-imports / syncs all producers from Asana project to the local DB.

Usage:
  python manage.py import_asana_producers [--dry-run] [--verbose]

Requires ASANA_PAT and ASANA_PROJECT_GID environment variables.
"""

import os
import re
import json
import requests
from datetime import date
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from producers.models import Producer

ASANA_PAT     = os.environ.get('ASANA_PAT', '')
PROJECT_GID   = os.environ.get('ASANA_PROJECT_GID', '')
ASANA_HEADERS = {
    'Authorization': f'Bearer {ASANA_PAT}',
    'Accept': 'application/json',
}


# ── Value normalisation maps ────────────────────────────────────────────────

CATEGORY_MAP = {
    # raw token (after stripping parentheticals and splitting by comma) → canonical DB value
    # Health / supplements
    'supplements': 'Supplements',
    'supplement': 'Supplements',
    'digestive': 'Supplements',
    'immunity': 'Supplements',
    'nutraceuticals': 'Nutraceuticals',
    'nutraceutical': 'Nutraceuticals',
    # Ayurvedic
    'ayurvedic medicines': 'Ayurvedic Medicines',
    'ayurvedic medicine': 'Ayurvedic Medicines',
    'ayurvedic': 'Ayurvedic Medicines',
    'ayurvedic classics': 'Ayurvedic Medicines',
    'classical ayurvedic': 'Ayurvedic Medicines',
    'otc remedies': 'Ayurvedic Medicines',
    'otc': 'Ayurvedic Medicines',
    # Cosmetics
    'cosmetics': 'Cosmetics & Personal Care',
    'cosmetics & personal care': 'Cosmetics & Personal Care',
    'beauty & personal care': 'Cosmetics & Personal Care',
    'beauty': 'Cosmetics & Personal Care',
    'personal care': 'Cosmetics & Personal Care',
    'hair care': 'Cosmetics & Personal Care',
    'skin care': 'Cosmetics & Personal Care',
    # Herbal
    'herbal extracts': 'Herbal Extracts',
    'herbal extract': 'Herbal Extracts',
    'herbal': 'Herbal Extracts',
    # Essential oils
    'essential oils': 'Essential Oils',
    'essential oil': 'Essential Oils',
    # Food
    'food & beverages': 'Food & Beverages',
    'food and beverages': 'Food & Beverages',
    'food': 'Food & Beverages',
    'beverages': 'Food & Beverages',
    # Raw materials
    'raw materials': 'Raw Materials & Herbs',
    'raw materials & herbs': 'Raw Materials & Herbs',
    'herbs': 'Raw Materials & Herbs',
    'dried herbs': 'Raw Materials & Herbs',
    # Equipment
    'equipment': 'Equipment & Machinery',
    'equipment & machinery': 'Equipment & Machinery',
    'machinery': 'Equipment & Machinery',
    # Other
    'packaging': 'Packaging',
    'contract manufacturing': 'Contract Manufacturing',
    'pharmaceutical': 'Pharmaceutical',
    'pharmaceuticals': 'Pharmaceutical',
    'wellness products': 'Wellness Products',
    'wellness': 'Wellness Products',
    'other': 'Other',
}

CERT_MAP = {
    'gmp': 'GMP',
    'iso': 'ISO',
    'fssai': 'FSSAI',
    'ayush': 'AYUSH License',
    'ayush license': 'AYUSH License',
    'fda': 'FDA',
    'who-gmp': 'GMP',
    'who gmp': 'GMP',
    'organic': 'Organic Certified',
    'organic certified': 'Organic Certified',
    'halal': 'Halal',
    'kosher': 'Kosher',
}

COMM_STATUS_MAP = {
    'no response': 'No Response',
    'in contact': 'In Contact',
    'meeting scheduled': 'Meeting Scheduled',
    'meeting held': 'Meeting Held',
    'proposal sent': 'Proposal Sent',
    'negotiating': 'Negotiating',
    'on hold': 'On Hold',
    'closed won': 'Closed Won',
    'closed lost': 'Closed Lost',
    'whatsapp': 'WhatsApp',
    'email': 'Email',
    'call': 'Call',
    'follow up': 'Follow Up',
}

COOP_MAP = {
    'strong': Producer.COOP_STRONG,
    'high': Producer.COOP_STRONG,
    'medium': Producer.COOP_MEDIUM,
    'moderate': Producer.COOP_MEDIUM,
    'weak': Producer.COOP_WEAK,
    'low': Producer.COOP_WEAK,
    'no response': Producer.COOP_NO_RESPONSE,
    'no response yet': Producer.COOP_NO_RESPONSE,
    'no_response': Producer.COOP_NO_RESPONSE,
}

PRIORITY_MAP = {
    'high': Producer.PRIORITY_HIGH,
    'medium': Producer.PRIORITY_MEDIUM,
    'low': Producer.PRIORITY_LOW,
    'normal': Producer.PRIORITY_MEDIUM,
}

FUNNEL_MAP = {
    'onboarding': Producer.FUNNEL_ONBOARDING,
    'подключение': Producer.FUNNEL_ONBOARDING,
    'support': Producer.FUNNEL_SUPPORT,
    'сопровождение': Producer.FUNNEL_SUPPORT,
}

ONBOARDING_STAGE_MAP = {
    'interest': Producer.STAGE_INTEREST,
    'in communication': Producer.STAGE_IN_COMMUNICATION,
    'negotiation': Producer.STAGE_NEGOTIATION,
    'contract signed': Producer.STAGE_CONTRACT_SIGNED,
    'on the platform': Producer.STAGE_ON_PLATFORM,
    'on platform': Producer.STAGE_ON_PLATFORM,
    'stopped': Producer.STAGE_STOPPED,
    # Russian
    'интерес': Producer.STAGE_INTEREST,
    'в коммуникации': Producer.STAGE_IN_COMMUNICATION,
    'переговоры': Producer.STAGE_NEGOTIATION,
    'контракт подписан': Producer.STAGE_CONTRACT_SIGNED,
    'на платформе': Producer.STAGE_ON_PLATFORM,
    'остановлен': Producer.STAGE_STOPPED,
}

SUPPORT_STAGE_MAP = {
    'agreed': Producer.STAGE_AGREED,
    'signed': Producer.STAGE_SIGNED,
    'products received': Producer.STAGE_PRODUCTS,
    'ready to sell': Producer.STAGE_READY,
    'in store': Producer.STAGE_IN_STORE,
    # Russian
    'договорились': Producer.STAGE_AGREED,
    'подписали': Producer.STAGE_SIGNED,
    'получили продукты': Producer.STAGE_PRODUCTS,
    'готов к продаже': Producer.STAGE_READY,
    'в магазине': Producer.STAGE_IN_STORE,
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _norm(s):
    return (s or '').strip().lower()


def _map_list(raw_list, mapping, split_compound=False):
    """Map a list of raw strings to canonical values using a dict.
    If split_compound=True, each item is first stripped of parentheticals
    and split by comma to handle compound Asana labels like
    'Digestive, Immunity, Supplements (health categories)'.
    """
    out = []
    for item in raw_list:
        if split_compound:
            # Strip parenthetical suffixes: "Foo (bar categories)" → "Foo"
            clean = re.sub(r'\s*\([^)]*\)', '', item).strip()
            tokens = [t.strip() for t in clean.split(',') if t.strip()]
        else:
            tokens = [item.strip()]

        for token in tokens:
            n = _norm(token)
            mapped = mapping.get(n)
            if mapped:
                if mapped not in out:
                    out.append(mapped)
            else:
                v = token.title()
                if v and v not in out:
                    out.append(v)
    return out


def _parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


def _get_custom_field(fields, name_fragment):
    """Return the raw custom field dict whose name contains name_fragment (case-insensitive)."""
    for f in fields:
        if name_fragment.lower() in (f.get('name') or '').lower():
            return f
    return None


def _text_value(fields, name_fragment):
    f = _get_custom_field(fields, name_fragment)
    if not f:
        return ''
    return (f.get('text_value') or f.get('display_value') or '').strip()


def _enum_value(fields, name_fragment):
    f = _get_custom_field(fields, name_fragment)
    if not f:
        return ''
    ev = f.get('enum_value')
    if ev:
        return (ev.get('name') or '').strip()
    return (f.get('display_value') or '').strip()


def _multi_enum_values(fields, name_fragment):
    f = _get_custom_field(fields, name_fragment)
    if not f:
        return []
    multi = f.get('multi_enum_values') or []
    return [v.get('name', '').strip() for v in multi if v.get('name')]


def _number_value(fields, name_fragment):
    f = _get_custom_field(fields, name_fragment)
    if not f:
        return None
    v = f.get('number_value')
    if v is not None:
        try:
            return int(v)
        except (ValueError, TypeError):
            return None
    return None


def _date_value(fields, name_fragment):
    f = _get_custom_field(fields, name_fragment)
    if not f:
        return None
    dv = f.get('date_value')
    # Asana date_value can be a dict: {'date': 'YYYY-MM-DD', 'date_time': None}
    if isinstance(dv, dict):
        return _parse_date(dv.get('date') or dv.get('date_time'))
    return _parse_date(dv or f.get('display_value'))


# ── Asana fetching ───────────────────────────────────────────────────────────

def fetch_asana_tasks(verbose=False):
    url = f'https://app.asana.com/api/1.0/projects/{PROJECT_GID}/tasks'
    params = {
        'opt_fields': (
            'name,notes,completed,'
            'custom_fields.name,custom_fields.type,'
            'custom_fields.text_value,custom_fields.display_value,'
            'custom_fields.enum_value.name,'
            'custom_fields.multi_enum_values.name,'
            'custom_fields.number_value,'
            'custom_fields.date_value'
        ),
        'limit': 100,
    }
    tasks = []
    while url:
        resp = requests.get(url, headers=ASANA_HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        tasks.extend(data.get('data', []))
        next_page = data.get('next_page')
        url    = next_page['uri'] if next_page else None
        params = {}  # pagination URI already has params
        if verbose:
            print(f'  Fetched {len(tasks)} tasks so far…')
    return tasks


def parse_task(task, verbose=False):
    """Return a dict with normalised field values ready to apply to a Producer."""
    name   = (task.get('name') or '').strip()
    fields = task.get('custom_fields') or []
    # Prefer custom "Notes" field; fall back to task description
    notes  = (_text_value(fields, 'notes') or (task.get('notes') or '')).strip()

    if verbose:
        print(f'\n  Parsing: {name}')
        for f in fields:
            print(f'    [{f.get("name")}] type={f.get("type")} val={f.get("text_value") or f.get("enum_value") or f.get("multi_enum_values") or f.get("number_value") or f.get("date_value") or f.get("display_value")}')

    # ── Funnel & Stage ───────────────────────────────────────────────────────
    funnel_raw = _enum_value(fields, 'funnel') or _enum_value(fields, 'воронка')
    stage_raw  = _enum_value(fields, 'stage')  or _enum_value(fields, 'этап')
    funnel = FUNNEL_MAP.get(_norm(funnel_raw), Producer.FUNNEL_ONBOARDING)
    if funnel == Producer.FUNNEL_ONBOARDING:
        stage = ONBOARDING_STAGE_MAP.get(_norm(stage_raw), Producer.STAGE_INTEREST)
    else:
        stage = SUPPORT_STAGE_MAP.get(_norm(stage_raw), Producer.STAGE_AGREED)

    # ── Priority ────────────────────────────────────────────────────────────
    priority_raw = _enum_value(fields, 'priority') or _enum_value(fields, 'приоритет')
    priority = PRIORITY_MAP.get(_norm(priority_raw), Producer.PRIORITY_MEDIUM)

    # ── Cooperation potential ────────────────────────────────────────────────
    coop_raw = (_enum_value(fields, 'cooperation') or
                _enum_value(fields, 'coop') or
                _enum_value(fields, 'потенциал'))
    coop = COOP_MAP.get(_norm(coop_raw), Producer.COOP_MEDIUM)

    # ── Product categories (multi-enum) ────────────────────────────────────
    cat_raw = (_multi_enum_values(fields, 'category') or
               _multi_enum_values(fields, 'категор') or
               _multi_enum_values(fields, 'product type') or
               _multi_enum_values(fields, 'тип продукта'))
    categories = _map_list(cat_raw, CATEGORY_MAP, split_compound=True)

    # ── Certifications (multi-enum) ─────────────────────────────────────────
    cert_raw = (_multi_enum_values(fields, 'certif') or
                _multi_enum_values(fields, 'сертиф'))
    certifications = _map_list(cert_raw, CERT_MAP)

    # ── Communication status (multi-enum) ───────────────────────────────────
    comm_raw = (_multi_enum_values(fields, 'communication status') or
                _multi_enum_values(fields, 'comm') or
                _multi_enum_values(fields, 'коммуникация'))
    comm_status = _map_list(comm_raw, COMM_STATUS_MAP)

    # ── Next step (enum or text) ─────────────────────────────────────────────
    next_step = (_enum_value(fields, 'next step') or
                 _text_value(fields, 'next step') or
                 _enum_value(fields, 'следующий шаг') or
                 _text_value(fields, 'следующий шаг'))[:100]

    # ── Contact info (text) ──────────────────────────────────────────────────
    contact_info = (_text_value(fields, 'contact info') or
                    _text_value(fields, 'contacts') or
                    _text_value(fields, 'контакт'))

    # ── Company ──────────────────────────────────────────────────────────────
    company = (_text_value(fields, 'company') or
               _text_value(fields, 'компания') or
               _text_value(fields, 'organization'))

    # ── Phone / website / city ───────────────────────────────────────────────
    phone   = _text_value(fields, 'phone')
    website = _text_value(fields, 'website') or _text_value(fields, 'сайт')
    city    = _text_value(fields, 'city') or _text_value(fields, 'город')
    country = _text_value(fields, 'country') or _text_value(fields, 'страна')
    email   = _text_value(fields, 'email')

    # ── Product count (number) ───────────────────────────────────────────────
    product_count = (_number_value(fields, 'product count') or
                     _number_value(fields, 'catalog size') or
                     _number_value(fields, 'sku') or
                     _number_value(fields, 'number of sku') or
                     _number_value(fields, 'количество'))

    # ── Dates ─────────────────────────────────────────────────────────────────
    control_date = (_date_value(fields, 'next follow') or
                    _date_value(fields, 'control date') or
                    _date_value(fields, 'follow') or
                    _date_value(fields, 'next contact') or
                    _date_value(fields, 'контроль'))
    last_contact = (_date_value(fields, 'last contact') or
                    _date_value(fields, 'last_contact') or
                    _date_value(fields, 'последний контакт'))

    return {
        'name': name,
        'notes': notes,
        'company': company,
        'phone': phone,
        'email': email,
        'website': website,
        'city': city,
        'country': country,
        'funnel': funnel,
        'stage': stage,
        'priority': priority,
        'cooperation_potential': coop,
        'product_type': ', '.join(categories),
        'certifications': ', '.join(certifications),
        'communication_status': ', '.join(comm_status),
        'next_step': next_step,
        'contact_info': contact_info,
        'product_count': product_count,
        'control_date': control_date,
        'last_contact': last_contact,
    }


# ── Command ──────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Re-import / sync producers from Asana'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print changes without saving')
        parser.add_argument('--verbose', action='store_true', help='Verbose Asana field dump')
        parser.add_argument('--name', type=str, help='Only process a single producer by name (substring match)')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        name_filter = options.get('name')

        self.stdout.write('Fetching tasks from Asana…')
        tasks = fetch_asana_tasks(verbose=verbose)
        self.stdout.write(f'  Got {len(tasks)} tasks')

        if name_filter:
            tasks = [t for t in tasks if name_filter.lower() in (t.get('name') or '').lower()]
            self.stdout.write(f'  Filtered to {len(tasks)} tasks matching "{name_filter}"')

        created = 0
        updated = 0
        skipped = 0

        for task in tasks:
            task_name = (task.get('name') or '').strip()
            if not task_name or task.get('completed'):
                skipped += 1
                continue

            parsed = parse_task(task, verbose=verbose)
            name = parsed['name']

            # Try to find by exact name first, then case-insensitive
            producer = (Producer.objects.filter(name=name).first() or
                        Producer.objects.filter(name__iexact=name).first())

            changes = {}
            # Do NOT overwrite stage/funnel — those may have been manually advanced in CRM
            FIELDS_TO_SYNC = [
                'notes', 'company', 'phone', 'email', 'website', 'city', 'country',
                'priority', 'cooperation_potential',
                'product_type', 'certifications', 'communication_status',
                'next_step', 'contact_info', 'product_count',
                'control_date', 'last_contact',
            ]

            if producer:
                for field in FIELDS_TO_SYNC:
                    new_val = parsed.get(field)
                    old_val = getattr(producer, field)
                    # Only overwrite if new value is non-empty/non-null
                    if new_val not in (None, '', []) and new_val != old_val:
                        changes[field] = (old_val, new_val)

                if changes:
                    self.stdout.write(f'\n  UPDATE: {name}')
                    for field, (old, new) in changes.items():
                        self.stdout.write(f'    {field}: {repr(old)} → {repr(new)}')
                    if not dry_run:
                        for field, (_, new) in changes.items():
                            setattr(producer, field, new)
                        producer.save()
                    updated += 1
                else:
                    if verbose:
                        self.stdout.write(f'  no changes: {name}')
            else:
                self.stdout.write(f'\n  CREATE: {name}')
                if verbose:
                    for k, v in parsed.items():
                        if v not in (None, ''):
                            self.stdout.write(f'    {k}: {repr(v)}')
                if not dry_run:
                    Producer.objects.create(**{k: v for k, v in parsed.items() if k != 'name'},
                                            name=name)
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. updated={updated}  created={created}  skipped={skipped}'
            + (' [DRY RUN — no changes saved]' if dry_run else '')
        ))
