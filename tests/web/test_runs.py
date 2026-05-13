"""Run history + run detail + live progress polling tests."""

from __future__ import annotations

from importlib import reload
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from star_crawl.db import migrate as db_migrate
from star_crawl.db.connection import connect


@pytest.fixture
def runs_data_dir(tmp_path: Path, monkeypatch) -> Path:
    """Seed a corpus with mixed run statuses."""
    monkeypatch.setenv("STAR_CRAWL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STAR_CRAWL_AUTH", raising=False)
    db_migrate.migrate(tmp_path)
    conn = connect(tmp_path)
    try:
        conn.execute(
            """INSERT INTO sources (name, display_name, base_url, fetcher,
                                    seed_strategy, config_json, article_count)
               VALUES ('grab_engineering', 'Grab Engineering',
                       'https://engineering.grab.com', 'http', 'rss', '{}', 3)"""
        )
        conn.execute(
            """INSERT INTO crawl_runs
                  (id, source_name, started_at, finished_at, status,
                   discovered, extracted_new, extracted_dup, error_count, config_hash)
               VALUES (1, 'grab_engineering', '2026-05-09 14:20', '2026-05-09 14:23',
                       'success', 10, 3, 7, 0, 'h1')"""
        )
        conn.execute(
            """INSERT INTO crawl_runs
                  (id, source_name, started_at, finished_at, status,
                   discovered, extracted_new, extracted_dup, error_count, config_hash)
               VALUES (2, 'grab_engineering', '2026-05-09 12:30', '2026-05-09 12:31',
                       'failed', 0, 0, 0, 1, 'h2')"""
        )
        conn.execute(
            """INSERT INTO crawl_runs
                  (id, source_name, started_at, status,
                   discovered, extracted_new, extracted_dup, error_count, config_hash)
               VALUES (3, 'grab_engineering', '2026-05-10 10:00',
                       'running', 5, 2, 0, 0, 'h3')"""
        )
        conn.execute(
            """INSERT INTO errors (run_id, url, kind, message)
               VALUES (2, 'https://engineering.grab.com/x', 'fetch', 'HTTP 503')"""
        )
        conn.execute(
            """INSERT INTO articles
                  (source_name, url, title, content_text, content_md,
                   word_count, content_hash, first_run_id, published_at)
               VALUES ('grab_engineering', 'https://engineering.grab.com/p1',
                       'Article from run 1', 'body', 'body', 100, 'h_a1',
                       1, '2026-05-09T00:00:00Z')"""
        )
        # frontier rows for the running run
        conn.execute(
            """INSERT INTO frontier (run_id, source_name, url, state)
               VALUES (3, 'grab_engineering', 'https://engineering.grab.com/p2', 'in_progress')"""
        )
        conn.commit()
    finally:
        conn.close()
    return tmp_path


@pytest.fixture
def client_runs(runs_data_dir):
    import star_crawl.web.app as app_module
    reload(app_module)
    return TestClient(app_module.app)


@pytest.mark.integration
def test_runs_list(client_runs):
    r = client_runs.get("/panel/runs")
    assert r.status_code == 200
    assert "Crawl runs" in r.text
    # All three runs visible
    assert ">success<" in r.text
    assert ">failed<" in r.text
    assert ">running<" in r.text


@pytest.mark.integration
def test_runs_filter_by_status(client_runs):
    r = client_runs.get("/panel/runs?status=failed")
    assert r.status_code == 200
    # The pill class for the failed run is present
    assert 'class="pill failed"' in r.text
    # Success and running rows should NOT appear (dropdown options share the
    # text, but the pill class only appears on actual rows)
    assert 'class="pill success"' not in r.text
    assert 'class="pill running"' not in r.text


@pytest.mark.integration
def test_runs_filter_invalid_status(client_runs):
    r = client_runs.get("/panel/runs?status=garbage")
    assert r.status_code == 422


@pytest.mark.integration
def test_run_detail(client_runs):
    r = client_runs.get("/panel/run/1")
    assert r.status_code == 200
    assert "Article from run 1" in r.text
    # Stat strip
    assert "Discovered" in r.text
    assert ">10<" in r.text or " 10 " in r.text


@pytest.mark.integration
def test_run_detail_with_errors(client_runs):
    r = client_runs.get("/panel/run/2")
    assert r.status_code == 200
    assert "fetch" in r.text
    assert "HTTP 503" in r.text


@pytest.mark.integration
def test_run_detail_404(client_runs):
    r = client_runs.get("/panel/run/9999")
    assert r.status_code == 404


@pytest.mark.integration
def test_running_row_carries_polling(client_runs):
    """The running run's HTML row must include hx-trigger='every 2s'."""
    r = client_runs.get("/panel/runs")
    assert r.status_code == 200
    # Find the row for run #3
    assert 'id="run-row-3"' in r.text
    # The running row carries hx-trigger
    running_section = r.text.split('id="run-row-3"', 1)[1].split("</div>", 1)[0]
    assert 'hx-trigger="every 2s"' in running_section
    assert 'hx-get="/runs/3/progress"' in running_section


@pytest.mark.integration
def test_progress_partial_running_keeps_trigger(client_runs):
    r = client_runs.get("/runs/3/progress")
    assert r.status_code == 200
    # The fragment is just the row — not a full HTML doc
    assert "<html" not in r.text.lower()
    # Still polling because run 3 is 'running'
    assert 'hx-trigger="every 2s"' in r.text


@pytest.mark.integration
def test_progress_partial_terminal_drops_trigger(client_runs):
    """When status is terminal (success), the fragment must NOT carry the
    polling trigger so the loop ends client-side."""
    r = client_runs.get("/runs/1/progress")
    assert r.status_code == 200
    assert "<html" not in r.text.lower()
    assert "hx-trigger" not in r.text  # no polling on terminal status


@pytest.mark.integration
def test_progress_partial_404(client_runs):
    r = client_runs.get("/runs/9999/progress")
    assert r.status_code == 404
