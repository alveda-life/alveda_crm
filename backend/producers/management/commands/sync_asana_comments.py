"""
Sync producer comments from Asana with TRUE Asana timestamps.

For each onboarding/support producer:
1. Match it to an Asana task (by asana_task_gid, else by exact/iexact name).
2. Fetch all stories from Asana for that task.
3. For each story of type=comment, upsert a ProducerComment using `asana_story_id`
   so we never duplicate, and set `created_at` = Asana's `created_at`.

Usage:
  python manage.py sync_asana_comments [--dry-run] [--name "Kairali"] [--purge-bulk]
    --purge-bulk  — also delete the previously bulk-imported duplicates
                    (those with timestamp 2026-04-15 21:24:* UTC)
"""
import os
import re
import requests
from datetime import datetime, timezone as dt_tz
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_datetime

from producers.models import Producer, ProducerComment
from accounts.models import User

ASANA_PAT     = os.environ.get('ASANA_PAT', '')
PROJECT_GID   = os.environ.get('ASANA_PROJECT_GID', '')
ASANA_HEADERS = {
    'Authorization': f'Bearer {ASANA_PAT}',
    'Accept': 'application/json',
}


def fetch_asana_tasks(verbose=False):
    """Return list of {gid, name} for all tasks in the project."""
    url = f'https://app.asana.com/api/1.0/projects/{PROJECT_GID}/tasks'
    params = {'opt_fields': 'name,completed', 'limit': 100}
    tasks = []
    while url:
        resp = requests.get(url, headers=ASANA_HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        tasks.extend(data.get('data', []))
        next_page = data.get('next_page')
        url    = next_page['uri'] if next_page else None
        params = {}
        if verbose:
            print(f'  Fetched {len(tasks)} tasks…')
    return tasks


def fetch_task_stories(task_gid):
    """Return all stories (comments + system events) for an Asana task."""
    url = f'https://app.asana.com/api/1.0/tasks/{task_gid}/stories'
    params = {'opt_fields': 'gid,type,resource_subtype,text,created_at,created_by.name'}
    stories = []
    while url:
        resp = requests.get(url, headers=ASANA_HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        stories.extend(data.get('data', []))
        next_page = data.get('next_page')
        url    = next_page['uri'] if next_page else None
        params = {}
    return stories


class Command(BaseCommand):
    help = 'Sync producer comments from Asana with their true timestamps.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--name', type=str, help='Filter producers by name substring')
        parser.add_argument('--purge-bulk', action='store_true',
            help='Delete bulk-imported comments (timestamp 2026-04-15 21:24:* UTC) before syncing')

    def handle(self, *args, **opts):
        dry      = opts['dry_run']
        name_f   = opts.get('name') or ''
        purge    = opts['purge_bulk']

        davit = User.objects.filter(username='davit.bagashvili').first()

        if purge:
            self.stdout.write('Purging bulk-imported comments (2026-04-15 21:24 UTC)…')
            start = datetime(2026, 4, 15, 21, 24, 0, tzinfo=dt_tz.utc)
            end   = datetime(2026, 4, 15, 21, 25, 0, tzinfo=dt_tz.utc)
            qs = ProducerComment.objects.filter(created_at__gte=start, created_at__lt=end)
            n  = qs.count()
            self.stdout.write(f'  {n} bulk comments to delete')
            if not dry:
                qs.delete()

        self.stdout.write('Fetching Asana tasks…')
        asana_tasks = fetch_asana_tasks()
        self.stdout.write(f'  {len(asana_tasks)} tasks total')

        # Build name-lookup
        by_name = {}
        for t in asana_tasks:
            n = (t.get('name') or '').strip()
            if n:
                by_name.setdefault(n.lower(), []).append(t)

        producers = Producer.objects.all()
        if name_f:
            producers = producers.filter(name__icontains=name_f)

        total_imported   = 0
        total_already    = 0
        total_unmatched  = 0
        per_producer     = []

        for p in producers:
            # Find Asana task — by stored gid, else by name lookup
            task = None
            if p.asana_task_gid:
                task = next((t for t in asana_tasks if t.get('gid') == p.asana_task_gid), None)
            if not task:
                cands = by_name.get(p.name.lower(), [])
                if cands:
                    task = cands[0]
                    if not p.asana_task_gid and not dry:
                        p.asana_task_gid = task['gid']
                        p.save(update_fields=['asana_task_gid'])
            if not task:
                total_unmatched += 1
                continue

            # Fetch stories
            try:
                stories = fetch_task_stories(task['gid'])
            except Exception as e:
                self.stdout.write(f'  ! Error fetching stories for {p.name}: {e}')
                continue

            # Filter only real user comments
            comments = [s for s in stories
                        if s.get('type') == 'comment'
                        and (s.get('resource_subtype') or 'comment_added') == 'comment_added'
                        and (s.get('text') or '').strip()]

            imported_now = 0
            for s in comments:
                story_gid = s.get('gid')
                if not story_gid:
                    continue
                created_at = parse_datetime(s.get('created_at') or '')
                if not created_at:
                    continue
                text = (s.get('text') or '').strip()

                existing = ProducerComment.objects.filter(asana_story_id=story_gid).first()
                if existing:
                    # Update timestamp/text if drifted
                    fields = []
                    if existing.created_at != created_at:
                        existing.created_at = created_at
                        fields.append('created_at')
                    if existing.text != text:
                        existing.text = text
                        fields.append('text')
                    if existing.producer_id != p.id:
                        existing.producer = p
                        fields.append('producer')
                    if fields and not dry:
                        ProducerComment.objects.filter(pk=existing.pk).update(
                            **{f: getattr(existing, f) for f in fields}
                        )
                    total_already += 1
                    continue

                # Create new
                if not dry:
                    c = ProducerComment.objects.create(
                        producer=p,
                        text=text,
                        asana_story_id=story_gid,
                        author=davit,
                    )
                    # Override auto_now_add timestamp
                    ProducerComment.objects.filter(pk=c.pk).update(created_at=created_at)
                imported_now += 1

            total_imported += imported_now
            per_producer.append((p.name, len(comments), imported_now))

        # Report
        self.stdout.write(self.style.SUCCESS(
            f'\nSync done. imported={total_imported}  already_present={total_already}  unmatched_producers={total_unmatched}'
        ))
        if per_producer:
            self.stdout.write('\nPer-producer (asana_total / new_imported):')
            per_producer.sort(key=lambda x: -x[2])
            for name, total, new in per_producer[:30]:
                self.stdout.write(f'  {name}: {total} comments in Asana, {new} newly imported')
