# Provenance Guard

A backend system any creative-sharing platform could plug into to classify submitted text as AI-generated or human-written, score confidence with honest uncertainty, surface a plain-language transparency label, and let creators appeal a classification.

Perfect AI detection is an unsolved problem. Provenance Guard does **not** pretend to a binary truth — it reports calibrated uncertainty and gives creators a path to contest a decision. The full design spec is in [`planning.md`](./planning.md).

---

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate                 # Windows  (source .venv/bin/activate on Mac/Linux)
pip install -r requirements.txt
cp .env.example .env                   # then add your GROQ_API_KEY
python app.py                          # serves http://localhost:5000
```

> **No Groq key?** The LLM signal falls back to a documented heuristic so the system runs end-to-end for local testing. With a real `GROQ_API_KEY` the semantic signal is far sharper. The example numbers below were produced in **fallback mode** — note the floored `llm_score` (0.25 / 1.0) is the heuristic, not the real model.

### Endpoints

| Endpoint | Body | Returns |
|----------|------|---------|
| `POST /submit` | `{"text": "...", "creator_id": "..."}` | `content_id`, `attribution`, `confidence`, `label`, `signals` |
| `POST /appeal` | `{"content_id": "...", "creator_reasoning": "..."}` | `content_id`, `status`, `message` |
| `GET /log` | — | `{"entries": [...]}` most recent audit entries |

```bash
curl -s -X POST http://localhost:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "The sun dipped below the horizon, painting the sky in amber.", "creator_id": "test-user-1"}'
```

---

## Architecture overview

A submission's text is scored independently by **two distinct signals**, their scores are combined into one calibrated confidence, that confidence selects one of three transparency labels, and the whole decision is written to the audit log before the response returns.

```
 text + creator_id ──► POST /submit
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        llm_signal              stylometry_signal
        (semantic, Groq)        (structural, pure Python)
        → P(AI) 0..1            → P(AI) 0..1
              └───────────┬───────────┘
                          ▼
              scoring.combine()  →  ai_score, attribution, confidence
                          ▼
              scoring.label_for() →  transparency label text
                          ▼
              audit.write_decision() ──► SQLite
                          ▼
        response: {content_id, attribution, confidence, label, signals}
```

An appeal references the original `content_id`, flips its status from `classified` to `under_review`, and records the creator's reasoning alongside the original decision — no automatic re-classification.

Modules: `app.py` (routes), `signals.py` (the two signals), `scoring.py` (combination + labels), `audit.py` (SQLite audit log).

---

## Detection signals

Two signals that capture **genuinely different properties** — one semantic, one structural. The combination is more informative than either alone.

### Signal 1 — LLM classification (Groq, `llama-3.3-70b-versatile`)
- **Measures:** semantic and stylistic coherence holistically — does the text *read* as AI? Picks up generic hedging, even tone, lack of lived specificity.
- **Why it works:** an LLM assesses meaning, not just surface statistics, and has effectively learned what AI "tells" look like.
- **What it misses:** lightly-edited AI text; formal human prose that mimics AI cadence. It is non-deterministic and costs an API call.

### Signal 2 — Stylometric heuristics (pure Python)
- **Sentence-length burstiness** — humans vary sentence length a lot; AI is uniform. Low variance → AI-like.
- **Type-token ratio** — vocabulary diversity; flat mid-range diversity reads AI-like, high diversity reads human.
- **Punctuation variety** — humans use irregular marks (— ; : ( ) … ! ?); AI is more even.
- **What it misses:** short texts (statistics are noisy); formal/edited human writing that is structurally uniform; repetitive poetry. Short inputs (< 40 words) are deliberately blended toward "uncertain."

---

## Confidence scoring

The two signals each output `P(AI)` in `0..1`. They are combined with the LLM weighted higher (it is the more reliable signal):

```
ai_score   = 0.60 * llm_score + 0.40 * stylo_score
confidence = 2 * |ai_score - 0.5|        # 0 = coin-flip, 1 = certain
```

`confidence` is the **certainty of the verdict**, so a borderline `ai_score` near 0.5 yields low confidence and a "uncertain" label, while an extreme score yields high confidence and a decisive label.

**Asymmetric thresholds (the false-positive guard):**

| `ai_score` | attribution | label |
|------------|-------------|-------|
| `>= 0.72` | `likely_ai` | high-confidence AI |
| `<= 0.32` | `likely_human` | high-confidence human |
| `0.32 .. 0.72` | `uncertain` | uncertain |

The AI region (width 0.28) is deliberately narrower than the human region (width 0.32), and the uncertain middle is generous. **A false positive — labeling a human's work as AI — is worse than a false negative on a writing platform**, so it takes stronger evidence to accuse a creator than to clear them.

### How I validated it's meaningful

I tested four deliberately chosen inputs (clearly AI, clearly human, two borderline) and confirmed the scores separate and match intuition rather than collapsing to a constant. Two example submissions with **noticeably different confidence**:

| Submission | `llm` | `stylo` | `ai_score` | `confidence` | attribution | label |
|------------|-------|---------|-----------|-------------|-------------|-------|
| "Artificial intelligence represents a transformative paradigm shift… stakeholders must collaborate to ensure responsible deployment." | 1.00 | 0.56 | 0.82 | **0.64** | `likely_ai` | high-confidence AI |
| "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but WAY too much sodium…" | 0.25 | 0.36 | 0.30 | **0.41** | `likely_human` | high-confidence human |

The clearly-AI essay produces a high-confidence AI label; the casual human review produces a human label with a very different score. (Numbers from fallback mode; a real Groq key sharpens the `llm` column and widens the gap.)

---

## Transparency label — the three variants (verbatim)

`{pct}` = `round(confidence * 100)`.

> **high-confidence AI:**
> `🤖 Likely AI-generated. Our analysis strongly suggests this text was produced by an AI system (confidence: {pct}%). This is an automated estimate, not a verdict — if you wrote this yourself, you can appeal.`

> **high-confidence human:**
> `✍️ Likely human-written. Our analysis strongly suggests a person wrote this text (confidence: {pct}%). This is an automated estimate, not a certainty.`

> **uncertain:**
> `❓ Uncertain origin. We couldn't confidently tell whether a person or an AI wrote this (confidence: {pct}%). We've chosen not to guess — treat the authorship as unverified.`

Design intent: a non-technical reader should understand the verdict *and* that it is an estimate. The AI variant is the only one that invites an appeal, because that is the variant where a wrong call harms a creator.

---

## Appeals workflow

`POST /appeal` with the original `content_id` and `creator_reasoning`:
1. looks up the original audit entry,
2. changes `status` from `classified` → `under_review`,
3. stores `appeal_reasoning` and `appeal_timestamp` on that entry,
4. returns a confirmation.

A human reviewer sees the original decision (attribution, confidence, both signal scores) and the creator's reasoning together in one entry via `GET /log`. No automatic re-classification.

---

## Rate limiting

Applied to `POST /submit` via Flask-Limiter (`memory://` storage):

