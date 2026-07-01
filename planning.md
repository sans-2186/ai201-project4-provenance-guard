# Provenance Guard — Planning Spec

## Architecture

### How it works

Someone submits text via `POST /submit`. The Flask app checks the payload, assigns a `content_id`, and runs two detection signals:

1. **Groq LLM** — reads the text and scores how AI-like it feels
2. **Stylometric heuristics** — counts structural patterns in pure Python

Each signal returns a score from 0.0 (human) to 1.0 (AI). Those get combined into one confidence score, mapped to an attribution (`likely_ai`, `uncertain`, or `likely_human`), and turned into a plain-English label. Everything gets saved to a SQLite audit log and sent back to the client.

If the creator disagrees, they hit `POST /appeal` with their `content_id` and reasoning. Status flips to `under_review` and the appeal gets logged. No auto re-classification — it just queues the item for a human reviewer.

### Diagram

```
SUBMISSION FLOW
===============

  Client                Flask App              Signal 1 (LLM)        Signal 2 (Stylometric)
    |                       |                        |                        |
    |  POST /submit         |                        |                        |
    |  {text, creator_id}   |                        |                        |
    |---------------------->|                        |                        |
    |                       |  raw text              |                        |
    |                       |----------------------->|                        |
    |                       |  llm_score (0–1)       |                        |
    |                       |<-----------------------|                        |
    |                       |  raw text              |                        |
    |                       |------------------------------------------------->|
    |                       |  stylometric_score (0–1)                        |
    |                       |<-------------------------------------------------|
    |                       |  weighted avg → label  |                        |
    |                       |  → audit log (SQLite)  |                        |
    |  {content_id, label}  |                        |                        |
    |<----------------------|                        |                        |


APPEAL FLOW
===========

  Client                Flask App              Audit Log (SQLite)
    |                       |                        |
    |  POST /appeal         |                        |
    |  {content_id, reason} |                        |
    |---------------------->|  lookup + update       |
    |                       |----------------------->|
    |                       |  status → under_review |
    |  {status, message}    |<-----------------------|
    |<----------------------|                        |
```

---

## Detection Signals

### Signal 1: LLM Classification (Groq)

**Measures:** Whether the text *reads* human or AI — phrasing, tone, hedging language ("furthermore," "it is important to note").

**Why it works:** AI text tends to be polished and impersonal. Human writing is messier — contractions, tangents, uneven formality.

**Output:** `llm_score` float, 0.0–1.0 (higher = more AI-like)

**Misses:** Lightly edited AI with personal anecdotes added. Formal non-native speakers. Heavy paraphrasing.

### Signal 2: Stylometric Heuristics

**Measures:** Three stats in pure Python:
- Sentence length variance (AI = uniform, human = varied)
- Type-token ratio / vocabulary diversity (AI = repetitive)
- Punctuation density (AI = regular and moderate)

Each normalized to 0–1, then averaged.

**Why it works:** These are structural, not semantic — catches different things than the LLM.

**Output:** `stylometric_score` float, 0.0–1.0

**Misses:** Formal academic prose, poetry, very short text (< 20 words), bullet lists.

### Combining them

```
confidence = 0.60 × llm_score + 0.40 × stylometric_score
```

LLM gets more weight — it's better at reading longer prose. Stylometrics add a structural check when semantics are ambiguous.

---

## Uncertainty & Thresholds

A score of **0.6** means "leaning AI, but not sure" — both signals landed in the gray zone.

| Score | Attribution | Meaning |
|-------|-------------|---------|
| ≥ 0.65 | `likely_ai` | Strong AI signals |
| 0.35–0.65 | `uncertain` | Mixed — don't trust this blindly |
| ≤ 0.35 | `likely_human` | Strong human signals |

The 30-point uncertain band is intentional. I'd rather say "not sure" than wrongly flag a human writer.

---

## Transparency Labels

**Likely AI (≥ 0.65):**
> **Likely AI-Generated** — This content was assessed as likely AI-generated (confidence: {pct}%). Our analysis detected patterns consistent with AI-assisted writing, including uniform sentence structure and characteristic phrasing. If you believe this assessment is incorrect, you may submit an appeal.

**Likely Human (≤ 0.35):**
> **Likely Human-Written** — This content was assessed as likely human-written (confidence: {pct}%). Writing patterns — including natural variation in sentence length and vocabulary — suggest authentic human authorship.

**Uncertain (0.35–0.65):**
> **Attribution Uncertain** — We could not confidently determine authorship (confidence: {pct}%). The text shows mixed signals from our analysis. Manual review is recommended if provenance is important. You may submit an appeal with additional context.

---

## Appeals

**Who:** Any creator with a `content_id` from `/submit` (no auth check in this prototype).

**What they send:** `content_id` + `creator_reasoning` (free text).

**What happens:**
1. Look up submission (404 if missing)
2. Status → `under_review`
3. Log appeal reasoning + timestamp
4. Return confirmation

A reviewer would see a queue of `under_review` items with the original text, both signal scores, the label, and the creator's explanation.

---

## Edge Cases

1. **Formal academic writing** — uniform sentences + impersonal tone can look AI. Likely lands in uncertain or false-positive AI. That's what appeals are for.
2. **Edited AI with personal anecdotes** — LLM score drops, stylometrics stay high. Should land uncertain, not "likely human."
3. **Very short text** — not enough data for stylometrics. Scores are unreliable.
4. **Poetry with repetition** — low TTR mimics AI patterns. Stylometrics high, LLM may disagree → uncertain.

---

## API

| Method | Endpoint | Body | Returns |
|--------|----------|------|---------|
| POST | `/submit` | `{text, creator_id}` | `{content_id, attribution, confidence, label, llm_score, stylometric_score}` |
| POST | `/appeal` | `{content_id, creator_reasoning}` | `{content_id, status, message}` |
| GET | `/log` | — | `{entries: [...]}` |

---

## AI Tool Plan

**M3 — Submit + Signal 1:** Feed detection signals + diagram to AI. Generate Flask skeleton, Groq signal, audit log. Verify with curl — check `content_id`, `llm_score`, and log entry.

**M4 — Signal 2 + Scoring:** Feed stylometric spec + thresholds + diagram. Generate heuristics + weighted scoring. Test 4 inputs (clear AI, clear human, formal human, edited AI) and confirm scores actually vary.

**M5 — Production:** Feed labels + appeals + diagram. Generate label function, `/appeal`, Flask-Limiter. Verify all 3 labels are reachable, appeals update status, rate limit returns 429 after 10/min.
