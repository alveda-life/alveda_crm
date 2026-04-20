"""Re-run diarization (with translation to English) on existing contacts.

Useful when the diarization prompt changes or when older transcripts were
labelled while the call was still in a non-English language and the
Operator/Partner split came out wrong.

Usage:
    python manage.py rediarize_contacts                 # all contacts with a transcription
    python manage.py rediarize_contacts --only-non-english
    python manage.py rediarize_contacts --ids 12 34 56
    python manage.py rediarize_contacts --resummarize   # also rerun the AI summary
    python manage.py rediarize_contacts --dry-run
"""

import re
import logging
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile

from contacts.models import Contact
from contacts.transcription import _diarize_with_openai

logger = logging.getLogger(__name__)

_DEVANAGARI_RE = re.compile(r'[\u0900-\u097F]')   # Hindi / Marathi
_TAMIL_RE       = re.compile(r'[\u0B80-\u0BFF]')
_CYRILLIC_RE    = re.compile(r'[\u0400-\u04FF]')


def _looks_non_english(text: str) -> bool:
    if not text:
        return False
    if _DEVANAGARI_RE.search(text) or _TAMIL_RE.search(text) or _CYRILLIC_RE.search(text):
        return True
    return False


class Command(BaseCommand):
    help = 'Re-run diarization (with English translation) on existing contacts.'

    def add_arguments(self, parser):
        parser.add_argument('--ids', type=int, nargs='*', default=None,
                            help='Specific contact IDs to process')
        parser.add_argument('--only-non-english', action='store_true',
                            help='Only process contacts whose raw transcription contains non-Latin script')
        parser.add_argument('--resummarize', action='store_true',
                            help='Also rerun the AI summary after re-diarization')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would change but do not save')
        parser.add_argument('--limit', type=int, default=None,
                            help='Hard cap on how many contacts to process this run')

    def handle(self, *args, **opts):
        qs = Contact.objects.exclude(transcription='').exclude(transcription__isnull=True)
        if opts['ids']:
            qs = qs.filter(pk__in=opts['ids'])

        qs = qs.order_by('-id')
        if opts['limit']:
            qs = qs[: opts['limit']]

        total = qs.count() if not opts['limit'] else len(list(qs))
        self.stdout.write(self.style.NOTICE(f'Scanning {total} contact(s)...'))

        processed = 0
        skipped = 0
        for contact in qs.iterator():
            raw = (contact.transcription or '').strip()
            if not raw:
                skipped += 1
                continue
            if opts['only_non_english'] and not _looks_non_english(raw):
                skipped += 1
                continue

            self.stdout.write(f'  → contact {contact.id} ({len(raw)} chars)')
            new_diarized = _diarize_with_openai(raw)
            if not new_diarized or new_diarized == raw:
                self.stdout.write(self.style.WARNING(f'    diarization returned unchanged text'))

            if opts['dry_run']:
                preview = (new_diarized or '')[:200].replace('\n', ' ')
                self.stdout.write(f'    preview: {preview}...')
                processed += 1
                continue

            contact.diarized_transcript = new_diarized

            try:
                base = (contact.audio_file.name.rsplit('/', 1)[-1].rsplit('.', 1)[0]
                        if contact.audio_file else f'contact_{contact.id}')
                txt_content = ContentFile((new_diarized or '').encode('utf-8'),
                                          name=f'{base}_transcript.txt')
                contact.transcript_file.save(f'{base}_transcript.txt', txt_content, save=False)
            except Exception as e:
                logger.warning(f'transcript_file rewrite failed for contact {contact.id}: {e}')

            update_fields = ['diarized_transcript', 'transcript_file']

            if opts['resummarize']:
                contact.summary_status = 'pending'
                update_fields.append('summary_status')

            contact.save(update_fields=update_fields)

            if opts['resummarize']:
                try:
                    from contacts.summarization import summarize_transcription
                    summarize_transcription(contact)
                except Exception as e:
                    logger.error(f'resummarize failed for contact {contact.id}: {e}')

            processed += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done. processed={processed}, skipped={skipped}, total_seen={total}'
        ))
