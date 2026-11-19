"""SQLite storage for runs and per-prompt results."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    brand TEXT NOT NULL,
    engine TEXT NOT NULL,
    model TEXT NOT NULL,
    mode TEXT NOT NULL,          -- 'live' or 'sample'
    prompt_count INTEGER NOT NULL,
    mention_count INTEGER NOT NULL,
    mention_rate REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    prompt TEXT NOT NULL,
    mentioned INTEGER NOT NULL,
    variant TEXT,
    char_index INTEGER,
    position_pct REAL,
    list_rank INTEGER,
    snippet TEXT,
    sentiment TEXT,
    answer_chars INTEGER NOT NULL,
    answer TEXT NOT NULL
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def save_run(conn: sqlite3.Connection, brand: str, engine: str, model: str,
             mode: str, results: list[dict]) -> int:
    """Save one run and its results. Returns the run id."""
    mentioned = sum(1 for r in results if r["mentioned"])
    rate = round(100.0 * mentioned / len(results), 1) if results else 0.0
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO runs (started_at, brand, engine, model, mode,"
        " prompt_count, mention_count, mention_rate)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (started, brand, engine, model, mode, len(results), mentioned, rate))
    run_id = cur.lastrowid
    for r in results:
        conn.execute(
            "INSERT INTO results (run_id, prompt, mentioned, variant,"
            " char_index, position_pct, list_rank, snippet, sentiment,"
            " answer_chars, answer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, r["prompt"], 1 if r["mentioned"] else 0, r["variant"],
             r["char_index"], r["position_pct"], r["list_rank"], r["snippet"],
             r["sentiment"], r["answer_chars"], r["answer"]))
    conn.commit()
    return run_id


def list_runs(conn: sqlite3.Connection, brand: str | None = None,
              limit: int = 50) -> list[dict]:
    if brand:
        rows = conn.execute(
            "SELECT * FROM runs WHERE brand = ? ORDER BY id DESC LIMIT ?",
            (brand, limit))
    else:
        rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?",
                            (limit,))
    return [dict(r) for r in rows]


def run_history(conn: sqlite3.Connection, brand: str) -> list[dict]:
    """Per-prompt mention history for a brand (oldest first)."""
    rows = conn.execute(
        "SELECT r.started_at, r.mode, res.prompt, res.mentioned"
        " FROM results res JOIN runs r ON r.id = res.run_id"
        " WHERE r.brand = ? ORDER BY r.id ASC", (brand,))
    return [dict(r) for r in rows]


def results_for_run(conn: sqlite3.Connection, run_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM results WHERE run_id = ? ORDER BY id ASC", (run_id,))
    return [dict(r) for r in rows]


def export_json(conn: sqlite3.Connection, brand: str) -> str:
    """All runs + results for a brand as a JSON string (for debugging)."""
    runs = list_runs(conn, brand, limit=1000)
    for run in runs:
        run["results"] = results_for_run(conn, run["id"])
    return json.dumps(runs, indent=2, ensure_ascii=False)
