"""
Extract per-call partner insights (market, product, platform, etc.) from transcripts.

Runs in background threads; uses OPENAI_API_KEY like summarization.
All generated narrative in English; verbatim_partner_quote preserves original wording.
"""
import hashlib
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List

from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
MAX_TRANSCRIPT_CHARS = 100_000
INSIGHTS_MODEL = (os.environ.get('OPENAI_INSIGHTS_MODEL') or 'gpt-4.1').strip() or 'gpt-4.1'
INSIGHTS_FALLBACK_MODELS = [m.strip() for m in (os.environ.get('OPENAI_INSIGHTS_FALLBACK') or 'gpt-4o').split(',') if m.strip()]

INSIGHTS_USER_PROMPT = """You extract business intelligence from a sales call between an AskAyurveda operator and a PARTNER (doctor / trainer / blogger).

{product_context_block}

ALL narrative fields MUST be written in ENGLISH. The partner may speak any language — put their exact spoken wording in verbatim_partner_quote (copy from PARTNER lines in the transcript) and a faithful English translation in quote_english.

Extract ONLY material partner statements relevant to:
- Our products / offers / commissions / medical sets
- Ayurveda market perception, demand, skepticism
- Competitors, alternatives, other platforms or sellers
- Manufacturers / brands / quality concerns
- Attitude toward the Ask Ayurveda platform, trust, usability
- Prescribing / recommendation process and medication procurement process
- Earning money, margins, motivation, risk
- Any other materially relevant partner perspective

MUST EXTRACT (if any of these patterns appear in the transcript — emit a SEPARATE insight for each one that is supported by partner words; do NOT collapse them into a generic "wants more brands"):
- Multi-brand / per-indication prescribing pattern (e.g. partner says different brands for Asava Arista vs Churna vs proprietary drugs like rheumatil) → category=prescribing_procurement. This signals a structural conflict with single-brand catalogs.
- Specific competing brand or manufacturer NAMES the partner already prefers (e.g. "Amil", "Dabur", "Patanjali", "Himalaya", "Baidyanath", "Charaka", "Madhutapeshwar", "Kerala Ayurveda", "Planet Ayurveda") → category=competitors or manufacturers. List the names verbatim — these are a concrete supplier roadmap.
- Concrete platform feature request the operator could not fulfil (e.g. consultation time-slot scheduling, search by indication, etc.) → category=platform_ask_ayurveda.
- Share-of-wallet / scope limitation (mixed allopathy + Ayurveda practice, multi-modality clinic) when it limits how much of partner's prescription volume can flow through AskAyurveda → category=market_ayurveda or platform_ask_ayurveda.
- Existing direct pharma tie-ups / commissions / rep relationships at the doctor level (competitive landscape — how pharma already monetises this doctor) → category=competitors or earning_money.
- Strong adoption-blocker statements: partner explicitly says they would have abandoned / left / not used the product without help, or that the flow is "hectic / complicated / confusing" → category=platform_ask_ayurveda. ALWAYS emit this as its own item; never bury it inside a generic "limited brands" insight.
- Stated daily/weekly usage commitment or refusal ("would use daily once X happens", "I need Y first") → category=platform_ask_ayurveda or product.

QUALITY RULES (read carefully — violations make the whole report useless):
- Aim for 1–8 DISTINCT, NON-OVERLAPPING insights. For calls longer than ~5 minutes with substantive partner input, expect 4–7. Fewer is fine for short or low-signal calls.
- If there are no useful business insights, return insights: []. Do not invent filler.
- DEDUPLICATION (strict): If two candidate insights are about the same business idea (e.g. "wants more brands", "limited brand catalog", "existing tie-up with bigger brand assortment", "platform lacks brand variety") — MERGE them into ONE consolidated insight that covers all angles and quotes. Never emit near-duplicates. After drafting, re-read your list and collapse anything that overlaps in topic, decision, or partner intent.
- Do NOT include biography/background-only items (e.g., "doctor runs a clinic", "doctor is Ayurvedic physician") unless directly tied to buying/prescribing/platform decisions.
- Ignore low-signal acknowledgements ("ok", "yes", "got it", "hmm") unless they carry business meaning.
- If a point does not fit predefined categories, keep it as "other" (never drop it).
- Use Product Context to interpret partner feedback, but NEVER invent product facts that are not in transcript or product context.
- Prefer insights that reveal: platform gaps, adoption blockers, procurement/prescribing realities, competitor advantages, pricing/commission pressure, and concrete growth opportunities.
- Reject insights that are only generic product praise/critique ("brand X has good quality") unless they clearly affect supplier choice, prescribing behavior, procurement flow, or willingness to use Ask Ayurveda.

EVERY insight MUST include ALL of these (no empty fields allowed):
- verbatim_partner_quote: exact excerpt from PARTNER lines (non-English allowed). If multiple supporting quotes exist after merging duplicates, pick the strongest one.
- quote_english: faithful English translation of that excerpt
- detail_english: 2–4 sentences explaining what the partner actually said, the surrounding context, AND the business implication for AskAyurveda (market/competitor/platform/process angle and any action this should inform)

Return JSON ONLY (no markdown fences) with this exact shape:
{{
  "call_title_english": "<one-line summary of the call focus>",
  "insights": [
    {{
      "category": "product|market_ayurveda|competitors|manufacturers|platform_ask_ayurveda|prescribing_procurement|earning_money|other",
      "sentiment": "positive|negative|neutral|mixed",
      "title": "<short English headline, must be unique vs other items>",
      "detail_english": "<2-4 sentences combining what the partner said and what it means for AskAyurveda>",
      "verbatim_partner_quote": "<exact partner wording from transcript>",
      "quote_english": "<English translation>"
    }}
  ]
}}

If there are genuinely zero substantive partner statements, return insights as []. An empty list is a valid, expected outcome for low-signal calls.

Partner evidence lines (quotes must come from here):
{partner_evidence}

Transcript:
{transcript}
"""


