"""Add-source form + run-now subprocess tests."""

from __future__ import annotations

from importlib import reload
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient

from star_crawl.db import migrate as db_migrate
from star_crawl.db.connection import connect


@pytest.fixture
def client_writable(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("STAR_CRAWL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STAR_CRAWL_AUTH", raising=False)
    # Switch CWD so the router writes configs/sources under tmp_path
    monkeypatch.chdir(tmp_path)
    db_migrate.migrate(tmp_path)

    import star_crawl.web.app as app_module
    reload(app_module)
    return TestClient(app_module.app, follow_redirects=False)


@pytest.mark.integration
def test_new_source_form_renders(client_writable):
    r = client_writable.get("/sources/new")
    assert r.status_code == 200
    assert "Add a new source" in r.text


@pytest.mark.integration
def test_create_rss_source(client_writable, tmp_path: Path):
    r = client_writable.post(
        "/sources",
        data={
            "name": "example_blog",
            "display_name": "Example Blog",
            "base_url": "https://example.com/blog",
            "fetcher": "http",
            "seed_strategy": "rss",
            "seed_url": "https://example.com/blog/feed.xml",
            "url_filter": r"^https://example\.com/blog/[^/]+/?$",
        },
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/sources"

    # YAML written
    yaml_path = tmp_path / "configs" / "sources" / "example_blog.yaml"
    assert yaml_path.exists()
    loaded = yaml.safe_load(yaml_path.read_text())
    assert loaded["name"] == "example_blog"
    assert loaded["seed"]["strategy"] == "rss"
    assert loaded["seed"]["url"] == "https://example.com/blog/feed.xml"

    # DB row mirrored immediately
    conn = connect(tmp_path)
    try:
        row = conn.execute("SELECT * FROM sources WHERE name = 'example_blog'").fetchone()
        assert row is not None
        assert row["display_name"] == "Example Blog"
    finally:
        conn.close()


@pytest.mark.integration
def test_create_rejects_duplicate_name(client_writable, tmp_path: Path):
    payload = {
        "name": "blog_a",
        "display_name": "Blog A",
        "base_url": "https://example.com",
        "fetcher": "http",
        "seed_strategy": "rss",
        "seed_url": "https://example.com/feed",
        "url_filter": r"^https://example\.com/[^/]+$",
    }
    r1 = client_writable.post("/sources", data=payload)
    assert r1.status_code == 303
    r2 = client_writable.post("/sources", data=payload)
    assert r2.status_code == 422
    assert "already exists" in r2.text


@pytest.mark.integration
def test_create_pagination_requires_template_with_n(client_writable):
    r = client_writable.post(
        "/sources",
        data={
            "name": "pag_blog",
            "display_name": "Pag",
            "base_url": "https://example.com",
            "fetcher": "http",
            "seed_strategy": "pagination",
            "seed_template": "https://example.com/blog/page/X/",  # no {n}
            "seed_range_start": "1",
            "seed_range_end": "5",
            "url_filter": r"^https://example\.com/[^/]+$",
        },
    )
    assert r.status_code == 422
    assert "{n}" in r.text


@pytest.mark.integration
def test_create_rejects_invalid_name(client_writable):
    r = client_writable.post(
        "/sources",
        data={
            "name": "Bad-Name",  # uppercase + dash
            "display_name": "Bad",
            "base_url": "https://example.com",
            "fetcher": "http",
            "seed_strategy": "rss",
            "seed_url": "https://example.com/feed",
            "url_filter": r"^https://example\.com/[^/]+$",
        },
    )
    assert r.status_code == 422
    assert "[a-z]" in r.text or "must match" in r.text


@pytest.mark.integration
def test_create_rejects_bad_regex(client_writable):
    r = client_writable.post(
        "/sources",
        data={
            "name": "bad_regex",
            "display_name": "X",
            "base_url": "https://example.com",
            "fetcher": "http",
            "seed_strategy": "rss",
            "seed_url": "https://example.com/feed",
            "url_filter": "[invalid(",
        },
    )
    assert r.status_code == 422


@pytest.mark.integration
def test_run_endpoint_spawns_subprocess(client_writable, tmp_path: Path):
    """POST /sources/{name}/run dispatches the subprocess and redirects."""
    # First create the source so the run endpoint can find it
    client_writable.post(
        "/sources",
        data={
            "name": "spawn_test",
            "display_name": "Spawn Test",
            "base_url": "https://example.com",
            "fetcher": "http",
            "seed_strategy": "rss",
            "seed_url": "https://example.com/feed",
            "url_filter": r"^https://example\.com/[^/]+$",
        },
    )

    with patch("star_crawl.web.routers.sources.subprocess.Popen") as mock_popen:
        r = client_writable.post("/sources/spawn_test/run")
    assert r.status_code == 303
    assert r.headers["location"] == "/runs"
    assert mock_popen.called
    args, kwargs = mock_popen.call_args
    # Cmd ends with "run spawn_test"
    cmd = args[0]
    assert cmd[-2:] == ["run", "spawn_test"]
    # Subprocess started in its own session
    assert kwargs.get("start_new_session") is True


@pytest.mark.integration
def test_run_endpoint_404_for_unknown_source(client_writable):
    r = client_writable.post("/sources/nonexistent_source/run")
    assert r.status_code == 404
