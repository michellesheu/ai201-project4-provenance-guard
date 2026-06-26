"""Structured audit log backed by SQLite.

Every attribution decision and every appeal is recorded here. This is the
canonical record graders inspect via GET /log.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "audit_log.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit (
                content_id        TEXT PRIMARY KEY,
                creator_id        TEXT,
                timestamp         TEXT,
                attribution       TEXT,
                confidence        REAL,
                llm_score         REAL,
                stylo_score       REAL,
                label             TEXT,
                status            TEXT,
                appeal_reasoning  TEXT,
                appeal_timestamp  TEXT
            )
            """
        )


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_decision(entry):
    """Insert a classification decision. `entry` is a dict."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO audit (content_id, creator_id, timestamp, attribution,
                               confidence, llm_score, stylo_score, label, status,
                               appeal_reasoning, appeal_timestamp)
            VALUES (:content_id, :creator_id, :timestamp, :attribution,
                    :confidence, :llm_score, :stylo_score, :label, :status,
                    NULL, NULL)
            """,
            entry,
        )


def file_appeal(content_id, reasoning):
    """Flip a decision to under_review and attach the creator's reasoning.

    Returns the updated row as a dict, or None if content_id is unknown.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM audit WHERE content_id = ?", (content_id,)
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            """
            UPDATE audit
               SET status = 'under_review',
                   appeal_reasoning = ?,
                   appeal_timestamp = ?
             WHERE content_id = ?
            """,
            (reasoning, now_iso(), content_id),
        )
        updated = conn.execute(
            "SELECT * FROM audit WHERE content_id = ?", (content_id,)
        ).fetchone()
        return dict(updated)


def recent(limit=50):
    """Most recent audit entries, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print(json.dumps(recent(), indent=2))
