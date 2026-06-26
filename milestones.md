# Provenance Guard — Milestones

Backend system that classifies submitted creative text as AI vs human, scores confidence with honest uncertainty, surfaces a transparency label, and handles creator appeals.

- **Due:** Sunday, June 28, 2026 — 11:59 PM PDT
- **Grading:** 29 points (25 required + 4 stretch)
- **Stack:** Flask + Groq (`llama-3.3-70b-versatile`) + stylometric heuristics + Flask-Limiter + SQLite/JSON audit log
- **Time:** ~9–11 hours total

## Required features (must hit all 7)

1. Content submission endpoint — returns attribution + confidence + label text
2. Multi-signal pipeline — ≥2 *distinct* signals (semantic LLM + structural stylometry)
3. Confidence scoring with uncertainty — score not binary; 0.51 ≠ 0.95 label
4. Transparency label — 3 plain-language variants (high-conf AI, high-conf human, uncertain)
5. Appeals workflow — capture reasoning, log it, set status "under review"
6. Rate limiting — documented limits + reasoning
7. Audit log — structured, ≥3 visible entries via `GET /log`

---

## Milestone 0: Setup (~20 min)

- [ ] Create GitHub repo `ai201-project4-provenance-guard`, init with README
- [ ] Clone, create venv: `python -m venv .venv` then `.venv\Scripts\activate`
- [ ] Add `requirements.txt`:
  ```
  flask>=3.0.0
  flask-limiter>=3.5.0
  groq==0.15.0
  python-dotenv==1.0.1
  ```
- [ ] `pip install -r requirements.txt`
- [ ] Create `.env` with `GROQ_API_KEY=your_key_here`; add `.env` to `.gitignore` (NEVER commit)

---

## Milestone 1: Understand system + define architecture (~30 min)

No code yet. Make core design decisions.

- [ ] Read all 7 required features. Write architecture narrative in plain English: path one text takes from submission → label. Name every component.
- [ ] Pick 2 detection signals. For each write: what property it measures, why it differs human vs AI, what it *can't* capture (blind spot).
  - Signal 1: LLM (Groq) — semantic/stylistic coherence
  - Signal 2: Stylometric heuristics — sentence length variance, type-token ratio, punctuation density (pure Python)
- [ ] Trace the false-positive scenario: human work misclassified → how does confidence reflect it, what does label say, how does creator appeal? (False positive worse than false negative on writing platform.)
- [ ] Sketch API surface: endpoints, each accepts/returns what (the contract)
- [ ] Draw 2 flow diagrams (ASCII fine):
  - **Submission:** `POST /submit` → signal1 → signal2 → scoring → label → audit log → response
  - **Appeal:** `POST /appeal` → status update → audit log → response
  - Label each arrow with what passes (raw text, signal score, combined score, label text)

**Checkpoint:** Can describe full path naming every component. 2 signals chosen w/ blind spots. Endpoint list. Both flow diagrams done.

---

## Milestone 2: Write `planning.md` spec before any code (~1–2 hr)

This doc is your primary AI prompting tool for M3–M5. Vague spec → vague code.

- [ ] Create `planning.md` answering 5 questions with specific, implementation-ready answers:
  1. **Detection signals** — what are the 2+, what each measures, output shape (0–1 score? flag?), how combined into one confidence score
  2. **Uncertainty representation** — what does 0.6 mean? How map raw outputs → calibrated score? Thresholds: likely-AI / uncertain / likely-human
  3. **Transparency label design** — exact text for each of 3 variants, written now
  4. **Appeals workflow** — who appeals, what info, what happens on receipt (status change + what logged), what reviewer sees
  5. **Anticipated edge cases** — ≥2 *specific* failure scenarios (e.g. "poem heavy on repetition + simple vocab may score AI"), not generic risks
- [ ] Add `## Architecture` section — M1 diagram (ASCII) + 2–3 sentence narrative of both flows
- [ ] Add `## AI Tool Plan` section — for M3/M4/M5 each: which spec sections to feed AI, what to ask it to generate, how to verify
- [ ] Review label variants, revise if needed before building

**Checkpoint:** All 5 questions answered specifically. 3 label variants written. Scoring gives different labels at different ranges (not a 0.5 binary flip). Architecture + AI Tool Plan sections present.

---

## Milestone 3: Submission endpoint + first signal (~2–3 hr)

Get ONE signal working end-to-end before adding the second.

- [ ] Prompt AI with detection-signals section + diagram → generate Flask skeleton w/ `POST /submit` stub + first signal function. Review carefully, edit before using — check signature matches spec, route matches contract.
- [ ] Build Flask app. `POST /submit` accepts JSON with `text` + `creator_id`. Return hardcoded response first to verify route works.
- [ ] Implement first signal (Groq): function sends text to API, prompt returns structured assessment. Test standalone with a few inputs before wiring in.
- [ ] Wire signal into endpoint. Response must include: `content_id` (unique — appeal needs it), `attribution`, placeholder `confidence`, placeholder `label`. Test with curl:
  ```
  curl -s -X POST http://localhost:5000/submit \
    -H "Content-Type: application/json" \
    -d '{"text": "The sun dipped below the horizon...", "creator_id": "test-user-1"}'
  ```
- [ ] Set up audit log. Every submit writes structured entry (JSON or SQLite, NOT `print()`):
  ```json
  {
    "content_id": "3f7a2b1e-...",
    "creator_id": "test-user-1",
    "timestamp": "2025-04-01T14:32:10.123Z",
    "attribution": "likely_ai",
    "confidence": 0.78,
    "llm_score": 0.81,
    "status": "classified"
  }
  ```
