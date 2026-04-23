"""
Producer Weekly Report — onboarding-funnel snapshot since the previous run.

Pipeline:
  1. Resolve period:
       period_from = previous DONE report's period_to (chained, NOT calendar week)
       period_to   = build start time
       Fallback for first run: period_to - 7 days.
  2. Collect:
       - New onboarding producers created in window.
       - Existing producers (created before window) whose stage moved during
         the window OR who received any comments during the window.
  3. Compress producer state + comments into compact LLM input.
  4. LLM "significance filter": classify each producer's activity as
       "significant" or "trivial". Trivial = follow-up reminders, generic
       check-ins, contact requests, "called again", etc. Significant = stage
       progression, terms/price changes, agreement reached, blockers,
       refusals, key decisions, breakthrough.
  5. Persist filtered cards + executive summary + markdown.

The LLM call is wrapped with retry/backoff. The Django thread is daemonised
and registered with auto-retry so transient failures self-heal.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import timedelta
from typing import Any, Dict, List

from django.db import close_old_connections
from django.utils import timezone

from contacts.insights import (
    INSIGHTS_FALLBACK_MODELS,
    INSIGHTS_MODEL,
    OPENAI_API_KEY,
    _polish_json_text,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]
DEFAULT_LOOKBACK_DAYS = 7
MAX_COMMENTS_PER_PRODUCER = 20      # safety cap to keep prompt size sane
MAX_PRODUCERS_PER_REPORT = 250      # safety cap on producers analysed
MAX_COMMENT_CHARS = 600             # truncate per-comment text

ONBOARDING_STAGE_LABELS = {
    'interest':           'Interest',
    'in_communication':   'In Communication',
    'terms_negotiation':  'Negotiation',
    'negotiation':        'Signing Contract',
    'contract_signed':    'Contract Signed',
    'on_platform':        'On the Platform',
    'stopped':            'Stopped',
}


SIGNIFICANCE_PROMPT = """You are an onboarding-funnel analyst for AskAyurveda's producer (manufacturer) team.

Your team is bringing Ayurvedic-medicine producers ONTO our platform. You receive a list of producers who had any activity in the reporting window (new producers, stage changes, or new comments from managers).

Your job is to filter for SIGNIFICANT business changes only and write a concise summary card per producer.

────────────────────────────────────────────────────────────────────
WHAT COUNTS AS SIGNIFICANT (keep these)
────────────────────────────────────────────────────────────────────
- The producer moved to a new funnel stage (interest → communication → negotiation → contract → on platform → stopped). ALWAYS significant.
- New producer just added to onboarding. ALWAYS significant (label = "new_producer").
- Concrete commercial / legal progress: terms agreed or rejected, commission % discussed, price/MOQ negotiated, contract drafted/sent/signed, exclusivity agreed.
- Decisions: producer agreed to join, refused, paused, asked for time to decide, requested specific changes to the deal.
- Blockers identified or unblocked: legal review delay, missing documents, certifications missing, regulatory issue, capacity issue.
- Key contact secured/changed: reached the decision-maker, founder responded, owner involved, manager replaced.
- Operational milestones toward go-live: first product list received, catalog uploaded, samples sent, payment terms confirmed.
- Material strategic info: producer revealed competitive intel, mentioned existing distributor exclusivity, shared volume figures, asked about platform fees.
- Loss / churn: producer stopped responding for >2 weeks AND manager flagged it; or moved to "stopped" stage.

────────────────────────────────────────────────────────────────────
WHAT IS TRIVIAL (drop these — DO NOT make a card)
────────────────────────────────────────────────────────────────────
- "Called/wrote/messaged again" without new info or commitment.
- "Sent a reminder" / "followed up" / "ping" / "no response yet".
- "Asked for a contact / WhatsApp number / email".
- Generic check-ins or scheduling small talk ("let's connect next week").
- Manager status updates with no producer-side change ("will try again tomorrow").
- Internal task notes ("uploaded to Asana", "added to spreadsheet").
- Routine acknowledgements ("ok, noted", "thanks").

If a producer has ONLY trivial activity in the window → DROP THEM. Do not pad the report.

────────────────────────────────────────────────────────────────────
OUTPUT
────────────────────────────────────────────────────────────────────
Return JSON ONLY (no markdown fences) with this exact shape:

