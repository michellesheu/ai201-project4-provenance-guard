# Provenance Guard

A backend system for creative-sharing platforms that classifies submitted text as AI-generated or human-written, scores confidence with honest uncertainty, surfaces a plain-language transparency label, and lets creators appeal a classification.

Full README (architecture, signals, scoring, label variants, rate limits, limitations) is written in Milestone 6. See `planning.md` for the design spec.

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env            # then add your GROQ_API_KEY
python app.py
```

Server runs on `http://localhost:5000`.
