"""
Render an InsightAggregate as a stylized PDF using ReportLab Platypus.
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Tuple

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle, KeepTogether, ListFlowable, ListItem,
    PageBreak, HRFlowable,
)


PRIMARY = HexColor('#5E35B1')
ACCENT = HexColor('#7E57C2')
GREY_BG = HexColor('#F4F1FA')
GREY_BORDER = HexColor('#D7CCEB')
TEXT_DARK = HexColor('#212121')
TEXT_MUTED = HexColor('#616161')
WARN_BG = HexColor('#FFF8E1')
WARN_BORDER = HexColor('#FFB300')
QUOTE_BG = HexColor('#FAFAFA')

CATEGORY_COLORS = {
    'platform_ask_ayurveda': HexColor('#7E57C2'),
    'earning_money': HexColor('#EF6C00'),
    'prescribing_procurement': HexColor('#2E7D32'),
    'competitors': HexColor('#C62828'),
    'manufacturers': HexColor('#AD1457'),
    'product': HexColor('#1565C0'),
    'market_ayurveda': HexColor('#00838F'),
    'other': HexColor('#546E7A'),
}

CATEGORY_LABELS = {
    'product': 'Product / Offer',
    'market_ayurveda': 'Ayurveda Market',
    'competitors': 'Competitors / Alternatives',
    'manufacturers': 'Manufacturers / Brands',
    'platform_ask_ayurveda': 'Ask Ayurveda Platform',
    'prescribing_procurement': 'Prescribing / Procurement',
    'earning_money': 'Earnings / Margins',
    'other': 'Other',
}

SENTIMENT_COLORS = {
    'positive': HexColor('#2E7D32'),
    'negative': HexColor('#C62828'),
    'neutral': HexColor('#616161'),
    'mixed': HexColor('#F9A825'),
}


def _esc(s: Any) -> str:
    """Escape for ReportLab Paragraph (a tiny HTML subset)."""
    if s is None:
        return ''
    s = str(s)
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return s


def _styles() -> Dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    s: Dict[str, ParagraphStyle] = {}
    s['title'] = ParagraphStyle(
        'title', parent=base['Title'],
        fontName='Helvetica-Bold', fontSize=20, leading=24,
        textColor=colors.white, alignment=TA_LEFT, spaceAfter=2,
    )
    s['title_sub'] = ParagraphStyle(
        'title_sub', parent=base['Normal'],
        fontName='Helvetica', fontSize=10, leading=14,
        textColor=HexColor('#EDE7F6'), alignment=TA_LEFT,
    )
    s['h2'] = ParagraphStyle(
        'h2', parent=base['Heading2'],
        fontName='Helvetica-Bold', fontSize=13, leading=16,
        textColor=PRIMARY, spaceBefore=10, spaceAfter=6,
    )
    s['body'] = ParagraphStyle(
        'body', parent=base['BodyText'],
        fontName='Helvetica', fontSize=10, leading=14,
        textColor=TEXT_DARK, alignment=TA_LEFT, spaceAfter=4,
    )
    s['muted'] = ParagraphStyle(
        'muted', parent=base['BodyText'],
        fontName='Helvetica', fontSize=8.5, leading=11,
        textColor=TEXT_MUTED, alignment=TA_LEFT,
    )
    s['theme_title'] = ParagraphStyle(
        'theme_title', parent=base['Heading3'],
        fontName='Helvetica-Bold', fontSize=12, leading=15,
        textColor=TEXT_DARK, spaceAfter=2,
    )
    s['theme_meta'] = ParagraphStyle(
        'theme_meta', parent=base['BodyText'],
        fontName='Helvetica', fontSize=8.5, leading=11,
        textColor=TEXT_MUTED, spaceAfter=4,
    )
    s['recommend'] = ParagraphStyle(
        'recommend', parent=base['BodyText'],
        fontName='Helvetica', fontSize=10, leading=14,
        textColor=HexColor('#4E342E'),
    )
    s['quote'] = ParagraphStyle(
        'quote', parent=base['BodyText'],
        fontName='Helvetica-Oblique', fontSize=9.5, leading=12.5,
        textColor=HexColor('#37474F'),
        leftIndent=8,
    )
    s['quote_author'] = ParagraphStyle(
        'quote_author', parent=base['BodyText'],
        fontName='Helvetica-Bold', fontSize=8.5, leading=10,
        textColor=TEXT_MUTED,
    )
    s['kpi_value'] = ParagraphStyle(
        'kpi_value', parent=base['Normal'],
        fontName='Helvetica-Bold', fontSize=18, leading=20,
        textColor=PRIMARY, alignment=1,
    )
    s['kpi_label'] = ParagraphStyle(
        'kpi_label', parent=base['Normal'],
        fontName='Helvetica', fontSize=8.5, leading=10,
        textColor=TEXT_MUTED, alignment=1,
    )
    return s


def _header_block(agg, st: Dict[str, ParagraphStyle], width_mm: float):
    """Purple header bar with title, period, generated-at."""
    title = f'Aggregate Insight Report'
    subtitle = (
        f'{agg.date_from.isoformat()} → {agg.date_to.isoformat()}'
    )
    inner = [
        [Paragraph(title, st['title'])],
        [Paragraph(subtitle, st['title_sub'])],
    ]
    tbl = Table(inner, colWidths=[width_mm * mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PRIMARY),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (0, 0), 12),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return tbl


def _kpi_row(agg, st: Dict[str, ParagraphStyle], width_mm: float):
    """Three KPI tiles."""
    cells = [[
        [Paragraph(str(agg.total_calls), st['kpi_value']),
         Paragraph('Calls', st['kpi_label'])],
        [Paragraph(str(agg.total_insights), st['kpi_value']),
         Paragraph('Raw insights', st['kpi_label'])],
        [Paragraph(str(agg.unique_partners), st['kpi_value']),
         Paragraph('Unique partners', st['kpi_label'])],
    ]]
    col_w = (width_mm / 3.0) * mm
    tbl = Table(cells, colWidths=[col_w, col_w, col_w])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), GREY_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, GREY_BORDER),
        ('LINEBEFORE', (1, 0), (1, -1), 0.5, GREY_BORDER),
        ('LINEBEFORE', (2, 0), (2, -1), 0.5, GREY_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return tbl


def _bar(percent: float, color, width_mm: float, height: float = 5):
    """Cluster strength bar."""
    pct = max(0.0, min(100.0, float(percent)))
    full_w = width_mm * mm
    fill_w = full_w * (pct / 100.0)
    if fill_w < 1:
        fill_w = 1
    cells = [['', '']]
    tbl = Table(cells, colWidths=[fill_w, max(0.1, full_w - fill_w)], rowHeights=[height])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), color),
        ('BACKGROUND', (1, 0), (1, 0), HexColor('#ECEFF1')),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return tbl


def _sentiment_chips(sb: Dict[str, Any], st: Dict[str, ParagraphStyle]) -> str:
    parts = []
    for k in ('positive', 'negative', 'neutral', 'mixed'):
        v = int(sb.get(k, 0) or 0)
        if v:
            color_hex = SENTIMENT_COLORS[k].hexval()[2:]
            parts.append(f'<font color="#{color_hex}"><b>{k}: {v}</b></font>')
    return ' &nbsp;·&nbsp; '.join(parts)


def _theme_block(idx: int, c: Dict[str, Any], st: Dict[str, ParagraphStyle], width_mm: float, max_partners: int):
    """Render one cluster card as a KeepTogether flowable."""
    cat = str(c.get('category', 'other')).lower()
    cat_color = CATEGORY_COLORS.get(cat, CATEGORY_COLORS['other'])
    cat_label = CATEGORY_LABELS.get(cat, 'Other')

    partner_count = int(c.get('partner_count') or 0)
    mention_count = int(c.get('mention_count') or 0)
    pct = (partner_count / max(1, max_partners)) * 100

    sb_str = _sentiment_chips(c.get('sentiment_breakdown') or {}, st)

    title_text = f'<b>{idx}. {_esc(c.get("theme") or "Untitled cluster")}</b>'
    meta_text = (
        f'<font color="#{cat_color.hexval()[2:]}"><b>{_esc(cat_label)}</b></font>'
        f' &nbsp;·&nbsp; <b>{partner_count}</b> partner(s)'
        f' &nbsp;·&nbsp; {mention_count} mention(s)'
    )
    if sb_str:
        meta_text += f' &nbsp;·&nbsp; Sentiment — {sb_str}'

    parts: List[Any] = [
        Paragraph(title_text, st['theme_title']),
        Paragraph(meta_text, st['theme_meta']),
        _bar(pct, cat_color, width_mm - 8),
        Spacer(1, 6),
    ]

    explanation = (c.get('explanation') or '').strip()
    if explanation:
        parts.append(Paragraph(_esc(explanation), st['body']))
        parts.append(Spacer(1, 4))

    rec = (c.get('recommended_action') or '').strip()
    if rec:
        rec_tbl = Table(
            [[Paragraph(f'<b>Recommended action:</b> {_esc(rec)}', st['recommend'])]],
            colWidths=[(width_mm - 8) * mm],
        )
        rec_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), WARN_BG),
            ('LINEBEFORE', (0, 0), (0, -1), 2.5, WARN_BORDER),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        parts.append(rec_tbl)
        parts.append(Spacer(1, 6))

    quotes = c.get('representative_quotes') or []
    if quotes:
        parts.append(Paragraph('<b>Representative quotes</b>', st['theme_meta']))
        for q in quotes[:4]:
            quote_text = _esc((q.get('quote') or '').strip())
            author = _esc(q.get('partner_name') or 'Partner')
            parts.append(
                Paragraph(f'« {quote_text} »', st['quote'])
            )
            parts.append(
                Paragraph(f'— {author}', st['quote_author'])
            )
            parts.append(Spacer(1, 3))

    # Wrap in a bordered card via outer Table
    inner = [[p] for p in parts]
    card = Table(inner, colWidths=[(width_mm) * mm])
    card.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, GREY_BORDER),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (0, 0), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
        ('LINEBEFORE', (0, 0), (0, -1), 3, cat_color),
    ]))

    return KeepTogether([card, Spacer(1, 10)])


def _on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawRightString(
        A4[0] - 15 * mm,
        12 * mm,
        f'AskAyurveda · Aggregate Insight Report · page {doc.page}',
    )
    canvas.restoreState()


def render_aggregate_pdf(agg) -> bytes:
    """Build a PDF (bytes) for an InsightAggregate row."""
    buf = io.BytesIO()
    page_w_mm = 210
    page_h_mm = 297
    margin_l = 15
    margin_r = 15
    margin_t = 15
    margin_b = 18
    content_w_mm = page_w_mm - margin_l - margin_r

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin_l * mm, rightMargin=margin_r * mm,
        topMargin=margin_t * mm, bottomMargin=margin_b * mm,
        title=f'Aggregate insights {agg.date_from} - {agg.date_to}',
        author='AskAyurveda CRM',
    )
    frame = Frame(
        margin_l * mm, margin_b * mm,
        content_w_mm * mm,
        (page_h_mm - margin_t - margin_b) * mm,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        id='content',
    )
    doc.addPageTemplates([PageTemplate(id='main', frames=[frame], onPage=_on_page)])

    st = _styles()
    story: List[Any] = []

    story.append(_header_block(agg, st, content_w_mm))
    story.append(Spacer(1, 14))
    story.append(_kpi_row(agg, st, content_w_mm))
    story.append(Spacer(1, 14))

    payload = agg.clusters_json or {}
    summary = (payload.get('executive_summary') or agg.summary_text or '').strip()
    if summary:
        story.append(Paragraph('Executive summary', st['h2']))
        story.append(Paragraph(_esc(summary), st['body']))
        story.append(Spacer(1, 8))

    priorities = [str(x).strip() for x in (payload.get('top_priorities') or []) if str(x).strip()]
    if priorities:
        story.append(Paragraph('Top priorities', st['h2']))
        story.append(ListFlowable(
            [ListItem(Paragraph(_esc(p), st['body']), leftIndent=12, bulletColor=PRIMARY) for p in priorities],
            bulletType='bullet', start='•', leftIndent=14,
        ))
        story.append(Spacer(1, 10))

    clusters = payload.get('clusters') or []
    story.append(HRFlowable(width='100%', thickness=0.6, color=GREY_BORDER, spaceBefore=4, spaceAfter=10))

    story.append(Paragraph(
        f'Themes ranked by unique partners ({len(clusters)})',
        st['h2'],
    ))

    if not clusters:
        story.append(Paragraph(
            '<i>No clustered themes — this period had no material business signal.</i>',
            st['muted'],
        ))
    else:
        max_partners = max((int(c.get('partner_count') or 0) for c in clusters), default=1)
        for i, c in enumerate(clusters, 1):
            story.append(_theme_block(i, c, st, content_w_mm, max_partners))

    doc.build(story)
    return buf.getvalue()