def _density_bucket(count: int) -> str:
    from .models import CallInsight
    if count <= 3:
        return CallInsight.DENSITY_LOW
    if count <= 7:
        return CallInsight.DENSITY_MEDIUM
    return CallInsight.DENSITY_HIGH


def _category_label(category: str) -> str:
    labels = {
        'product': 'Product / Offer',
        'market_ayurveda': 'Ayurveda Market',
        'competitors': 'Competitors / Alternatives',
        'manufacturers': 'Manufacturers / Brands',
        'platform_ask_ayurveda': 'Ask Ayurveda Platform',
        'prescribing_procurement': 'Prescribing / Procurement',
        'earning_money': 'Earnings / Margins',
        'other': 'Other Material Insight',
    }
    return labels.get((category or '').strip().lower(), 'Other Material Insight')


def _sentiment_label(sentiment: str) -> str:
    labels = {
        'positive': 'Positive',
        'negative': 'Negative',
        'neutral': 'Neutral',
        'mixed': 'Mixed',
    }
    return labels.get((sentiment or '').strip().lower(), 'Neutral')


def _build_markdown(data: Dict[str, Any], insight_count: int, density_bucket: str) -> str:
    title = (data.get('call_title_english') or 'Call insights').strip()
    lines: List[str] = [
        f'## {title}',
        '',
        f'{insight_count} insights · {density_bucket} density',
        '',
    ]
    insights = data.get('insights') or []
    for i, it in enumerate(insights, 1):
        if not isinstance(it, dict):
            continue
        cat = _category_label(str(it.get('category', 'other')))
        sent = _sentiment_label(str(it.get('sentiment', 'neutral')))
        tl = it.get('title', f'Insight {i}')
        lines.append(f'### {i}. {tl}')
        lines.append(f'Category: {cat} · Sentiment: {sent}')
        lines.append('')
        lines.append(it.get('detail_english', '').strip())
        lines.append('')
        original_q = (it.get('verbatim_partner_quote') or '').strip()
        lines.append('> **Partner quote:** ' + original_q)
        lines.append('')
    return '\n'.join(lines).strip()


def _sanitize_insights(raw: Any, partner_lines: List[str]) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        cat = str(it.get('category', 'other')).lower()
        if cat == 'physician_practice':
            cat = 'prescribing_procurement'
        if cat not in {
            'product', 'market_ayurveda', 'competitors', 'manufacturers',
            'platform_ask_ayurveda', 'prescribing_procurement', 'earning_money', 'other',
        }:
            cat = 'other'
        sent = str(it.get('sentiment', 'neutral')).lower()
        if sent not in {'positive', 'negative', 'neutral', 'mixed'}:
            sent = 'neutral'
        out.append({
            'category': cat,
            'sentiment': sent,
            'title': str(it.get('title', '')).strip()[:300],
            'detail_english': str(it.get('detail_english', '')).strip(),
            'why_it_matters': str(it.get('why_it_matters', '')).strip(),
            'verbatim_partner_quote': str(it.get('verbatim_partner_quote', '')).strip(),
            'quote_english': str(it.get('quote_english', '')).strip(),
        })
    filtered = [x for x in out if x['title'] or x['detail_english'] or x['verbatim_partner_quote']]
    filtered = [x for x in filtered if not _is_low_signal_insight(x)]
    filtered = [x for x in filtered if _is_quote_grounded(x.get('verbatim_partner_quote', ''), partner_lines)]
    filtered = [x for x in filtered if _is_business_useful(x)]
    filtered = _dedupe_insights(filtered)
    return filtered


