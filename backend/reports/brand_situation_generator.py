"""
Generates weekly BrandSituationReport.
For each active brand (In Communication / Negotiation / Contract Signed) AI determines:
- Was there a REAL fundamental change this week vs prior weeks?
- What is the current status (concrete, from comments)?

Runs every Friday 15:00 IST (Asia/Kolkata) via APScheduler.
"""
import os
import json
import time
import threading
import pytz
from datetime import datetime, timedelta, date
from django.utils import timezone
from django.db import close_old_connections

IST_TZ = pytz.timezone('Asia/Kolkata')

ACTIVE_STAGES = ['in_communication', 'terms_negotiation', 'negotiation', 'contract_signed']

STAGE_LABELS = {
    'in_communication':  'In Communication',
    'terms_negotiation': 'Negotiation',
    'negotiation':       'Signing Contract',
    'contract_signed':   'Contract Signed',
}

_MAX_RETRIES = 5
_RETRY_DELAYS = [10, 30, 60, 120, 300]


def _week_bounds_ist(reference=None):
    """Return (monday_date, sunday_date) of the week containing `reference` in IST."""
    now = (reference or datetime.now(IST_TZ)).astimezone(IST_TZ)
    monday = (now - timedelta(days=now.weekday())).date()
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _gather_brand_history(producer, current_week_monday):
    """
    Gather full comment history for one brand grouped by week.
    Fills EVERY week between the first comment (or producer creation) and `current_week_monday`,
    even if the brand had zero activity that week (empty list).

    Returns a tuple (history_by_week, start_monday).
    """
    from producers.models import ProducerComment
    comments = list(
        ProducerComment.objects
        .filter(producer=producer)
        .order_by('created_at')
    )
    by_week = {}
    for c in comments:
        ist_dt = c.created_at.astimezone(IST_TZ)
        monday = (ist_dt - timedelta(days=ist_dt.weekday())).date()
        by_week.setdefault(monday.isoformat(), []).append({
            'date': ist_dt.strftime('%d.%m.%Y'),
            'text': (c.text or '')[:400],
        })

    # Determine the start week: EARLIEST of (producer.created_at, first comment).
    # Producer.created_at is when work on the funnel started; using the min
    # guarantees we count every week we have been "onboarding" them.
    candidate_dts = []
    if producer.created_at:
        candidate_dts.append(producer.created_at.astimezone(IST_TZ))
    if comments:
        candidate_dts.append(comments[0].created_at.astimezone(IST_TZ))
    if not candidate_dts:
        candidate_dts.append(datetime.now(IST_TZ))
    first_dt = min(candidate_dts)
    start_monday = (first_dt - timedelta(days=first_dt.weekday())).date()

    # Fill every Monday between start_monday and current_week_monday inclusive.
    cursor = start_monday
    while cursor <= current_week_monday:
        by_week.setdefault(cursor.isoformat(), [])
        cursor += timedelta(days=7)

    return dict(sorted(by_week.items())), start_monday


