"""Queue partner call-insight extraction for historical transcribed calls.

Fills missing CallInsight rows (or re-runs failed ones) in batches so the
OpenAI work is spread across threads instead of blocking a single request.

Usage:
    python manage.py enqueue_call_insights
    python manage.py enqueue_call_insights --dry-run
    python manage.py enqueue_call_insights --threads 4
    python manage.py enqueue_call_insights --ids 12 34 56
    python manage.py enqueue_call_insights --include-done   # regenerate all done (expensive)
"""

import logging
import threading
from queue import Queue

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.db.models import Exists, OuterRef, Q

from contacts.models import CallInsight, Contact
from contacts.insights import extract_call_insights_background

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Backfill CallInsight rows for contacts with completed transcription.'

    def add_arguments(self, parser):
        parser.add_argument('--ids', nargs='+', type=int, default=None,
                            help='Only process the listed contact IDs.')
        parser.add_argument('--threads', type=int, default=2,
                            help='Number of parallel workers (default: 2).')
        parser.add_argument('--dry-run', action='store_true',
                            help='List which contacts would be processed and exit.')
        parser.add_argument(
            '--include-done',
            action='store_true',
            help='Also enqueue contacts that already have a successful CallInsight.',
        )

    def handle(self, *args, **opts):
        qs = (
            Contact.objects.filter(transcription_status=Contact.TRANSCRIPTION_DONE)
            .filter(Q(transcription__gt='') | Q(diarized_transcript__gt=''))
            .select_related('partner')
            .order_by('id')
        )
        if opts['ids']:
            qs = qs.filter(id__in=opts['ids'])
        elif not opts['include_done']:
            done_exists = Exists(
                CallInsight.objects.filter(
                    contact_id=OuterRef('pk'),
                    status=CallInsight.STATUS_DONE,
                )
            )
            qs = qs.annotate(_insight_done=done_exists).filter(_insight_done=False)

        total = qs.count()
        self.stdout.write(self.style.NOTICE(f'Found {total} contact(s) to process.'))

        if total == 0:
            return

        if opts['dry_run']:
            for c in qs[:200]:
                self.stdout.write(
                    f'  #{c.id:>5}  partner={c.partner.name!r:<36}'
                )
            if total > 200:
                self.stdout.write(f'  …and {total - 200} more')
            self.stdout.write(self.style.WARNING('Dry-run — nothing was changed.'))
            return

        ids = list(qs.values_list('id', flat=True))
        threads = max(1, int(opts['threads']))

        if threads == 1:
            for i, cid in enumerate(ids, 1):
                self._run_one(cid, i, total)
            return

        queue: Queue = Queue()
        for cid in ids:
            queue.put(cid)

        counter = {'done': 0}
        lock = threading.Lock()

        def worker():
            while True:
                try:
                    cid = queue.get_nowait()
                except Exception:
                    return
                try:
                    with lock:
                        counter['done'] += 1
                        idx = counter['done']
                    self._run_one(cid, idx, total)
                finally:
                    queue.task_done()

        workers = [threading.Thread(target=worker, daemon=True) for _ in range(threads)]
        for w in workers:
            w.start()
        for w in workers:
            w.join()

    def _run_one(self, contact_id: int, idx: int, total: int):
        close_old_connections()
        try:
            contact = Contact.objects.select_related('partner').get(pk=contact_id)
        except Contact.DoesNotExist:
            self.stdout.write(self.style.WARNING(
                f'[{idx}/{total}] #{contact_id} missing, skip'
            ))
            return

        name = contact.partner.name if contact.partner_id else '—'
        self.stdout.write(f'[{idx}/{total}] #{contact_id}  {name}')
        try:
            extract_call_insights_background(contact_id)
            row = CallInsight.objects.filter(contact_id=contact_id).first()
            st = row.status if row else '—'
            self.stdout.write(self.style.SUCCESS(f'    → insight_status={st!r}'))
        except Exception as e:  # pragma: no cover
            logger.exception('enqueue_call_insights failed for %s', contact_id)
            self.stdout.write(self.style.ERROR(f'    → ERROR: {e}'))
        finally:
            close_old_connections()
