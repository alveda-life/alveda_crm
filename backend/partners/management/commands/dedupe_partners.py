"""
Collapse duplicate Partner rows that share the same external CRM user_id.

How duplicates appeared
-----------------------
Before [partners/0013_partner_user_id_unique](../../migrations/0013_partner_user_id_unique.py)
nothing in the database prevented two rows with the same `user_id`. When the CRM
sync job (`run_crm_partners_sync`) was launched concurrently from multiple
gunicorn workers, each one would do an upsert based on an in-memory snapshot of
existing partners — and create the same row two or three times.

What this command does
----------------------
Groups partners by non-empty `user_id`, keeps the OLDEST row (smallest pk) as
the canonical "keeper", and:

  1. Re-points every related Contact and ProducerTask FK from each duplicate
     onto the keeper.
  2. Deletes the duplicate rows.

The keeper's stage / notes / assigned_to are preserved untouched — we never
choose between two human-managed values automatically.

Usage
-----
    python manage.py dedupe_partners              # actually merge + delete
    python manage.py dedupe_partners --dry-run    # only print what would happen
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count


class Command(BaseCommand):
    help = 'Collapse duplicate Partner rows that share the same user_id.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would happen without modifying anything',
        )

    def handle(self, *args, **options):
        from partners.models import Partner
        from contacts.models import Contact
        from tasks.models import Task

        dry_run = options['dry_run']

        # Find every user_id that appears more than once (ignore blanks).
        dup_user_ids = list(
            Partner.objects.exclude(user_id='')
            .values('user_id')
            .annotate(n=Count('id'))
            .filter(n__gt=1)
            .values_list('user_id', flat=True)
        )

        if not dup_user_ids:
            self.stdout.write(self.style.SUCCESS('No duplicate partners found.'))
            return

        self.stdout.write(
            f'Found {len(dup_user_ids)} duplicate user_id group(s). '
            f'{"DRY RUN — no changes." if dry_run else "Merging…"}'
        )

        groups = defaultdict(list)
        for p in Partner.objects.filter(user_id__in=dup_user_ids).order_by('id'):
            groups[p.user_id].append(p)

        total_merged = 0
        total_deleted = 0
        contacts_moved = 0
        tasks_moved = 0

        for uid, rows in groups.items():
            keeper = rows[0]
            duplicates = rows[1:]
            dup_ids = [r.id for r in duplicates]

            self.stdout.write(
                f'  user_id={uid}: keeper id={keeper.id} ({keeper.name!r}, stage={keeper.stage}); '
                f'merging {len(duplicates)} duplicate(s) id={dup_ids}'
            )

            if dry_run:
                contacts_moved += Contact.objects.filter(partner_id__in=dup_ids).count()
                tasks_moved += Task.objects.filter(partner_id__in=dup_ids).count()
                total_merged += len(duplicates)
                continue

            with transaction.atomic():
                contacts_moved += Contact.objects.filter(
                    partner_id__in=dup_ids
                ).update(partner=keeper)

                tasks_moved += Task.objects.filter(
                    partner_id__in=dup_ids
                ).update(partner=keeper)

                deleted, _ = Partner.objects.filter(id__in=dup_ids).delete()
                total_deleted += deleted
                total_merged += len(duplicates)

        verb = 'Would merge' if dry_run else 'Merged'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {total_merged} duplicate(s) into {len(groups)} keeper(s). '
            f'Re-attached contacts={contacts_moved} tasks={tasks_moved}'
            + ('' if dry_run else f' · deleted rows={total_deleted}')
        ))
