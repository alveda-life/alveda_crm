"""
Build a cross-call aggregate report from individual CallInsight items.

Goal: cluster similar partner statements across many calls so the team can see
"how many doctors said X" instead of reading every transcript.

Pipeline:
  1. Pull all CallInsight (status=done) within [date_from, date_to].
  2. Compress every individual insight item into a one-line record carrying
     partner_id / partner_name / category / sentiment / title / quote.
  3. Ask the LLM (gpt-4.1 by default) to cluster them by underlying business
     theme — same operation as call-level dedup but cross-call.
  4. For each cluster compute partner_count from the actual partner_ids the
     model assigned (we trust the LLM for cluster membership but recompute
     unique-partner counts ourselves so we never report inflated numbers).
  5. Rank clusters by unique partner count desc, build markdown.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, time as dtime, timezone as dttz
from typing import Any, Dict, List

from django.db import close_old_connections
from django.utils import timezone

from .insights import (
    INSIGHTS_FALLBACK_MODELS,
    INSIGHTS_MODEL,
    OPENAI_API_KEY,
    _polish_json_text,
    _product_context_block,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]
MAX_INSIGHTS_PER_CALL = 30  # safety cap per record so prompt size stays sane
MAX_TOTAL_RECORDS = 800     # cap total items sent to LLM (older items dropped first)
MAX_PROMPT_QUOTE_CHARS = 380


_CATEGORY_LABELS = {
    'product': 'Product / Offer',
    'market_ayurveda': 'Ayurveda Market',
    'competitors': 'Competitors / Alternatives',
    'manufacturers': 'Manufacturers / Brands',
    'platform_ask_ayurveda': 'Ask Ayurveda Platform',
    'prescribing_procurement': 'Prescribing / Procurement',
    'physician_practice': 'Prescribing / Procurement',
    'earning_money': 'Earnings / Margins',
    'other': 'Other',
}


AGGREGATE_PROMPT = """You aggregate sales-call partner insights across MANY calls into a single ranked report for AskAyurveda leadership.

{product_context_block}

INPUT: a JSON array of individual insight records, each with:
  rid (record id), partner_id, partner_name, category, sentiment, title, quote.
Multiple records can come from the same partner (different topics in the same call).

GOAL: cluster records that express the SAME underlying business idea (across different doctors / different wordings / different languages). Then rank clusters by how many UNIQUE partners voiced them.

CLUSTERING RULES (strict — read TWICE before writing output):
- Same business idea = same cluster, even if wording, framing, or polarity differs.
  CRITICAL EXAMPLES of records that MUST collapse into ONE cluster:
   * "Few brands available on AskAyurveda" + "Add more brands to the catalog" + "Catalog is limited to 1–2 manufacturers" + "We need more pharmaceutical companies" + "I want more variety of brands" → ONE cluster about catalog breadth.
   * "Commission too low" + "Margins not competitive vs my pharma tie-up" + "Earnings here are smaller than what I get elsewhere" → ONE cluster about earnings competitiveness.
   * "Platform is confusing" + "Set creation flow is hectic" + "Need more onboarding help" → ONE cluster about platform usability.
- Frame each cluster around the underlying NEED or PROBLEM, never around a specific phrasing. Two records discussing the SAME need from positive vs negative angles still belong together.
- Different clusters ONLY if the action implication is genuinely different:
   * Catalog breadth ≠ Commission structure ≠ Platform UX ≠ Logistics/delivery ≠ Patient acquisition.
- Drop records that are pure biography, acknowledgement, or filler. Do NOT make a cluster from a single fluff record.
- TARGET 8–15 strong, well-merged clusters. Hard cap at 15. If you have <8 truly distinct themes, return fewer rather than padding.
- A cluster may have a single record if the point is genuinely material (sharp competitor pricing, named competitor mention, explicit feature request, etc.).
- Before finalising: re-read every cluster theme and ask "could this be merged with another?". If yes, merge.