_TOPIC_HINTS = {
    'brand_catalog': ('brand', 'brands', 'catalog', 'tie-up', 'tie up', 'assortment', 'variety', 'pharma', 'pharmaceutical'),
    'commission_margin': ('commission', 'margin', 'percent', '%', 'payout', 'earning'),
    'platform_usability': ('platform', 'app', 'set', 'medication set', 'login', 'onboarding', 'complex', 'confus', 'hectic', 'left it', 'leave it'),
    'procurement': ('purchase', 'buy', 'procure', 'supplier', 'order', 'stock', 'distributor'),
    'prescribing': ('prescrib', 'recommend', 'patient', 'condition'),
    'competitor': ('competitor', 'amil', 'dabur', 'patanjali', 'himalaya', 'baidyanath', 'kerala', 'arya vaidya', 'hamdard'),
    'pricing': ('price', 'cost', 'rate', 'cheaper', 'expensive'),
    'demand': ('demand', 'market', 'patients want', 'sales', 'volume'),
}


def _topic_keys(item: Dict[str, Any]) -> set:
    text = ' '.join([
        item.get('title', ''),
        item.get('detail_english', ''),
        item.get('verbatim_partner_quote', ''),
        item.get('quote_english', ''),
    ]).lower()
    keys = set()
    for k, words in _TOPIC_HINTS.items():
        if any(w in text for w in words):
            keys.add(k)
    return keys


def _content_tokens(item: Dict[str, Any]) -> set:
    blob = ' '.join([
        item.get('title', ''),
        item.get('detail_english', ''),
        item.get('quote_english', ''),
    ])
    norm = _norm(blob)
    stop = {
        'the', 'and', 'for', 'with', 'that', 'this', 'they', 'them', 'their',
        'partner', 'doctor', 'patient', 'patients', 'have', 'will', 'would',
        'about', 'from', 'into', 'onto', 'when', 'where', 'which', 'these',
        'those', 'there', 'because', 'also', 'more', 'less', 'than', 'such',
        'some', 'other', 'just', 'like', 'been', 'were', 'are',
    }
    return {t for t in norm.split() if len(t) >= 5 and t not in stop}


