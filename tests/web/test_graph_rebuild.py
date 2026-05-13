"""POST /graph/rebuild kicks off a subprocess + redirects."""

from __future__ import annotations

from importlib import reload
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from star_crawl.db import migrate as db_migrate


@pytest.fixture
def graph_client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("STAR_CRAWL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STAR_CRAWL_AUTH", raising=False)
    db_migrate.migrate(tmp_path)
    import star_crawl.web.app as app_module
    reload(app_module)
    return TestClient(app_module.app, follow_redirects=False)


@pytest.mark.integration
def test_rebuild_spawns_subprocess_and_redirects(graph_client):
    with patch("star_crawl.web.routers.graph.subprocess.Popen") as mock_popen:
        r = graph_client.post("/graph/rebuild")
    assert r.status_code == 303
    assert r.headers["location"] == "/graph?rebuilding=1"
    assert mock_popen.called
    args, kwargs = mock_popen.call_args
    # Bash script that runs both extract + build
    cmd = args[0]
    assert cmd[0] == "bash" and cmd[1] == "-c"
    script = cmd[2]
    assert "extract-keywords" in script
    assert "build-graph" in script
    assert kwargs.get("start_new_session") is True


@pytest.mark.integration
def test_rebuild_button_present_on_graph_page(graph_client, tmp_path: Path, monkeypatch):
    # Seed a corpus + minimal graph_meta so the page renders the non-empty
    # template, where the rebuild button lives in the header.
    from star_crawl.db.connection import connect

    conn = connect(tmp_path)
    try:
        conn.execute(
            "INSERT INTO sources (name, display_name, base_url, fetcher, "
            "seed_strategy, config_json) VALUES "
            "('s', 'S', 'https://e.com', 'http', 'rss', '{}')"
        )
        # Need ≥20 keywords to bypass the empty-state template
        for i in range(25):
            conn.execute(
                "INSERT INTO keywords (term, display, source_kind, doc_freq) "
                "VALUES (?, ?, 'keybert', ?)",
                (f"kw_{i}", f"Kw {i}", 3),
            )
        conn.execute(
            "INSERT INTO graph_meta (n_articles, n_keywords, n_edges, "
            "n_clusters, config_hash) VALUES (10, 25, 30, 3, 'h')"
        )
        conn.commit()
    finally:
        conn.close()

    r = graph_client.get("/panel/graph")
    assert r.status_code == 200
    assert '/graph/rebuild' in r.text
    assert "Rebuild graph" in r.text


@pytest.mark.integration
def test_rebuild_button_on_empty_page(graph_client):
    """Empty-state page (no graph yet) also exposes a rebuild button."""
    r = graph_client.get("/panel/graph")
    # Empty state — keyword_count == 0 → graph_empty.html
    assert r.status_code == 200
    assert "Corpus too small" in r.text
    assert "/graph/rebuild" in r.text
    assert "Rebuild graph" in r.text


@pytest.mark.integration
def test_rebuilding_banner_shown_with_query_param(graph_client, tmp_path: Path):
    """After redirect to /graph?rebuilding=1 a callout is rendered."""
    from star_crawl.db.connection import connect

    conn = connect(tmp_path)
    try:
        conn.execute(
            "INSERT INTO sources (name, display_name, base_url, fetcher, "
            "seed_strategy, config_json) VALUES "
            "('s', 'S', 'https://e.com', 'http', 'rss', '{}')"
        )
        for i in range(25):
            conn.execute(
                "INSERT INTO keywords (term, display, source_kind, doc_freq) "
                "VALUES (?, ?, 'keybert', 3)", (f"kw_{i}", f"Kw {i}"),
            )
        conn.execute(
            "INSERT INTO graph_meta (n_articles, n_keywords, n_edges, "
            "n_clusters, config_hash) VALUES (10, 25, 30, 3, 'h')"
        )
        conn.commit()
    finally:
        conn.close()

    r = graph_client.get("/panel/graph?rebuilding=1")
    assert r.status_code == 200
    assert "Rebuild started" in r.text