def _weeks_in_funnel(start_monday, current_monday):
    """Inclusive count of weeks the producer has been in the funnel.

    Both args are dates of the Monday of the respective weeks (IST).
    Always >= 1 (the first week itself counts).
    """
    if not start_monday:
        return 1
    days = (current_monday - start_monday).days
    return max(1, days // 7 + 1)


SYSTEM_PROMPT = """You are a factual deal-log writer for our Ayurveda manufacturer onboarding team.
For each brand you receive comments grouped by week. The keys in weeks_json represent EVERY week from the start of work with this brand up to today. An empty array [] means there were ZERO comments that week.

═══════════════════════════════════════════════════════════════
GOLDEN RULE: FACTS ONLY. NO EVALUATION. NO COACHING. NO BLAME.
═══════════════════════════════════════════════════════════════
Your only job is to write a tight English description of what happened that week, paraphrasing the actual comments. The COLOR (changed / wasted_side) is what conveys "good vs bad week" — not the wording. The text must NEVER say things like:
   ❌ "this minimal effort is insufficient"
   ❌ "we should have set a deadline"
   ❌ "we did not push hard enough"
   ❌ "the lack of progress is on us"
   ❌ "the lack of initiative reflects poorly on our team"
   ❌ "we did not escalate further"
   ❌ "we failed to …", "we missed …", "we wasted …"
   ❌ "we did not manage to …"
   ❌ "operator did X", "the operator …"
   ❌ Any opinion, recommendation, lesson, or scolding.
Just describe the facts. The color and the section header already tell the reader whether the week was strong or weak — DO NOT pile on with judgment.

═══════════════════════════════════════════════════════════════
CLASSIFICATION (drives color only — not wording)
═══════════════════════════════════════════════════════════════
For EACH week pick ONE of:

1. changed=true (REAL deal progress) — wasted_side=null
   Substantive forward motion: meeting held with real agreements, margin/timing/terms agreed, signed documents or price list received, contract signed, decision-maker secured, funnel stage changed, etc.

2. changed=false, wasted_side="ours" (RED — week passed on our side)
   Default for any week where nothing concrete came back from the partner. Includes empty weeks, "sent a reminder / follow-up / proposal / LinkedIn invite", "waiting for response", "will send next week".

3. changed=false, wasted_side="partner" (ORANGE — week blocked on partner side)
   Use only when the partner EXPLICITLY caused the delay: "they asked for more time", "they postponed the meeting", "manager on vacation", or 3+ documented reminders ignored after a clear escalation. ONE outbound ping with no answer = "ours".

═══════════════════════════════════════════════════════════════
SUMMARY WRITING RULES (per week)
═══════════════════════════════════════════════════════════════
- Language: ENGLISH ONLY. Never Russian.
- Length: 80–250 characters. Short and concrete. No filler.
- Voice: third-person factual ("We sent …", "Mona shared …"). Never "the operator". Never "we / our team did X poorly".
- Content: paraphrase the actual comments of that week into clean English. Mention names/roles when they appear.
- If the week is empty ([]): leave summary as an empty string "" — the Python layer fills the canned empty-week sentence.
- DO NOT prepend any standard "We did not manage to secure an update…" sentence — that prefix has been removed. Just describe what happened.
- DO NOT add evaluative tail-sentences. End on a fact, not an opinion.

EXAMPLES (good vs bad):

GREEN week (changed=true):
   ✅ "Mona, VP at Kairali, ran a call on Dec 8: margin agreed at 28%, monthly payments, dispatch 24h + 2–7 day delivery. She asked for a detailed deck and we sent it the same day; next call locked for SKU alignment."

RED week (wasted_side="ours") — comment log says: "Sent out hello message to stay in touch, soon will recheck the Margin topic":
   ✅ "We sent a hello message to stay in touch and noted that the margin topic will be revisited soon. No other activity this week."
   ❌ "We merely sent a hello message to stay in touch — this minimal effort is insufficient to drive our negotiations with Jiva. We should have set a deadline …"
   ❌ "We did not manage to secure an update from this producer this week. Despite recent reminders, we still failed to …"

RED week (wasted_side="ours") — comment log says: "Pinged Mona on WhatsApp, no reply yet":
   ✅ "We pinged Mona on WhatsApp; no reply received this week."
   ❌ "We pinged Mona on WhatsApp but no reply came in — we did not push hard enough on our side."

ORANGE week (wasted_side="partner") — comment log says "Mona postponed the call to next week":
   ✅ "Mona postponed the integration call to next week."
   ❌ "Mona postponed the call — the delay is objectively on the Kairali side and we should have escalated."

📊 READINESS PERCENT (very important — used to rank brands inside the same stage):
You must also output `readiness_percent` (integer 0–100). 100% = brand is fully on platform / live with first orders. The scale is anchored to the funnel stage:
  • Interest / first contact: 0–10
  • In Communication, sporadic replies: 10–25
  • In Communication, active dialogue with decision-maker: 25–40
  • Negotiation / "Signing Contract", commercial terms agreed: 40–60
  • Negotiation, contract draft sent / under review: 60–75
  • Contract Signed, contract just signed: 75–85
  • Contract Signed, integration in progress (logistics, listings, test orders): 85–95
  • On Platform → ALWAYS exactly 100
Within the SAME stage, push the % higher when there is consistent recent forward motion (last 2–3 weeks GREEN), and lower when the brand has been stuck in red weeks recently. The number lets us rank brands inside one stage from "almost done" to "barely moving".

📝 CURRENT_STATUS (very detailed, this is the most-read field):
- Length: 350–600 characters. Be EXHAUSTIVE.
- Cover, in order: live contact (name + role), what was the most recent concrete event with date, what is currently in flight (contract / integration / docs / test order / pricing), what specific deliverable we are waiting for and from whom, what the next planned step is and the timeline. Mention any open blockers.
- No filler. No generic "waiting for response" without naming the person and the artefact.

RETURN JSON in EXACTLY this shape (no markdown, no explanations, no truncation):
__JSON_SHAPE__

Brand: __BRAND_NAME__
Stage: __STAGE__
Comments grouped by week (key = Monday of the week YYYY-MM-DD; empty [] = zero activity):
__WEEKS_JSON__
"""

# This shape is inserted as plain text (avoids .format() collisions with braces).
_JSON_SHAPE_EXAMPLE = '''{
  "weeks": {
    "2025-12-08": {"changed": true,  "wasted_side": null,      "summary": "Mona (VP, Kairali) ran a call on Dec 8: margin agreed at 28%, monthly payments, dispatch 24h + 2-7 day delivery. She asked for a detailed deck and we sent it the same day."},
    "2025-12-15": {"changed": false, "wasted_side": "ours",    "summary": "We sent two follow-up emails to Mona and a LinkedIn message to the new e-comm contact. No replies received this week."},
    "2025-12-22": {"changed": false, "wasted_side": "ours",    "summary": ""},
    "2025-12-29": {"changed": false, "wasted_side": "partner", "summary": "Mona replied that she needs a couple more days for internal confirmation, pushing the Dec 18 deadline."}
  },
  "current_status": "Detailed 350-600 char status. Live contact: Mona Walia, VP. Most recent event: Mar 25 — contract signed by both sides. Currently in flight: integration kickoff and order-flow setup; we requested order-flow Google Drive shared documents on Apr 16 and Mona promised them within a day. Awaiting from Mona: order-flow docs and confirmation of the integration call slot with Astha. Next planned step: integration call this week to align logistics, listings and the first test order; no open blockers from the partner so far.",
  "readiness_percent": 88
}'''


def _analyze_brand_with_ai(brand_name, stage_label, weeks_data):
    from openai import OpenAI

    weeks_json = json.dumps(weeks_data, ensure_ascii=False, indent=2)
    # Plain string replacement to avoid .format() collisions with JSON braces.
    prompt = (
        SYSTEM_PROMPT
        .replace('__JSON_SHAPE__', _JSON_SHAPE_EXAMPLE)
        .replace('__BRAND_NAME__', brand_name)
        .replace('__STAGE__', stage_label)
        .replace('__WEEKS_JSON__', weeks_json)
    )

    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY', ''))
            resp = client.chat.completions.create(
                model='gpt-4o-mini',
                max_tokens=8192,
                response_format={'type': 'json_object'},
                messages=[{'role': 'user', 'content': prompt}],
            )
            raw = resp.choices[0].message.content.strip()
            return json.loads(raw)
        except Exception as e:
            last_error = e
            time.sleep(_RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)])

    return {'error': str(last_error), 'weeks': {}, 'current_status': 'Analysis error'}


