import os
import json
import re
import time
import logging
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

OPENAI_API_KEY     = os.environ.get('OPENAI_API_KEY', '')
MAX_FILE_SIZE      = 25 * 1024 * 1024  # 25 MB — OpenAI Whisper limit
MAX_RETRIES        = 3
RETRY_DELAYS       = [5, 15, 30]

# Whisper's `prompt` parameter STRONGLY biases output toward the prompt's language
# and even leaks prompt phrases into the transcript. We therefore use NO topic prompt
# and instead rely on:
#   - the `translations` endpoint which natively converts any input language → English
#   - segment-level dedup + regex cleanup to neutralise loops
#   - GPT-4o-mini second pass for diarization (Operator/Partner labelling)


# ---------------------------------------------------------------------------
# Whisper hallucination cleanup
# ---------------------------------------------------------------------------
def _dedupe_segments(segments):
    """
    Whisper-1 frequently loops on a phrase when it hits silence or unintelligible
    audio (especially on Hindi/Marathi). Detect repeated consecutive segments by
    text content and drop the duplicates.
    """
    if not segments:
        return None
    cleaned = []
    last_text = None
    repeat_run = 0
    for seg in segments:
        if hasattr(seg, 'text'):
            text = getattr(seg, 'text', '') or ''
        elif isinstance(seg, dict):
            text = seg.get('text', '') or ''
        else:
            text = ''
        text = text.strip()
        if not text:
            continue
        # normalize for comparison: collapse whitespace, lowercase
        norm = re.sub(r'\s+', ' ', text).strip().lower()
        if last_text is not None and norm == last_text:
            repeat_run += 1
            if repeat_run >= 1:
                continue
        else:
            repeat_run = 0
        cleaned.append(text)
        last_text = norm
    return ' '.join(cleaned).strip()


def _clean_whisper_text(text):
    """
    Best-effort cleanup of looping Whisper output when no segments are available
    (or as a second-pass safety net). Removes any 15-200 char chunk that repeats
    2+ times in a row. Works for Devanagari / Tamil / Latin scripts.
    """
    if not text:
        return text

    # Pass 1: collapse identical adjacent chunks (greedy, longest match wins).
    # We try shrinking window sizes from long to short.
    for window in (200, 120, 80, 50, 25):
        pattern = re.compile(
            r'(.{' + str(window) + r',' + str(window * 2) + r'}?)(?:\s*\1){1,}',
            re.UNICODE | re.DOTALL,
        )
        prev = None
        while prev != text:
            prev = text
            text = pattern.sub(r'\1', text)

    # Pass 2: split on Devanagari/Latin sentence-ish separators and drop adjacent
    # duplicate sentences (case-insensitive after collapsing whitespace).
    parts = re.split(r'(?<=[।\.\?\!])\s+|\s{2,}', text)
    out = []
    last_norm = None
    for p in parts:
        p_strip = p.strip()
        if not p_strip:
            continue
        norm = re.sub(r'\s+', ' ', p_strip).lower()
        if norm == last_norm:
            continue
        out.append(p_strip)
        last_norm = norm
    return ' '.join(out).strip()

_NON_ASCII_RE = re.compile(r'[^\x00-\x7f]')


def _looks_non_english(text: str) -> bool:
    """Heuristic: >5% non-ASCII chars → assume the audio is in a non-English language
    (Devanagari, Tamil, Cyrillic etc.) and route through translation endpoint."""
    if not text:
        return False
    non_ascii = len(_NON_ASCII_RE.findall(text))
    return (non_ascii / max(len(text), 1)) > 0.05


