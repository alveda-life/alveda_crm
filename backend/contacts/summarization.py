import os
import re
import json
import time
import logging

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

DEFAULT_EVALUATION_PROMPT = (
    'Evaluate the call along three dimensions and produce one integer score (1–10) for each:\n'
    '\n'
    '1. SURVEY / DISCOVERY — Did the operator understand the partner\'s situation? '
    'Did they ask the right questions for THIS specific call (first contact, follow-up, '
    'issue resolution, etc.)? If a problem surfaced, did they clarify it? '
    'Do NOT penalize for skipping questions that were irrelevant to this conversation.\n'
    '\n'
    '2. PRODUCT EXPLANATION — Did the partner understand what the operator explained? '
    'Was the explanation clear, accurate and practical? Judge by the partner\'s OWN '
    'words — if they confirmed understanding ("ok", "I see", paraphrased it back), '
    'the explanation was good enough.\n'
    '\n'
    '3. OVERALL — Was the call productive? Did it achieve its concrete goal '
    '(introduce the platform, check in, resolve an issue, gather info, schedule a next step)? '
    'Was the operator professional and respectful of the partner\'s time?'
)

ANALYSIS_PROMPT = """You are a senior call coach reviewing a phone call between an AskAyurveda operator and a partner. Read the transcript like a thoughtful human reviewer would. The operator is your colleague — your job is to help them grow. That means being HONEST: real mistakes ARE real, and pretending a mediocre call was great helps nobody.

{product_block}

═══════════════════════════════════════════════════════════════
THE GOAL — READ THIS FIRST
═══════════════════════════════════════════════════════════════
We use this analysis to make operators BETTER. Two failure modes both
destroy that goal:

  ❌ FAILURE MODE A — Inventing problems.
     Flagging things as mistakes when they were actually fine. Operators
     stop trusting the feedback and ignore it.

  ❌ FAILURE MODE B — Whitewashing.
     Calling weak calls "great" because no rule was technically broken.
     Operators never see what to improve and never grow. This is just
     as bad — arguably worse, because it pretends nothing is wrong.

Your job is HONEST assessment. If the call had real problems, name them
clearly. If the call was solid, say so. If the call was mediocre, do
not award an 8.

═══════════════════════════════════════════════════════════════
EVALUATION RUBRIC — THE PRIMARY SOURCE OF TRUTH
═══════════════════════════════════════════════════════════════
Below this prompt, in the SCORING CRITERIA block, you will receive a
checklist that the business has defined for every operator call. Treat
each numbered / bulleted point in that block as a MANDATORY check.

How to use it (do this for EVERY call, mentally, before you write
anything):

  STEP 1 — PARSE
  Extract every distinct expectation in the SCORING CRITERIA block as
  a separate check (e.g. "greet and introduce", "state purpose of
  call", "identify exactly where the partner stopped in the funnel",
  "understand what the partner compares the product to", "agree on
  date for next call", etc.). There will typically be 6–10 of them.

  STEP 2 — VERDICT FOR EACH
  For EVERY extracted check, assign one of:
    • PASS  — operator clearly did this; quote the line.
    • FAIL  — operator did not do this, or did it superficially.
              Quote the missing/weak moment.
    • N/A   — genuinely doesn't apply to this specific call (rare;
              be honest, don't hide failures behind N/A).

  STEP 3 — REPORT
  EVERY FAIL must appear as a numbered item in `errors_found` AND in
  the matching *_detail block. Do not stop after 2–3 items. If 6
  checks failed, list 6 items. Whitewashing by truncation is a failure
  mode of this analysis.

═══════════════════════════════════════════════════════════════
GLOBAL CHECKS — ALWAYS APPLY (in addition to the rubric above)
═══════════════════════════════════════════════════════════════
These apply to every call regardless of what the rubric says.

  G1. FACTUAL ACCURACY (CRITICAL)
      Cross-check every product claim the operator made against the
      Product Information block above. Common failures:
      • Saying the partner PAYS commission instead of EARNS it.
      • Wrong commission %, wrong bonus amounts, wrong referral terms.
      • Inventing features that don't exist.
      Any factual error is ALWAYS a real coaching point. Quote the
      exact line. This counts in addition to any rubric check.

  G2. FUNNEL-STAGE DIAGNOSIS (CRITICAL)
      The single most important discovery question on every call where
      the partner is not yet using the product is:
      "WHERE EXACTLY did you stop?"
      Did the operator pinpoint the precise step the partner got stuck
      at — registered but never logged in? logged in but never opened
      the catalogue? opened the catalogue but never created a MedSet?
      created a MedSet but never shared the link? shared the link but
      no client clicked? Surface answers like "I was busy", "I haven't
      seen it yet", or "I'll check later" WITHOUT a follow-up that
      pins down the exact stuck step = a FAIL of G2. This must appear
      in errors_found whenever it fails — it almost always fails when
      the partner has zero activity.

  G3. ROOT-CAUSE DEPTH
      For whatever stuck step is identified, did the operator dig
      into the WHY (concrete reason — "I couldn't find the catalogue
      link", "I didn't understand how the slider works", "the
      products didn't match what my patients ask for")? Or did they
      accept the first surface answer? Surface acceptance = FAIL.

  G4. CONCRETE NEXT STEP WITH A DATE
      Before the call ends, did the operator lock in a specific
      action AND a follow-up date? "I'll WhatsApp you" / "let me know
      when you've tried it" with no date = FAIL.

If any of G1–G4 fail, they MUST appear in errors_found alongside the
rubric failures. They are independent of the rubric.

═══════════════════════════════════════════════════════════════
WHAT IS NOT A MISTAKE — DO NOT FLAG THESE
═══════════════════════════════════════════════════════════════
Apply judgment. The following are normal operator behaviour and must
not appear as coaching points:

  • Asking the partner to repeat ("Sorry?", "Could you say that
    again?") — this is good listening, not a failure.
  • Letting the partner finish a thought before answering.
  • Choosing a concise phrase over a longer "ideal" one when the
    concise phrase actually worked.
  • Following the partner's lead when they shift topic naturally.
  • Mirroring the partner's vocabulary (even when simpler than ideal).
  • Imaginary "better wording" you invented — if the original got the
    job done, leave it.

═══════════════════════════════════════════════════════════════
CAUSE vs SYMPTOM — TRACE BACK BEFORE BLAMING
═══════════════════════════════════════════════════════════════
When the partner shows confusion, find the ROOT cause in the
transcript. It is usually an EARLIER operator action (often wrong
information given minutes before), not the operator line that happens
to sit right next to the confusion.

Example: if the operator said "you pay 30%" three turns earlier and
the partner is now saying "I didn't understand", the root cause is the
wrong commission framing — not the operator's later clarifying
question. Quote the actual root-cause line, not the symptom-adjacent
line.

═══════════════════════════════════════════════════════════════
SCORING CALIBRATION — BE HONEST
═══════════════════════════════════════════════════════════════
Counting fails = total of (rubric checks that FAILED) + (G1–G4 that
FAILED). Use that count as your anchor:

  • 9–10  Outstanding.  0 fails. Partner clearly progressed; concrete
                        next step + date locked; partner showed real
                        understanding. Rare.
  • 7–8   Good.         0–1 fails (only minor / non-critical).
  • 5–6   Mixed.        2–3 fails. Default for many real-world calls.
  • 3–4   Weak.         4–5 fails. Partner is no better off after
                        this call than before.
  • 1–2   Broken.       6+ fails, OR a critical fail (G1 wrong
                        product info, G2 no funnel diagnosis at all)
                        combined with no next step.

Default to honesty. A factual error + no funnel diagnosis + no concrete
next step is NOT an 8 — it is a 4 or 5 with three coaching points
listed exhaustively.

═══════════════════════════════════════════════════════════════
LANGUAGE — STRICT
═══════════════════════════════════════════════════════════════
- Write EVERYTHING in ENGLISH ONLY. No Cyrillic anywhere.
- For dialogue lines use the labels "Partner:" and "Operator:".
- If the transcript is in another language, translate quotes into
  natural English (preserve meaning, not literal wording).

═══════════════════════════════════════════════════════════════
CONTEXT
═══════════════════════════════════════════════════════════════
- Could be a FIRST call or a FOLLOW-UP. Evaluate accordingly.
- Calls are short (5–15 min). Be realistic about what fits in that time.
- Use the SCORING CALIBRATION block above. Do not auto-default to 7–8.
  A factual error or no concrete next step pulls the score into 5–6.

═══════════════════════════════════════════════════════════════
SEMANTIC COLOR MARKERS — USE THEM FOR DIALOGUE
═══════════════════════════════════════════════════════════════
The frontend renders text inside these markers as colored callouts.

- :::ok  ... :::  → light GREEN. Use for things the operator did WELL.
- :::bad ... :::  → light RED.   Use for the exact exchange that proves
                                 a real, defensible mistake.
- :::fix ... :::  → mint GREEN.  Use for the better phrasing the
                                 operator could try next time.

Inside each block put dialogue lines like:
> Partner: "exact quote, translated to English"
> Operator: "exact quote, translated to English"

═══════════════════════════════════════════════════════════════
BANNED PHRASING (style)
═══════════════════════════════════════════════════════════════
- "missed extracting details" / "missed uncovering" / "failed to clarify"
- "partly explained" / "partially achieved"
- "could be more specific" / "could have been clearer"
- "needed clearer elaboration"
- "The operator captured..." / "The operator partly..."
- Any sentence that describes what happened without quoting it.
- Any "fix" suggestion that simply rephrases what already worked.

Every sentence must either contain a direct quote or be a 1-line
factual statement. No interpretive summaries.

═══════════════════════════════════════════════════════════════
SECONDARY LENSES — APPLY JUDGMENT
═══════════════════════════════════════════════════════════════
Beyond the mandatory C1–C5 checks above, also consider these. They are
not auto-flags — apply judgment. Mention them only when a clear miss
materially hurt the call.

  L1. Root-cause depth — when the partner is stuck, did the operator
      dig into a CONCRETE reason or settle for a surface answer
      ("I'm busy") without follow-up?
  L2. Open-ended discovery — when learning how the partner works
      (practice, patient flow, alternatives), did the operator ask
      open questions or only yes/no?
  L3. Genuine feedback collection — did the operator collect product-
      useful feedback, or just "is everything ok?"
  L4. Real value of the call — did this call concretely move the
      partner forward, or was it a mechanical check-in?

Do not mention a lens just because it "wasn't explicitly covered".
Many lenses don't apply to every call (e.g. an end-of-call recap is
unnecessary on a 2-minute callback request).

═══════════════════════════════════════════════════════════════
TONE — TEACHING, NEVER HUMILIATING
═══════════════════════════════════════════════════════════════
The operator will read this themselves. Write the way a respected
colleague would speak in a 1:1 — warm, specific, useful.

- Use teaching language: "Next time we can try…", "A stronger move here
  would be…", "An opportunity to grow this skill is…".
- Never use blame language: "you failed to…", "you missed…", "you
  should have…", "it is unacceptable…".
- Open every coaching point by acknowledging the operator's intent /
  what they were trying to do, then suggest the upgrade.
- For every flagged issue, give a concrete alternative phrase the
  operator can copy on the next call.
- Always end with what they did well. People grow from strengths.

═══════════════════════════════════════════════════════════════
OUTPUT — JSON OBJECT (no markdown fences, no extra text)
═══════════════════════════════════════════════════════════════
{{
  "summary": "<4–7 sentences in English: who called whom, partner's current funnel position, what was discussed, what was agreed, next step. Be specific.>",

  "errors_found": "<Markdown numbered list, English. EXHAUSTIVE. Walk through every rubric check and every G1–G4 global check, then list EVERY single FAIL. Do not stop at 1–3 items. If 6 things failed, list 6. Each line: tag the rubric point (or G1/G2/G3/G4), one factual sentence, with the exact quote. Format:\\n\\n1. **G1 — Wrong commission framing.** Operator said \\"You pay 30% commission\\" — partner EARNS, not pays. Caused the partner's \\"I didn't understand\\" two turns later.\\n2. **G2 — No funnel-stage diagnosis.** Partner said \\"I haven't seen it yet\\". Operator did not ask whether they ever logged in, opened the catalogue, or got stuck on a specific step.\\n3. **Rubric: Identify exact stuck step.** Same gap as above — operator accepted \\"I was getting ready\\" as the explanation without follow-up.\\n4. **Rubric: Define action plan (create MedSet + share link).** Operator never instructed how to create a MedSet or what to do after the call.\\n5. **G4 — No next-step date.** Call ended with \\"WhatsApp me, day after tomorrow I'll give the order\\" — no concrete operator-driven action or follow-up date locked in.\\n\\nOnly if every rubric check AND every G1–G4 genuinely pass, write exactly: \\"No mistakes detected — the operator handled this call well.\\" Do NOT use that line to be polite — it must be true.>",

  "quality": {{
    "survey":              <int 1–10>,
    "survey_comment":      "<1–2 sentences in English with at least one direct quote.>",
    "survey_detail":       "<Markdown in English. Use the colored block markers. Structure:\\n\\n### ✅ What worked\\n:::ok\\n> Partner: \\"...\\"\\n> Operator: \\"...\\"\\n> Partner: \\"...\\"\\n:::\\n\\n👍 [1 sentence: what useful info this discovery yielded.]\\n\\n(Repeat for each genuinely good moment.)\\n\\n### 🌱 Coaching opportunity\\n(Include this section whenever any C1–C5 check failed inside the survey/discovery dimension, OR when an L1/L2/L3 lens was clearly missed.)\\n\\n:::bad\\n> Partner: \\"...\\"\\n> Operator: \\"...\\"\\n> Partner: \\"...\\"\\n:::\\n\\n**What was happening:** [1 factual sentence describing what the operator was trying to do.]\\n\\n**A stronger move next time:**\\n:::fix\\n> Operator: \\"recommended phrasing — no random extras.\\"\\n:::\\n\\nIf nothing genuinely needs coaching, omit the entire 🌱 section and write: \\"Discovery on this call was solid — no coaching points for this dimension.\\">",

    "explanation":         <int 1–10>,
    "explanation_comment": "<Same rules: 1–2 sentences with at least one direct quote.>",
    "explanation_detail":  "<Same Markdown format as survey_detail. Use :::ok / :::bad / :::fix blocks only when warranted.>",

    "overall":             <int 1–10>,
    "overall_comment":     "<1 factual sentence in English describing the concrete outcome of the call.>",
    "overall_detail":      "<Same Markdown format. Show the exchange where the next step was (or wasn't) established. Close with what the operator did well.>"
  }},

  "recommendations": "<Markdown in English. ONLY include genuine coaching points. For each:\\n\\n### 1. [Concrete title — what specifically happened]\\n\\n**In the call:**\\n:::bad\\n> Partner: \\"...\\"\\n> Operator: \\"...\\"\\n> Partner: \\"...\\"\\n:::\\n\\n**What was happening:** [factual sentence — describe operator intent first.]\\n\\n**Try this next time:**\\n:::fix\\n> Operator: \\"alternative that fixes ONLY this point.\\"\\n:::\\n\\n---\\n\\n### 📋 Bottom line\\n- [1 specific factual point about this call]\\n\\nIf there are no real coaching points, write: \\"This was a solid call — no specific recommendations beyond keeping the current approach.\\">",

  "improvement_plan": "<Markdown in English. Always include this section, but its character changes with the call:\\n\\n• If the call had real coaching points → list 1–3 concrete habits to build, each with a copy-ready phrase.\\n• If the call was solid → focus on what to keep doing and one optional stretch goal.\\n\\nFormat:\\n\\n### 🚀 Improvement Plan\\n\\n1. **[Habit to build]** — [1 sentence: what and why, in coaching language.]\\n   - Try this opener next time:\\n     :::fix\\n     > Operator: \\"...\\"\\n     :::\\n\\n### 💪 Keep doing\\n- [1 thing that worked well — quote-anchored]\\n- [Another thing that worked well, if any]\\n\\nMaximum 3 improvement items + up to 3 keep-doing items.>",

  "feedback": "<2–3 sentences in English. What was this call about? What concrete outcome? If any C1–C5 check failed, name the failure honestly. If everything genuinely passed, say the call was good and why.>"
}}

CORE RULES:
1. ENGLISH ONLY everywhere. No Cyrillic characters allowed.
2. Use the labels "Partner:" and "Operator:" — never "Партнёр" / "Оператор".
3. Wrap dialogue in :::ok / :::bad / :::fix when it's part of a coaching point. You don't need to wrap every quoted line in a block.
4. Run BOTH the user-supplied rubric AND G1–G4 on every call. EVERY FAIL must appear in errors_found and the matching detail block. Be exhaustive — do not cap at 1–3 items.
5. The user-supplied rubric (in the SCORING CRITERIA block below) is the primary source of truth for what "good" looks like. Treat each numbered/bulleted point as a separate, named check — quote it back when you flag a fail.
6. Tone is teaching, not policing. Acknowledge what the operator was trying to do, then suggest the upgrade. Never use blame words ("you failed", "you missed", "you should have").
7. Always end strong: highlight what the operator did well in the "💪 Keep doing" section.
8. Before writing "No mistakes detected" — pause and re-walk every rubric point + G1–G4 one by one. If even one fails, list it. Honesty over politeness.

═══════════════════════════════════════════════════════════════
SCORING CRITERIA (apply to all three dimensions: survey, explanation, overall)
═══════════════════════════════════════════════════════════════
{evaluation_criteria}

Call transcript:
{transcript}"""