- [ ] Add `GET /log` returning recent entries as JSON: `return jsonify({"entries": get_log()})`

**Checkpoint:** App runs. `POST /submit` returns JSON w/ `content_id`, attribution, placeholder confidence. Each submit writes structured log entry. `GET /log` returns them.

---

## Milestone 4: Second signal + confidence scoring (~2 hr)

Pipeline becomes multi-signal. Hard part: combining 2 signals → one calibrated score.

- [ ] Prompt AI with signals + uncertainty sections + diagram → generate second signal function + scoring logic. Verify generated thresholds actually match your spec (AI often silently diverges).
- [ ] Implement second signal (stylometry) standalone: compute 2–3 metrics (sentence length variance, type-token ratio), combine into one signal score. Test on signal-1 inputs — do they agree? Disagree where?
- [ ] Implement confidence scoring: combine both per spec. Must vary meaningfully across inputs + map to ≥3 label categories.
- [ ] Test with ≥4 deliberate inputs: clearly AI, clearly human, 2 borderline. Do scores match intuition? If not, print both signal scores separately to find the misbehaving one. (Starter test set in spec.)
- [ ] Update audit log to capture both individual signal scores + combined confidence.

**Checkpoint:** Both signals run, combine into one score. Clear-AI text scores noticeably different from clear-human. Log records individual + combined. ≥4 inputs tested across range.

---

## Milestone 5: Production layer (~2–3 hr)

4 features. Label + appeals depend on M4 scoring — verify that first.

- [ ] Prompt AI with label variants + appeals sections + diagram → generate label function + `POST /appeal`. Verify label produces all 3 variants matching your text; verify appeal updates status + logs.
- [ ] **Transparency label:** implement 3 variants. Label MUST change with confidence — not constant. Test all 3 reachable by varying inputs.
- [ ] **Appeals workflow:** `POST /appeal` accepts `content_id` + `creator_reasoning`. Update status → "under review", log appeal alongside original decision, return confirmation. No auto re-classification needed.
  ```
  curl -s -X POST http://localhost:5000/appeal \
    -H "Content-Type: application/json" \
    -d '{"content_id": "PASTE-ID", "creator_reasoning": "I wrote this myself"}'
  ```
  Verify via `GET /log`: entry shows `"status": "under_review"` + `appeal_reasoning` populated.
- [ ] **Rate limiting:** apply Flask-Limiter to `/submit`. Limits realistic (writer submitting own work) but block flooding. Document chosen limits + reasoning in README.
  ```python
  from flask_limiter import Limiter
  from flask_limiter.util import get_remote_address
  limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")
  ```
  ```python
  @app.route("/submit", methods=["POST"])
  @limiter.limit("10 per minute;100 per day")
  def submit(): ...
  ```
  Test: send 12 rapid requests → first 10 are `200`, rest `429`. Paste the 429 status output into README (evidence).
- [ ] **Complete audit log:** verify captures timestamp, content ID, attribution, confidence, both signal scores, appeal-filed flag. Structured format. ≥3 entries.

**Checkpoint:** All 4 production features work end-to-end, no workarounds. Label varies by confidence. Appeals reflected in log. Rate limit triggers. Log ≥3 structured entries covering submissions + ≥1 appeal.

---

## Milestone 6: Document + walkthrough (~1–2 hr)

README is the canonical graded record.

- [ ] Write README covering all required sections (explain *reasoning*, not just implementation):
  - **Architecture overview** — path submission → transparency label
  - **Detection signals** — what each measures, why chosen, what it misses
  - **Confidence scoring** — how combined, how validated as meaningful, **+ 2 example submissions with noticeably different scores** (actual numbers from M4)
  - **Transparency label** — typed text of all 3 variants verbatim (quoted string or table). Screenshot optional, written text REQUIRED.
  - **Rate limiting** — chosen limits + reasoning
  - **Known limitations** — ≥1 specific content type system misclassifies + why (tied to a signal property, not "needs more data")
  - **Spec reflection** — one way spec helped, one way implementation diverged + why
  - **AI usage** — ≥2 specific instances: what you directed AI to do, what it produced, what you revised/overrode
- [ ] Record short portfolio walkthrough video (~couple min): show system working end-to-end, talk through a few design decisions. Short + unpolished fine.

**Checkpoint:** README covers all sections w/ substantive design-decision explanations. 3 label variants written out. Walkthrough recorded.

---

## Submission (Course Portal)

- [ ] GitHub repo link
- [ ] `planning.md` in repo root (written before impl, updated before stretch)
- [ ] `README.md` with all sections above
- [ ] Portfolio walkthrough video

---

## Stretch features (+4 pts, optional)

Update `planning.md` before starting each; document in README (what built + how works).

- [ ] **Ensemble detection** — 3+ signals with documented weighting/voting
- [ ] **Provenance certificate** — "verified human" credential via extra verification step + how displayed
- [ ] **Analytics dashboard** — view of detection patterns, appeal rates, +1 metric
- [ ] **Multi-modal support** — second content type (image descriptions / structured metadata) alongside text

---

## Key design reminders

- **False positive (human work labeled AI) is worse than false negative.** Reflect this asymmetry in scoring + label design.
- Confidence score is a *design decision* before technical — decide what 0.5 means to a user first, then build to it.
- Label is a UX problem — show it to someone unfamiliar, ask what they understand.
- Perfect AI detection is unsolved — acknowledge uncertainty honestly, give creators an appeal path. That's the real engineering challenge.
