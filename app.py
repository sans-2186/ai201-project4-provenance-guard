import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from services.audit_log import get_log, init_db, log_appeal, log_submission
from services.labels import generate_label
from services.scoring import classify_attribution, combine_scores
from signals.llm_signal import get_llm_score
from signals.stylometric import get_stylometric_score

load_dotenv()

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

init_db()


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json(silent=True)
    if not data or "text" not in data or "creator_id" not in data:
        return jsonify({"error": "Missing required fields: text, creator_id"}), 400

    text = data["text"].strip()
    creator_id = data["creator_id"]
    if not text:
        return jsonify({"error": "text cannot be empty"}), 400

    content_id = str(uuid.uuid4())
    llm_score = get_llm_score(text)
    stylometric_score = get_stylometric_score(text)
    confidence = combine_scores(llm_score, stylometric_score)
    attribution = classify_attribution(confidence)
    label = generate_label(confidence)

    log_submission(
        content_id=content_id,
        creator_id=creator_id,
        text=text,
        attribution=attribution,
        confidence=confidence,
        llm_score=llm_score,
        stylometric_score=stylometric_score,
    )

    return jsonify(
        {
            "content_id": content_id,
            "attribution": attribution,
            "confidence": confidence,
            "label": label,
            "llm_score": llm_score,
            "stylometric_score": stylometric_score,
        }
    )


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True)
    if not data or "content_id" not in data or "creator_reasoning" not in data:
        return jsonify({"error": "Missing required fields: content_id, creator_reasoning"}), 400

    content_id = data["content_id"]
    creator_reasoning = data["creator_reasoning"].strip()
    if not creator_reasoning:
        return jsonify({"error": "creator_reasoning cannot be empty"}), 400

    result = log_appeal(content_id, creator_reasoning)
    if result is None:
        return jsonify({"error": f"No submission found for content_id: {content_id}"}), 404

    return jsonify(
        {
            "content_id": content_id,
            "status": "under_review",
            "message": "Appeal received and queued for review.",
        }
    )


@app.route("/log", methods=["GET"])
def audit_log():
    return jsonify({"entries": get_log()})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
