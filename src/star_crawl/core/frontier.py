"""SQLite-backed frontier — URL queue with persistent state for resume."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

PENDING = "pending"
IN_PROGRESS = "in_progress"
DONE = "done"
FAILED = "failed"
SKIPPED = "skipped"


def enqueue(
    conn: sqlite3.Connection,
    run_id: int,
    source_name: str,
    url: str,
) -> bool:
    """Insert URL into frontier as pending. Returns True if newly enqueued."""
    try:
        conn.execute(
            """INSERT INTO frontier (run_id, source_name, url, state)
               VALUES (?, ?, ?, ?)""",
            (run_id, source_name, url, PENDING),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def claim_next(conn: sqlite3.Connection, run_id: int) -> tuple[int, str] | None:
    """Atomically claim the next pending URL: pending → in_progress.

    Returns (frontier_id, url) or None when no pending URLs remain.
    """
    row = conn.execute(
        """SELECT id, url FROM frontier
            WHERE run_id = ? AND state = ?
            ORDER BY id LIMIT 1""",
        (run_id, PENDING),
    ).fetchone()
    if row is None:
        return None
    fid = row["id"] if isinstance(row, sqlite3.Row) else row[0]
    url = row["url"] if isinstance(row, sqlite3.Row) else row[1]
    conn.execute(
        "UPDATE frontier SET state = ?, attempts = attempts + 1 WHERE id = ?",
        (IN_PROGRESS, fid),
    )
    return int(fid), str(url)


def mark_done(conn: sqlite3.Connection, frontier_id: int) -> None:
    conn.execute(
        "UPDATE frontier SET state = ?, completed_at = ? WHERE id = ?",
        (DONE, datetime.now(timezone.utc).isoformat(), frontier_id),
    )


def mark_failed(conn: sqlite3.Connection, frontier_id: int, error: str) -> None:
    conn.execute(
        """UPDATE frontier SET state = ?, completed_at = ?, last_error = ?
            WHERE id = ?""",
        (FAILED, datetime.now(timezone.utc).isoformat(), error[:1000], frontier_id),
    )


def mark_skipped(conn: sqlite3.Connection, frontier_id: int, reason: str) -> None:
    conn.execute(
        """UPDATE frontier SET state = ?, completed_at = ?, last_error = ?
            WHERE id = ?""",
        (SKIPPED, datetime.now(timezone.utc).isoformat(), reason[:1000], frontier_id),
    )


def reset_in_progress(conn: sqlite3.Connection, run_id: int) -> int:
    """Move any in_progress URLs back to pending (called on resume).

    Returns the count of rows moved.
    """
    cur = conn.execute(
        "UPDATE frontier SET state = ? WHERE run_id = ? AND state = ?",
        (PENDING, run_id, IN_PROGRESS),
    )
    return cur.rowcount


def pending_count(conn: sqlite3.Connection, run_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM frontier WHERE run_id = ? AND state = ?",
        (run_id, PENDING),
    ).fetchone()
    return int(row[0])


def find_resumable_run(
    conn: sqlite3.Connection, source_name: str
) -> int | None:
    """Find an unfinished run for this source (status='running')."""
    row = conn.execute(
        """SELECT id FROM crawl_runs
            WHERE source_name = ? AND status = 'running'
            ORDER BY started_at DESC LIMIT 1""",
        (source_name,),
    ).fetchone()
    if row is None:
        return None
    return int(row[0] if not isinstance(row, sqlite3.Row) else row["id"])


def url_already_known(conn: sqlite3.Connection, source_name: str, url: str) -> bool:
    """Check if this URL has already been successfully ingested for this source."""
    row = conn.execute(
        "SELECT 1 FROM articles WHERE source_name = ? AND url = ? LIMIT 1",
        (source_name, url),
    ).fetchone()
    return row is not None
