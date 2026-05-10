"""Apply pending SQL migrations from src/star_crawl/migrations/."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from star_crawl.db.connection import connect


def _migrations_dir() -> Path:
    return Path(__file__).parent.parent / "migrations"


def _list_migrations() -> list[tuple[int, Path]]:
    out: list[tuple[int, Path]] = []
    for path in sorted(_migrations_dir().glob("*.sql")):
        try:
            version = int(path.name.split("_", 1)[0])
        except ValueError:
            continue
        out.append((version, path))
    return out


def applied_versions(conn: sqlite3.Connection) -> set[int]:
    try:
        rows = conn.execute("SELECT version FROM _schema_version").fetchall()
        return {r["version"] for r in rows}
    except sqlite3.Error:
        return set()


def migrate(data_dir: Path | None = None) -> list[int]:
    """Apply pending migrations. Idempotent. Returns list of versions applied."""
    applied: list[int] = []
    conn = connect(data_dir)
    try:
        conn.executescript(
            "CREATE TABLE IF NOT EXISTS _schema_version "
            "(version INTEGER PRIMARY KEY, "
            "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);"
        )
        conn.commit()

        existing = applied_versions(conn)
        for version, path in _list_migrations():
            if version in existing:
                continue
            sql = path.read_text(encoding="utf-8")
            conn.executescript(sql)
            conn.execute("INSERT INTO _schema_version(version) VALUES (?)", (version,))
            conn.commit()
            applied.append(version)
    finally:
        conn.close()

    return applied


def pending_count(data_dir: Path | None = None) -> int:
    conn = connect(data_dir)
    try:
        existing = applied_versions(conn)
    finally:
        conn.close()
    return len([v for v, _ in _list_migrations() if v not in existing])
