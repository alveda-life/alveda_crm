import os
import json
import re
import time
import shutil
import tempfile
import subprocess
import logging
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

OPENAI_API_KEY     = os.environ.get('OPENAI_API_KEY', '')
MAX_FILE_SIZE      = 25 * 1024 * 1024  # 25 MB — OpenAI audio API per-file size limit
MAX_RETRIES        = 3
RETRY_DELAYS       = [5, 15, 30]


def _env_int(name: str, default: int, min_value: int = 1) -> int:
    raw = os.environ.get(name, '').strip()
    if not raw:
        return default
    try:
        value = int(raw)
        if value < min_value:
            return default
        return value
    except ValueError:
        return default

# We use OpenAI's `gpt-4o-transcribe` model (released March 2025) instead of
# the legacy `whisper-1`. It does not loop on Hindi/Marathi/Hinglish calls, so
# we no longer need the dedupe / collapse / regex-cleanup passes that were
# previously layered on top of whisper-1 output.
#
# `gpt-4o-transcribe` only supports `response_format='json'` (no verbose_json,
# no segments, no per-segment timestamps), so we cannot read `duration` from
# the response — we read it via `ffprobe` (or `mutagen` as a fallback).
#
# The model also has an INPUT-CONTEXT limit of ~25 minutes of audio (returns
# `input_too_large` regardless of file size beyond that), so anything longer
# than CHUNK_SECONDS is split into pieces with ffmpeg and EACH chunk is
# transcribed AND diarized independently. The diarized chunks are then
# concatenated. This avoids two failure modes:
#   1. losing the tail of the call to the diarizer's input length cap,
#   2. the diarizer's output `max_tokens` cap clipping long dialogues.
TRANSCRIBE_MODEL = 'gpt-4o-mini-transcribe'
CHUNK_SECONDS    = _env_int('TRANSCRIBE_CHUNK_SECONDS', 7 * 60)  # default: 7 min
CHUNK_OVERLAP_SECONDS = _env_int('TRANSCRIBE_CHUNK_OVERLAP_SECONDS', 4, min_value=0)


def _audio_duration_seconds(file_path: str) -> int:
    """
    Return audio duration in seconds, or 0 if it cannot be determined.
    Tries ffprobe first (always available in the backend image), then falls
    back to `mutagen` if installed.
    """
    if shutil.which('ffprobe'):
        try:
            out = subprocess.check_output(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
                stderr=subprocess.STDOUT, timeout=30,
            )
            return int(round(float(out.strip())))
        except Exception as e:
            logger.warning(f'ffprobe failed for {file_path}: {e}')

    try:
        from mutagen import File as MutagenFile  # type: ignore
        f = MutagenFile(file_path)
        if f is not None and getattr(f, 'info', None) is not None:
            return int(round(float(f.info.length)))
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f'mutagen failed for {file_path}: {e}')

    return 0


