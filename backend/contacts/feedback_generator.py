import os
import re
import json
import time
import logging
from datetime import date, timedelta
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

DAILY_PROMPT = """You are a senior call coach and mentor for operator {operator_name}. This is a personal coaching note that the operator will open themselves. The point of this section is NOT criticism — it is GROWTH. The operator comes here to see specific growth zones and examples of how to do things better; not "here is what's wrong" but "here is how to become stronger".

Address the operator directly as "you". Never write "the operator did", only "you".

Date: {date}
Calls analysed: {calls_count}
Average score: {avg_score}/10

Per-call analysis (errors found, improvement plan and recommendations for every call):

{calls_summary}

═══════════════════════════════════════════════════════════════
RESPONSE FORMAT — Markdown in English
═══════════════════════════════════════════════════════════════

## 📊 Day summary: {date}
Calls: {calls_count}, average score: {avg_score}/10. One paragraph (2–3 sentences) — the overall picture of the day in a friendly tone, without judgmental adjectives like "excellent"/"bad". For example: "Today you had {calls_count} calls covering different funnel stages — there are a few moments worth pausing on so the next calls land even more precisely."

## 🎯 Growth zones for today
The MAIN part of the note. These are not complaints — they are development points. Group everything you found in the per-call analysis into 2–4 SKILLS (no more than 4). Possible skills:

- **Diagnosing the funnel stage** — where exactly the partner is stuck (after registration? after entering the dashboard? did not reach MedSet?)
- **Drilling into the real reason** — keep digging UNTIL specifics, do not accept "I was busy" as the final answer
- **Precise product explanation** — commission, MedSet, referral programme — with zero factual inaccuracies
- **Closing the call with a concrete next step and date**
- **Collecting product feedback**
- **Confirming the partner understood** before finishing

For EACH skill use strictly this format:

### 🌱 [Skill name]
**What this is about:** 1–2 coaching-tone sentences — what this skill is and why it matters. No blame.

**Example from your calls today (call with [partner name]):**
> Partner: "[EXACT quote from the transcript]"
> You: "[EXACT quote]"
> Partner: "[EXACT quote — reaction]"

**What was happening here:** 1 factual sentence — what the partner meant, how the situation unfolded. NO words like "missed", "failed", "should have".

**💡 Try this on your next call:**
> "[A READY-TO-COPY phrase the operator can use word-for-word. At least 2–3 sentences. Specific — tailored to exactly this situation. If it's about diagnosis — it's a question. If it's about product explanation — it's an explanation. If it's about the next step — it's a closing line.]"

**Why this works:** 1 sentence — what result this approach produces (e.g. "the partner will clearly understand what is expected and won't forget the next step within 24 hours").

(Repeat the block for each of the 2–4 skills. This is the most important section of the note.)

## 💪 What you are already doing well
2–3 moments from today's calls that worked — shorter than the growth zones. Each moment:

**Call with [partner name]:**
> Partner: "[quote]"
> You: "[quote]"

What worked: 1 sentence — what useful result it produced.

## 🚀 Tomorrow's focus
1–2 sentences. Very short: "Tomorrow, try to focus on [skill #1] and [skill #2]. That will give the fastest jump in the quality of your calls."

═══════════════════════════════════════════════════════════════
RULES — mandatory
═══════════════════════════════════════════════════════════════
1. Tone — mentor, not auditor. "Try", "One way to approach this", "A useful move here is" — yes. "You must", "You did not", "you should have", "you needed to" — NO.
2. EVERY growth zone MUST contain a ready-to-copy example phrase. Without examples the note is useless — the operator won't understand how to do better. If it's about a question — give a ready question. If about a product explanation — give a ready explanation. If about closing — give a ready closing line.
3. All quotes — EXACTLY from the call transcript. Do not invent the partner's words.
4. The example phrase must address EXACTLY THIS situation, not a generic "ask for details". For instance, if the partner said "I didn't use it, I was busy" — the example must be a concrete follow-up question: "Understood, schedules get tight. Tell me though, which exact steps in the dashboard did you reach? You completed registration — did you make it into the catalogue, or not yet?"
5. No empty adjectives: "great approach", "effective", "well done", "handled it nicely". Only facts and examples.
6. Do not invent problems. If the partner calmly answered "ok" / "yes" / moved on to the next topic — the situation is fine.
7. If the per-call analyses say "No mistakes detected" for every call — skip the growth-zones section and write: "Today every key moment landed cleanly. Keep going. Tomorrow, try experimenting with one of these moves: [1 optional move with example]."
8. All example phrases — in English. Tone warm, human, like a senior colleague.
9. Length — 4–6 minutes of reading. Do not skimp on examples — they are the main value."""