DIARIZE_PROMPT = """You are processing a transcription of a sales phone call between an AskAyurveda operator \
(who calls partners — doctors, trainers, bloggers — to explain and promote Ayurveda products) \
and the partner (the person being called).

Your tasks (do BOTH in one pass):
1. TRANSLATE the transcript to natural professional English. Source may be Hindi, Marathi, Tamil, \
Russian, or any mix — output MUST be English only.
2. SPLIT the dialogue into turns and label each turn as either "Operator" or "Partner".

CRITICAL FAITHFULNESS RULES — read carefully:
- Translate VERBATIM. Do NOT summarize, paraphrase, condense, polish, "improve" or skip ANY content.
- Every sentence, hesitation, repetition, filler, number, name, product, price, time and date in the \
source MUST appear in the output. Length of the output (in words) should be roughly equal to or larger \
than the source — never shorter.
- Do NOT merge multiple turns of the same speaker into a generic "summary" turn. Keep micro-turns \
("hmm", "ok", "right", "achha", "ji haan") as separate Partner turns when appropriate.
- If a phrase makes no sense after translation, keep the original word inside the translated text \
in parentheses, e.g. "we sent the (kit) to your address" — but never drop content.

Speaker identification rules:
- Operator: greets, introduces themselves and the AskAyurveda platform, explains products / commissions \
/ medical sets, asks discovery questions, handles objections, schedules follow-ups, mentions WhatsApp / \
link / commission / Ayurveda product names from a sales-script angle.
- Partner: responds to questions, expresses interest / doubts / budget / time concerns, asks clarifying \
questions about the product or pricing, mentions their own clinic / practice / clients, agrees or \
refuses to receive materials.
- If a turn is just an acknowledgement ("haan", "ok", "ji", "hmm") attribute it based on conversational \
flow — usually it belongs to whoever is being addressed.
- If you genuinely cannot tell, alternate to keep the dialogue believable but bias toward Partner \
because Whisper sometimes drops short Partner replies entirely. Never label every line as Operator.
- It is CRITICAL that BOTH speakers appear. If the raw transcript only contains operator-like \
sentences, infer the Partner replies as "(no clear reply captured)" rather than dropping the role.

Return ONLY valid JSON, no markdown, no extra commentary, with this shape:
{{"dialogue": [
  {{"speaker": "Operator", "text": "<verbatim english translation of the operator turn>"}},
  {{"speaker": "Partner",  "text": "<verbatim english translation of the partner turn>"}}
]}}

Source transcription (any language):
{transcription}"""


def _diarize_with_openai(transcription_text: str) -> str:
    """
    Use OpenAI to split a raw transcript into Operator / Partner turns.
    Returns plain text with **Operator:** / **Partner:** prefixes.
    Falls back to raw text if anything fails.
    """
    if not OPENAI_API_KEY or not transcription_text.strip():
        return transcription_text

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        message = client.chat.completions.create(
            model='gpt-4o-mini',
            max_tokens=12000,
            response_format={"type": "json_object"},
            messages=[
                {'role': 'system', 'content': (
                    'You translate non-English call transcripts to English AND label '
                    'speakers as Operator or Partner. Output JSON only.'
                )},
                {'role': 'user', 'content': DIARIZE_PROMPT.format(transcription=transcription_text[:12000])},
            ],
        )
        raw = message.choices[0].message.content.strip()

        import re as _re
        raw = _re.sub(r'[\x00-\x09\x0b\x0c\x0e-\x1f]', ' ', raw)

        data = json.loads(raw)
        turns = data if isinstance(data, list) else data.get('dialogue', data.get('turns', []))

        # Safety net: if AI returned only one role, force a synthetic alternation so
        # the downstream UI never shows "[No response recorded]" for every Partner row.
        speakers_seen = {(t.get('speaker') or '').lower() for t in turns}
        only_one_role = len(speakers_seen & {'operator', 'partner'}) < 2

        lines = []
        for i, turn in enumerate(turns):
            speaker = (turn.get('speaker') or 'Speaker').strip()
            if speaker.lower() in ('unknown', 'speaker', ''):
                speaker = 'Operator' if i % 2 == 0 else 'Partner'
            if only_one_role:
                speaker = 'Operator' if i % 2 == 0 else 'Partner'
            text = (turn.get('text') or '').strip()
            if text:
                lines.append(f'**{speaker}:** {text}')
        return '\n\n'.join(lines)

    except Exception as e:
        logger.warning(f'Diarization failed, using raw transcript: {e}')
        return transcription_text