def _dedupe_insights(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse near-duplicate insights so that 1/2/4 are not 'про одно и то же'.

    Rule of thumb: same category + meaningful topic-key overlap, OR same category +
    high content token Jaccard, OR same category + identical/contained quote — merge.
    The first occurrence keeps title/why_it_matters; we extend its detail with the
    extra angle from the duplicate so nothing is lost.
    """
    if not items:
        return []
    kept: List[Dict[str, Any]] = []
    kept_topics: List[set] = []
    kept_tokens: List[set] = []
    kept_quotes: List[str] = []
    for it in items:
        topics = _topic_keys(it)
        tokens = _content_tokens(it)
        quote_norm = _norm(it.get('verbatim_partner_quote', ''))
        merged = False
        for idx, prev in enumerate(kept):
            if prev['category'] != it['category'] and not (topics & kept_topics[idx]):
                continue
            jaccard = 0.0
            if tokens or kept_tokens[idx]:
                inter = len(tokens & kept_tokens[idx])
                union = max(1, len(tokens | kept_tokens[idx]))
                jaccard = inter / union
            shared_topics = bool(topics & kept_topics[idx])
            quote_overlap = (
                quote_norm and kept_quotes[idx] and (
                    quote_norm in kept_quotes[idx] or kept_quotes[idx] in quote_norm
                )
            )
            same_topic_strong = shared_topics and prev['category'] == it['category']
            if jaccard >= 0.65 or quote_overlap or (same_topic_strong and jaccard >= 0.5):
                extra = (it.get('detail_english') or '').strip()
                if extra and extra not in (prev.get('detail_english') or ''):
                    prev['detail_english'] = (prev.get('detail_english', '').rstrip() + ' ' + extra).strip()
                if not prev.get('why_it_matters') and it.get('why_it_matters'):
                    prev['why_it_matters'] = it['why_it_matters']
                kept_topics[idx] = kept_topics[idx] | topics
                kept_tokens[idx] = kept_tokens[idx] | tokens
                merged = True
                break
        if not merged:
            kept.append(dict(it))
            kept_topics.append(topics)
            kept_tokens.append(tokens)
            kept_quotes.append(quote_norm)
    return kept


def _extract_partner_lines(transcript_text: str) -> List[str]:
    lines: List[str] = []
    for m in re.finditer(r'\*\*Partner:\*\*\s*(.+)', transcript_text or ''):
        line = (m.group(1) or '').strip()
        if line:
            lines.append(line)
    return lines


def _norm(s: str) -> str:
    s = (s or '').lower()
    s = re.sub(r'[^a-z0-9\s%]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _is_low_signal_insight(item: Dict[str, Any]) -> bool:
    quote = (item.get('verbatim_partner_quote') or '').strip().lower()
    detail = (item.get('detail_english') or '').strip().lower()
    title = (item.get('title') or '').strip().lower()
    noise_patterns = [
        r'^(ok|okay|yes|yeah|hmm|hmmm|got it|right|fine|sure)[\.\!\? ]*$',
        r'^(i got it|understood|done|h[aá]n|achha|ji)[\.\!\? ]*$',
    ]
    if quote and any(re.match(p, quote) for p in noise_patterns):
        return True
    tiny_quote = len(quote) < 18 and not re.search(r'\d|%|commission|brand|platform|patient|set|price|sale', quote)
    weak_detail = len(detail) < 50 and len(title) < 20
    return tiny_quote and weak_detail


def _is_quote_grounded(quote: str, partner_lines: List[str]) -> bool:
    q = _norm(quote)
    if not q:
        return False
    partner_norm = [_norm(x) for x in (partner_lines or []) if _norm(x)]
    if not partner_norm:
        return True
    if len(q) >= 24 and any(q in line for line in partner_norm):
        return True

    q_tokens = {t for t in q.split() if len(t) >= 4}
    if not q_tokens:
        return True
    for line in partner_norm:
        lt = {t for t in line.split() if len(t) >= 4}
        inter = len(q_tokens & lt)
        if inter >= max(4, int(len(q_tokens) * 0.4)):
            return True
    return False


def _is_business_useful(item: Dict[str, Any]) -> bool:
    category = (item.get('category') or '').strip().lower()
    quote = (item.get('verbatim_partner_quote') or '').lower()
    text = f"{item.get('title', '')} {item.get('detail_english', '')} {quote}".lower()

    strategic_keywords = (
        'platform', 'ask ayurveda', 'commission', 'margin', 'pricing', 'price',
        'competitor', 'supplier', 'procure', 'buy', 'purchase', 'stock',
        'prescrib', 'recommend', 'set', 'brand', 'manufacturer', 'market', 'demand',
        'conversion', 'adoption', 'trust', 'quality', 'patient',
    )
    biography_patterns = (
        'integrated clinic', 'doctor is', 'i am an ayurvedic physician',
        'my clinic', 'my biography', 'my background',
    )
    decision_signal = (
        'buy', 'purchase', 'procure', 'source', 'supplier', 'from', 'tie-up',
        'commission', 'margin', 'prescrib', 'recommend', 'switch', 'prefer', 'instead',
        'adopt', 'use platform', 'onboard', 'catalog', 'medication set', 'link',
        'barrier', 'difficult', 'confus', 'not using', 'stopped at',
    )
    quote_business_signal = (
        'buy', 'purchase', 'procure', 'source', 'supplier', 'order', 'stock',
        'tie-up', 'commission', 'margin', 'prescrib', 'recommend',
        'switch', 'prefer', 'instead', 'catalog', 'medication set', 'link',
        'not using', 'stopped',
    )

    if any(p in text for p in biography_patterns) and not any(k in text for k in strategic_keywords):
        return False

    # Generic efficacy/quality statements are not useful unless tied to business decision/process.
    generic_quality_only = (
        any(k in text for k in ('good result', 'effective', 'quality', 'trustworthy', 'works well'))
        and not any(k in text for k in decision_signal)
    )
    if generic_quality_only:
        return False

    generic_modality_background = (
        any(k in text for k in ('allopathic', 'ayurvedic treatment', 'integrated clinic', 'mixopathic'))
        and not any(k in text for k in ('prescrib', 'recommend', 'procure', 'buy', 'supplier', 'commission', 'platform'))
    )
    if generic_modality_background:
        return False

    # Category-specific gates for tougher precision.
    if category in {'competitors', 'manufacturers'}:
        if not any(k in text for k in ('brand', 'competitor', 'supplier', 'manufacturer', 'alternative')):
            return False
        if not any(k in quote for k in quote_business_signal):
            return False

    if category in {'platform_ask_ayurveda', 'product', 'prescribing_procurement', 'earning_money'}:
        if not any(k in text for k in decision_signal + strategic_keywords):
            return False

    if category in {
        'product', 'market_ayurveda', 'competitors', 'manufacturers',
        'platform_ask_ayurveda', 'prescribing_procurement', 'earning_money',
    }:
        return True

    # For "other", keep only clearly strategic/process-oriented points.
    return any(k in text for k in strategic_keywords)


def _polish_json_text(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('```', 2)[1] if '```' in raw else raw
        if raw.startswith('json'):
            raw = raw[4:].lstrip()
    raw = raw.strip()
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)
    raw = re.sub(r'[\x00-\x09\x0b\x0c\x0e-\x1f]', ' ', raw)
    return raw


def _product_context_block() -> str:
    try:
        from accounts.models import CRMSettings
        info = (CRMSettings.get().product_info or '').strip()
        if info:
            return (
                "Product Context (from AI Settings):\n"
                f"{info}\n"
            )
    except Exception:
        pass
    return "Product Context: [not provided]\n"


def _send_telegram_async(insight_pk: int):
    close_old_connections()
    try:
        from .models import CallInsight
        from .telegram_insights import format_insight_html, send_insight_html

        ci = CallInsight.objects.select_related('partner', 'contact', 'created_by').filter(pk=insight_pk).first()
        if not ci or ci.status != CallInsight.STATUS_DONE:
            return

        if not (os.environ.get('TELEGRAM_BOT_TOKEN') or '').strip():
            CallInsight.objects.filter(pk=insight_pk).update(
                telegram_status=CallInsight.TELEGRAM_SKIPPED,
                telegram_last_error='',
                telegram_last_attempt_at=timezone.now(),
            )
            return

        body = format_insight_html(ci)

        CallInsight.objects.filter(pk=insight_pk).update(
            telegram_status=CallInsight.TELEGRAM_PENDING,
            telegram_last_attempt_at=timezone.now(),
        )
        ids = send_insight_html(body)
        CallInsight.objects.filter(pk=insight_pk).update(
            telegram_status=CallInsight.TELEGRAM_SENT,
            telegram_last_error='',
            telegram_message_ids=ids,
            telegram_last_attempt_at=timezone.now(),
            telegram_retries=0,
        )
    except Exception as e:
        try:
            from django.db.models import F
            from .models import CallInsight
            CallInsight.objects.filter(pk=insight_pk).update(
                telegram_status=CallInsight.TELEGRAM_FAILED,
                telegram_last_error=repr(e)[:4000],
                telegram_last_attempt_at=timezone.now(),
                telegram_retries=F('telegram_retries') + 1,
            )
        except Exception:
            pass
        logger.warning('Telegram async send failed for insight %s: %s', insight_pk, e)
    finally:
        close_old_connections()


def extract_call_insights(contact_id: int, force: bool = False) -> None:
    """
    Generate or refresh CallInsight for a contact. Idempotent when transcript unchanged.
    """
    if not OPENAI_API_KEY:
        logger.warning('OPENAI_API_KEY not set — call insights skipped')
        return

    from openai import OpenAI
    from .models import CallInsight, Contact

    close_old_connections()
    try:
        contact = Contact.objects.select_related('partner', 'created_by').filter(pk=contact_id).first()
        if not contact or contact.transcription_status != Contact.TRANSCRIPTION_DONE:
            return

        transcript = (contact.diarized_transcript or contact.transcription or '').strip()
        if not transcript:
            return

        fingerprint = hashlib.sha256(transcript.encode('utf-8')).hexdigest()
        work = transcript[:MAX_TRANSCRIPT_CHARS]
        truncated = len(transcript) > MAX_TRANSCRIPT_CHARS

        insight, _created = CallInsight.objects.get_or_create(
            contact=contact,
            defaults={
                'partner': contact.partner,
                'call_date': contact.date,
                'created_by': contact.created_by,
                'status': CallInsight.STATUS_PENDING,
            },
        )

        if (
            not force
            and insight.status == CallInsight.STATUS_DONE
            and insight.transcript_fingerprint == fingerprint
        ):
            return

        insight.partner = contact.partner
        insight.call_date = contact.date
        insight.created_by = contact.created_by
        insight.status = CallInsight.STATUS_PROCESSING
        insight.telegram_status = CallInsight.TELEGRAM_PENDING
        insight.telegram_message_ids = []
        insight.telegram_last_error = ''
        insight.save()

        partner_lines = _extract_partner_lines(work)
        partner_evidence = '\n'.join(f'- {line}' for line in partner_lines[:180])
        if not partner_evidence:
            partner_evidence = '- [No explicit Partner labels detected; use best effort from transcript.]'
        prompt = INSIGHTS_USER_PROMPT.format(
            transcript=work,
            partner_evidence=partner_evidence,
            product_context_block=_product_context_block(),
        )
        if truncated:
            prompt += (
                f"\n\n[Note: transcript truncated to {MAX_TRANSCRIPT_CHARS} characters for this pass.]"
            )

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                attempt_prompt = prompt
                if attempt > 0:
                    attempt_prompt += "\n\n[Retry requirement: improve precision and remove weak/biography-only items.]"
                client = OpenAI(api_key=OPENAI_API_KEY)
                models_to_try = [INSIGHTS_MODEL] + [m for m in INSIGHTS_FALLBACK_MODELS if m != INSIGHTS_MODEL]
                message = None
                model_used = None
                model_errors: List[str] = []
                for mdl in models_to_try:
                    try:
                        message = client.chat.completions.create(
                            model=mdl,
                            max_tokens=8192,
                            response_format={'type': 'json_object'},
                            messages=[
                                {'role': 'system', 'content': 'Return valid JSON only.'},
                                {'role': 'user', 'content': attempt_prompt},
                            ],
                        )
                        model_used = mdl
                        break
                    except Exception as model_err:
                        msg = str(model_err)
                        model_errors.append(f'{mdl}: {msg[:200]}')
                        if not any(tok in msg.lower() for tok in ('model', 'not found', 'does not exist', 'unsupported', 'permission')):
                            raise
                        logger.warning('Insights model %s unavailable, trying next: %s', mdl, msg[:200])
                if message is None:
                    raise RuntimeError('All insight models failed: ' + ' | '.join(model_errors))
                logger.info('CallInsight using model=%s for contact=%s', model_used, contact_id)
                raw = message.choices[0].message.content or ''
                raw = _polish_json_text(raw)
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError('Model returned non-object JSON')

                insights_list = _sanitize_insights(data.get('insights'), partner_lines=partner_lines)
                if truncated and isinstance(data.get('call_title_english'), str):
                    data['call_title_english'] = data['call_title_english'].strip() + ' (partial transcript)'

                data['insights'] = insights_list
                count = len(insights_list)
                bucket = _density_bucket(count)
                md = _build_markdown(data, insight_count=count, density_bucket=bucket)

                insight.insights_json = data
                insight.insights_markdown = md
                insight.insight_count = count
                insight.density_bucket = bucket
                insight.transcript_fingerprint = fingerprint
                insight.status = CallInsight.STATUS_DONE
                insight.last_error = ''
                insight.retries = 0
                insight.last_attempt_at = timezone.now()
                insight.telegram_status = CallInsight.TELEGRAM_PENDING
                insight.telegram_retries = 0
                insight.telegram_last_error = ''
                insight.save()

                threading.Thread(
                    target=_send_telegram_async,
                    args=(insight.pk,),
                    daemon=True,
                ).start()
                logger.info('CallInsight done for contact %s (%d items)', contact_id, count)
                return

            except Exception as e:
                last_error = e
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
                logger.warning(
                    'CallInsight attempt %s/%s failed for contact %s: %s',
                    attempt + 1, MAX_RETRIES, contact_id, e,
                )
                time.sleep(delay)

        from django.db.models import F
        CallInsight.objects.filter(pk=insight.pk).update(
            status=CallInsight.STATUS_FAILED,
            last_error=repr(last_error)[:4000] if last_error else 'unknown',
            retries=F('retries') + 1,
            last_attempt_at=timezone.now(),
        )
        logger.error('CallInsight failed for contact %s: %s', contact_id, last_error)

    finally:
        close_old_connections()


def extract_call_insights_background(contact_id: int):
    """Entry point for threading / management commands."""
    close_old_connections()
    try:
        extract_call_insights(contact_id, force=False)
    except Exception as e:
        logger.exception('extract_call_insights_background crashed: %s', e)
    finally:
        close_old_connections()
