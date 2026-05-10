"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from star_crawl.db import migrate as db_migrate
from star_crawl.db.connection import connect


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """A temp data dir with an initialized schema."""
    db_migrate.migrate(tmp_path)
    return tmp_path


@pytest.fixture
def tmp_conn(tmp_data_dir: Path):
    """A SQLite connection on a fresh, migrated DB."""
    conn = connect(tmp_data_dir)
    yield conn
    conn.close()
