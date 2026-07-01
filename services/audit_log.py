import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "audit.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_entries (
                content_id TEXT PRIMARY KEY,
                creator_id TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                attribution TEXT NOT NULL,
                confidence REAL NOT NULL,
                llm_score REAL NOT NULL,
                stylometric_score REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'classified',
                appeal_reasoning TEXT,
                appeal_timestamp TEXT
            )
            """
        )


def log_submission(
    content_id: str,
    creator_id: str,
    text: str,
    attribution: str,
    confidence: float,
    llm_score: float,
    stylometric_score: float,
) -> dict:
    entry = {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attribution": attribution,
        "confidence": confidence,
        "llm_score": llm_score,
        "stylometric_score": stylometric_score,
        "status": "classified",
    }
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_entries
                (content_id, creator_id, text, timestamp, attribution,
                 confidence, llm_score, stylometric_score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                content_id,
                creator_id,
                text,
                entry["timestamp"],
                attribution,
                confidence,
                llm_score,
                stylometric_score,
                "classified",
            ),
        )
    return entry


def log_appeal(content_id: str, creator_reasoning: str) -> dict | None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM audit_entries WHERE content_id = ?", (content_id,)
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            """
            UPDATE audit_entries
            SET status = 'under_review',
                appeal_reasoning = ?,
                appeal_timestamp = ?
            WHERE content_id = ?
            """,
            (creator_reasoning, now, content_id),
        )
        updated = conn.execute(
            "SELECT * FROM audit_entries WHERE content_id = ?", (content_id,)
        ).fetchone()
    return _row_to_dict(updated)


def get_log(limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_entries ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    entry = {
        "content_id": row["content_id"],
        "creator_id": row["creator_id"],
        "timestamp": row["timestamp"],
        "attribution": row["attribution"],
        "confidence": row["confidence"],
        "llm_score": row["llm_score"],
        "stylometric_score": row["stylometric_score"],
        "status": row["status"],
    }
    if row["appeal_reasoning"]:
        entry["appeal_reasoning"] = row["appeal_reasoning"]
        entry["appeal_timestamp"] = row["appeal_timestamp"]
    return entry