WEEKLY_PROMPT = """You are a senior call coach and mentor for operator {operator_name}. This is a personal weekly coaching note. The point is to help the operator grow: surface RECURRING growth zones over the week and give concrete moves that can be turned into a habit. NOT criticism — growth.

Address the operator directly as "you". Never write "the operator", only "you".

Week: {week_start} — {week_end}
Calls: {calls_count}, average score: {avg_score}/10
Breakdown: Discovery {avg_survey}/10, Explanation {avg_explanation}/10, Overall {avg_overall}/10

Daily summaries for the week:
{daily_summaries}

═══════════════════════════════════════════════════════════════
RESPONSE FORMAT — Markdown in English
═══════════════════════════════════════════════════════════════

## 📊 Week summary: {week_start} — {week_end}
Calls: {calls_count}, average score: {avg_score}/10. One paragraph (2–3 sentences) — the overall picture of the week in a friendly tone.

## 🎯 Growth zones for this week
The MAIN part. Find 2–3 RECURRING skills that showed up in several calls over the week and where there is room to grow. These are not one-off cases — they are patterns that repeat and are worth turning into a new habit.

For EACH skill use strictly this format:

### 🌱 [Skill name]
**What this is about:** 2–3 coaching-tone sentences — what this skill is, why it matters on our calls, what result it produces. Write as if you were explaining to a junior colleague over coffee.

**Where it shows up in your calls this week:** 2 short examples from different calls, one block per example:

📞 *Call with [name], [date]:*
> Partner: "[quote]"
> You: "[quote]"
> Partner: "[quote — reaction]"

📞 *Call with [name], [date]:*
> Partner: "[quote]"
> You: "[quote]"
> Partner: "[quote — reaction]"

**💡 Lock this habit in:**
Give 2 ready-to-copy phrase moves for typical situations of this skill. Each phrase — a separate block:

When the partner says "[typical partner phrase]" — try:
> "[ready-to-use operator sentence, 2–3 lines, tailored to exactly this situation]"

When [another typical situation] — try:
> "[ready sentence]"

**Why this works:** 1 sentence — what effect these moves have on the partner.

(Repeat the block for each of the 2–3 skills. This is the most important part of the note.)

## 💪 What is already going well
2–3 recurring strengths from the week — things you are doing consistently well. Each point — a short block with one quote example.

## 🚀 Focus for next week
2–3 sentences with concrete moves to anchor. For example: "Next week, try closing EVERY call with one of the phrases above — that will build a habit, and within 2 weeks it will no longer require conscious effort."

═══════════════════════════════════════════════════════════════
RULES — mandatory
═══════════════════════════════════════════════════════════════
1. Tone — mentor, not auditor. "Try", "One way to approach this", "A strong move here is" — yes. "You must", "You did not", "you should have" — NO.
2. EVERY growth zone MUST contain at least 2 ready-to-copy example phrases. Without examples the note is useless. The example must address EXACTLY this typical situation (if it's about discovery — it's a question, if about product explanation — it's an explanation, if about closing — it's a closing line).
3. All quotes — EXACTLY from the call transcripts. Do not invent words.
4. No empty adjectives: "effective", "well handled", "good approach", "quality work". Only facts and examples.
5. Do not invent problems. Include a skill in the growth zones only if it showed up in 2+ calls during the week.
6. If the week was clean overall — write: "This week no systemic growth zones were detected — you keep the quality steady. Take 1 optional move to experiment with: [move + example]."
7. All example phrases — in English, warm human language, like a senior colleague.
8. Length — 5–7 minutes of reading. Do not skimp on examples."""


MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]


def _generate_feedback(feedback_obj, prompt_text):
    from openai import OpenAI

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            message = client.chat.completions.create(
                model='gpt-4o',
                max_tokens=8192,
                messages=[{'role': 'user', 'content': prompt_text}],
            )
            content = message.choices[0].message.content.strip()
            feedback_obj.content = content
            feedback_obj.status = 'done'
            feedback_obj.save(update_fields=['content', 'status'])
            logger.info(f'Feedback generated for {feedback_obj.operator} ({feedback_obj.feedback_type}, {feedback_obj.period_start})')
            return
        except Exception as e:
            last_error = e
            delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
            logger.warning(f'Feedback attempt {attempt+1}/{MAX_RETRIES} failed: {e}. Retrying in {delay}s...')
            import time
            time.sleep(delay)

    logger.error(f'Feedback generation failed after {MAX_RETRIES} attempts: {last_error}')
    feedback_obj.status = 'failed'
    feedback_obj.save(update_fields=['status'])


