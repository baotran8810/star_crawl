"""Source + time filter tests for the graph view (US3)."""

from __future__ import annotations

from importlib import reload
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from star_crawl.db import migrate as db_migrate
from star_crawl.db.connection import connect
from star_crawl.graph.builder import build_graph
from star_crawl.graph.extract import update_doc_freq


def _seed_two_sources(tmp_path: Path) -> None:
    """Two sources, each contributing distinct keyword clusters.

    grab_engineering: kafka/stream/queue (5 articles each)
    uber_engineering: postgres/replica/vacuum (5 articles each)
    """
    db_migrate.migrate(tmp_path)
    conn = connect(tmp_path)
    try:
        for name in ("grab_engineering", "uber_engineering"):
            conn.execute(
                "INSERT INTO sources (name, display_name, base_url, fetcher, "
                "seed_strategy, config_json) VALUES "
                "(?, ?, ?, 'http', 'rss', '{}')",
                (name, name.replace("_", " ").title(), f"https://{name}.com"),
            )

        article_id = 1
        # Grab articles published 2026-03-01..05
        for i in range(5):
            conn.execute(
                "INSERT INTO articles (source_name, url, title, content_text, "
                "content_md, word_count, content_hash, published_at) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?)",
                ("grab_engineering", f"https://grab.com/{i}",
                 f"Grab {i}", "body", "body", 100, f"hg_{i}",
                 f"2026-03-0{i+1}T00:00:00Z"),
            )
        # Uber articles published 2026-04-01..05
        for i in range(5):
            conn.execute(
                "INSERT INTO articles (source_name, url, title, content_text, "
                "content_md, word_count, content_hash, published_at) VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?)",
                ("uber_engineering", f"https://uber.com/{i}",
                 f"Uber {i}", "body", "body", 100, f"hu_{i}",
                 f"2026-04-0{i+1}T00:00:00Z"),
            )

        # Keywords
        for term, display in [
            ("kafka", "Kafka"), ("stream", "Stream"), ("queue", "Queue"),
            ("postgres", "Postgres"), ("replica", "Replica"), ("vacuum", "Vacuum"),
        ]:
            conn.execute(
                "INSERT INTO keywords (term, display, source_kind) VALUES (?, ?, 'keybert')",
                (term, display),
            )

        # Need 20+ keywords to bypass the empty-state threshold
        for i in range(20):
            conn.execute(
                "INSERT INTO keywords (term, display, source_kind) VALUES (?, ?, 'keybert')",
                (f"filler_{i}", f"Filler{i}"),
            )

        kw = {r["term"]: int(r["id"])
              for r in conn.execute("SELECT id, term FROM keywords").fetchall()}
        grab_articles = [int(r["id"]) for r in conn.execute(
            "SELECT id FROM articles WHERE source_name = 'grab_engineering' ORDER BY id"
        ).fetchall()]
        uber_articles = [int(r["id"]) for r in conn.execute(
            "SELECT id FROM articles WHERE source_name = 'uber_engineering' ORDER BY id"
        ).fetchall()]

        for aid in grab_articles:
            for term in ("kafka", "stream", "queue"):
                conn.execute(
                    "INSERT INTO article_keywords (article_id, keyword_id, score, is_glossary) "
                    "VALUES (?, ?, 0.7, 0)",
                    (aid, kw[term]),
                )
        for aid in uber_articles:
            for term in ("postgres", "replica", "vacuum"):
                conn.execute(
                    "INSERT INTO article_keywords (article_id, keyword_id, score, is_glossary) "
                    "VALUES (?, ?, 0.7, 0)",
                    (aid, kw[term]),
                )
        conn.commit()

        update_doc_freq(conn)
        conn.commit()

        # Update sources.article_count denormalization
        conn.execute(
            "UPDATE sources SET article_count = "
            "(SELECT COUNT(*) FROM articles WHERE source_name = sources.name)"
        )
        conn.commit()
    finally:
        conn.close()

    build_graph(data_dir=tmp_path, min_doc_freq=3, min_co_count=2, min_npmi=0.1)


@pytest.fixture
def two_source_client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("STAR_CRAWL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STAR_CRAWL_AUTH", raising=False)
    _seed_two_sources(tmp_path)
    import star_crawl.web.app as app_module
    reload(app_module)
    return TestClient(app_module.app)


@pytest.mark.integration
def test_source_filter_restricts_keywords(two_source_client):
    """When source=grab_engineering, only Grab-cluster keywords appear."""
    r = two_source_client.get("/graph.json?source=grab_engineering&min_freq=1&min_npmi=0")
    assert r.status_code == 200
    data = r.json()
    terms = {n["data"]["term"] for n in data["nodes"]}
    assert "kafka" in terms
    assert "postgres" not in terms  # excluded by source filter


@pytest.mark.integration
def test_source_filter_uber_only(two_source_client):
    r = two_source_client.get("/graph.json?source=uber_engineering&min_freq=1&min_npmi=0")
    assert r.status_code == 200
    data = r.json()
    terms = {n["data"]["term"] for n in data["nodes"]}
    assert "postgres" in terms
    assert "kafka" not in terms


@pytest.mark.integration
def test_multiple_source_filter(two_source_client):
    r = two_source_client.get(
        "/graph.json?source=grab_engineering&source=uber_engineering&min_freq=1&min_npmi=0"
    )
    data = r.json()
    terms = {n["data"]["term"] for n in data["nodes"]}
    assert "kafka" in terms
    assert "postgres" in terms


@pytest.mark.integration
def test_time_filter_since(two_source_client):
    """Restricting to >= 2026-04-01 keeps only Uber's articles → uber keywords."""
    r = two_source_client.get("/graph.json?since=2026-04-01&min_freq=1&min_npmi=0")
    data = r.json()
    terms = {n["data"]["term"] for n in data["nodes"]}
    assert "postgres" in terms
    assert "kafka" not in terms


@pytest.mark.integration
def test_time_filter_until(two_source_client):
    """Restricting to <= 2026-03-31 keeps only Grab's articles."""
    r = two_source_client.get("/graph.json?until=2026-03-31&min_freq=1&min_npmi=0")
    data = r.json()
    terms = {n["data"]["term"] for n in data["nodes"]}
    assert "kafka" in terms
    assert "postgres" not in terms


@pytest.mark.integration
def test_no_match_returns_empty(two_source_client):
    """Far-future since → no articles match → empty graph."""
    r = two_source_client.get("/graph.json?since=2099-01-01&min_freq=1&min_npmi=0")
    assert r.status_code == 200
    data = r.json()
    assert data["nodes"] == []
    assert data["edges"] == []


@pytest.mark.integration
def test_filters_reflected_in_meta(two_source_client):
    r = two_source_client.get("/graph.json?source=grab_engineering&since=2026-01-01")
    data = r.json()
    fa = data["meta"]["filters_applied"]
    assert fa["sources"] == ["grab_engineering"]
    assert fa["since"] == "2026-01-01"
