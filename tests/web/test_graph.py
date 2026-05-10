"""Web routes for the graph view."""

from __future__ import annotations

import json
from importlib import reload
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from star_crawl.db import migrate as db_migrate
from star_crawl.db.connection import connect
from star_crawl.graph.builder import build_graph


def _seed_built_graph(tmp_path: Path) -> None:
    """Reuse the builder fixture: 10 articles, 6 keywords across 2 clusters."""
    db_migrate.migrate(tmp_path)
    conn = connect(tmp_path)
    try:
        conn.execute(
            "INSERT INTO sources (name, display_name, base_url, fetcher, "
            "seed_strategy, config_json) VALUES ('grab', 'Grab', "
            "'https://e.com', 'http', 'rss', '{}')"
        )
        for i in range(30):
            conn.execute(
                "INSERT INTO articles (source_name, url, title, content_text, "
                "content_md, word_count, content_hash) VALUES "
                "(?, ?, ?, ?, ?, ?, ?)",
                ("grab", f"https://e.com/{i}", f"Article {i}",
                 "body", "body", 100, f"h_{i}"),
            )
        keywords = [
            ("kafka", "Kafka", "glossary"),
            ("stream", "Stream", "keybert"),
            ("queue", "Queue", "keybert"),
            ("postgres", "Postgres", "glossary"),
            ("replica", "Replica", "keybert"),
            ("vacuum", "Vacuum", "keybert"),
            ("isolated_kw", "Isolated", "keybert"),
        ]
        # Pad up past EMPTY_THRESHOLD (20) with low-freq dummies so the
        # /graph route doesn't divert to the empty-state template.
        for i in range(20):
            keywords.append((f"filler_{i}", f"Filler{i}", "keybert"))

        for term, display, kind in keywords:
            conn.execute(
                "INSERT INTO keywords (term, display, doc_freq, source_kind) "
                "VALUES (?, ?, 0, ?)",
                (term, display, kind),
            )

        kw_ids = {
            r["term"]: int(r["id"])
            for r in conn.execute("SELECT id, term FROM keywords").fetchall()
        }
        a_ids = [
            int(r["id"]) for r in conn.execute("SELECT id FROM articles ORDER BY id").fetchall()
        ]

        # Cluster 1: kafka/stream/queue in 12 articles (0..11)
        for i in range(12):
            for term in ("kafka", "stream", "queue"):
                conn.execute(
                    "INSERT INTO article_keywords (article_id, keyword_id, score, is_glossary) "
                    "VALUES (?, ?, 0.7, 0)",
                    (a_ids[i], kw_ids[term]),
                )
        # Cluster 2: postgres/replica/vacuum in 12 articles (12..23)
        for i in range(12, 24):
            for term in ("postgres", "replica", "vacuum"):
                conn.execute(
                    "INSERT INTO article_keywords (article_id, keyword_id, score, is_glossary) "
                    "VALUES (?, ?, 0.7, 0)",
                    (a_ids[i], kw_ids[term]),
                )
        # Isolated keyword: 5 articles, no co-occurrence with others
        for i in range(24, 29):
            conn.execute(
                "INSERT INTO article_keywords (article_id, keyword_id, score, is_glossary) "
                "VALUES (?, ?, 0.4, 0)",
                (a_ids[i], kw_ids["isolated_kw"]),
            )
        conn.commit()
    finally:
        conn.close()

    # Now run extract.update_doc_freq + build
    from star_crawl.graph.extract import update_doc_freq
    conn = connect(tmp_path)
    try:
        update_doc_freq(conn)
        conn.commit()
    finally:
        conn.close()
    build_graph(data_dir=tmp_path, min_doc_freq=3, min_co_count=2, min_npmi=0.1)


@pytest.fixture
def graph_client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("STAR_CRAWL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STAR_CRAWL_AUTH", raising=False)
    _seed_built_graph(tmp_path)

    import star_crawl.web.app as app_module
    reload(app_module)
    return TestClient(app_module.app)


@pytest.fixture
def empty_graph_client(tmp_path: Path, monkeypatch):
    """No graph built — empty state."""
    monkeypatch.setenv("STAR_CRAWL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STAR_CRAWL_AUTH", raising=False)
    db_migrate.migrate(tmp_path)

    import star_crawl.web.app as app_module
    reload(app_module)
    return TestClient(app_module.app)


@pytest.mark.integration
def test_graph_page_renders(graph_client):
    r = graph_client.get("/graph")
    assert r.status_code == 200
    assert "Topic graph" in r.text
    assert "cytoscape" in r.text.lower()


@pytest.mark.integration
def test_graph_page_empty_state(empty_graph_client):
    r = empty_graph_client.get("/graph")
    assert r.status_code == 200
    assert "Corpus too small" in r.text
    # Empty state has no Cytoscape script
    assert "id=\"cy\"" not in r.text


@pytest.mark.integration
def test_graph_json_returns_payload(graph_client):
    r = graph_client.get("/graph.json?min_freq=3&min_npmi=0.1")
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data and "edges" in data
    assert len(data["nodes"]) >= 6  # the 6 connected keywords
    # Each node has the expected shape
    for n in data["nodes"]:
        assert "data" in n
        assert "display" in n["data"]
        assert "doc_freq" in n["data"]
        assert "color" in n["data"]


@pytest.mark.integration
def test_graph_json_filter_by_cluster(graph_client):
    # Get cluster IDs available
    r = graph_client.get("/graph.json?min_freq=3&min_npmi=0.1")
    data = r.json()
    clusters_present = {n["data"]["cluster_id"] for n in data["nodes"] if n["data"]["cluster_id"]}
    if not clusters_present:
        return  # nothing to filter
    target = next(iter(clusters_present))
    r2 = graph_client.get(f"/graph.json?cluster={target}&min_freq=3&min_npmi=0.1")
    assert r2.status_code == 200
    data2 = r2.json()
    for n in data2["nodes"]:
        assert n["data"]["cluster_id"] == target


@pytest.mark.integration
def test_keyword_panel_renders(graph_client):
    # Pick any keyword ID
    r = graph_client.get("/graph.json?min_freq=3&min_npmi=0.1")
    nodes = r.json()["nodes"]
    assert nodes
    kw_id = nodes[0]["data"]["kw_id"]

    r2 = graph_client.get(f"/keywords/{kw_id}")
    assert r2.status_code == 200
    # Side panel partial — no full HTML wrapper
    assert "<html" not in r2.text.lower()
    assert "Top neighbors" in r2.text


@pytest.mark.integration
def test_keyword_panel_404(graph_client):
    r = graph_client.get("/keywords/9999")
    assert r.status_code == 404


@pytest.mark.integration
def test_keyword_search(graph_client):
    r = graph_client.get("/keywords/search?q=kaf")
    assert r.status_code == 200
    assert "Kafka" in r.text
    # Empty query returns empty fragment cleanly
    r2 = graph_client.get("/keywords/search?q=")
    assert r2.status_code == 200


@pytest.mark.integration
def test_graph_json_503_when_not_built(empty_graph_client):
    r = empty_graph_client.get("/graph.json")
    assert r.status_code == 503
    assert "build-graph" in r.text