EMPTY_WEEK_PHRASE = 'No activity was logged this week.'

# Markers that prove partner DID something tangible (justifies wasted_side="partner")
_PARTNER_ACTION_MARKERS = [
    # explicit partner verbs
    'they said', 'they answered', 'they responded', 'they replied',
    'they asked', 'they confirmed', 'they postponed', 'they rescheduled',
    'they promised', 'they shared', 'they sent', 'they provided',
    'partner asked', 'partner said', 'they wished', 'they need',
    'they declined', 'they pushed', 'partner not available', 'partner is busy',
    # passive markers indicating partner action
    'rescheduled', 'postponed', 'delayed', 'meeting moved',
    'asked for more time', 'asked for couple of days', 'asked for time',
    'on vacation', 'asked for amendment', 'asked one more time',
    'agreed mostly', 'agreed on terms', 'confirmed the meeting',
    'meeting confirmed', 'shared post-call', 'shared documents',
    'shared comments', 'provided comments', 'provided some comments',
    'received an email', 'received email', 'received updated',
    'signed contract', 'contract signed', 'signed from',
    'accepted', 'they accepted', 'accepted invite', 'accepted contact',
    'responded', 'feedback', 'reply received', 'reply from',
    'requested', 'requested more', 'requested amendment',
    'pushed deadline', 'declined offer',
    # named-person verbs (Mona/Sandeep/etc.) — these usually mean partner actor
    'mona shared', 'mona contacted', 'mona promised', 'mona confirmed',
    'mona asked', 'mona wrote', 'mona responded',
    # Russian
    'они ответили', 'они сказали', 'они подтвердили', 'они отложили',
    'они перенесли', 'они попросили', 'партнёр ответил', 'партнёр попросил',
    'отказались', 'просят время', 'они просят', 'перенесена', 'перенесено',
    'отложили', 'согласились', 'подписали', 'согласовано',
]