{{
  "executive_summary": "2-4 English sentences capturing the headline movement of the week (how many new, how many advanced, biggest wins, biggest blockers).",
  "highlights": [
    "1-5 short bullet strings (the most important things the team should look at first, ordered by urgency)"
  ],
  "cards": [
    {{
      "producer_id": <int>,
      "kind": "new_producer" | "stage_change" | "commercial_progress" | "blocker" | "loss" | "key_decision" | "milestone" | "other",
      "headline": "<=80 char English summary of WHAT changed (e.g. 'Signed contract after 6 weeks of negotiation')",
      "detail": "1-3 English sentences. Quote what was actually said by the producer or the manager when relevant. State the BUSINESS impact, not the manager activity.",
      "stage_change": {{ "from": "<stage_value or null>", "to": "<stage_value or null>" }} | null,
      "evidence_comment_ids": [<int>, ...]
    }}
  ]
}}

Rules:
- Every card MUST have a producer_id matching one in the input.
- evidence_comment_ids MUST reference comment ids from THAT producer's comments array.
- If kind = "new_producer" → no evidence comments needed (set [] is fine).
- Sort `cards` by importance: new_producer + stage_change first, then commercial_progress, then blockers, then milestones, then key_decision, then loss, then other.
- If the input is empty OR every producer is trivial → return {{ "executive_summary": "No significant onboarding-funnel changes this period.", "highlights": [], "cards": [] }}.
- Do NOT invent stage names — use only the values shown in the producer record.
- Do NOT mention manager activity unless it represents a producer-side outcome.

────────────────────────────────────────────────────────────────────
INPUT
────────────────────────────────────────────────────────────────────
Period: from {period_from} to {period_to}