def _split_audio_with_ffmpeg(file_path: str, chunk_seconds: int, work_dir: str, overlap_seconds: int = 0) -> list:
    """
    Split `file_path` into ~chunk_seconds-long pieces.

    - overlap_seconds == 0: ffmpeg segment muxer with stream copy.
    - overlap_seconds > 0: explicit windows with stride=(chunk-overlap).
      We prefer copy and fall back to lightweight mp3 re-encode when copy fails.

    Returns a sorted list of chunk paths inside `work_dir`.
    Falls back to [file_path] if ffmpeg is missing / fails.
    """
    if not shutil.which('ffmpeg'):
        logger.error('ffmpeg not found — cannot split audio, falling back to single file')
        return [file_path]

    if overlap_seconds <= 0:
        ext = os.path.splitext(file_path)[1].lower() or '.mp3'
        pattern = os.path.join(work_dir, f'chunk_%03d{ext}')
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-i', file_path,
            '-f', 'segment',
            '-segment_time', str(chunk_seconds),
            '-c', 'copy',
            '-reset_timestamps', '1',
            pattern,
        ]
        try:
            subprocess.check_call(cmd, timeout=300)
        except Exception as e:
            logger.warning(f'ffmpeg stream-copy split failed ({e}); retrying with re-encode to mp3')
            pattern = os.path.join(work_dir, 'chunk_%03d.mp3')
            cmd = [
                'ffmpeg', '-y', '-loglevel', 'error',
                '-i', file_path,
                '-f', 'segment',
                '-segment_time', str(chunk_seconds),
                '-c:a', 'libmp3lame', '-b:a', '64k', '-ac', '1',
                '-reset_timestamps', '1',
                pattern,
            ]
            try:
                subprocess.check_call(cmd, timeout=600)
            except Exception as e2:
                logger.error(f'ffmpeg re-encode split also failed: {e2}')
                return [file_path]

        chunks = sorted(
            os.path.join(work_dir, f) for f in os.listdir(work_dir)
            if f.startswith('chunk_')
        )
        return chunks or [file_path]

    duration_secs = _audio_duration_seconds(file_path)
    if duration_secs <= 0:
        logger.warning('Cannot compute duration for overlap split; falling back to non-overlap split')
        return _split_audio_with_ffmpeg(file_path, chunk_seconds, work_dir, overlap_seconds=0)

    stride = chunk_seconds - overlap_seconds
    if stride <= 0:
        logger.warning(
            'Invalid overlap (%ss) for chunk size %ss; falling back to non-overlap split',
            overlap_seconds, chunk_seconds
        )
        return _split_audio_with_ffmpeg(file_path, chunk_seconds, work_dir, overlap_seconds=0)

    ext = os.path.splitext(file_path)[1].lower() or '.mp3'
    chunk_paths = []
    start = 0
    idx = 0
    while start < duration_secs:
        out_path = os.path.join(work_dir, f'chunk_{idx:03d}{ext}')
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-ss', str(start),
            '-t', str(chunk_seconds),
            '-i', file_path,
            '-c', 'copy',
            '-reset_timestamps', '1',
            out_path,
        ]
        try:
            subprocess.check_call(cmd, timeout=300)
        except Exception:
            out_path = os.path.join(work_dir, f'chunk_{idx:03d}.mp3')
            cmd = [
                'ffmpeg', '-y', '-loglevel', 'error',
                '-ss', str(start),
                '-t', str(chunk_seconds),
                '-i', file_path,
                '-c:a', 'libmp3lame', '-b:a', '64k', '-ac', '1',
                '-reset_timestamps', '1',
                out_path,
            ]
            try:
                subprocess.check_call(cmd, timeout=600)
            except Exception as e2:
                logger.error(f'ffmpeg overlap split failed on chunk {idx}: {e2}')
                return chunk_paths or [file_path]

        chunk_paths.append(out_path)
        idx += 1
        start += stride

    return chunk_paths or [file_path]


def _transcribe_one(client, file_name: str, audio_bytes: bytes) -> str:
    """One round-trip to OpenAI's transcription endpoint. Returns raw text."""
    resp = client.audio.transcriptions.create(
        model=TRANSCRIBE_MODEL,
        file=(file_name, audio_bytes),
        response_format='json',
    )
    return (resp.text or '').strip()


def _transcribe_file(client, file_path: str) -> str:
    """Read `file_path` and transcribe it as a single chunk."""
    with open(file_path, 'rb') as fh:
        audio_bytes = fh.read()
    return _transcribe_one(client, os.path.basename(file_path), audio_bytes)


def _concat_with_overlap_dedupe(current_text: str, new_text: str, max_scan_chars: int = 2500) -> str:
    """
    Concatenate chunk texts while removing duplicated boundary caused by overlap.
    Uses case-insensitive suffix/prefix exact match on characters.
    """
    if not current_text:
        return new_text or ''
    if not new_text:
        return current_text

    tail = current_text[-max_scan_chars:]
    head = new_text[:max_scan_chars]
    tail_cmp = tail.casefold()
    head_cmp = head.casefold()

    max_len = min(len(tail_cmp), len(head_cmp))
    overlap_len = 0
    # Ignore tiny matches to avoid deleting legitimate repeated short words.
    for size in range(max_len, 40, -1):
        if tail_cmp[-size:] == head_cmp[:size]:
            overlap_len = size
            break

    if overlap_len > 0:
        return f'{current_text}\n\n{new_text[overlap_len:].lstrip()}'
    return f'{current_text}\n\n{new_text}'