```
@limiter.limit("10 per minute;100 per day")
```

**Reasoning — the numbers are defensible, not arbitrary:** a real creator submits their own work occasionally — a handful of pieces in a sitting, not hundreds. **10 per minute** comfortably covers a person revising and resubmitting while making it useless to flood the endpoint; **100 per day** caps a single source's total load (each submission can cost a Groq call, so this also bounds API spend) without obstructing a prolific legitimate writer. An adversary scripting bulk submissions hits the per-minute wall almost immediately.

**Evidence** — sending 12 rapid requests (limit is 10/min):

```
status codes: [200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 429, 429]
200s: 10 | 429s: 2
```

---

## Audit log

Every decision and appeal is written to a structured SQLite log (`audit_log.db`) — not `print()` statements. Each entry captures timestamp, content ID, creator ID, attribution, confidence, **both individual signal scores**, the label, status, and any appeal reasoning. Sample from `GET /log` (3 entries; the AI one has been appealed):

```json
[
  {
    "content_id": "07222667-...",
    "creator_id": "u-mid",
    "timestamp": "2026-06-26T03:02:40.497Z",
    "attribution": "uncertain",
    "confidence": 0.31,
    "llm_score": 0.25,
    "stylo_score": 0.481,
    "status": "classified",
    "appeal_reasoning": null
  },
  {
    "content_id": "a0b46773-...",
    "creator_id": "u-human",
    "timestamp": "2026-06-26T03:02:40.463Z",
    "attribution": "likely_human",
    "confidence": 0.41,
    "llm_score": 0.25,
    "stylo_score": 0.362,
    "status": "classified",
    "appeal_reasoning": null
  },
  {
    "content_id": "4244cc45-...",
    "creator_id": "u-ai",
    "timestamp": "2026-06-26T03:02:40.421Z",
    "attribution": "likely_ai",
    "confidence": 0.64,
    "llm_score": 1.0,
    "stylo_score": 0.555,
    "status": "under_review",
    "appeal_reasoning": "I wrote this essay myself for a class assignment."
  }
]
```

---

## Known limitations

- **Formal, edited human prose** (essays, published-style writing) is the system's clearest failure mode. Its low sentence-length burstiness and even punctuation make the *stylometry* signal read it as AI-like, dragging the combined score up. This is a direct property of the structural signal, not a data-quantity problem. The wide "uncertain" band and the appeal path are the mitigation — the system declines to accuse rather than risk a false positive.
- **Repetitive poetry / song lyrics** crush type-token ratio and sentence-length variance, mimicking AI uniformity, and would tend to misclassify.
- **Short submissions (< 40 words)** carry unreliable stylometric statistics; they are blended toward "uncertain" by design.

---

## Spec reflection

- **Where the spec helped:** writing the three label variants and the threshold table in `planning.md` *before* coding meant `scoring.py` had exact targets to implement against. When I wired the label function I was matching pre-written text, not inventing UX mid-build, and all three variants were reachable on the first integration test.
- **Where the implementation diverged:** the spec framed `confidence` loosely as "what 0.6 means." In implementation I split it into two explicit quantities — `ai_score` (the raw P(AI) that drives the thresholds) and `confidence` (certainty = `2*|ai_score-0.5|`, what the user sees). The single number in the spec was ambiguous about whether a "human" verdict should report a *low* or *high* confidence; separating the two removed that ambiguity.

---

## AI usage

1. **Scoring scaffold.** I directed an AI tool to generate the `scoring.combine()` skeleton from my detection-signals and uncertainty sections. It produced a symmetric threshold split at 0.5; I **overrode** it with the asymmetric `0.72 / 0.32` thresholds because the symmetric version ignored the false-positive-is-worse requirement that the whole design hinges on.
2. **Stylometry metrics.** I asked an AI tool to draft the three stylometric metric calculations. It generated reasonable code but mapped type-token ratio with the sign inverted (high diversity → AI). I **revised** the mapping after testing on the clearly-human sample, which exposed the bug because a high-diversity casual review was scoring AI-like.

---

## Walkthrough

A short portfolio walkthrough video (a couple of minutes) demonstrating `/submit` across the three label variants, an appeal flipping status to `under_review`, and the rate limiter returning `429`, with a quick tour of the two-signal design.

*(Recorded separately and submitted via the Course Portal.)*
