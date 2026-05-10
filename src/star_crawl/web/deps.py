"""FastAPI dependencies: read-only DB connection, settings."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from star_crawl.db.connection import connect


def data_dir() -> Path:
    return Path(os.environ.get("STAR_CRAWL_DATA_DIR", "data"))


def get_conn() -> Iterator[sqlite3.Connection]:
    """Yield a read-only SQLite connection, close when done."""
    conn = connect(data_dir(), read_only=True)
    try:
        yield conn
    finally:
        conn.close()


def is_htmx_request(request) -> bool:
    return request.headers.get("HX-Request", "").lower() == "true"
