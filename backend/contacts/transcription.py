import os
import json
import re
import time
import logging
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

OPENAI_API_KEY     = os.environ.get('OPENAI_API_KEY', '')
MAX_FILE_SIZE      = 25 * 1024 * 1024  # 25 MB — OpenAI audio API limit
MAX_RETRIES        = 3
RETRY_DELAYS       = [5, 15, 30]

# We use OpenAI's `gpt-4o-transcribe` model (released March 2025) instead of
# the legacy `whisper-1`. It does not loop on Hindi/Marathi/Hinglish calls, so
# we no longer need the dedupe / collapse / regex-cleanup passes that were
# previously layered on top of whisper-1 output.
#
# `gpt-4o-transcribe` only supports `response_format='json'` (no verbose_json,
# no segments, no per-segment timestamps), so:
#   - we cannot do segment-level dedupe (and we no longer need to)
#   - we cannot read `duration` from the response → we read it from the audio
#     file itself via `mutagen` if available, otherwise call_duration stays
#     null and the existing value (if any) is preserved
TRANSCRIBE_MODEL = 'gpt-4o-mini-transcribe'


def _audio_duration_seconds(audio_bytes: bytes, file_name: str) -> int:
    """
    Return audio duration in seconds, or 0 if it cannot be determined.
    Uses `mutagen` if installed (pure-Python, supports m4a/mp3/ogg/wav/flac).
    """
    try:
        from mutagen import File as MutagenFile  # type: ignore
        import io
        f = MutagenFile(io.BytesIO(audio_bytes))
        if f is not None and getattr(f, 'info', None) is not None:
            return int(round(float(f.info.length)))
    except ImportError:
        logger.info('mutagen is not installed — call_duration will be left untouched for new transcriptions')
    except Exception as e:
        logger.warning(f'Failed to read audio duration for {file_name}: {e}')
    return 0


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

            # Step 1: transcribe with gpt-4o-transcribe. The model handles
            # mixed-language input (Hinglish, Marathi, Tamil, Russian, etc.)
            # natively and does NOT loop on long audio the way whisper-1 does.
            # Output is the raw transcript in the source language(s) — we hand
            # it directly to the diarizer which translates to English in the
            # same pass.
            transcribe_resp = client.audio.transcriptions.create(
                model=TRANSCRIBE_MODEL,
                file=(file_name, audio_bytes),
                response_format='json',
            )
            source_text = (transcribe_resp.text or '').strip()

            # Duration from the audio file itself — gpt-4o-transcribe does not
            # return it. If mutagen is unavailable we leave call_duration alone
            # so the existing value is preserved.
            duration_secs = _audio_duration_seconds(audio_bytes, file_name)

            logger.info(
                'contact %s gpt-4o-transcribe: duration=%ss chars=%d',
                contact.id, duration_secs, len(source_text),
            )

            # Step 2: GPT-4o-mini diarization which also does the English
            # translation in one pass.
            diarized = _diarize_with_openai(source_text)

            base_name   = os.path.splitext(file_name)[0]
            txt_content = ContentFile(diarized.encode('utf-8'), name=f'{base_name}_transcript.txt')
            contact.transcript_file.save(f'{base_name}_transcript.txt', txt_content, save=False)

            contact.transcription        = source_text
            contact.diarized_transcript  = diarized
            contact.transcription_status = 'done'
            contact.summary_status       = 'pending'
            contact.transcription_last_error = (
                f'OK: model={TRANSCRIBE_MODEL} '
                f'duration={duration_secs}s '
                f'chars={len(source_text)} '
                f'diarized_chars={len(diarized or "")}'
            )

            update_fields = [
                'transcription', 'diarized_transcript',
                'transcript_file', 'transcription_status', 'summary_status',
                'transcription_last_error',
            ]
            # Only overwrite call_duration if we successfully measured it.
            # Otherwise keep whatever was there before (likely set by an earlier
            # whisper-1 transcription).
            if duration_secs > 0:
                contact.call_duration = duration_secs
                update_fields.append('call_duration')

            contact.save(update_fields=update_fields)

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
