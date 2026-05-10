"""Migration idempotency tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from star_crawl.db import migrate as db_migrate
from star_crawl.db.connection import connect


@pytest.mark.unit
def test_migrate_applies_all(tmp_path: Path):
    applied = db_migrate.migrate(tmp_path)
    assert applied  # at least one migration ran
    assert all(isinstance(v, int) for v in applied)


@pytest.mark.unit
def test_migrate_is_idempotent(tmp_path: Path):
    db_migrate.migrate(tmp_path)
    second = db_migrate.migrate(tmp_path)
    assert second == []  # second pass applies nothing


@pytest.mark.unit
def test_pending_count_zero_after_migrate(tmp_path: Path):
    db_migrate.migrate(tmp_path)
    assert db_migrate.pending_count(tmp_path) == 0


@pytest.mark.unit
def test_articles_table_exists_after_migrate(tmp_path: Path):
    db_migrate.migrate(tmp_path)
    conn = connect(tmp_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='articles'"
        ).fetchall()
        assert len(rows) == 1
    finally:
        conn.close()


@pytest.mark.unit
def test_fts5_table_exists_after_migrate(tmp_path: Path):
    db_migrate.migrate(tmp_path)
    conn = connect(tmp_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE name='articles_fts'"
        ).fetchall()
        assert len(rows) == 1
    finally:
        conn.close()


@pytest.mark.unit
def test_wal_mode_enabled(tmp_path: Path):
    db_migrate.migrate(tmp_path)
    conn = connect(tmp_path)
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        conn.close()