Producers (JSON):
{producers_json}
"""


def _truncate(s: str, limit: int) -> str:
    s = (s or '').strip()
    if len(s) <= limit:
        return s
    return s[: limit - 1].rstrip() + '…'


def _resolve_period(now=None) -> tuple:
    """
    period_from = period_to of latest DONE report (chained).
    First run → now() - DEFAULT_LOOKBACK_DAYS.
    """
    from .models import ProducerWeeklyReport

    now = now or timezone.now()
    last = (
        ProducerWeeklyReport.objects
        .filter(status=ProducerWeeklyReport.STATUS_DONE)
        .order_by('-period_to').first()
    )
    if last and last.period_to:
        return last.period_to, now
    return now - timedelta(days=DEFAULT_LOOKBACK_DAYS), now


def _collect_window(period_from, period_to) -> Dict[str, Any]:
    """
    Build the compressed payload for the LLM.

    A producer is included if any of these is true within the window:
      - created_at in window (NEW)
      - stage_changed_at in window AND created_at < period_from (stage moved)
      - has any comment in the window
    """
    from .models import Producer, ProducerComment

    new_producers = list(
        Producer.objects.filter(
            funnel=Producer.FUNNEL_ONBOARDING,
            created_at__gte=period_from, created_at__lt=period_to,
        ).select_related('assigned_to', 'created_by')
    )
    new_ids = {p.id for p in new_producers}

    stage_moved = list(
        Producer.objects.filter(
            funnel=Producer.FUNNEL_ONBOARDING,
            stage_changed_at__gte=period_from, stage_changed_at__lt=period_to,
            created_at__lt=period_from,
        ).select_related('assigned_to')
    )
    stage_moved_ids = {p.id for p in stage_moved}

    comments_qs = (
        ProducerComment.objects.filter(
            created_at__gte=period_from, created_at__lt=period_to,
            producer__funnel=Producer.FUNNEL_ONBOARDING,
        )
        .select_related('producer', 'author')
        .order_by('created_at')
    )

    comments_by_pid: Dict[int, List[ProducerComment]] = {}
    for c in comments_qs.iterator():
        comments_by_pid.setdefault(c.producer_id, []).append(c)

    commented_ids = set(comments_by_pid.keys())

    relevant_ids = (new_ids | stage_moved_ids | commented_ids)

    if not relevant_ids:
        return {
            'producers_payload': [],
            'new_count': 0,
            'changed_count': 0,
            'comments_count': 0,
        }

    # Pull the missing Producer rows for commented producers we haven't loaded.
    already = {p.id: p for p in (new_producers + stage_moved)}
    missing_ids = relevant_ids - set(already)
    if missing_ids:
        for p in Producer.objects.filter(id__in=missing_ids).select_related('assigned_to'):
            already[p.id] = p

    # Cap to MAX_PRODUCERS_PER_REPORT, prioritising new + stage-moved.
    sorted_ids = (
        sorted(new_ids)
        + sorted(stage_moved_ids - new_ids)
        + sorted(commented_ids - new_ids - stage_moved_ids)
    )
    if len(sorted_ids) > MAX_PRODUCERS_PER_REPORT:
        sorted_ids = sorted_ids[:MAX_PRODUCERS_PER_REPORT]

    payload: List[Dict[str, Any]] = []
    total_comments = 0
    for pid in sorted_ids:
        p = already.get(pid)
        if not p:
            continue
        comments = comments_by_pid.get(pid, [])[:MAX_COMMENTS_PER_PRODUCER]
        comment_blocks = []
        for c in comments:
            author = (c.author.get_full_name() or c.author.username) if c.author else 'unknown'
            comment_blocks.append({
                'id': c.id,
                'at': c.created_at.isoformat(),
                'author': author,
                'text': _truncate(c.text, MAX_COMMENT_CHARS),
            })
        total_comments += len(comment_blocks)

        payload.append({
            'producer_id': p.id,
            'name': p.name or '',
            'company': p.company or '',
            'is_new_in_window': p.id in new_ids,
            'stage_now': p.stage,
            'stage_label_now': ONBOARDING_STAGE_LABELS.get(p.stage, p.stage),
            'stage_changed_in_window': p.id in stage_moved_ids,
            'stage_changed_at': p.stage_changed_at.isoformat() if p.stage_changed_at else None,
            'created_at': p.created_at.isoformat(),
            'assigned_to': (p.assigned_to.get_full_name() or p.assigned_to.username) if p.assigned_to else None,
            'priority': p.priority,
            'cooperation_potential': p.cooperation_potential,
            'communication_status': p.communication_status,
            'next_step': _truncate(p.next_step or '', 200),
            'notes': _truncate(p.notes or '', 400),
            'comments': comment_blocks,
        })

    return {
        'producers_payload': payload,
        'new_count': len(new_ids),
        'changed_count': len((stage_moved_ids | commented_ids) - new_ids),
        'comments_count': total_comments,
    }


def _build_markdown(report, payload: Dict[str, Any]) -> str:
    pf = report.period_from.strftime('%Y-%m-%d %H:%M')
    pt = report.period_to.strftime('%Y-%m-%d %H:%M')
    lines: List[str] = [
        f'## Producer Weekly Report — {pf} → {pt} IST',
        '',
        f'**Coverage:** {report.total_new_producers} new · '
        f'{report.total_changed_producers} with significant change · '
        f'{report.total_comments_considered} comments analysed',
        '',
    ]
    summary = (payload.get('executive_summary') or '').strip()
    if summary:
        lines.append('### Executive summary')
        lines.append(summary)
        lines.append('')

    highlights = payload.get('highlights') or []
    if highlights:
        lines.append('### Highlights')
        for h in highlights:
            lines.append(f'- {h}')
        lines.append('')

    cards = payload.get('cards') or []
    if not cards:
        lines.append('_No significant changes in this period._')
        return '\n'.join(lines).strip()

    new_cards = [c for c in cards if c.get('kind') == 'new_producer']
    other = [c for c in cards if c.get('kind') != 'new_producer']

    if new_cards:
        lines.append(f'### New producers ({len(new_cards)})')
        for c in new_cards:
            lines.append(f"- **{c.get('headline', '')}** · _{c.get('producer_name', '')}_")
            if c.get('detail'):
                lines.append(f"  {c['detail']}")
        lines.append('')

    if other:
        lines.append(f'### Significant changes ({len(other)})')
        for c in other:
            sc = c.get('stage_change') or {}
            sc_str = ''
            if sc.get('from') or sc.get('to'):
                a = ONBOARDING_STAGE_LABELS.get(sc.get('from'), sc.get('from') or '?')
                b = ONBOARDING_STAGE_LABELS.get(sc.get('to'), sc.get('to') or '?')
                sc_str = f" · {a} → {b}"
            lines.append(f"- **{c.get('headline', '')}** · _{c.get('producer_name', '')}_{sc_str}")
            if c.get('detail'):
                lines.append(f"  {c['detail']}")
        lines.append('')

    return '\n'.join(lines).strip()


def build_weekly_report(report_id: int, force: bool = False) -> None:
    """Generate or refresh a ProducerWeeklyReport row."""
    if not OPENAI_API_KEY:
        logger.warning('OPENAI_API_KEY not set — weekly report skipped')
        return

    from openai import OpenAI
    from .models import ProducerWeeklyReport, Producer  # noqa: F401  (Producer used implicitly)

    close_old_connections()
    try:
        report = ProducerWeeklyReport.objects.filter(pk=report_id).first()
        if not report:
            return
        if not force and report.status == ProducerWeeklyReport.STATUS_DONE:
            return

        report.status = ProducerWeeklyReport.STATUS_PROCESSING
        report.last_attempt_at = timezone.now()
        report.save(update_fields=['status', 'last_attempt_at', 'updated_at'])

        collected = _collect_window(report.period_from, report.period_to)
        producers_payload = collected['producers_payload']

        # Empty window — no producers / comments at all.
        if not producers_payload:
            report.summary_text = 'No producer activity in this period.'
            report.new_producers_json = []
            report.changes_json = []
            report.total_new_producers = 0
            report.total_changed_producers = 0
            report.total_comments_considered = 0
            report.rendered_markdown = _build_markdown(report, {
                'executive_summary': report.summary_text,
                'highlights': [],
                'cards': [],
            })
            report.status = ProducerWeeklyReport.STATUS_DONE
            report.completed_at = timezone.now()
            report.last_error = ''
            report.retries = 0
            report.save()
            logger.info('ProducerWeeklyReport %s done — empty window', report_id)
            return

        prompt = SIGNIFICANCE_PROMPT.format(
            period_from=report.period_from.isoformat(),
            period_to=report.period_to.isoformat(),
            producers_json=json.dumps(producers_payload, ensure_ascii=False),
        )

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                client = OpenAI(api_key=OPENAI_API_KEY)
                models_to_try = [INSIGHTS_MODEL] + [
                    m for m in INSIGHTS_FALLBACK_MODELS if m != INSIGHTS_MODEL
                ]
                message = None
                model_used = None
                model_errors: List[str] = []
                for mdl in models_to_try:
                    try:
                        message = client.chat.completions.create(
                            model=mdl,
                            max_tokens=4096,
                            response_format={'type': 'json_object'},
                            messages=[
                                {'role': 'system', 'content': 'Return valid JSON only.'},
                                {'role': 'user', 'content': prompt},
                            ],
                        )
                        model_used = mdl
                        break
                    except Exception as me:
                        msg = str(me)
                        model_errors.append(f'{mdl}: {msg[:200]}')
                        if not any(t in msg.lower() for t in ('model', 'not found', 'does not exist', 'unsupported', 'permission')):
                            raise
                        logger.warning('WeeklyReport model %s unavailable: %s', mdl, msg[:200])
                if message is None:
                    raise RuntimeError('All models failed: ' + ' | '.join(model_errors))

                raw = _polish_json_text(message.choices[0].message.content or '')
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError('Model returned non-object JSON')

                cards_raw = data.get('cards') or []
                producer_lookup = {p['producer_id']: p for p in producers_payload}

                new_cards: List[Dict[str, Any]] = []
                change_cards: List[Dict[str, Any]] = []
                seen_pids: set = set()

                for card in cards_raw:
                    if not isinstance(card, dict):
                        continue
                    try:
                        pid = int(card.get('producer_id'))
                    except (TypeError, ValueError):
                        continue
                    if pid not in producer_lookup or pid in seen_pids:
                        continue
                    seen_pids.add(pid)
                    p = producer_lookup[pid]

                    sc = card.get('stage_change') or None
                    if isinstance(sc, dict):
                        sc = {
                            'from': sc.get('from') if sc.get('from') in ONBOARDING_STAGE_LABELS or sc.get('from') is None else None,
                            'to': sc.get('to') if sc.get('to') in ONBOARDING_STAGE_LABELS or sc.get('to') is None else None,
                        }
                        if not sc.get('from') and not sc.get('to'):
                            sc = None
                    else:
                        sc = None

                    evidence_ids: List[int] = []
                    valid_comment_ids = {c['id'] for c in p.get('comments', [])}
                    for x in (card.get('evidence_comment_ids') or []):
                        try:
                            ix = int(x)
                        except (TypeError, ValueError):
                            continue
                        if ix in valid_comment_ids:
                            evidence_ids.append(ix)

                    out_card = {
                        'producer_id': pid,
                        'producer_name': p.get('name') or '',
                        'producer_company': p.get('company') or '',
                        'assigned_to': p.get('assigned_to'),
                        'stage_now': p.get('stage_now'),
                        'stage_label_now': p.get('stage_label_now'),
                        'kind': str(card.get('kind') or 'other').lower(),
                        'headline': str(card.get('headline') or '').strip()[:200],
                        'detail': str(card.get('detail') or '').strip(),
                        'stage_change': sc,
                        'evidence_comment_ids': evidence_ids,
                    }
                    if out_card['kind'] == 'new_producer':
                        new_cards.append(out_card)
                    else:
                        change_cards.append(out_card)

                payload = {
                    'executive_summary': str(data.get('executive_summary') or '').strip(),
                    'highlights': [str(x).strip() for x in (data.get('highlights') or []) if str(x).strip()][:5],
                    'cards': new_cards + change_cards,
                    'model_used': model_used,
                }

                report.summary_text = payload['executive_summary']
                report.new_producers_json = new_cards
                report.changes_json = change_cards
                report.total_new_producers = collected['new_count']
                report.total_changed_producers = collected['changed_count']
                report.total_comments_considered = collected['comments_count']
                report.rendered_markdown = _build_markdown(report, payload)
                report.status = ProducerWeeklyReport.STATUS_DONE
                report.completed_at = timezone.now()
                report.last_error = ''
                report.retries = 0
                report.save()
                logger.info(
                    'ProducerWeeklyReport %s done — %d new, %d significant changes (analysed %d producers)',
                    report_id, len(new_cards), len(change_cards), len(producers_payload),
                )
                return
            except Exception as e:
                last_error = e
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
                logger.warning(
                    'WeeklyReport attempt %s/%s failed for #%s: %s',
                    attempt + 1, MAX_RETRIES, report_id, e,
                )
                time.sleep(delay)

        from django.db.models import F
        ProducerWeeklyReport.objects.filter(pk=report_id).update(
            status=ProducerWeeklyReport.STATUS_FAILED,
            last_error=repr(last_error)[:4000] if last_error else 'unknown',
            retries=F('retries') + 1,
            last_attempt_at=timezone.now(),
        )
        logger.error('ProducerWeeklyReport %s failed: %s', report_id, last_error)
    finally:
        close_old_connections()


def build_weekly_report_background(report_id: int):
    close_old_connections()
    try:
        build_weekly_report(report_id, force=False)
    except Exception as e:
        logger.exception('build_weekly_report_background crashed: %s', e)
    finally:
        close_old_connections()


def enqueue_weekly_report(report_id: int):
    threading.Thread(
        target=build_weekly_report_background, args=(report_id,), daemon=True,
    ).start()


def create_and_run_weekly_report(triggered_by: str = 'scheduled', user=None):
    """
    Resolve the chained period, create a pending row and kick off the build.

    Returns the (newly created) ProducerWeeklyReport row.
    """
    from .models import ProducerWeeklyReport

    period_from, period_to = _resolve_period()

    # Avoid spawning duplicates if the previous job is still running.
    inflight = ProducerWeeklyReport.objects.filter(
        status__in=[ProducerWeeklyReport.STATUS_PENDING, ProducerWeeklyReport.STATUS_PROCESSING],
    ).order_by('-created_at').first()
    if inflight:
        return inflight

    report = ProducerWeeklyReport.objects.create(
        period_from=period_from,
        period_to=period_to,
        status=ProducerWeeklyReport.STATUS_PENDING,
        triggered_by=triggered_by,
        created_by=user if (user and getattr(user, 'is_authenticated', False)) else None,
    )
    enqueue_weekly_report(report.pk)
    return report
