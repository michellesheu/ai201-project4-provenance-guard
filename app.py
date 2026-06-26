"""Provenance Guard — Flask API.

M3: POST /submit (first signal only, placeholder confidence/label) + GET /log.
Scoring, second signal, label, appeals, and rate limiting are added in later
milestones.
"""
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request

import audit
from signals import llm_signal

load_dotenv()

app = Flask(__name__)
audit.init_db()


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    creator_id = data.get("creator_id") or "anonymous"
    if not text:
        return jsonify({"error": "field 'text' is required"}), 400

    content_id = str(uuid.uuid4())
    llm_score = llm_signal(text)

    # Placeholder until M4 scoring lands.
    attribution = "likely_ai" if llm_score >= 0.5 else "likely_human"
    confidence = 0.5
    label = "Classification pending — scoring not yet implemented."

    audit.write_decision(
        {
            "content_id": content_id,
            "creator_id": creator_id,
            "timestamp": audit.now_iso(),
            "attribution": attribution,
            "confidence": confidence,
            "llm_score": llm_score,
            "stylo_score": None,
            "label": label,
            "status": "classified",
        }
    )

    return jsonify(
        {
            "content_id": content_id,
            "attribution": attribution,
            "confidence": confidence,
            "label": label,
            "signals": {"llm_score": round(llm_score, 3)},
        }
    )


@app.route("/log", methods=["GET"])
def get_log():
    return jsonify({"entries": audit.recent()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
