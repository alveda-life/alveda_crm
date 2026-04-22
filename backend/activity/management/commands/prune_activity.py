from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from activity.models import UserActivityEvent


class Command(BaseCommand):
    help = 'Delete UserActivityEvent rows older than --days (default 90).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=90,
            help='Delete events older than N days (default 90).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would be deleted without touching the DB.',
        )

    def handle(self, *args, days, dry_run, **opts):
        if days < 1:
            self.stderr.write('--days must be >= 1')
            return
        cutoff = timezone.now() - timedelta(days=days)
        qs = UserActivityEvent.objects.filter(created_at__lt=cutoff)
        count = qs.count()
        if dry_run:
            self.stdout.write(
                f'[dry-run] would delete {count} events older than {cutoff.isoformat()}'
            )
            return
        deleted, _ = qs.delete()
        self.stdout.write(
            self.style.SUCCESS(f'Deleted {deleted} events older than {cutoff.isoformat()}')
        )