# Markers that indicate ONLY our-side activity ("sent and waiting")
_OURS_ONLY_MARKERS = [
    'sent reminder', 'sent a reminder', 'sent another reminder',
    'sent follow', 'sent follow-up', 'pinged', 'reminded',
    'sent proposal', 'sent presentation', 'sent contract',
    'sent message', 'sent email', 'sent linkedin', 'sent invite',
    'reached out', 'contacted', 'asked for a call',
    'no response', 'no reply', 'awaiting reply', 'awaiting response',
    'waiting for response', 'waiting for reply', 'waiting for confirmation',
    'will follow up', 'will send', 'will share', 'will ping',
    # Russian
    'отправили напоминание', 'отправили follow', 'пинганули',
    'нет ответа', 'ждём ответа', 'ожидаем ответа',
    'отправили презентацию', 'отправили предложение',
]


def _has_partner_action(comments_for_week):
    blob = ' '.join((c.get('text', '') or '').lower() for c in comments_for_week)
    return any(m in blob for m in _PARTNER_ACTION_MARKERS)


import re as _re

_CYRILLIC_RE = _re.compile(r'[\u0400-\u04FF]')

# Phrases that are NEVER allowed in any summary (blame, slang, evaluation,
# coaching, hallucinated words). Anything matching kills the whole sentence.
_BANNED_FRAGMENTS = [
    # operator blame
    'operator did', 'operator failed', 'operator noted', 'operator only',
    'operator was', 'operator has', 'operator is',
    'the operator', 'an operator',
    'оператор', 'оператр',
    # russian slang
    'просран', 'спортивн',
    # generic blame / evaluation words
    'wasted', 'lazy', 'did nothing',
    'ineffective', 'inefficient', 'неэффект',
    # judgement / coaching style — strictly forbidden by user
    'minimal effort', 'insufficient', 'is insufficient',
    'we should have', 'should have set', 'should have escalated',
    'we did not push', 'did not push hard', 'not push hard enough',
    'lack of progress is on us', 'lack of initiative',
    'reflects poorly', 'on our team',
    'we did not escalate', 'did not escalate further',
    'did not lock a hard deadline', 'lock a hard deadline',
    'we did not manage', 'did not manage to secure',
    'we failed', 'we missed', 'we did not succeed',
    'no substantive reply was received from the partner and we did not',
    'the lack of forward motion is on our side',
    'is on us', 'is on our side',
    'this minimal', 'too little', 'too late',
    'should be more proactive', 'should be more aggressive',
]


def _scrub(text):
    """Remove sentences containing banned fragments. Drop any cyrillic-only fragments."""
    if not text:
        return ''
    sentences = _re.split(r'(?<=[.!?])\s+', text.strip())
    clean = []
    for s in sentences:
        low = s.lower()
        if any(b in low for b in _BANNED_FRAGMENTS):
            continue
        # Keep only sentences that are not majority cyrillic
        cyr_chars = len(_CYRILLIC_RE.findall(s))
        latin_chars = sum(1 for c in s if c.isalpha() and c.isascii())
        if cyr_chars > 0 and cyr_chars > latin_chars:
            continue
        clean.append(s)
    return ' '.join(clean).strip()


def _build_actions_recap(comments_for_week, brand_name):
    """Build a short, factual English description of what was logged this week.

    Pure paraphrase: list the comments back as a sentence. No evaluation,
    no coaching, no "we did not push hard enough".
    """
    bullets = []
    for c in comments_for_week[:5]:
        t = (c.get('text') or '').strip()
        if not t:
            continue
        t = _re.sub(r'\s+', ' ', t)
        bullets.append(t[:200])
    if not bullets:
        return EMPTY_WEEK_PHRASE
    if len(bullets) == 1:
        return bullets[0].rstrip('.') + '.'
    return ' '.join(b.rstrip('.') + '.' for b in bullets)


def _normalize_summary(week_iso, info, comments_for_week, brand_name):
    """Sanitise AI summary; never add evaluative / blame phrasing.

    - Empty week → EMPTY_WEEK_PHRASE.
    - "ours" or "partner" weeks → just the cleaned AI summary, or a
      factual paraphrase of the raw comments if AI text was scrubbed.
    - No mandated prefix, no tail-judgement.
    """
    info = dict(info or {})
    changed = bool(info.get('changed'))
    side    = info.get('wasted_side')
    summary = _scrub((info.get('summary') or '').strip())
    has_comments = bool(comments_for_week)

    if changed:
        if not summary:
            summary = (
                f'Forward progress was logged with {brand_name} this week — '
                f'see the comments for the specific deliverable.'
            )
        info['wasted_side'] = None
        info['summary'] = summary
        return info

    # wasted week
    if side not in ('ours', 'partner'):
        side = 'ours'

    if not has_comments:
        info['changed']     = False
        info['wasted_side'] = 'ours'
        info['summary']     = EMPTY_WEEK_PHRASE
        return info

    # Auto-downgrade partner→ours when the log shows only our actions.
    if side == 'partner' and not _has_partner_action(comments_for_week):
        side = 'ours'

    if not summary:
        summary = _build_actions_recap(comments_for_week, brand_name)

    info['summary']     = summary
    info['wasted_side'] = side
    info['changed']     = False
    return info