def transcribe_audio(contact):
    """
    Calls OpenAI Whisper API (verbose_json) to transcribe contact.audio_file.
    Then uses Claude to split into Operator / Partner turns.
    Saves transcription, diarized_transcript, call_duration, transcript_file.
    Updates transcription_status. Triggers summarization on success.
    """
    if not OPENAI_API_KEY:
        logger.warning('OPENAI_API_KEY is not set — transcription skipped')
        return

    if not contact.audio_file:
        return

    from openai import OpenAI

    contact.transcription_status = 'processing'
    contact.save(update_fields=['transcription_status'])

    audio_field = contact.audio_file
    file_size   = audio_field.size

    if file_size > MAX_FILE_SIZE:
        contact.transcription_status = 'failed'
        contact.transcription = (
            f'[Transcription failed: file too large ({file_size // (1024*1024)} MB). Max 25 MB.]'
        )
        contact.save(update_fields=['transcription_status', 'transcription'])
        return

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            client    = OpenAI(api_key=OPENAI_API_KEY)
            audio_field.seek(0)
            file_name = os.path.basename(audio_field.name)

            audio_bytes = audio_field.read()

            # Step 1: native transcription in source language (verbose_json gives us
            # per-segment data we use to remove Whisper hallucination loops).
            transcribe_resp = client.audio.transcriptions.create(
                model='whisper-1',
                file=(file_name, audio_bytes),
                response_format='verbose_json',
                timestamp_granularities=['segment'],
                temperature=0,
            )
            source_text   = (transcribe_resp.text or '').strip()
            duration_secs = int(getattr(transcribe_resp, 'duration', 0) or 0)
            segments      = getattr(transcribe_resp, 'segments', None) or []

            deduped = _dedupe_segments(segments)
            if deduped and len(deduped) >= len(source_text) * 0.5:
                source_text = deduped
            source_text = _clean_whisper_text(source_text)

            # Step 2: if the audio is non-English, ask Whisper to TRANSLATE to English
            # natively (this is the dedicated whisper-1 translation endpoint). For
            # already-English calls translation is a no-op.
            english_text = source_text
            if _looks_non_english(source_text):
                try:
                    audio_field.seek(0)
                    translate_resp = client.audio.translations.create(
                        model='whisper-1',
                        file=(file_name, audio_field.read()),
                        response_format='verbose_json',
                        temperature=0,
                    )
                    en_raw      = (translate_resp.text or '').strip()
                    en_segments = getattr(translate_resp, 'segments', None) or []
                    en_clean    = _dedupe_segments(en_segments) or en_raw
                    en_clean    = _clean_whisper_text(en_clean)
                    if en_clean and len(en_clean) > len(english_text) * 0.5:
                        english_text = en_clean
                except Exception as ex:
                    logger.warning(f'Whisper translation failed for contact {contact.id}: {ex}')

            # Step 3: GPT-4o-mini diarization (Operator/Partner labels). Feed it the
            # English text so it does not waste budget on translation again.
            raw_text = english_text
            diarized = _diarize_with_openai(english_text)

            base_name   = os.path.splitext(file_name)[0]
            txt_content = ContentFile(diarized.encode('utf-8'), name=f'{base_name}_transcript.txt')
            contact.transcript_file.save(f'{base_name}_transcript.txt', txt_content, save=False)

            contact.transcription        = raw_text
            contact.diarized_transcript  = diarized
            contact.call_duration        = duration_secs if duration_secs > 0 else None
            contact.transcription_status = 'done'
            contact.summary_status       = 'pending'
            contact.save(update_fields=[
                'transcription', 'diarized_transcript', 'call_duration',
                'transcript_file', 'transcription_status', 'summary_status',
            ])

            logger.info(f'Transcription + diarization done for contact {contact.id} ({duration_secs}s)')

            from .summarization import summarize_transcription
            summarize_transcription(contact)
            return

        except Exception as e:
            last_error = e
            delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
            logger.warning(f'Transcription attempt {attempt+1}/{MAX_RETRIES} failed for contact {contact.id}: {e}. Retrying in {delay}s...')
            time.sleep(delay)

    logger.error(f'Transcription failed after {MAX_RETRIES} attempts for contact {contact.id}: {last_error}')
    contact.transcription_status = 'failed'
    contact.save(update_fields=['transcription_status'])
