"""
Send CallInsight notifications to Telegram (Bot API) using HTML parse_mode.

Env:
  TELEGRAM_BOT_TOKEN        — required to send
  TELEGRAM_INSIGHTS_CHAT_ID — optional, defaults to product-spec chat
"""
import logging
import os
from html import escape
from typing import List

import requests

logger = logging.getLogger(__name__)

# Default chat from product requirements when env is unset.
# Telegram supergroups use the -100 prefix on the API; raw id 1003721500076 alone returns "chat not found".
_DEFAULT_CHAT_ID = '-1003721500076'
_TELEGRAM_API = 'https://api.telegram.org'
_MAX_LEN = 3800  # safety margin under the 4096 hard limit

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
_SENTIMENT_LABELS = {
    'positive': 'Positive',
    'negative': 'Negative',
    'neutral': 'Neutral',
    'mixed': 'Mixed',
}


def _chat_id() -> str:
    return (os.environ.get('TELEGRAM_INSIGHTS_CHAT_ID') or _DEFAULT_CHAT_ID).strip()


def _h(s: str) -> str:
    """HTML-escape user content for Telegram parse_mode=HTML."""
    return escape(str(s or ''), quote=False)


def _format_call_date(dt) -> str:
    if not dt:
        return '—'
    try:
        return dt.strftime('%Y-%m-%d %H:%M UTC')
    except Exception:
        return str(dt)


def format_insight_html(ci) -> str:
    """Build a Telegram-ready HTML report for a CallInsight row."""
    data = ci.insights_json or {}
    items = data.get('insights') or []
    title = (data.get('call_title_english') or 'Call insights').strip()

    partner_name = ci.partner.name if getattr(ci, 'partner_id', None) else 'Partner'

    head = [
        f'<b>📞 Call Insights — {_h(partner_name)}</b>',
        f'Contact #{ci.contact_id} · {_h(_format_call_date(ci.call_date))}',
        f'{ci.insight_count} insights · {_h(ci.density_bucket)} density',
        '',
        f'<b>{_h(title)}</b>',
    ]

    blocks: List[str] = ['\n'.join(head)]

    if not items:
        blocks.append('<i>No material business insights extracted from this call.</i>')

    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            continue
        cat = _CATEGORY_LABELS.get(str(it.get('category', 'other')).lower(), 'Other')
        sent = _SENTIMENT_LABELS.get(str(it.get('sentiment', 'neutral')).lower(), 'Neutral')
        item_title = (it.get('title') or f'Insight {i}').strip()
        detail = (it.get('detail_english') or '').strip()
        quote = (it.get('verbatim_partner_quote') or '').strip()

        parts = [
            f'<b>{i}. {_h(item_title)}</b>',
            f'<i>{_h(cat)} · {_h(sent)}</i>',
        ]
        if detail:
            parts.append('')
            parts.append(_h(detail))
        if quote:
            parts.append('')
            parts.append(f'💬 «{_h(quote)}»')
        blocks.append('\n'.join(parts))

    sep = '\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n'
    return sep.join(blocks)


def _split_for_telegram(text: str) -> List[str]:
    """Split on the insight separator first, then on paragraphs, then hard-cut."""
    sep = '\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n'
    if len(text) <= _MAX_LEN:
        return [text]

    chunks: List[str] = []
    current = ''
    for piece in text.split(sep):
        candidate = piece if not current else current + sep + piece
        if len(candidate) <= _MAX_LEN:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ''
        if len(piece) <= _MAX_LEN:
            current = piece
            continue
        # piece itself too big — split by paragraphs, then hard-cut.
        for para in piece.split('\n\n'):
            cand2 = para if not current else current + '\n\n' + para
            if len(cand2) <= _MAX_LEN:
                current = cand2
            else:
                if current:
                    chunks.append(current)
                    current = ''
                while len(para) > _MAX_LEN:
                    chunks.append(para[:_MAX_LEN])
                    para = para[_MAX_LEN:]
                current = para
    if current:
        chunks.append(current)
    return chunks


def send_insight_html(text: str) -> List[int]:
    """Send HTML-formatted message(s). Returns list of telegram message_ids."""
    token = (os.environ.get('TELEGRAM_BOT_TOKEN') or '').strip()
    if not token:
        logger.warning('TELEGRAM_BOT_TOKEN not set — skipping Telegram insight send')
        return []
    chat_id = _chat_id()
    if not chat_id:
        logger.warning('No TELEGRAM_INSIGHTS_CHAT_ID — skipping Telegram insight send')
        return []

    url = f'{_TELEGRAM_API}/bot{token}/sendMessage'
    parts = _split_for_telegram(text or '')
    message_ids: List[int] = []
    for i, part in enumerate(parts):
        body = part if i == 0 else f'<i>(continued {i + 1}/{len(parts)})</i>\n\n{part}'
        try:
            r = requests.post(
                url,
                json={
                    'chat_id': chat_id,
                    'text': body,
                    'parse_mode': 'HTML',
                    'disable_web_page_preview': True,
                },
                timeout=60,
            )
            data = r.json()
            if not data.get('ok'):
                raise RuntimeError(data.get('description') or r.text)
            mid = data.get('result', {}).get('message_id')
            if mid:
                message_ids.append(mid)
        except Exception as e:
            logger.warning('Telegram sendMessage failed: %s', e)
            raise
    return message_ids


# Back-compat plain-text shim (kept so any old callers keep working).
def send_insight_text_chunks(text: str) -> List[int]:
    return send_insight_html(text)
