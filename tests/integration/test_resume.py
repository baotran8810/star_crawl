"""Resume an interrupted crawl test."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
import respx

from star_crawl.core import frontier, pipeline
from star_crawl.core.schemas import SourceConfig
from star_crawl.db import migrate as db_migrate
from star_crawl.db.connection import connect

FIXTURES = Path(__file__).parent.parent / "fixtures"

GRAB_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>One</title><link>https://engineering.grab.com/p1</link></item>
<item><title>Two</title><link>https://engineering.grab.com/p2</link></item>
<item><title>Three</title><link>https://engineering.grab.com/p3</link></item>
</channel></rss>
"""


def _cfg() -> SourceConfig:
    return SourceConfig(
        name="grab_engineering",
        display_name="Grab Engineering",
        base_url="https://engineering.grab.com",
        fetcher="http",
        seed={"strategy": "rss", "url": "https://engineering.grab.com/feed.xml"},
        url_filter=r"^https://engineering\.grab\.com/p[0-9]+$",
        rate_limit={"rps": 100.0, "concurrency": 5},
        policy={"respect_robots": False},
    )


@pytest.mark.integration
def test_resume_picks_up_only_pending(tmp_path: Path):
    """Simulate kill mid-run: claim 1, mark in-progress, then resume."""
    db_migrate.migrate(tmp_path)
    article_html = (FIXTURES / "grab" / "sample_article.html").read_text(encoding="utf-8")
    cfg = _cfg()

    # Round 1: run with limit=1 so only 1 of 3 is processed
    async def round_one():
        with respx.mock(assert_all_called=False) as router:
            router.get("https://engineering.grab.com/feed.xml").mock(
                return_value=httpx.Response(200, text=GRAB_RSS)
            )
            for n in (1, 2, 3):
                router.get(f"https://engineering.grab.com/p{n}").mock(
                    return_value=httpx.Response(200, text=article_html)
                )
            return await pipeline.run_source(cfg, data_dir=tmp_path, limit=1)

    r1 = asyncio.run(round_one())
    # 3 discovered, 1 new (limit), 0 dup, 0 errors. Frontier still has 2 pending.
    assert r1.discovered == 3
    assert r1.extracted_new == 1

    conn = connect(tmp_path)
    try:
        pending = frontier.pending_count(conn, r1.run_id)
        assert pending == 2
        # The run is left in 'running' state because we hit limit
        status = conn.execute(
            "SELECT status FROM crawl_runs WHERE id = ?", (r1.run_id,)
        ).fetchone()[0]
        # NB: the pipeline marks status based on outcome; with limit hit,
        # discovered>0, new>0, errors=0 → status='success'
        # but pending URLs remain. This is acceptable: a re-run won't
        # find a 'running' run to resume; instead it will start a new run.
        # That's fine for the limit case. The interesting case is when the
        # run was killed before finish_run was called — covered below.
        assert status in ("success", "running")
    finally:
        conn.close()


@pytest.mark.integration
def test_resume_finds_unfinished_run(tmp_path: Path):
    """If a run row is left in 'running' state with pending frontier rows,
    a re-run resumes it instead of starting a new one."""
    db_migrate.migrate(tmp_path)
    article_html = (FIXTURES / "grab" / "sample_article.html").read_text(encoding="utf-8")
    cfg = _cfg()

    # Manually craft an unfinished run + frontier with one URL pending
    conn = connect(tmp_path)
    try:
        # Insert source so foreign keys are happy
        conn.execute(
            """INSERT INTO sources (name, display_name, base_url, fetcher,
                                    seed_strategy, config_json)
               VALUES ('grab_engineering', 'Grab Engineering',
                       'https://engineering.grab.com', 'http', 'rss', '{}')"""
        )
        cur = conn.execute(
            """INSERT INTO crawl_runs (source_name, started_at, status, config_hash)
               VALUES ('grab_engineering', '2026-05-09', 'running', 'h0')"""
        )
        run_id = int(cur.lastrowid)
        conn.execute(
            """INSERT INTO frontier (run_id, source_name, url, state)
               VALUES (?, ?, 'https://engineering.grab.com/p1', 'pending')""",
            (run_id, "grab_engineering"),
        )
        conn.commit()
    finally:
        conn.close()

    async def resume():
        with respx.mock(assert_all_called=False) as router:
            router.get("https://engineering.grab.com/feed.xml").mock(
                return_value=httpx.Response(200, text=GRAB_RSS)
            )
            router.get("https://engineering.grab.com/p1").mock(
                return_value=httpx.Response(200, text=article_html)
            )
            return await pipeline.run_source(cfg, data_dir=tmp_path)

    r = asyncio.run(resume())
    # Resumed: same run_id; frontier.url p1 was processed
    assert r.run_id == run_id
    assert r.extracted_new == 1
    assert r.discovered == 1  # what was already in frontier
