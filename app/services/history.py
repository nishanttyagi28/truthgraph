"""Optional SQLite verification history (disabled by default)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import HISTORY_DB_PATH, HISTORY_ENABLED
from app.models.results import VerificationResult


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    path = Path(db_path or HISTORY_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | None = None) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                claim TEXT NOT NULL,
                verdict TEXT NOT NULL,
                confidence REAL NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.commit()


def record_verification(
    result: VerificationResult,
    *,
    db_path: str | None = None,
    enabled: bool | None = None,
) -> int | None:
    """Persist a verification dossier when history is enabled. Returns row id."""
    if not (HISTORY_ENABLED if enabled is None else enabled):
        return None

    init_db(db_path)
    created_at = datetime.now(timezone.utc).isoformat()
    payload = result.model_dump_json()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO verification_history
                (created_at, claim, verdict, confidence, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (created_at, result.claim, result.verdict, result.confidence, payload),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_history(
    limit: int = 20,
    *,
    db_path: str | None = None,
    enabled: bool | None = None,
) -> list[dict]:
    if not (HISTORY_ENABLED if enabled is None else enabled):
        return []

    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, claim, verdict, confidence, payload_json
            FROM verification_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    out: list[dict] = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        out.append(item)
    return out