For each cluster output:
- theme: short English headline (<=90 chars), business-actionable. Frame around the underlying need ("Catalog breadth blocks daily prescribing"), not around a single quote.
- category: one of product|market_ayurveda|competitors|manufacturers|platform_ask_ayurveda|prescribing_procurement|earning_money|other
- explanation: 3–5 sentences in English (~400–600 characters total). Explain WHAT the consolidated point is, the typical wording across partners, the WHY it matters for AskAyurveda, and the strategic implication. Be concrete, no platitudes.
- recommended_action: 1–2 sentences, concrete next step the team should consider
- sentiment_breakdown: object {{ "positive": n, "negative": n, "neutral": n, "mixed": n }} counting member records
- representative_quotes: 2–4 strongest verbatim member quotes, each {{ "partner_id": <int>, "partner_name": "...", "quote": "..." }}; preserve original wording (non-English allowed)
- record_ids: ARRAY of EVERY rid that belongs to this cluster (this is the source of truth for partner counts; be exhaustive — never omit a record that clearly belongs)

ALSO produce:
- executive_summary: 2–4 sentences capturing the biggest takeaways across all clusters
- top_priorities: array of 1–5 short bullet strings (the most actionable items, ordered by urgency)

Return JSON ONLY (no markdown fences) with this exact shape:
{{
  "executive_summary": "...",
  "top_priorities": ["...", "..."],
  "clusters": [
    {{
      "theme": "...",
      "category": "...",
      "explanation": "...",
      "recommended_action": "...",
      "sentiment_breakdown": {{"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}},
      "representative_quotes": [{{"partner_id": 1, "partner_name": "Dr X", "quote": "..."}}],
      "record_ids": [1, 2, 3]
    }}
  ]
}}

If the input is empty or has no material business signal, return clusters: [] with a short executive_summary stating that.

Records (JSON):
{records_json}
"""


MERGE_PROMPT = """You are a strict deduplication editor for a sales-insight report.

You receive a JSON array of clusters. Each cluster has:
  cid (int), theme, category, sample_quotes (1–3 short verbatim quotes).

YOUR JOB: identify clusters that express the SAME underlying business need or problem and group them together. Different surface wording, opposite framing (problem vs. feature request), different category labels — all of these are still the SAME insight if the action implication is the same.

CRITICAL EXAMPLES OF THINGS THAT MUST BE GROUPED TOGETHER:
- "Few brands available" + "Add more brands to the catalog" + "Limited multi-brand catalog" + "Doctors prescribe multi-brand per indication; single-brand catalogs don't fit" + "Need more pharmaceutical companies" + "Want more variety of brands" → ONE GROUP. (All about catalog breadth.)
- "Commission too low" + "Earnings not competitive" + "Margins worse than my pharma tie-up" + "Want better commission" → ONE GROUP. (All about earning competitiveness.)
- "Platform onboarding confusing" + "Platform navigation is hard" + "Set creation flow is hectic" + "Need more onboarding help" + "Account registration issues" + "Mobile accessibility issues" → ONE GROUP. (All about platform usability/access.)
- "Slow delivery" + "Logistics issues" + "Patients wait too long" → ONE GROUP. (Delivery operations.)
- "Want consultation scheduling" + "Want availability notifications" + "Want appointment slots" → ONE GROUP. (Consultation scheduling.)

A cluster is its OWN group only if no other cluster shares the same underlying need.

DO NOT split based on:
- Different category labels (e.g., 'product' vs 'prescribing_procurement' vs 'manufacturers' — these often label the same brand-catalog issue from different angles).
- Different polarity (positive vs negative wording about the same topic).
- Different specificity (broad complaint vs specific instance of the same complaint).

Return JSON ONLY:
{{
  "groups": [
    {{"cids": [1, 6], "rationale": "both about catalog breadth"}},
    {{"cids": [3], "rationale": "standalone — commission topic"}}
  ]
}}

Every cid from the input MUST appear in exactly one group. No omissions, no duplicates.

Clusters to consider:
{clusters_json}
"""


# Keyword fingerprint families: clusters whose themes share a strong family token
# get force-merged after the LLM merge pass as a deterministic safety net.
# Keys are family ids; values are the keyword sets that identify the family.
_MERGE_FAMILIES: List[Dict[str, Any]] = [
    {
        'id': 'catalog_breadth',
        'keywords': {'brand', 'brands', 'catalog', 'catalogue', 'multi-brand',
                     'pharmaceutical', 'pharmaceuticals', 'manufacturer', 'manufacturers',
                     'variety of', 'more brand', 'few brand', 'limited brand',
                     'single-brand', 'kerala ayurveda only'},
        'min_hits': 1,
    },
    {
        'id': 'commission_earnings',
        'keywords': {'commission', 'commissions', 'margin', 'margins', 'earning',
                     'earnings', 'tie-up', 'tieup', 'payout', 'incentive', 'incentives'},
        'min_hits': 1,
    },
    {
        'id': 'platform_usability',
        'keywords': {'onboard', 'onboarding', 'navigation', 'usability', 'ux',
                     'set creation', 'registration', 'mobile access', 'accessibility',
                     'confusing', 'hectic', 'platform access'},
        'min_hits': 1,
    },
    {
        'id': 'logistics_delivery',
        'keywords': {'delivery', 'logistic', 'logistics', 'shipping', 'dispatch',
                     'wait', 'waiting'},
        'min_hits': 1,
    },
    {
        'id': 'scheduling',
        'keywords': {'scheduling', 'availability', 'appointment', 'slot', 'slots',
                     'time slot', 'consultation time'},
        'min_hits': 1,
    },
]


def _family_for_cluster(cluster: Dict[str, Any]) -> str | None:
    """Return the family id whose keywords are present in the cluster's text."""
    blob = ' '.join([
        str(cluster.get('theme', '')),
        str(cluster.get('explanation', '')),
        ' '.join(q.get('quote', '') for q in (cluster.get('representative_quotes') or [])),
    ]).lower()
    best_family = None
    best_hits = 0
    for fam in _MERGE_FAMILIES:
        hits = sum(1 for kw in fam['keywords'] if kw in blob)
        if hits >= fam['min_hits'] and hits > best_hits:
            best_family = fam['id']
            best_hits = hits
    return best_family


def _parse_period(date_from, date_to):
    """Return (start_dt, end_dt) inclusive, both timezone-aware UTC."""
    start = datetime.combine(date_from, dtime.min, tzinfo=dttz.utc)
    end = datetime.combine(date_to, dtime.max, tzinfo=dttz.utc)
    return start, end


def _truncate_quote(s: str, limit: int = MAX_PROMPT_QUOTE_CHARS) -> str:
    s = (s or '').strip()
    if len(s) <= limit:
        return s
    return s[: limit - 1].rstrip() + '…'


def _collect_records(date_from, date_to) -> Dict[str, Any]:
    """Build the compressed input array sent to the LLM and basic counts."""
    from .models import CallInsight

    start, end = _parse_period(date_from, date_to)
    qs = (
        CallInsight.objects
        .filter(status=CallInsight.STATUS_DONE, call_date__gte=start, call_date__lte=end)
        .select_related('partner')
        .order_by('-call_date')
    )

    records: List[Dict[str, Any]] = []
    partner_lookup: Dict[int, str] = {}
    total_calls = 0
    rid = 1
    for ci in qs.iterator():
        total_calls += 1
        items = (ci.insights_json or {}).get('insights') or []
        if not isinstance(items, list):
            continue
        for it in items[:MAX_INSIGHTS_PER_CALL]:
            if not isinstance(it, dict):
                continue
            partner_id = ci.partner_id
            partner_name = ci.partner.name if ci.partner_id else 'Partner'
            if partner_id:
                partner_lookup[partner_id] = partner_name
            records.append({
                'rid': rid,
                'partner_id': partner_id,
                'partner_name': partner_name,
                'category': str(it.get('category', 'other')).lower(),
                'sentiment': str(it.get('sentiment', 'neutral')).lower(),
                'title': str(it.get('title', '')).strip()[:200],
                'quote': _truncate_quote(it.get('verbatim_partner_quote', '')),
            })
            rid += 1

    if len(records) > MAX_TOTAL_RECORDS:
        records = records[:MAX_TOTAL_RECORDS]

    unique_partners = len({r['partner_id'] for r in records if r.get('partner_id')})
    return {
        'records': records,
        'partner_lookup': partner_lookup,
        'total_calls': total_calls,
        'unique_partners': unique_partners,
    }


def _normalise_clusters(clusters: Any, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(clusters, list):
        return []
    record_by_id = {r['rid']: r for r in records}
    out: List[Dict[str, Any]] = []
    for cl in clusters:
        if not isinstance(cl, dict):
            continue
        rids_raw = cl.get('record_ids') or []
        rids: List[int] = []
        for x in rids_raw:
            try:
                rids.append(int(x))
            except (TypeError, ValueError):
                continue
        members = [record_by_id[r] for r in rids if r in record_by_id]
        partner_ids = sorted({m['partner_id'] for m in members if m.get('partner_id')})

        # Recompute sentiment breakdown from real member records to avoid LLM drift.
        sb = Counter()
        for m in members:
            sb[m.get('sentiment') or 'neutral'] += 1
        sentiment_breakdown = {k: int(sb.get(k, 0)) for k in ('positive', 'negative', 'neutral', 'mixed')}

        category = str(cl.get('category', 'other')).lower()
        if category == 'physician_practice':
            category = 'prescribing_procurement'
        if category not in _CATEGORY_LABELS:
            category = 'other'

        # Trust LLM-picked quotes but ensure each ties to a real member partner where possible.
        quotes_raw = cl.get('representative_quotes') or []
        quotes: List[Dict[str, Any]] = []
        for q in quotes_raw[:6]:
            if not isinstance(q, dict):
                continue
            quote_text = str(q.get('quote', '')).strip()
            if not quote_text:
                continue
            try:
                pid = int(q.get('partner_id')) if q.get('partner_id') is not None else None
            except (TypeError, ValueError):
                pid = None
            pname = str(q.get('partner_name') or '').strip() or 'Partner'
            quotes.append({
                'partner_id': pid,
                'partner_name': pname,
                'quote': quote_text,
            })
        if not quotes and members:
            quotes = [{
                'partner_id': members[0]['partner_id'],
                'partner_name': members[0]['partner_name'],
                'quote': members[0]['quote'],
            }]

        out.append({
            'theme': str(cl.get('theme', '')).strip()[:200] or 'Untitled cluster',
            'category': category,
            'explanation': str(cl.get('explanation', '')).strip(),
            'recommended_action': str(cl.get('recommended_action', '')).strip(),
            'sentiment_breakdown': sentiment_breakdown,
            'representative_quotes': quotes,
            'partner_ids': partner_ids,
            'partner_count': len(partner_ids),
            'mention_count': len(members),
            '_rids': sorted(set(rids)),  # internal: needed for merge passes
        })

    out.sort(key=lambda c: (-c['partner_count'], -c['mention_count']))
    return out


def _strip_internal_fields(clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove fields prefixed with `_` before persisting to the DB."""
    return [{k: v for k, v in c.items() if not k.startswith('_')} for c in clusters]


def _merge_clusters_by_groups(
    clusters: List[Dict[str, Any]],
    groups: List[List[int]],
    records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Apply merge groups (each group is a list of cluster indices) and rebuild
    the resulting consolidated clusters from underlying records.
    """
    record_by_id = {r['rid']: r for r in records}
    out: List[Dict[str, Any]] = []
    for grp in groups:
        if not grp:
            continue
        merged_rids: List[int] = []
        chosen_idx = grp[0]  # primary cluster keeps headline/explanation
        max_partners = -1
        for idx in grp:
            if idx < 0 or idx >= len(clusters):
                continue
            c = clusters[idx]
            for r in c.get('partner_ids', []):
                pass  # partner_ids are derived from members; we'll recompute
            # Reconstruct rid set from each cluster's stored members.
            # (partner_ids alone isn't enough — we need the actual records.)
            for rid in c.get('_rids', []):
                merged_rids.append(rid)
            if c.get('partner_count', 0) > max_partners:
                max_partners = c.get('partner_count', 0)
                chosen_idx = idx
        # Dedup rids
        merged_rids = sorted(set(merged_rids))
        members = [record_by_id[r] for r in merged_rids if r in record_by_id]
        if not members and chosen_idx < len(clusters):
            # Fall back to keeping the chosen cluster as-is.
            out.append(clusters[chosen_idx])
            continue

        partner_ids = sorted({m['partner_id'] for m in members if m.get('partner_id')})
        sb = Counter()
        for m in members:
            sb[m.get('sentiment') or 'neutral'] += 1
        sentiment_breakdown = {k: int(sb.get(k, 0)) for k in ('positive', 'negative', 'neutral', 'mixed')}

        primary = clusters[chosen_idx]
        # Combine representative quotes from all merged clusters, dedup by quote text.
        seen_quotes: set = set()
        combined_quotes: List[Dict[str, Any]] = []
        for idx in grp:
            if idx < 0 or idx >= len(clusters):
                continue
            for q in (clusters[idx].get('representative_quotes') or []):
                key = (q.get('quote') or '').strip().lower()[:120]
                if not key or key in seen_quotes:
                    continue
                seen_quotes.add(key)
                combined_quotes.append(q)
            if len(combined_quotes) >= 6:
                break

        # Merge explanations: keep primary, append non-overlapping sentences from others.
        explanation = primary.get('explanation', '').strip()

        merged_cluster = {
            'theme': primary.get('theme', '').strip()[:200] or 'Untitled cluster',
            'category': primary.get('category', 'other'),
            'explanation': explanation,
            'recommended_action': primary.get('recommended_action', '').strip(),
            'sentiment_breakdown': sentiment_breakdown,
            'representative_quotes': combined_quotes[:6] or primary.get('representative_quotes', []),
            'partner_ids': partner_ids,
            'partner_count': len(partner_ids),
            'mention_count': len(members),
            '_rids': merged_rids,
        }
        out.append(merged_cluster)

    out.sort(key=lambda c: (-c['partner_count'], -c['mention_count']))
    return out


def _llm_merge_pass(
    clusters: List[Dict[str, Any]],
    records: List[Dict[str, Any]],
    client,
    model_used: str,
) -> List[Dict[str, Any]]:
    """
    Ask the LLM to identify merge groups across the existing clusters and apply them.

    Returns the merged cluster list. If anything goes wrong we return the input unchanged.
    """
    if len(clusters) < 2:
        return clusters

    compact = []
    for i, c in enumerate(clusters):
        sample_quotes = [
            (q.get('quote') or '').strip()[:160]
            for q in (c.get('representative_quotes') or [])[:3]
            if (q.get('quote') or '').strip()
        ]
        compact.append({
            'cid': i,
            'theme': c.get('theme', ''),
            'category': c.get('category', 'other'),
            'sample_quotes': sample_quotes,
        })

    prompt = MERGE_PROMPT.format(clusters_json=json.dumps(compact, ensure_ascii=False))

    try:
        message = client.chat.completions.create(
            model=model_used,
            max_tokens=2048,
            response_format={'type': 'json_object'},
            messages=[
                {'role': 'system', 'content': 'Return valid JSON only.'},
                {'role': 'user', 'content': prompt},
            ],
        )
        raw = _polish_json_text(message.choices[0].message.content or '')
        data = json.loads(raw)
        groups_raw = (data.get('groups') or [])
        groups: List[List[int]] = []
        seen_cids: set = set()
        for g in groups_raw:
            cids = []
            for x in (g.get('cids') or []):
                try:
                    ix = int(x)
                except (TypeError, ValueError):
                    continue
                if 0 <= ix < len(clusters) and ix not in seen_cids:
                    cids.append(ix)
                    seen_cids.add(ix)
            if cids:
                groups.append(cids)

        # Backstop: any cluster cid the model forgot becomes its own group.
        for i in range(len(clusters)):
            if i not in seen_cids:
                groups.append([i])

        if not groups:
            return clusters

        merged = _merge_clusters_by_groups(clusters, groups, records)
        if any(len(g) > 1 for g in groups):
            logger.info(
                'LLM merge pass collapsed %d clusters into %d (groups=%s)',
                len(clusters), len(merged), [g for g in groups if len(g) > 1],
            )
        return merged
    except Exception as e:
        logger.warning('LLM merge pass failed, keeping clusters as-is: %s', e)
        return clusters


def _family_merge_pass(
    clusters: List[Dict[str, Any]],
    records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Deterministic safety net: any clusters whose theme/explanation match the
    same keyword family (catalog_breadth, commission_earnings, platform_usability,
    logistics_delivery, scheduling) get force-merged.
    """
    families: Dict[str, List[int]] = defaultdict(list)
    standalone: List[int] = []
    for i, c in enumerate(clusters):
        fam = _family_for_cluster(c)
        if fam:
            families[fam].append(i)
        else:
            standalone.append(i)

    groups: List[List[int]] = []
    merged_anything = False
    for fam, idxs in families.items():
        if len(idxs) > 1:
            merged_anything = True
            logger.info('Family merge: %s collapses clusters %s', fam, idxs)
        groups.append(idxs)
    for i in standalone:
        groups.append([i])

    if not merged_anything:
        return clusters
    return _merge_clusters_by_groups(clusters, groups, records)


def _build_markdown(payload: Dict[str, Any], clusters: List[Dict[str, Any]]) -> str:
    period = payload.get('period') or {}
    totals = payload.get('totals') or {}
    lines: List[str] = [
        f"## Aggregate Insight Report — {period.get('from', '?')} to {period.get('to', '?')}",
        '',
        (
            f"**Period coverage:** {totals.get('calls', 0)} calls · "
            f"{totals.get('insights', 0)} raw insights · "
            f"{totals.get('partners', 0)} unique partners"
        ),
        '',
    ]

    summary = (payload.get('executive_summary') or '').strip()
    if summary:
        lines.append('### Executive summary')
        lines.append(summary)
        lines.append('')

    top = payload.get('top_priorities') or []
    if top:
        lines.append('### Top priorities')
        for item in top:
            t = str(item or '').strip()
            if t:
                lines.append(f'- {t}')
        lines.append('')

    if not clusters:
        lines.append('_No clustered themes available for this period._')
        return '\n'.join(lines).strip()

    lines.append('### Themes (ranked by unique partners)')
    lines.append('')
    for i, c in enumerate(clusters, 1):
        cat = _CATEGORY_LABELS.get(c['category'], 'Other')
        sb = c['sentiment_breakdown']
        sb_str = ' · '.join(f'{k}: {v}' for k, v in sb.items() if v)
        lines.append(f"### {i}. {c['theme']}")
        lines.append(
            f"**{c['partner_count']} partner(s)** · {c['mention_count']} mention(s) · "
            f"Category: {cat}"
            + (f' · Sentiment — {sb_str}' if sb_str else '')
        )
        lines.append('')
        if c['explanation']:
            lines.append(c['explanation'])
            lines.append('')
        if c['recommended_action']:
            lines.append(f"**Recommended action:** {c['recommended_action']}")
            lines.append('')
        if c['representative_quotes']:
            lines.append('**Representative quotes:**')
            for q in c['representative_quotes'][:4]:
                pname = q.get('partner_name') or 'Partner'
                lines.append(f"- _{pname}_: \u00ab{q['quote']}\u00bb")
            lines.append('')
    return '\n'.join(lines).strip()


def build_aggregate(aggregate_id: int, force: bool = False) -> None:
    """Generate or refresh an InsightAggregate row."""
    if not OPENAI_API_KEY:
        logger.warning('OPENAI_API_KEY not set — aggregate skipped')
        return

    from openai import OpenAI
    from .models import InsightAggregate

    close_old_connections()
    try:
        agg = InsightAggregate.objects.filter(pk=aggregate_id).first()
        if not agg:
            return
        if not force and agg.status == InsightAggregate.STATUS_DONE:
            return

        agg.status = InsightAggregate.STATUS_PROCESSING
        agg.last_attempt_at = timezone.now()
        agg.save(update_fields=['status', 'last_attempt_at', 'updated_at'])

        collected = _collect_records(agg.date_from, agg.date_to)
        records = collected['records']

        if not records:
            payload = {
                'period': {'from': agg.date_from.isoformat(), 'to': agg.date_to.isoformat()},
                'totals': {'calls': collected['total_calls'], 'insights': 0, 'partners': 0},
                'executive_summary': 'No completed call insights were available in this period.',
                'top_priorities': [],
                'clusters': [],
            }
            agg.summary_text = payload['executive_summary']
            agg.clusters_json = payload
            agg.rendered_markdown = _build_markdown(payload, [])
            agg.total_calls = collected['total_calls']
            agg.total_insights = 0
            agg.unique_partners = 0
            agg.status = InsightAggregate.STATUS_DONE
            agg.completed_at = timezone.now()
            agg.last_error = ''
            agg.retries = 0
            agg.save()
            return

        prompt = AGGREGATE_PROMPT.format(
            product_context_block=_product_context_block(),
            records_json=json.dumps(records, ensure_ascii=False),
        )

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
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
                                {'role': 'user', 'content': prompt},
                            ],
                        )
                        model_used = mdl
                        break
                    except Exception as model_err:
                        msg = str(model_err)
                        model_errors.append(f'{mdl}: {msg[:200]}')
                        if not any(tok in msg.lower() for tok in ('model', 'not found', 'does not exist', 'unsupported', 'permission')):
                            raise
                        logger.warning('Aggregate model %s unavailable, trying next: %s', mdl, msg[:200])
                if message is None:
                    raise RuntimeError('All aggregate models failed: ' + ' | '.join(model_errors))

                logger.info('Aggregate %s using model=%s on %d records', aggregate_id, model_used, len(records))
                raw = _polish_json_text(message.choices[0].message.content or '')
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError('Model returned non-object JSON')

                clusters = _normalise_clusters(data.get('clusters'), records)

                # Two-stage dedup: ask the LLM to merge sibling clusters, then a
                # deterministic family-keyword pass as a safety net (catches
                # "few brands" vs "single-brand catalog doesn't fit" type splits
                # that nuanced wording can sneak past).
                if len(clusters) > 1:
                    clusters = _llm_merge_pass(clusters, records, client, model_used)
                    clusters = _family_merge_pass(clusters, records)
                    clusters = _llm_merge_pass(clusters, records, client, model_used)

                clusters = sorted(clusters, key=lambda c: (-c['partner_count'], -c['mention_count']))
                if len(clusters) > 15:
                    clusters = clusters[:15]

                clusters_clean = _strip_internal_fields(clusters)
                payload = {
                    'period': {'from': agg.date_from.isoformat(), 'to': agg.date_to.isoformat()},
                    'totals': {
                        'calls': collected['total_calls'],
                        'insights': len(records),
                        'partners': collected['unique_partners'],
                    },
                    'executive_summary': str(data.get('executive_summary') or '').strip(),
                    'top_priorities': [str(x).strip() for x in (data.get('top_priorities') or []) if str(x).strip()][:5],
                    'clusters': clusters_clean,
                    'model_used': model_used,
                }
                agg.summary_text = payload['executive_summary']
                agg.clusters_json = payload
                agg.rendered_markdown = _build_markdown(payload, clusters_clean)
                agg.total_calls = collected['total_calls']
                agg.total_insights = len(records)
                agg.unique_partners = collected['unique_partners']
                agg.status = InsightAggregate.STATUS_DONE
                agg.completed_at = timezone.now()
                agg.last_error = ''
                agg.retries = 0
                agg.save()
                logger.info(
                    'InsightAggregate %s done — %d clusters (post-merge)',
                    aggregate_id, len(clusters_clean),
                )
                return
            except Exception as e:
                last_error = e
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
                logger.warning(
                    'Aggregate attempt %s/%s failed for #%s: %s',
                    attempt + 1, MAX_RETRIES, aggregate_id, e,
                )
                time.sleep(delay)

        from django.db.models import F
        InsightAggregate.objects.filter(pk=aggregate_id).update(
            status=InsightAggregate.STATUS_FAILED,
            last_error=repr(last_error)[:4000] if last_error else 'unknown',
            retries=F('retries') + 1,
            last_attempt_at=timezone.now(),
        )
        logger.error('InsightAggregate %s failed: %s', aggregate_id, last_error)
    finally:
        close_old_connections()


def build_aggregate_background(aggregate_id: int):
    close_old_connections()
    try:
        build_aggregate(aggregate_id, force=False)
    except Exception as e:  # pragma: no cover
        logger.exception('build_aggregate_background crashed: %s', e)
    finally:
        close_old_connections()


def enqueue_aggregate(aggregate_id: int):
    """Spawn the aggregation as a daemon thread."""
    threading.Thread(target=build_aggregate_background, args=(aggregate_id,), daemon=True).start()


# ──────────────────────────────────────────────────────────────────────────
# Rolling "General Insights" — always-on view for the Partners block.
# Cached row per period kind, refreshed by a scheduler job and on-demand if
# the existing row is older than ROLLING_FRESH_MAX_AGE.
# ──────────────────────────────────────────────────────────────────────────
import datetime as _dt  # noqa: E402

# Scheduled rebuild runs Mon–Fri 17:00 IST. Allow up to 26 h of staleness so a
# normal weekday view always serves the cached row instead of triggering an
# unwanted on-demand rebuild. Manual UI refresh (POST) still forces a rebuild.
ROLLING_FRESH_MAX_AGE = _dt.timedelta(hours=26)

# kind → number of days back; KIND_ROLLING_ALL uses earliest CallInsight.
KIND_TO_DAYS = {
    'rolling_30d': 30,
    'rolling_60d': 60,
    'rolling_180d': 180,
    'rolling_all': None,
}


def _resolve_rolling_range(kind: str):
    """Return (date_from, date_to) for a rolling kind."""
    today = timezone.now().date()
    days = KIND_TO_DAYS.get(kind)
    if days is None:
        # All-time: span from earliest CallInsight (status=done) to today.
        from .models import CallInsight
        earliest = (
            CallInsight.objects.filter(status=CallInsight.STATUS_DONE)
            .order_by('call_date').values_list('call_date', flat=True).first()
        )
        if earliest is None:
            return today, today
        return earliest.date(), today
    return today - _dt.timedelta(days=days), today


def find_or_create_rolling(kind: str, force_refresh: bool = False):
    """
    Return the most recent InsightAggregate row for the given rolling kind.

    Logic:
      - If a row exists and is `done` AND completed within ROLLING_FRESH_MAX_AGE
        AND its date_from/date_to still match the rolling window → return as-is.
      - Otherwise create a NEW row covering the freshly-resolved window and
        kick off background generation. Returns the new (pending) row.

    Caller is responsible for permission checks.
    """
    from .models import InsightAggregate

    if kind not in KIND_TO_DAYS:
        raise ValueError(f'Unknown rolling kind: {kind}')

    df, dt = _resolve_rolling_range(kind)

    latest = (
        InsightAggregate.objects
        .filter(kind=kind)
        .order_by('-created_at')
        .first()
    )

    if (
        latest
        and not force_refresh
        and latest.status == InsightAggregate.STATUS_DONE
        and latest.completed_at
        and (timezone.now() - latest.completed_at) < ROLLING_FRESH_MAX_AGE
        and latest.date_from == df
        and latest.date_to == dt
    ):
        return latest

    # Reuse a still-running row (pending/processing) for the same window so we
    # don't spawn duplicate generations.
    if (
        latest
        and latest.status in (InsightAggregate.STATUS_PENDING, InsightAggregate.STATUS_PROCESSING)
        and latest.date_from == df
        and latest.date_to == dt
    ):
        return latest

    row = InsightAggregate.objects.create(
        kind=kind, date_from=df, date_to=dt,
        status=InsightAggregate.STATUS_PENDING,
    )
    enqueue_aggregate(row.pk)
    return row


def refresh_all_rolling():
    """Rebuild every rolling bucket. Called by the scheduler every 6h."""
    for k in KIND_TO_DAYS:
        try:
            find_or_create_rolling(k, force_refresh=True)
        except Exception as e:
            logger.warning('refresh_all_rolling: %s failed: %s', k, e)
    return list(KIND_TO_DAYS)
