"""Provenance Guard — Flask API.

M3: POST /submit (first signal only, placeholder confidence/label) + GET /log.
Scoring, second signal, label, appeals, and rate limiting are added in later
milestones.
"""
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import audit
import scoring
from signals import llm_signal, stylometry_signal

load_dotenv()

app = Flask(__name__)
audit.init_db()

# Rate limiting. Limits reflect realistic single-creator use (a writer
# submitting their own work) while blocking a script flooding the endpoint.
# See README for the reasoning behind these specific numbers.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    creator_id = data.get("creator_id") or "anonymous"
    if not text:
        return jsonify({"error": "field 'text' is required"}), 400

    content_id = str(uuid.uuid4())
    llm_score = llm_signal(text)
    stylo_score = stylometry_signal(text)

    ai_score, attribution, confidence = scoring.combine(llm_score, stylo_score)
    label = scoring.label_for(attribution, confidence)

    audit.write_decision(
        {
            "content_id": content_id,
            "creator_id": creator_id,
            "timestamp": audit.now_iso(),
            "attribution": attribution,
            "confidence": confidence,
            "llm_score": round(llm_score, 3),
            "stylo_score": round(stylo_score, 3),
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
            "signals": {
                "llm_score": round(llm_score, 3),
                "stylo_score": round(stylo_score, 3),
                "ai_score": ai_score,
            },
        }
    )


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True) or {}
    content_id = data.get("content_id")
    reasoning = (data.get("creator_reasoning") or "").strip()
    if not content_id or not reasoning:
        return jsonify(
            {"error": "fields 'content_id' and 'creator_reasoning' are required"}
        ), 400

    updated = audit.file_appeal(content_id, reasoning)
    if updated is None:
        return jsonify({"error": f"no submission found for content_id {content_id}"}), 404

    return jsonify(
        {
            "content_id": content_id,
            "status": updated["status"],
            "message": "Appeal received. This submission is now under review.",
        }
    )


@app.route("/log", methods=["GET"])
def get_log():
    return jsonify({"entries": audit.recent()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
