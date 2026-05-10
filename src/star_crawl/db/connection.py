"""SQLite connection helpers — WAL mode primary, read-only secondary.

The primary writer is the crawler. The web UI reads via `mode=ro` URI.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DATA_DIR = Path("data")
DB_FILE = "articles.db"


def db_path(data_dir: Path | None = None) -> Path:
    return (data_dir or DEFAULT_DATA_DIR) / DB_FILE


def connect(
    data_dir: Path | None = None,
    *,
    read_only: bool = False,
    timeout: float = 30.0,
) -> sqlite3.Connection:
    """Open a SQLite connection, applying WAL pragma on writers."""
    path = db_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    if read_only:
        uri = f"file:{path}?mode=ro&immutable=0"
        conn = sqlite3.connect(uri, uri=True, timeout=timeout)
    else:
        conn = sqlite3.connect(path, timeout=timeout)
        conn.executescript(
            """
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous = NORMAL;
            PRAGMA foreign_keys = ON;
            """
        )

    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_conn(
    data_dir: Path | None = None,
    *,
    read_only: bool = False,
) -> Iterator[sqlite3.Connection]:
    conn = connect(data_dir, read_only=read_only)
    try:
        yield conn
        if not read_only:
            conn.commit()
    except Exception:
        if not read_only:
            conn.rollback()
        raise
    finally:
        conn.close()
