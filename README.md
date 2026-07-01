# Provenance Guard

A Flask app that checks whether submitted text is likely human-written or AI-generated, returns a transparency label with a confidence score, logs every decision, and lets creators appeal.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate          # Mac/Linux
# source .venv/Scripts/activate    # Windows

pip install -r requirements.txt
cp .env.example .env               # add your GROQ_API_KEY
python app.py                      # http://localhost:5000
```

## How It Works

Two independent signals feed into one confidence score:

1. **Groq LLM** (`llama-3.3-70b-versatile`) — measures phrasing, tone, and hedging language (e.g. "furthermore," "it is important to note"). Captures whether text *reads* human or AI.
2. **Stylometric heuristics** — measures sentence length variance, vocabulary diversity (type-token ratio), and punctuation density. Captures structural patterns in pure Python.

**What each signal misses:**
- **LLM:** Lightly edited AI with personal anecdotes added; formal writing by non-native speakers; heavily paraphrased AI text.
- **Stylometric:** Formal academic prose, poetry, very short text (< 30 words), bullet lists and code snippets.

```
POST /submit → LLM signal → Stylometric signal → Scoring → Label → Audit log
POST /appeal → Status update → Audit log
GET  /log    → Recent entries
```

Full diagram and design rationale in [planning.md](planning.md).

## API

**Submit text:**
```bash
curl -s -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "Your text here...", "creator_id": "user-123"}' | python -m json.tool
```

**Appeal a classification:**
```bash
curl -s -X POST http://localhost:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "PASTE-ID", "creator_reasoning": "Why you disagree."}' | python -m json.tool
```

**View audit log:**
```bash
curl -s http://localhost:5000/log | python -m json.tool
```

## Scoring

```
confidence = 0.60 × llm_score + 0.40 × stylometric_score
```

| Score | Attribution | Label |
|-------|-------------|-------|
| ≥ 0.65 | `likely_ai` | Likely AI-Generated |
| 0.35–0.65 | `uncertain` | Attribution Uncertain |
| ≤ 0.35 | `likely_human` | Likely Human-Written |

One signal reads meaning, the other reads structure. When they agree, confidence is high. When they disagree, the score lands in the uncertain band instead of guessing wrong.

### Example scores

**AI text** (confidence 0.67): *"Artificial intelligence represents a transformative paradigm shift... It is important to note that while the benefits of AI are numerous..."*
→ `llm: 0.95`, `stylometric: 0.25`, `likely_ai`

**Human text** (confidence 0.10): *"ok so i finally tried that new ramen place downtown and honestly? underwhelming..."*
→ `llm: 0.05`, `stylometric: 0.17`, `likely_human`

**Validation:** I tested four inputs — clearly AI, clearly human, formal human, and lightly edited AI — and confirmed scores spread across the range. AI text hit ~0.67, casual human text hit ~0.10, and borderline cases landed between 0.35 and 0.65 in the uncertain band. Thresholds at 0.35 and 0.65 produce three distinct label categories, not a binary flip at 0.5.

## Labels

**Likely AI (≥ 0.65):**
> **Likely AI-Generated** — This content was assessed as likely AI-generated (confidence: {pct}%). Our analysis detected patterns consistent with AI-assisted writing, including uniform sentence structure and characteristic phrasing. If you believe this assessment is incorrect, you may submit an appeal.

**Likely Human (≤ 0.35):**
> **Likely Human-Written** — This content was assessed as likely human-written (confidence: {pct}%). Writing patterns — including natural variation in sentence length and vocabulary — suggest authentic human authorship.

**Uncertain (0.35–0.65):**
> **Attribution Uncertain** — We could not confidently determine authorship (confidence: {pct}%). The text shows mixed signals from our analysis. Manual review is recommended if provenance is important. You may submit an appeal with additional context.

## Rate Limiting

`/submit` is capped at **10/minute** and **100/day** per IP. Normal for a writer submitting their own work; blocks scripted flooding.

Test it (server must be running):
```bash
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "Rate limit test.", "creator_id": "ratelimit-test"}'
done
```

Result: first 10 requests return `200`, then `429` once the minute quota is hit.

**Observed output:**

```
200
200
200
200
200
200
200
200
200
200
429
429
```

## Demo: Submit Responses

**High-confidence AI submission:**

```bash
curl -s -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "Artificial intelligence represents a transformative paradigm shift...", "creator_id": "demo-ai"}' | python -m json.tool
```

```json
{
  "content_id": "9f70ef2e-4570-4f02-8204-af7fe91f00ac",
  "attribution": "likely_ai",
  "confidence": 0.6684,
  "llm_score": 0.95,
  "stylometric_score": 0.246,
  "label": "Likely AI-Generated — This content was assessed as likely AI-generated (confidence: 67%). Our analysis detected patterns consistent with AI-assisted writing..."
}
```

**Lower-confidence human submission:**

```bash
curl -s -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "The sun dipped below the horizon, painting the sky in hues of amber and rose...", "creator_id": "demo-human"}' | python -m json.tool
```

```json
{
  "content_id": "4882b2a9-ef04-4476-9132-eff72b857ce7",
  "attribution": "likely_human",
  "confidence": 0.3133,
  "llm_score": 0.3,
  "stylometric_score": 0.3333,
  "label": "Likely Human-Written — This content was assessed as likely human-written (confidence: 31%). Writing patterns — including natural variation in sentence length and vocabulary — suggest authentic human authorship."
}
```

Both responses include individual signal scores alongside the combined confidence score. Label text differs between results — not just the number.

**Appeal submission** (updates status to `under_review`):

```bash
curl -s -X POST http://localhost:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "4882b2a9-ef04-4476-9132-eff72b857ce7", "creator_reasoning": "Why you disagree."}' | python -m json.tool
```

```json
{
  "content_id": "4882b2a9-ef04-4476-9132-eff72b857ce7",
  "status": "under_review",
  "message": "Appeal received and queued for review."
}
```

## Audit Log Sample

At least 3 structured entries with attribution, confidence, and timestamp. One entry shows an appeal alongside the original classification:

```json
{
  "entries": [
    {
      "content_id": "4882b2a9-ef04-4476-9132-eff72b857ce7",
      "creator_id": "test-user-1",
      "timestamp": "2026-06-30T18:49:38.385307+00:00",
      "attribution": "likely_human",
      "confidence": 0.3133,
      "llm_score": 0.3,
      "stylometric_score": 0.3333,
      "status": "under_review",
      "appeal_reasoning": "Why you disagree.",
      "appeal_timestamp": "2026-06-30T18:52:14.797065+00:00"
    },
    {
      "content_id": "9f70ef2e-4570-4f02-8204-af7fe91f00ac",
      "creator_id": "test-user-2",
      "timestamp": "2026-06-30T18:37:58.943334+00:00",
      "attribution": "likely_ai",
      "confidence": 0.6684,
      "llm_score": 0.95,
      "stylometric_score": 0.246,
      "status": "under_review",
      "appeal_reasoning": "I wrote this myself from personal experience..."
    },
    {
      "content_id": "5e177a95-f7ba-4ea6-87ae-2a1506cb4bea",
      "creator_id": "test-user-1",
      "timestamp": "2026-06-30T18:37:45.395421+00:00",
      "attribution": "likely_human",
      "confidence": 0.2899,
      "llm_score": 0.05,
      "stylometric_score": 0.6498,
      "status": "classified"
    }
  ]
}
```

## Known Limitations

**Formal academic prose** is the biggest false-positive risk. Uniform sentences and impersonal tone look AI to both signals. An economics professor's policy brief might score mid-high even when it's entirely theirs. The uncertain band and appeals exist for exactly this.

**Lightly edited AI** — paste AI text, add "I remember when..." at the top. LLM score drops but stylometrics stay high → usually lands uncertain, not "likely human."

**Short text** (< 30 words) — stylometrics don't have enough to work with. Scores are unreliable.

## Spec Reflection

The spec helped most with concrete numbers — the 0.35/0.65 thresholds and 0.60/0.40 weight split meant I wasn't guessing during implementation. Writing label text upfront also kept the `/submit` response consistent.

One divergence: the spec assumed Groq would always be available. I added a keyword fallback for when `GROQ_API_KEY` isn't set, so local dev works without a key. Less accurate on borderline text; would remove in production.

## AI Usage

1. **Flask skeleton + Signal 1:** Fed detection signals + diagram to AI. Got the app structure and Groq integration. I tightened the JSON prompt and added a parsing fallback plus a keyword heuristic for keyless dev.

2. **Signal 2 + scoring:** Fed stylometric spec + thresholds. AI generated the three-metric function; I tweaked variance normalization after short texts produced extreme scores.

3. **Labels, appeals, rate limiting:** Fed label variants + appeals workflow. Verified label text matched spec, added Flask-Limiter with `storage_uri="memory://"`, tested all three label paths and appeal status updates via curl.

## Project Structure

```
├── app.py                  # Routes
├── planning.md             # Full spec
├── signals/
│   ├── llm_signal.py       # Groq classification
│   └── stylometric.py      # Structural heuristics
└── services/
    ├── scoring.py          # Confidence + attribution
    ├── labels.py           # Label text
    └── audit_log.py        # SQLite log
```