def generate_daily_feedback(operator, target_date=None):
    from .models import Contact, OperatorFeedback

    if not OPENAI_API_KEY:
        return

    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    existing = OperatorFeedback.objects.filter(
        operator=operator, feedback_type='daily', period_start=target_date
    ).first()
    if existing and existing.status == 'done':
        return existing

    calls = Contact.objects.filter(
        created_by=operator,
        date__date=target_date,
        summary_status='done',
    ).exclude(transcription='').select_related('partner')

    if not calls.exists():
        return None

    calls_list = list(calls)
    calls_count = len(calls_list)

    scores = [c.quality_overall for c in calls_list if c.quality_overall]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    calls_summary_parts = []
    for i, c in enumerate(calls_list, 1):
        part = f"### Call {i}: {c.partner.name}\n"
        part += f"Duration: {c.call_duration or 0}s\n"
        part += f"Scores: Discovery={c.quality_survey}, Explanation={c.quality_explanation}, Overall={c.quality_overall}\n"
        transcript = (c.diarized_transcript or c.transcription or '')[:4000]
        if transcript:
            part += f"\n--- Transcript (excerpt) ---\n{transcript}\n"
        if c.quality_errors_found:
            part += f"\n--- Errors detected in this call ---\n{c.quality_errors_found}\n"
        if c.quality_improvement_plan:
            part += f"\n--- Improvement plan for this call ---\n{c.quality_improvement_plan}\n"
        if c.quality_survey_detail:
            part += f"\n--- Discovery details ---\n{c.quality_survey_detail[:1200]}\n"
        if c.quality_explanation_detail:
            part += f"\n--- Explanation details ---\n{c.quality_explanation_detail[:1200]}\n"
        if c.quality_recommendations:
            part += f"\n--- Recommendations ---\n{c.quality_recommendations[:1200]}\n"
        calls_summary_parts.append(part)

    prompt = DAILY_PROMPT.format(
        operator_name=operator.get_full_name() or operator.username,
        date=target_date.strftime('%d.%m.%Y'),
        calls_count=calls_count,
        avg_score=avg_score,
        calls_summary='\n---\n'.join(calls_summary_parts),
    )

    if existing:
        fb = existing
        fb.calls_analyzed = calls_count
        fb.avg_score = avg_score
        fb.status = 'generating'
        fb.save(update_fields=['calls_analyzed', 'avg_score', 'status'])
    else:
        fb = OperatorFeedback.objects.create(
            operator=operator,
            feedback_type='daily',
            period_start=target_date,
            period_end=target_date,
            calls_analyzed=calls_count,
            avg_score=avg_score,
            status='generating',
        )

    _generate_feedback(fb, prompt)
    return fb


def generate_weekly_feedback(operator, week_end=None):
    from .models import Contact, OperatorFeedback

    if not OPENAI_API_KEY:
        return

    if week_end is None:
        today = date.today()
        week_end = today - timedelta(days=today.weekday() + 1)
    week_start = week_end - timedelta(days=6)

    existing = OperatorFeedback.objects.filter(
        operator=operator, feedback_type='weekly', period_start=week_start
    ).first()
    if existing and existing.status == 'done':
        return existing

    calls = Contact.objects.filter(
        created_by=operator,
        date__date__gte=week_start,
        date__date__lte=week_end,
        summary_status='done',
    ).exclude(transcription='')

    if not calls.exists():
        return None

    calls_list = list(calls)
    calls_count = len(calls_list)

    def _avg(field):
        vals = [getattr(c, field) for c in calls_list if getattr(c, field)]
        return round(sum(vals) / len(vals), 1) if vals else 0

    avg_score = _avg('quality_overall')
    avg_survey = _avg('quality_survey')
    avg_explanation = _avg('quality_explanation')

    daily_fbs = OperatorFeedback.objects.filter(
        operator=operator, feedback_type='daily',
        period_start__gte=week_start, period_end__lte=week_end,
        status='done',
    ).order_by('period_start')

    daily_parts = []
    for fb in daily_fbs:
        daily_parts.append(f"### {fb.period_start.strftime('%d.%m.%Y')} ({fb.calls_analyzed} calls, avg {fb.avg_score}/10)\n{fb.content[:600]}")

    if not daily_parts:
        daily_parts = ['No daily summaries available — analyzing calls directly.']

    prompt = WEEKLY_PROMPT.format(
        operator_name=operator.get_full_name() or operator.username,
        week_start=week_start.strftime('%d.%m.%Y'),
        week_end=week_end.strftime('%d.%m.%Y'),
        calls_count=calls_count,
        avg_score=avg_score,
        avg_survey=avg_survey,
        avg_explanation=avg_explanation,
        avg_overall=avg_score,
        daily_summaries='\n---\n'.join(daily_parts),
    )

    if existing:
        fb = existing
        fb.calls_analyzed = calls_count
        fb.avg_score = avg_score
        fb.status = 'generating'
        fb.period_end = week_end
        fb.save(update_fields=['calls_analyzed', 'avg_score', 'status', 'period_end'])
    else:
        fb = OperatorFeedback.objects.create(
            operator=operator, feedback_type='weekly',
            period_start=week_start, period_end=week_end,
            calls_analyzed=calls_count, avg_score=avg_score,
            status='generating',
        )

    _generate_feedback(fb, prompt)
    return fb


def generate_all_pending_feedback():
    """Generate daily feedback for yesterday and weekly on Mondays for all operators with calls."""
    from accounts.models import User

    close_old_connections()
    today = date.today()
    yesterday = today - timedelta(days=1)

    operators = User.objects.filter(is_active=True).exclude(role='admin')

    for op in operators:
        try:
            generate_daily_feedback(op, yesterday)
        except Exception as e:
            logger.error(f'Daily feedback failed for {op}: {e}')

    if today.weekday() == 0:
        last_sunday = today - timedelta(days=1)
        for op in operators:
            try:
                generate_weekly_feedback(op, last_sunday)
            except Exception as e:
                logger.error(f'Weekly feedback failed for {op}: {e}')

    close_old_connections()
