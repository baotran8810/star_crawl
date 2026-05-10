"""Integration test: pipeline end-to-end with mocked HTTP."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
import respx

from star_crawl.core import pipeline
from star_crawl.core.schemas import SourceConfig
from star_crawl.db import migrate as db_migrate

FIXTURES = Path(__file__).parent.parent / "fixtures"

GRAB_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Grab Eng</title>
<link>https://engineering.grab.com</link>
<item>
  <title>Building a real-time event pipeline</title>
  <link>https://engineering.grab.com/sample-article</link>
</item>
</channel></rss>
"""


def _grab_config() -> SourceConfig:
    return SourceConfig(
        name="grab_engineering",
        display_name="Grab Engineering",
        base_url="https://engineering.grab.com",
        fetcher="http",
        seed={
            "strategy": "rss",
            "url": "https://engineering.grab.com/feed.xml",
        },
        url_filter=r"^https://engineering\.grab\.com/[^/]+/?$",
        rate_limit={"rps": 100.0, "concurrency": 5},
        policy={"respect_robots": False},  # bypass robots in tests
    )


@pytest.mark.integration
def test_pipeline_extracts_and_persists(tmp_path: Path):
    """End-to-end: RSS → fetch → extract → SQLite."""
    db_migrate.migrate(tmp_path)

    article_html = (FIXTURES / "grab" / "sample_article.html").read_text(encoding="utf-8")

    async def _go():
        with respx.mock(assert_all_called=False) as router:
            router.get("https://engineering.grab.com/feed.xml").mock(
                return_value=httpx.Response(200, text=GRAB_RSS)
            )
            router.get("https://engineering.grab.com/sample-article").mock(
                return_value=httpx.Response(200, text=article_html)
            )

            return await pipeline.run_source(_grab_config(), data_dir=tmp_path)

    result = asyncio.run(_go())

    assert result.status == "success", result
    assert result.discovered == 1
    assert result.extracted_new == 1
    assert result.error_count == 0

    # verify DB state
    from star_crawl.db.connection import connect

    conn = connect(tmp_path)
    try:
        rows = conn.execute("SELECT * FROM articles").fetchall()
        assert len(rows) == 1
        a = rows[0]
        assert a["source_name"] == "grab_engineering"
        assert "real-time" in a["title"].lower()
        assert a["word_count"] >= 100
    finally:
        conn.close()


@pytest.mark.integration
def test_pipeline_dedup_on_rerun(tmp_path: Path):
    """Re-running same source against same content → zero new articles."""
    db_migrate.migrate(tmp_path)
    article_html = (FIXTURES / "grab" / "sample_article.html").read_text(encoding="utf-8")
    cfg = _grab_config()

    async def _go():
        with respx.mock(assert_all_called=False) as router:
            router.get("https://engineering.grab.com/feed.xml").mock(
                return_value=httpx.Response(200, text=GRAB_RSS)
            )
            router.get("https://engineering.grab.com/sample-article").mock(
                return_value=httpx.Response(200, text=article_html)
            )
            r1 = await pipeline.run_source(cfg, data_dir=tmp_path)
            r2 = await pipeline.run_source(cfg, data_dir=tmp_path)
            return r1, r2

    r1, r2 = asyncio.run(_go())
    assert r1.extracted_new == 1
    assert r2.extracted_new == 0
    assert r2.extracted_dup == 1