def summarize_transcription(contact):
    """
    Calls Claude to summarize the transcript and score call quality.
    Saves summary, quality scores, and comments to the contact.
    """
    if not OPENAI_API_KEY:
        logger.warning('OPENAI_API_KEY is not set — summarization skipped')
        return

    transcript = (contact.diarized_transcript or contact.transcription or '').strip()
    if not transcript:
        return

    from openai import OpenAI
    from accounts.models import CRMSettings

    contact.summary_status = 'processing'
    contact.save(update_fields=['summary_status'])

    settings = CRMSettings.get()

    product_block = (
        f'Product information for context:\n{settings.product_info.strip()}\n'
        if settings.product_info.strip()
        else ''
    )

    prompt = ANALYSIS_PROMPT.format(
        product_block        = product_block,
        evaluation_criteria  = (settings.evaluation_prompt or '').strip() or DEFAULT_EVALUATION_PROMPT,
        transcript           = transcript[:12000],
    )

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            client  = OpenAI(api_key=OPENAI_API_KEY)
            message = client.chat.completions.create(
                model='gpt-4o',
                max_tokens=8192,
                response_format={"type": "json_object"},
                messages=[
                    {'role': 'system', 'content': 'Return valid JSON only.'},
                    {'role': 'user', 'content': prompt},
                ],
            )

            raw = message.choices[0].message.content.strip()

            if raw.startswith('```'):
                raw = raw.split('```')[1]
                if raw.startswith('json'):
                    raw = raw[4:]
            raw = raw.strip()

            raw = re.sub(r',\s*}', '}', raw)
            raw = re.sub(r',\s*]', ']', raw)
            raw = re.sub(r'[\x00-\x09\x0b\x0c\x0e-\x1f]', ' ', raw)

            data    = json.loads(raw)
            quality = data.get('quality', {})

            def _score(val):
                try:
                    v = int(val)
                    return max(1, min(10, v))
                except (TypeError, ValueError):
                    return None

            def _txt(val):
                """Coerce model output to a stripped string (lists/dicts → joined str)."""
                if val is None:
                    return ''
                if isinstance(val, str):
                    return val.strip()
                if isinstance(val, list):
                    return '\n'.join(_txt(v) for v in val).strip()
                return str(val).strip()

            def _polish(text):
                """Cosmetic post-process for AI markdown output:
                  • split inline numbered items onto separate lines
                  • soften residual blame language the prompt forbade
                """
                if not text:
                    return text
                # ". 2. **" → ".\n\n2. **" (inline list items)
                text = re.sub(r'(?<=[\.\?\!])\s+(?=\d+\.\s+\*\*)', '\n\n', text)
                # blame → coaching
                replacements = [
                    (r'\bfailed to\b',         'did not'),
                    (r'\boperator failed\b',   'operator did not'),
                    (r'\byou failed to\b',     'next time, try to'),
                    (r'\byou should have\b',   'next time, try to'),
                    (r'\byou missed\b',        'an opportunity here was to'),
                    (r'\byou didn\'t\b',       'next time, try to'),
                    (r'\bwas unacceptable\b',  'was a missed opportunity'),
                ]
                for pat, repl in replacements:
                    text = re.sub(pat, repl, text, flags=re.IGNORECASE)
                return text

            contact.summary                     = _txt(data.get('summary'))
            contact.quality_survey              = _score(quality.get('survey'))
            contact.quality_survey_comment      = _polish(_txt(quality.get('survey_comment')))
            contact.quality_explanation         = _score(quality.get('explanation'))
            contact.quality_explanation_comment = _polish(_txt(quality.get('explanation_comment')))
            contact.quality_overall             = _score(quality.get('overall'))
            contact.quality_overall_comment     = _polish(_txt(quality.get('overall_comment')))
            contact.quality_survey_detail       = _polish(_txt(quality.get('survey_detail')))
            contact.quality_explanation_detail  = _polish(_txt(quality.get('explanation_detail')))
            contact.quality_overall_detail      = _polish(_txt(quality.get('overall_detail')))
            contact.quality_recommendations     = _polish(_txt(data.get('recommendations')))
            contact.quality_feedback            = _polish(_txt(data.get('feedback')))
            contact.quality_errors_found        = _polish(_txt(data.get('errors_found')))
            contact.quality_improvement_plan    = _polish(_txt(data.get('improvement_plan')))
            contact.summary_status              = 'done'
            contact.save(update_fields=[
                'summary', 'summary_status',
                'quality_survey', 'quality_survey_comment', 'quality_survey_detail',
                'quality_explanation', 'quality_explanation_comment', 'quality_explanation_detail',
                'quality_overall', 'quality_overall_comment', 'quality_overall_detail',
                'quality_recommendations', 'quality_feedback',
                'quality_errors_found', 'quality_improvement_plan',
            ])

            logger.info(f'Summary + quality scores done for contact {contact.id}')
            return

        except Exception as e:
            last_error = e
            delay = RETRY_DELAYS[attempt] if attempt < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
            logger.warning(f'Summarization attempt {attempt+1}/{MAX_RETRIES} failed for contact {contact.id}: {e}. Retrying in {delay}s...')
            time.sleep(delay)

    logger.error(f'Summarization failed after {MAX_RETRIES} attempts for contact {contact.id}: {last_error}')
    contact.summary_status = 'failed'
    contact.save(update_fields=['summary_status'])
