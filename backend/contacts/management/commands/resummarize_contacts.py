"""Re-run AI summarization + quality scoring on existing contacts.

Use after editing the global Evaluation Prompt or Product Information in
/admin/settings — old calls keep their previous scores until they are
re-evaluated.

Usage:
    python manage.py resummarize_contacts                 # all done contacts
    python manage.py resummarize_contacts --ids 12 34 56
    python manage.py resummarize_contacts --status done   # filter by current status
    python manage.py resummarize_contacts --threads 4     # parallel workers
    python manage.py resummarize_contacts --dry-run
"""

import logging
import threading
from queue import Queue

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from contacts.models import Contact
from contacts.summarization import summarize_transcription

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Re-run AI summarization and quality scoring on existing partner '
        'contacts. Useful after updating the global evaluation prompt.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--ids', nargs='+', type=int, default=None,
                            help='Only process the listed contact IDs.')
        parser.add_argument('--status', type=str, default=None,
                            help='Only process contacts whose summary_status equals this.')
        parser.add_argument('--threads', type=int, default=1,
                            help='Number of parallel workers (default: 1).')
        parser.add_argument('--dry-run', action='store_true',
                            help='List which contacts would be processed and exit.')

    def handle(self, *args, **opts):
        qs = (
            Contact.objects
            .exclude(transcription='')
            .exclude(transcription__isnull=True)
            .select_related('partner')
            .order_by('id')
        )
        if opts['ids']:
            qs = qs.filter(id__in=opts['ids'])
        if opts['status']:
            qs = qs.filter(summary_status=opts['status'])

        total = qs.count()
        self.stdout.write(self.style.NOTICE(
            f'Found {total} contact(s) with a transcript.'
        ))

        if total == 0:
            return

        if opts['dry_run']:
            for c in qs[:200]:
                self.stdout.write(
                    f'  #{c.id:>4}  partner={c.partner.name!r:<40}  '
                    f'status={c.summary_status!r}  len={len(c.transcription or "")}'
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
                f'[{idx}/{total}] #{contact_id} no longer exists, skipping'
            ))
            return

        partner_name = contact.partner.name if contact.partner_id else '—'
        self.stdout.write(f'[{idx}/{total}] #{contact_id}  {partner_name}')

        try:
            summarize_transcription(contact)
            contact.refresh_from_db(fields=['summary_status', 'quality_overall'])
            self.stdout.write(self.style.SUCCESS(
                f'    → status={contact.summary_status}  overall={contact.quality_overall}'
            ))
        except Exception as e:  # pragma: no cover
            logger.exception('resummarize failed for contact %s', contact_id)
            self.stdout.write(self.style.ERROR(f'    → ERROR: {e}'))
        finally:
            close_old_connections()
