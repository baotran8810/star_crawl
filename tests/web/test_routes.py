"""Smoke + behavior tests for web routes."""

from __future__ import annotations

import pytest


@pytest.mark.integration
def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


@pytest.mark.integration
def test_home_renders(client):
    """Legacy dashboard is now at /dashboard; / serves the workspace shell."""
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "Overview" in r.text
    assert "Grab Engineering" in r.text
    # security headers
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"


@pytest.mark.integration
def test_home_empty_state(client_empty):
    r = client_empty.get("/dashboard")
    assert r.status_code == 200
    assert "No articles yet" in r.text


@pytest.mark.integration
def test_sources_list(client):
    r = client.get("/panel/sources")
    assert r.status_code == 200
    assert "Grab Engineering" in r.text
    assert "Uber Engineering" in r.text


@pytest.mark.integration
def test_source_detail(client):
    r = client.get("/panel/source/grab_engineering")
    assert r.status_code == 200
    assert "Grab Engineering" in r.text
    assert "Building a real-time event pipeline" in r.text


@pytest.mark.integration
def test_source_detail_404(client):
    r = client.get("/panel/source/nonexistent")
    assert r.status_code == 404
    assert "not configured" in r.text


@pytest.mark.integration
def test_source_detail_htmx_returns_partial(client):
    r = client.get("/panel/source/grab_engineering", headers={"HX-Request": "true"})
    assert r.status_code == 200
    # partial: no <html> wrapper
    assert "<html" not in r.text.lower()
    assert "<table" in r.text.lower()


@pytest.mark.integration
def test_article_detail(client):
    r = client.get("/panel/article/1")
    assert r.status_code == 200
    assert "Building a real-time event pipeline" in r.text
    assert "Jane Doe" in r.text


@pytest.mark.integration
def test_article_404(client):
    r = client.get("/panel/article/9999")
    assert r.status_code == 404


@pytest.mark.integration
def test_search_returns_results(client):
    r = client.get("/panel/search?q=kafka")
    assert r.status_code == 200
    assert "real-time event pipeline" in r.text.lower()
    assert "<mark>" in r.text  # highlight marker


@pytest.mark.integration
def test_search_empty_query(client):
    r = client.get("/panel/search")
    assert r.status_code == 200
    assert "Type a query" in r.text


@pytest.mark.integration
def test_search_no_results(client):
    r = client.get("/panel/search?q=zzznotfoundzzz")
    assert r.status_code == 200
    assert "No matches" in r.text


@pytest.mark.integration
def test_search_filters_by_source(client):
    r = client.get("/panel/search?q=event&source=uber_engineering")
    assert r.status_code == 200
    # Should not include Grab's pipeline article
    assert "Building a real-time event pipeline" not in r.text


@pytest.mark.integration
def test_search_special_chars_dont_crash(client):
    # FTS5 syntax characters that would otherwise crash the parser
    for q in ['"', "*", "(", ")", "AND OR NOT", "drop table"]:
        r = client.get(f"/search?q={q}")
        assert r.status_code == 200, f"query {q!r} returned {r.status_code}"


@pytest.mark.integration
def test_search_htmx_returns_partial(client):
    r = client.get("/panel/search?q=kafka", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "<html" not in r.text.lower()


@pytest.mark.integration
def test_500_handler_no_trace_leaked(populated_data_dir):
    """FR-019 — internal stack traces MUST NOT reach the client."""
    from importlib import reload

    import star_crawl.web.app as app_module
    reload(app_module)
    from fastapi.testclient import TestClient

    @app_module.app.get("/__test_500__")
    def boom():
        raise RuntimeError("super-secret /usr/local/lib/python3.11/site-packages/private.py:42")

    # raise_server_exceptions=False lets the registered 500 handler run
    # instead of TestClient re-raising.
    client = TestClient(app_module.app, raise_server_exceptions=False)
    r = client.get("/__test_500__")
    assert r.status_code == 500
    assert "Traceback" not in r.text
    assert "RuntimeError" not in r.text
    assert "/usr/" not in r.text
    assert "private.py" not in r.text
    assert "site-packages" not in r.text


@pytest.mark.integration
def test_xss_in_content_is_sanitized(client_empty, populated_data_dir, monkeypatch):
    """Markdown with raw HTML should be stripped by bleach."""
    from star_crawl.db.connection import connect

    conn = connect(populated_data_dir)
    try:
        conn.execute(
            """INSERT INTO articles (source_name, url, title, content_text, content_md,
                                     word_count, content_hash)
               VALUES ('grab_engineering', 'https://engineering.grab.com/xss',
                       'XSS test',
                       'plain text body',
                       '<script>alert(1)</script>\n\nNormal paragraph.',
                       3, 'h_xss_demo')"""
        )
        article_id = conn.execute(
            "SELECT id FROM articles WHERE url = 'https://engineering.grab.com/xss'"
        ).fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    from importlib import reload

    import star_crawl.web.app as app_module
    reload(app_module)
    from fastapi.testclient import TestClient

    client = TestClient(app_module.app)
    r = client.get(f"/panel/article/{article_id}")
    assert r.status_code == 200
    # Body content must be sanitized — no script tag injected via markdown.
    # The base template has its own <script> for keyboard shortcuts; isolate
    # the rendered article body via the .prose container.
    import re
    prose_match = re.search(r'<div class="prose">(.*?)</div>', r.text, re.DOTALL)
    assert prose_match is not None
    prose_html = prose_match.group(1)
    # Real <script> tag must not appear; escaped &lt;script&gt; is fine.
    assert "<script" not in prose_html
    # The escaped form is OK — the danger was an executable script tag.
    assert "&lt;script&gt;" in prose_html  # confirms it was escaped, not rendered
    assert "Normal paragraph" in prose_html
