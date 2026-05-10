"""Frontier state machine + resume tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from star_crawl.core import frontier
from star_crawl.db import migrate as db_migrate
from star_crawl.db.connection import connect


def _setup_run(tmp_path: Path) -> int:
    """Create a source + crawl_run row and return the run_id."""
    db_migrate.migrate(tmp_path)
    conn = connect(tmp_path)
    try:
        conn.execute(
            """INSERT INTO sources (name, display_name, base_url, fetcher,
                                    seed_strategy, config_json)
               VALUES ('grab', 'Grab', 'https://example.com', 'http', 'rss', '{}')"""
        )
        cur = conn.execute(
            """INSERT INTO crawl_runs (source_name, started_at, status, config_hash)
               VALUES ('grab', '2026-05-10', 'running', 'h1')"""
        )
        run_id = cur.lastrowid
        conn.commit()
        return int(run_id)
    finally:
        conn.close()


@pytest.mark.unit
def test_enqueue_and_claim(tmp_path: Path):
    run_id = _setup_run(tmp_path)
    conn = connect(tmp_path)
    try:
        for i in range(3):
            assert frontier.enqueue(conn, run_id, "grab", f"https://e.com/{i}")
        conn.commit()

        first = frontier.claim_next(conn, run_id)
        assert first is not None
        fid, url = first
        assert "/0" in url
        # Claiming again skips the in_progress one
        second = frontier.claim_next(conn, run_id)
        assert second is not None
        assert "/1" in second[1]
    finally:
        conn.close()


@pytest.mark.unit
def test_mark_done_and_failed(tmp_path: Path):
    run_id = _setup_run(tmp_path)
    conn = connect(tmp_path)
    try:
        frontier.enqueue(conn, run_id, "grab", "https://e.com/a")
        frontier.enqueue(conn, run_id, "grab", "https://e.com/b")
        conn.commit()

        a = frontier.claim_next(conn, run_id)
        b = frontier.claim_next(conn, run_id)
        assert a and b
        frontier.mark_done(conn, a[0])
        frontier.mark_failed(conn, b[0], "boom")
        conn.commit()

        assert frontier.pending_count(conn, run_id) == 0
        # Both terminal — claim returns None
        assert frontier.claim_next(conn, run_id) is None
    finally:
        conn.close()


@pytest.mark.unit
def test_reset_in_progress_resume(tmp_path: Path):
    run_id = _setup_run(tmp_path)
    conn = connect(tmp_path)
    try:
        for i in range(5):
            frontier.enqueue(conn, run_id, "grab", f"https://e.com/{i}")
        # Claim 2 (simulate mid-run kill)
        frontier.claim_next(conn, run_id)
        frontier.claim_next(conn, run_id)
        conn.commit()

        # On resume:
        moved = frontier.reset_in_progress(conn, run_id)
        assert moved == 2
        # All 5 should now be pending again
        assert frontier.pending_count(conn, run_id) == 5
    finally:
        conn.close()


@pytest.mark.unit
def test_find_resumable_run(tmp_path: Path):
    run_id = _setup_run(tmp_path)
    conn = connect(tmp_path)
    try:
        assert frontier.find_resumable_run(conn, "grab") == run_id
        assert frontier.find_resumable_run(conn, "no-such-source") is None

        # finishing the run removes resumability
        conn.execute(
            "UPDATE crawl_runs SET status = 'success' WHERE id = ?", (run_id,)
        )
        conn.commit()
        assert frontier.find_resumable_run(conn, "grab") is None
    finally:
        conn.close()


@pytest.mark.unit
def test_url_already_known(tmp_path: Path):
    db_migrate.migrate(tmp_path)
    conn = connect(tmp_path)
    try:
        conn.execute(
            """INSERT INTO sources (name, display_name, base_url, fetcher,
                                    seed_strategy, config_json)
               VALUES ('grab', 'Grab', 'https://e.com', 'http', 'rss', '{}')"""
        )
        conn.execute(
            """INSERT INTO articles (source_name, url, title, content_text, content_md,
                                     word_count, content_hash)
               VALUES ('grab', 'https://e.com/a', 't', 'body', 'body', 1, 'h1')"""
        )
        conn.commit()
        assert frontier.url_already_known(conn, "grab", "https://e.com/a")
        assert not frontier.url_already_known(conn, "grab", "https://e.com/b")
    finally:
        conn.close()