def _post_process_weeks(ai_weeks, history, brand_name):
    """Apply mandated phrasings to every week."""
    out = {}
    for week_iso, comments_for_week in history.items():
        info = ai_weeks.get(week_iso) or {}
        out[week_iso] = _normalize_summary(week_iso, info, comments_for_week, brand_name)
    return out


def _run_generation(report_pk):
    from .models import BrandSituationReport
    from producers.models import Producer

    close_old_connections()
    BrandSituationReport.objects.filter(pk=report_pk).update(
        status=BrandSituationReport.STATUS_GENERATING
    )

    try:
        brands = list(
            Producer.objects
            .filter(funnel='onboarding', stage__in=ACTIVE_STAGES)
            .order_by('name')
        )

        # Current week Monday (IST) — used to fill missing weeks per brand.
        report = BrandSituationReport.objects.get(pk=report_pk)
        current_monday = report.week_start

        brand_data = {}
        for p in brands:
            history, start_monday = _gather_brand_history(p, current_monday)
            weeks_in_funnel = _weeks_in_funnel(start_monday, current_monday)
            funnel_started_at = start_monday.isoformat() if start_monday else None

            if not history:
                brand_data[str(p.pk)] = {
                    'name': p.name,
                    'stage': STAGE_LABELS.get(p.stage, p.stage),
                    'stage_key': p.stage,
                    'weeks': {},
                    'current_status': 'No comments yet',
                    'weeks_in_funnel': weeks_in_funnel,
                    'funnel_started_at': funnel_started_at,
                }
                continue

            ai_result = _analyze_brand_with_ai(
                brand_name=p.name,
                stage_label=STAGE_LABELS.get(p.stage, p.stage),
                weeks_data=history,
            )
            normalized_weeks = _post_process_weeks(
                ai_result.get('weeks', {}), history, p.name
            )
            try:
                readiness = int(ai_result.get('readiness_percent') or 0)
            except (TypeError, ValueError):
                readiness = 0
            readiness = max(0, min(100, readiness))
            # On Platform must always be 100
            if p.stage == 'on_platform':
                readiness = 100
            brand_data[str(p.pk)] = {
                'name': p.name,
                'stage': STAGE_LABELS.get(p.stage, p.stage),
                'stage_key': p.stage,
                'weeks': normalized_weeks,
                'current_status': ai_result.get('current_status', ''),
                'readiness_percent': readiness,
                'weeks_in_funnel': weeks_in_funnel,
                'funnel_started_at': funnel_started_at,
            }

        BrandSituationReport.objects.filter(pk=report_pk).update(
            status=BrandSituationReport.STATUS_DONE,
            brand_data=brand_data,
        )
    except Exception as e:
        BrandSituationReport.objects.filter(pk=report_pk).update(
            status=BrandSituationReport.STATUS_ERROR,
            error_message=str(e),
        )
    finally:
        close_old_connections()


def generate_brand_situation_report(force=False):
    """
    Create BrandSituationReport for the current week and start background generation.
    If `force=False` and a report for this week already exists with status done — returns it.
    """
    from .models import BrandSituationReport

    monday, sunday = _week_bounds_ist()

    existing = BrandSituationReport.objects.filter(week_start=monday).first()
    if existing and not force and existing.status == BrandSituationReport.STATUS_DONE:
        return existing

    if existing:
        # re-use slot, reset to pending and re-generate
        existing.status = BrandSituationReport.STATUS_PENDING
        existing.error_message = ''
        existing.save(update_fields=['status', 'error_message'])
        report = existing
    else:
        report = BrandSituationReport.objects.create(
            week_start=monday,
            week_end=sunday,
            status=BrandSituationReport.STATUS_PENDING,
        )

    t = threading.Thread(target=_run_generation, args=(report.pk,), daemon=True)
    t.start()
    return report


def retry_failed_situation_reports():
    """Re-trigger any reports stuck in pending/generating/error state."""
    from .models import BrandSituationReport
    stuck = BrandSituationReport.objects.exclude(status=BrandSituationReport.STATUS_DONE)
    for r in stuck:
        r.status = BrandSituationReport.STATUS_PENDING
        r.error_message = ''
        r.save(update_fields=['status', 'error_message'])
        t = threading.Thread(target=_run_generation, args=(r.pk,), daemon=True)
        t.start()
