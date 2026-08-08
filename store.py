"""SQLite persistence for tracked job listings."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = "jobs.db"


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT,
                status TEXT NOT NULL DEFAULT 'waiting',
                apply_url TEXT,
                added_at TEXT NOT NULL,
                last_checked_at TEXT,
                found_at TEXT,
                last_error TEXT
            )
            """
        )


def add_job(url: str) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO jobs (url, status, added_at) VALUES (?, 'waiting', ?)",
            (url, datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def delete_job(job_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))


def list_jobs() -> list[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute("SELECT * FROM jobs ORDER BY added_at DESC").fetchall()


def get_job(job_id: int) -> sqlite3.Row | None:
    with _conn() as conn:
        return conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()


def waiting_jobs() -> list[sqlite3.Row]:
    with _conn() as conn:
        return conn.execute("SELECT * FROM jobs WHERE status = 'waiting'").fetchall()


def mark_checked(job_id: int, title: str | None, error: str | None) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE jobs SET last_checked_at = ?, title = COALESCE(?, title), last_error = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), title, error, job_id),
        )


def mark_found(job_id: int, apply_url: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE jobs SET status = 'found', apply_url = ?, found_at = ? WHERE id = ?",
            (apply_url, datetime.now(timezone.utc).isoformat(), job_id),
        )