def _transcribe_chunked(
    client, file_path: str, chunk_seconds: int = CHUNK_SECONDS, overlap_seconds: int = CHUNK_OVERLAP_SECONDS
):
    """
    Split `file_path` into chunks, transcribe AND diarize each chunk
    independently, and return (raw_text, diarized_text) as concatenations.

    Per-chunk diarization is the key reason we chunk in the first place:
    feeding a 30-minute raw transcript into one diarize call clipped both the
    input (12k char cap) and the output (max_tokens cap), losing the tail of
    long calls.
    """
    with tempfile.TemporaryDirectory(prefix='transcribe_chunks_') as work_dir:
        chunks = _split_audio_with_ffmpeg(file_path, chunk_seconds, work_dir, overlap_seconds=overlap_seconds)
        logger.warning(
            f'Split into {len(chunks)} chunk(s): chunk={chunk_seconds}s overlap={overlap_seconds}s'
        )

        merged_raw = ''
        merged_diar = ''
        for idx, chunk_path in enumerate(chunks, 1):
            try:
                raw = _transcribe_file(client, chunk_path)
            except Exception as e:
                logger.error(f'Chunk {idx}/{len(chunks)} transcribe failed: {e}')
                raise
            logger.warning(f'Chunk {idx}/{len(chunks)}: raw={len(raw)} chars')
            if not raw:
                logger.warning(f'Chunk {idx}/{len(chunks)} produced empty raw text')
                continue
            merged_raw = _concat_with_overlap_dedupe(merged_raw, raw)

            diar = _diarize_with_openai(raw)
            if not diar.strip():
                # Never silently lose a chunk in final UI output.
                logger.warning(
                    f'Chunk {idx}/{len(chunks)} diarization empty; '
                    f'falling back to raw text for this chunk'
                )
                diar = raw
            logger.warning(f'Chunk {idx}/{len(chunks)}: diarized={len(diar)} chars')
            merged_diar = _concat_with_overlap_dedupe(merged_diar, diar)

        return merged_raw, merged_diar


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
        # No input truncation here: callers pre-chunk long calls (see
        # _transcribe_chunked) so each diarize call sees at most ~10 minutes
        # of speech, well within gpt-4o-mini's 128k context. max_tokens is
        # set to the model's per-response cap so long dialogues are not
        # clipped at the tail.
        message = client.chat.completions.create(
            model='gpt-4o-mini',
            max_tokens=16000,
            response_format={"type": "json_object"},
            messages=[
                {'role': 'system', 'content': (
                    'You translate non-English call transcripts to English AND label '
                    'speakers as Operator or Partner. Output JSON only.'
                )},
                {'role': 'user', 'content': DIARIZE_PROMPT.format(transcription=transcription_text)},
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
        diarized = '\n\n'.join(lines).strip()
        if not diarized:
            logger.warning('Diarization returned no dialogue lines; using raw transcript for this chunk')
            return transcription_text
        return diarized

    except Exception as e:
        logger.warning(f'Diarization failed, using raw transcript: {e}')
        return transcription_text


def _safe_save(contact, update_fields):
    """
    Wrapper around contact.save(update_fields=...) that swallows the
    "Save with update_fields did not affect any rows" error raised when
    the contact was deleted while the transcription was running.
    """
    from django.db import DatabaseError
    from .models import Contact
    try:
        contact.save(update_fields=update_fields)
    except (Contact.DoesNotExist, DatabaseError) as e:
        logger.info(f'Skipping save for contact {contact.pk} — already deleted ({e})')


def transcribe_audio(contact):
    """
    Transcribes contact.audio_file with `gpt-4o-mini-transcribe`. For audio
    longer than CHUNK_SECONDS (or whenever the model returns `input_too_large`)
    splits the file with ffmpeg and transcribes each chunk separately, then
    concatenates the results.

    After transcription the text is diarized into Operator/Partner turns,
    saved on the contact, and summarization is triggered.
    """
    if not OPENAI_API_KEY:
        logger.warning('OPENAI_API_KEY is not set — transcription skipped')
        return

    if not contact.audio_file:
        return

    from openai import OpenAI

    contact.transcription_status = 'processing'
    _safe_save(contact, ['transcription_status'])

    audio_field = contact.audio_file
    file_size   = audio_field.size
    file_name   = os.path.basename(audio_field.name)

    # Materialize the upload onto disk once. We need a real path on the
    # filesystem for ffprobe / ffmpeg, and we want to avoid keeping the entire
    # audio in memory across retries.
    with tempfile.NamedTemporaryFile(
        prefix='audio_', suffix=os.path.splitext(file_name)[1] or '.bin', delete=False
    ) as tmp:
        audio_field.seek(0)
        for chunk in audio_field.chunks():
            tmp.write(chunk)
        local_path = tmp.name

    try:
        duration_secs = _audio_duration_seconds(local_path)
        logger.warning(
            'contact %s starting transcription: size=%dB duration=%ss',
            contact.id, file_size, duration_secs,
        )

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                client = OpenAI(api_key=OPENAI_API_KEY)

                # Decide single-shot vs chunked based on measured duration.
                # If duration is unknown (0), prefer single-shot and fall back
                # to chunking only if OpenAI rejects the file as too large.
                use_chunks = duration_secs and duration_secs > CHUNK_SECONDS

                if use_chunks:
                    logger.warning(
                        'contact %s: duration %ss > %ss — chunking (%ss overlap)',
                        contact.id, duration_secs, CHUNK_SECONDS, CHUNK_OVERLAP_SECONDS,
                    )
                    source_text, diarized = _transcribe_chunked(
                        client, local_path, CHUNK_SECONDS, CHUNK_OVERLAP_SECONDS
                    )
                else:
                    try:
                        source_text = _transcribe_file(client, local_path)
                    except Exception as e:
                        msg = str(e).lower()
                        if 'input_too_large' in msg or 'too large for this model' in msg:
                            logger.warning(
                                'contact %s: single-shot rejected as input_too_large — falling back to chunking',
                                contact.id,
                            )
                            source_text, diarized = _transcribe_chunked(
                                client, local_path, CHUNK_SECONDS, CHUNK_OVERLAP_SECONDS
                            )
                        else:
                            raise
                    else:
                        diarized = _diarize_with_openai(source_text)

                logger.warning(
                    'contact %s gpt-4o-transcribe: duration=%ss raw=%d diarized=%d',
                    contact.id, duration_secs, len(source_text), len(diarized),
                )

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
                if duration_secs > 0:
                    contact.call_duration = duration_secs
                    update_fields.append('call_duration')

                _safe_save(contact, update_fields)

                logger.warning(f'Transcription + diarization done for contact {contact.id} ({duration_secs}s)')

                from .summarization import summarize_transcription
                summarize_transcription(contact)
                return

            except Exception as e:
                last_error = e
                delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
                logger.warning(
                    f'Transcription attempt {attempt+1}/{MAX_RETRIES} failed for contact {contact.id}: {e}. '
                    f'Retrying in {delay}s...'
                )
                time.sleep(delay)

        logger.error(f'Transcription failed after {MAX_RETRIES} attempts for contact {contact.id}: {last_error}')
        contact.transcription_status = 'failed'
        contact.transcription_last_error = f'FAILED: {last_error}'
        _safe_save(contact, ['transcription_status', 'transcription_last_error'])

    finally:
        try:
            os.unlink(local_path)
        except OSError:
            pass
