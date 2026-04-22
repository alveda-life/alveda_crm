"""
Auto-generates daily/weekly producer update reports via Claude.
"""
import os
import json
import threading
import pytz
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import close_old_connections

RIGA_TZ = pytz.timezone('Europe/Riga')

# Stage weight: higher = more advanced in the funnel
STAGE_WEIGHT = {
    'on_platform':      10,
    'in_store':          9,
    'contract_signed':   8,
    'ready_to_sell':     7,
    'negotiation':       6,
    'terms_negotiation': 5,
    'products_received': 5,
    'in_communication':  4,
    'signed':            3,
    'interest':          2,
    'agreed':            1,
    'stopped':           0,
}

STAGE_LABELS = {
    'interest':          'Interest',
    'in_communication':  'In Communication',
    'terms_negotiation': 'Negotiation',
    'negotiation':       'Signing Contract',
    'contract_signed':   'Contract Signed',
    'on_platform':       'On the Platform',
    'stopped':           'Stopped',
    'agreed':            'Agreed',
    'signed':            'Signed',
    'products_received': 'Products Received',
    'ready_to_sell':     'Ready to Sell',
    'in_store':          'In Store',
}


def _period_for_type(report_type):
    """Return (period_start, period_end) in UTC for the given report type."""
    now_riga = datetime.now(RIGA_TZ)

    if report_type == 'daily':
        start_riga = now_riga.replace(hour=0, minute=0, second=0, microsecond=0)
    else:  # weekly
        # Start of current week (Monday)
        days_since_mon = now_riga.weekday()
        start_riga = (now_riga - timedelta(days=days_since_mon)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    start_utc = start_riga.astimezone(pytz.utc)
    end_utc   = now_riga.astimezone(pytz.utc)
    return start_utc, end_utc


def _gather_snapshot(report_type, since, until):
    from producers.models import Producer, ProducerTask, ProducerComment

    since_riga = since.astimezone(RIGA_TZ)
    until_riga = until.astimezone(RIGA_TZ)

    # ── New producers ─────────────────────────────────────────────────────────
    new_producers = list(
        Producer.objects
        .filter(created_at__gte=since, created_at__lte=until)
        .select_related('assigned_to')
        .order_by('created_at')
    )

    # ── Stage changes ──────────────────────────────────────────────────────────
    stage_changed = list(
        Producer.objects
        .filter(stage_changed_at__gte=since, stage_changed_at__lte=until)
        .exclude(pk__in=[p.pk for p in new_producers])  # exclude new ones
        .select_related('assigned_to')
        .order_by('stage_changed_at')
    )

    # ── Tasks created ─────────────────────────────────────────────────────────
    tasks_created = list(
        ProducerTask.objects
        .filter(created_at__gte=since, created_at__lte=until)
        .select_related('producer', 'assigned_to', 'created_by')
        .order_by('created_at')
    )

    # ── Tasks completed ───────────────────────────────────────────────────────
    tasks_completed = list(
        ProducerTask.objects
        .filter(completed_at__gte=since, completed_at__lte=until)
        .select_related('producer', 'assigned_to', 'completed_by')
        .order_by('completed_at')
    )

    # ── Comments ──────────────────────────────────────────────────────────────
    comments = list(
        ProducerComment.objects
        .filter(created_at__gte=since, created_at__lte=until)
        .select_related('producer', 'author')
        .order_by('created_at')
    )

    # ── Current state ─────────────────────────────────────────────────────────
    all_ob  = Producer.objects.filter(funnel='onboarding').select_related('assigned_to')
    all_sup = Producer.objects.filter(funnel='support').select_related('assigned_to')

    ob_by_stage = {}
    for p in all_ob:
        ob_by_stage.setdefault(p.stage, []).append(p)

    # ── For weekly: active producers sorted by stage weight ───────────────────
    active_producers_weekly = []
    if report_type == 'weekly':
        producer_ids_active = set(
            [p.pk for p in new_producers]
            + [p.pk for p in stage_changed]
            + [t.producer_id for t in tasks_created]
            + [t.producer_id for t in tasks_completed]
            + [c.producer_id for c in comments]
        )
        active_producers_weekly = sorted(
            Producer.objects.filter(pk__in=producer_ids_active).select_related('assigned_to'),
            key=lambda p: -STAGE_WEIGHT.get(p.stage, 0)
        )

    def fmt_producer(p):
        op = p.assigned_to
        op_name = op.get_full_name() or op.username if op else 'Unassigned'
        return {
            'name':        p.name,
            'company':     p.company or '',
            'funnel':      p.funnel,
            'stage':       STAGE_LABELS.get(p.stage, p.stage),
            'assigned_to': op_name,
            'created_at':  p.created_at.astimezone(RIGA_TZ).strftime('%d.%m.%Y %H:%M'),
        }

    def fmt_task(t):
        op = t.assigned_to
        op_name = op.get_full_name() or op.username if op else 'Unassigned'
        return {
            'producer': t.producer.name,
            'company':  t.producer.company or '',
            'title':    t.title,
            'priority': t.priority,
            'status':   t.status,
            'assignee': op_name,
        }

    def fmt_comment(c):
        author = c.author
        author_name = author.get_full_name() or author.username if author else 'Unknown'
        time_str = c.created_at.astimezone(RIGA_TZ).strftime('%H:%M')
        date_str = c.created_at.astimezone(RIGA_TZ).strftime('%d.%m')
        return {
            'producer': c.producer.name,
            'company':  c.producer.company or '',
            'author':   author_name,
            'text':     c.text[:500] if c.text else '[attachment]',
            'time':     time_str,
            'date':     date_str,
        }

    # ── Group activity by operator ───────────────────────────────────────────
    from collections import defaultdict as _defaultdict
    from accounts.models import User

    operator_activity = _defaultdict(lambda: {
        'comments': [],
        'producers_touched': set(),
        'tasks_created': [],
        'tasks_completed': [],
    })

    for c in comments:
        author = c.author
        name = author.get_full_name() or author.username if author else 'Unknown'
        operator_activity[name]['comments'].append(fmt_comment(c))
        operator_activity[name]['producers_touched'].add(c.producer.name)

    for t in tasks_created:
        op = t.created_by or t.assigned_to
        name = op.get_full_name() or op.username if op else 'Unknown'
        operator_activity[name]['tasks_created'].append(fmt_task(t))

    for t in tasks_completed:
        op = t.completed_by or t.assigned_to
        name = op.get_full_name() or op.username if op else 'Unknown'
        operator_activity[name]['tasks_completed'].append(fmt_task(t))

    operator_summary = {}
    for op_name, data in operator_activity.items():
        by_producer = _defaultdict(list)
        for c in data['comments']:
            by_producer[c['producer']].append(c)

        operator_summary[op_name] = {
            'total_comments': len(data['comments']),
            'producers_touched': len(data['producers_touched']),
            'producers_list': sorted(data['producers_touched']),
            'tasks_created': len(data['tasks_created']),
            'tasks_completed': len(data['tasks_completed']),
            'activity_by_producer': {
                prod: [{'time': c['time'], 'date': c.get('date', ''), 'text': c['text']} for c in coms]
                for prod, coms in sorted(by_producer.items())
            },
        }

    # ── All producers pipeline snapshot (for AI readiness ranking) ─────────
    all_onboarding = list(
        Producer.objects.filter(funnel='onboarding')
        .exclude(stage='stopped')
        .select_related('assigned_to')
        .order_by('-stage_changed_at')
    )
    pipeline_producers = []
    for p in all_onboarding:
        latest_comments = list(
            ProducerComment.objects
            .filter(producer=p)
            .order_by('-created_at')[:5]
        )
        op = p.assigned_to
        pipeline_producers.append({
            'name': p.name,
            'stage': STAGE_LABELS.get(p.stage, p.stage),
            'stage_key': p.stage,
            'assigned_to': (op.get_full_name() or op.username) if op else 'Unassigned',
            'last_comments': [
                {
                    'date': c.created_at.astimezone(RIGA_TZ).strftime('%d.%m.%Y'),
                    'text': c.text[:200] if c.text else '',
                }
                for c in latest_comments
            ],
        })

    snap = {
        'period':        f'{since_riga.strftime("%d.%m.%Y %H:%M")} – {until_riga.strftime("%d.%m.%Y %H:%M")} (Riga)',
        'period_type':   report_type,
        'new_producers': [fmt_producer(p) for p in new_producers],
        'stage_changes': [
            {**fmt_producer(p), 'changed_at': p.stage_changed_at.astimezone(RIGA_TZ).strftime('%H:%M') if p.stage_changed_at else ''}
            for p in stage_changed
        ],
        'tasks_created':   [fmt_task(t) for t in tasks_created],
        'tasks_completed': [fmt_task(t) for t in tasks_completed],
        'comments':        [fmt_comment(c) for c in comments],
        'operator_activity': operator_summary,
        'pipeline_all_producers': pipeline_producers,
        'current_onboarding': {
            stage: len(producers)
            for stage, producers in ob_by_stage.items()
        },
        'current_support_total': all_sup.count(),
        'open_tasks_total': ProducerTask.objects.filter(status__in=['open', 'in_progress']).count(),
    }

    if report_type == 'weekly':
        def fmt_active(p):
            p_tasks = [t for t in tasks_created + tasks_completed if t.producer_id == p.pk]
            p_comments = [c for c in comments if c.producer_id == p.pk]
            p_changed = p.pk in [x.pk for x in stage_changed]
            return {
                **fmt_producer(p),
                'stage_changed_this_week': p_changed,
                'tasks_count':   len(p_tasks),
                'comments_count': len(p_comments),
                'comments': [fmt_comment(c) for c in p_comments],
            }
        snap['active_producers_sorted'] = [fmt_active(p) for p in active_producers_weekly]

    return snap


DAILY_SYSTEM_PROMPT = """You are the supervisor of the Ayurveda producer onboarding team.
You are given a JSON snapshot of one day. Write an ANALYTICAL report for the head of department.

Data: {crm_json}

═══════════════════════════════════════════════════════════════
WHAT IS REQUIRED:

You MUST NOT just copy the operator's comments. You must ANALYSE them and give the head of department a CLEAR PICTURE of the day.

The head of department wants to understand in 2 minutes:
1. Did the operator actually work or just sit through the day?
2. Are there RESULTS (replies, meetings, agreements)?
3. Or were there only OUTBOUND actions (sent and waiting)?
4. Which producers are showing real PROGRESS towards a contract?
5. Where is the STAGNATION and what to do about it?

ANALYSIS FORMAT — NOT A LIST OF COMMENTS, BUT CONCLUSIONS:

Split the operator's work into 3 buckets:

🟢 RESULTS (where a reply came in, a meeting happened, an agreement was reached):
From the comments, single out those where the producer actually responded. Write in your own words: "Kapiva — Senior VP Marketing replied, deck and cooperation model sent. Awaiting decision." That is progress.

🟡 ACTIVE OUTBOUND WITHOUT RESULTS YET (sent, no reply yet):
Group together: "LinkedIn requests and follow-ups sent to 15 producers (Biotique, OZiva, Kama Ayurveda, ...)". DO NOT list every comment — GROUP same-type actions.

🔴 NO MOVEMENT (producers with no activity, or no reply for a long time):
If there are producers where the operator did nothing or wrote "no response" — call them out.

FORBIDDEN:
- Copy comments verbatim
- Write "00:24 — Reminders are sent out" — that is not analysis, that is copy-paste
- List every producer in its own block with quotes
- Generic phrases like "actively worked", "managed communications"

MANDATORY:
- Count from the comments: how many LinkedIn requests, how many emails, how many WhatsApp, how many calls, how many replies received
- Pick out 3–5 most important events of the day (where real progress)
- Highlight problem areas
═══════════════════════════════════════════════════════════════

Structure (Markdown):

# 📋 Daily report — {date}

## 👤 [Operator name]

**Overall picture of the day:**
2–3 sentences: what was done, the volume of work, whether there is a result.

**Numbers:**
| Metric | Count |
|---|---|
| Producers worked on | X |
| LinkedIn requests/messages | X |
| Email/WhatsApp | X |
| Calls/meetings | X |
| Replies received | X |

### 🟢 Day's results (where there was a response/progress)
Per item — 1–2 sentences in your own words: what happened and what is the next step.

### 🟡 Outbound activity (sent, awaiting reply)
Group: "LinkedIn requests sent to X producers: [list]". Do not break each one out separately.

### 🔴 Problem areas
Where there is no reply for a long time, where there is stagnation.

## 🎯 Conclusion
3–4 sentences: productivity assessment, main wins, what is the priority for tomorrow.

## 📊 Closeness-to-onboarding ranking

IMPORTANT: The data contains a "pipeline_all_producers" section — ALL producers in onboarding with their latest comments. Analyse EACH and rate how close they are to onboarding (0–100%).

TABLE SORTING (STRICTLY MANDATORY):
First sort by FUNNEL STAGE (priority 1), then by readiness % (priority 2).
Stage order top-to-bottom:
1. On Platform
2. Contract Signed
3. Negotiation
4. In Communication
5. Interest

A producer in Negotiation is ALWAYS above any producer in In Communication, even if the latter has a higher %. Within the same stage — sort by %.

READINESS % (within a stage, based on comments):
- On Platform → ALWAYS EXACTLY 100% (this stage = producer already onboarded, no 90/95% allowed)
- Contract Signed → 80–95% (contract signed, integration / first orders in progress)
- Negotiation, margin/terms agreed → 60–75%
- Negotiation, productive meeting with agreements → 45–60%
- Reply from decision-maker, active dialogue → 30–45%
- Requests sent, replies without specifics → 15–30%
- Requests sent, no replies → 5–15%
- No contact → 0–5%

RULES:
- On Platform = 100% (producer already onboarded). Progress bar: ██████████ 100%
- Contract Signed/Negotiation — minimum 25%, even with no replies
- Do not inflate % when nothing is really happening

Format — table, FIRST sort by stage, THEN by %:

| # | Producer | Stage | Readiness | What is actually happening |
|---|---|---|---|---|
| 1 | Kerala Ayurveda | On Platform | ██████████ 100% | Onboarded, API integration complete, first orders flowing |
| 2 | Planet Ayurveda | Contract Signed | █████████░ 90% | Contract signed 08.04, Amazon prices agreed, awaiting integration call |
| 3 | Jiva Ayurveda | Negotiation | ███████░░░ 70% | 20% margin + bonus agreed, WhatsApp group created, contract being drafted |
| 4 | Sitaram Ayurveda | In Communication | ████░░░░░░ 40% | Digital Commerce Manager accepted LinkedIn, proposal requested by email |
| 5 | Biotique | Interest | ██░░░░░░░░ 20% | Regional BD accepted request, deck sent, no reply on proposal |
| 6 | CNS Ayurveda | Interest | █░░░░░░░░░ 5% | 1 LinkedIn request sent, no reply at all |

THE "What is actually happening" COLUMN — THE MOST IMPORTANT:
- The head reads EXACTLY THIS to understand the situation.
- Write from the comments: WHO is the contact (job title), WHAT is being discussed, WHAT document/margin we are waiting for.
- FORBIDDEN phrases: "Correspondence in progress", "Awaiting reply", "Interest stage", "Awaiting decision" — THIS IS GARBAGE, the head learns nothing from these.
- If the comments are unclear — write: "Last comment: '...text...' — status unclear"

Use █ and ░ — exactly 10 characters.

CRITICAL ABOUT THE TABLE:
- pipeline_all_producers contains exactly {pipeline_count} producers.
- The table MUST HAVE EXACTLY {pipeline_count} ROWS — one per producer.
- FORBIDDEN to write "... etc.", "... continued", "... remaining producers" — that is a defect.
- FORBIDDEN to duplicate producers — each name appears EXACTLY ONCE.
- After the table DO NOT write any of these instructions — no "The 'What is actually happening' column — ...", no commentary on the table.
- If there are fewer than {pipeline_count} rows or duplicates — the report is INVALID.

Write in English, business tone."""


WEEKLY_SYSTEM_PROMPT = """You are the supervisor of the Ayurveda producer onboarding team.
You are given a JSON snapshot of one week. Write an ANALYTICAL weekly report for the head of department.

Data: {crm_json}

═══════════════════════════════════════════════════════════════
WHAT IS REQUIRED:

DO NOT copy comments. ANALYSE them. The head of department wants to understand in 5 minutes:
1. Each operator — did they actually work the whole week or not?
2. What VOLUME of work was done (quantitatively)?
3. What REAL RESULTS (contracts, meetings, agreements)?
4. Which producers MOVED CLOSER to onboarding?
5. Where is the STAGNATION and PROBLEMS?

FORMAT:

Per operator:

1. WEEK SUMMARY — 3–4 sentences: work intensity, ratio of outbound actions to results.

2. NUMBERS — count from the comments the real numbers (LinkedIn, email, WhatsApp, calls, replies).

3. TOP ACHIEVEMENTS — 3–5 most important events where there is real progress towards onboarding. Write IN YOUR OWN WORDS: "Sitaram Ayurveda — over the week went from LinkedIn request to a proposal request by email. Digital Commerce Manager and Deputy Manager accepted requests, info received, terms discussion started."

4. DAY-BY-DAY BREAKDOWN — short, 1–2 lines per day. DO NOT list every comment. Write: "Thursday: main focus on finding new contacts (12 producers), 3 replies received (Biotique, Kapiva, Dhootapapeshwar)."

5. PROBLEM AREAS — where there is no movement, what to do.

FORBIDDEN:
- Copy-paste comments
- List every producer in its own block with quotes
- Generic phrases without numbers
═══════════════════════════════════════════════════════════════

Structure (Markdown):

# 📊 Weekly report — {week_range}

## 👤 [Operator name]

**Week summary:**
3–4 sentences — overall picture. Example: "Over the week covered 37 producers, left 113 comments. Main focus — finding new contacts via LinkedIn and follow-ups on existing ones. ~15 replies received, 3 calls held. Real progress on 5 producers (Sitaram, Kapiva, Rasayanam, Dhootapapeshwar, Biotique)."

**Week numbers:**
| Metric | Count |
|---|---|
| Producers worked on | X |
| LinkedIn requests | X |
| Email/WhatsApp | X |
| Calls/meetings | X |
| Replies received | X |
| Funnel advancements | X |

### 🟢 Main achievements of the week
3–5 items. Per item — 2–3 sentences: what happened, why it matters, what is the next step.

### 📅 By day
| Day | Focus | Result |
|---|---|---|
| Mon | ... | ... |
| Tue | ... | ... |
| ... | ... | ... |

### 🔴 Problem areas
Where there is stagnation, which producers are not moving, recommendations.

(Repeat per operator)

## 📊 Funnel
Current state: how many at each stage.

## 🎯 Conclusions
Productivity assessment, priorities for next week.

## 📊 Closeness-to-onboarding ranking

IMPORTANT: The data contains a "pipeline_all_producers" section — ALL producers in onboarding with latest comments. Analyse EACH and rate how close they are to onboarding (0–100%).

SORTING: first by stage (On Platform → Contract Signed → Negotiation → In Communication → Interest), then by %. A producer in Negotiation is ALWAYS above In Communication.

% inside a stage:
- On Platform → ALWAYS EXACTLY 100% (producer already onboarded)
- Contract Signed → 80–95%
- Negotiation, margin/terms agreed → 60–75%
- Negotiation, productive meetings → 45–60%
- Reply from decision-maker, active dialogue → 30–45%
- Requests sent, replies without specifics → 15–30%
- Requests sent, no replies → 5–15%
- No contact → 0–5%

RULES:
- On Platform = 100% always. Progress bar: ██████████ 100%
- Negotiation/Contract Signed — minimum 25%

| # | Producer | Stage | Readiness | What is actually happening |
|---|---|---|---|---|
| 1 | Kerala Ayurveda | On Platform | ██████████ 100% | Onboarded, API integration complete, orders flowing |
| 2 | Jiva Ayurveda | Negotiation | ███████░░░ 70% | 20% margin + bonus agreed, contract being drafted, WhatsApp group created |
| 3 | Biotique | Interest | ██░░░░░░░░ 20% | BD accepted LinkedIn request, deck sent, no reply |

THE "What is actually happening" COLUMN — THE MOST IMPORTANT:
- Write from the comments: WHO is the contact (job title), WHAT is being discussed, WHAT document we are waiting for.
- FORBIDDEN: "Correspondence in progress", "Awaiting reply", "Interest stage" — GARBAGE.
- If the comments are unclear — write: "Status unclear, last comment: '...'"

Use █ and ░ (10 characters).

CRITICAL:
- The table has EXACTLY {pipeline_count} ROWS (= number of producers).
- FORBIDDEN: "... etc.", "... remaining", duplicate names.
- After the table DO NOT repeat the instructions — no explanations from this prompt.

Write in English, business and analytical tone."""


_MAX_RETRIES = 3
_RETRY_DELAYS = [5, 15, 30]


def _run_generation(report_pk, snap, report_type):
    import time
    from .models import ProducerUpdateReport
    from openai import OpenAI

    close_old_connections()

    crm_json = json.dumps(snap, ensure_ascii=False, indent=2)
    riga_now = datetime.now(RIGA_TZ)
    date_str = riga_now.strftime('%d.%m.%Y')
    pipeline_count = len(snap.get('pipeline_all_producers', []))

    if report_type == 'daily':
        system = DAILY_SYSTEM_PROMPT.format(
            period=snap['period'],
            date=date_str,
            crm_json=crm_json,
            pipeline_count=pipeline_count,
        )
        user_msg = f'Build the daily producer report for {date_str}.'
    else:
        start_of_week = riga_now - timedelta(days=riga_now.weekday())
        end_of_week   = start_of_week + timedelta(days=4)
        week_range = f'{start_of_week.strftime("%d.%m")} – {end_of_week.strftime("%d.%m.%Y")}'
        system = WEEKLY_SYSTEM_PROMPT.format(
            period=snap['period'],
            week_range=week_range,
            crm_json=crm_json,
            pipeline_count=pipeline_count,
        )
        user_msg = f'Build the weekly producer report for the week of {week_range}.'

    ProducerUpdateReport.objects.filter(pk=report_pk).update(
        status=ProducerUpdateReport.STATUS_GENERATING
    )

    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            client  = OpenAI(api_key=os.environ.get('OPENAI_API_KEY', ''))
            message = client.chat.completions.create(
                model='gpt-4o',
                max_tokens=16000,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user_msg},
                ],
            )

            content = message.choices[0].message.content.strip()
            title = next(
                (line.lstrip('#').strip() for line in content.splitlines() if line.strip()),
                f'{"Daily" if report_type == "daily" else "Weekly"} report {date_str}'
            )
            if len(title) > 120:
                title = title[:117] + '…'

            ProducerUpdateReport.objects.filter(pk=report_pk).update(
                status=ProducerUpdateReport.STATUS_DONE,
                title=title,
                content=content,
            )
            close_old_connections()
            return

        except Exception as e:
            last_error = e
            delay = _RETRY_DELAYS[attempt] if attempt < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
            time.sleep(delay)

    ProducerUpdateReport.objects.filter(pk=report_pk).update(
        status=ProducerUpdateReport.STATUS_ERROR,
        error_message=str(last_error),
        title='Report generation error',
    )
    close_old_connections()


def generate_update_report(report_type):
    """Create a ProducerUpdateReport and start background generation. Returns the report instance."""
    from .models import ProducerUpdateReport

    since, until = _period_for_type(report_type)
    snap  = _gather_snapshot(report_type, since, until)
    report = ProducerUpdateReport.objects.create(
        report_type=report_type,
        period_start=since,
        period_end=until,
        status=ProducerUpdateReport.STATUS_PENDING,
    )

    t = threading.Thread(
        target=_run_generation,
        args=(report.pk, snap, report_type),
        daemon=True,
    )
    t.start()
    return report
