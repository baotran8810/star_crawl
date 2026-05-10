"""Web test fixtures."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from star_crawl.db import migrate as db_migrate
from star_crawl.db.connection import connect


def _seed_corpus(data_dir: Path) -> None:
    """Insert a small corpus so the UI has something to render."""
    db_migrate.migrate(data_dir)
    conn = connect(data_dir)
    try:
        conn.execute(
            """INSERT INTO sources (name, display_name, base_url, fetcher,
                                    seed_strategy, config_json, article_count,
                                    last_crawled_at)
               VALUES ('grab_engineering', 'Grab Engineering',
                       'https://engineering.grab.com', 'http', 'rss',
                       '{}', 3, ?)""",
            (datetime.now(timezone.utc).isoformat(),),
        )
        conn.execute(
            """INSERT INTO sources (name, display_name, base_url, fetcher,
                                    seed_strategy, config_json, article_count,
                                    last_crawled_at)
               VALUES ('uber_engineering', 'Uber Engineering',
                       'https://www.uber.com/us/en/blog/engineering/', 'http',
                       'pagination', '{}', 2, ?)""",
            (datetime.now(timezone.utc).isoformat(),),
        )

        conn.execute(
            """INSERT INTO crawl_runs (source_name, started_at, finished_at,
                                       status, discovered, extracted_new,
                                       error_count, config_hash)
               VALUES ('grab_engineering', ?, ?, 'success', 3, 3, 0, 'abc123')""",
            (
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        articles = [
            ("grab_engineering", "https://engineering.grab.com/event-pipeline",
             "Building a real-time event pipeline using Kafka",
             "We built a real-time event pipeline with Apache Kafka. The system "
             "handles millions of events per second with sub-second latency. "
             "Backpressure handling was a key learning. We chose Kafka over RabbitMQ.",
             "Building a real-time event pipeline using Kafka\n\nWe built a real-time event pipeline.",
             "Jane Doe", "2026-04-15T10:00:00Z", "en", 38, "h_event_pipeline"),
            ("grab_engineering", "https://engineering.grab.com/data-mesh",
             "Data Mesh at Grab: foundational tools",
             "Data mesh requires governance and self-serve infrastructure. "
             "Our certification framework treats data as a product. Quality gates "
             "ensure consumers can trust upstream domains.",
             "Data Mesh at Grab.", "Bob Lee", "2026-04-10T10:00:00Z", "en",
             27, "h_data_mesh"),
            ("uber_engineering", "https://www.uber.com/blog/zero-growth-stack/",
             "Zero-growth stack: scaling logistics with constant headcount",
             "Scaling without adding engineers requires platform investment. "
             "We bet on event-driven architecture and self-healing infra.",
             "Zero-growth stack.", "Alice K", "2026-04-12T10:00:00Z", "en",
             20, "h_zero_growth"),
        ]
        for a in articles:
            conn.execute(
                """INSERT INTO articles
                       (source_name, url, title, content_text, content_md,
                        author, published_at, lang, word_count, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                a,
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def populated_data_dir(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("STAR_CRAWL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STAR_CRAWL_AUTH", raising=False)
    _seed_corpus(tmp_path)
    return tmp_path


@pytest.fixture
def empty_data_dir(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("STAR_CRAWL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STAR_CRAWL_AUTH", raising=False)
    db_migrate.migrate(tmp_path)
    return tmp_path


@pytest.fixture
def client(populated_data_dir: Path) -> TestClient:
    # Re-import app so it picks up the env var freshly each test
    from importlib import reload

    import star_crawl.web.app as app_module
    reload(app_module)
    return TestClient(app_module.app)


@pytest.fixture
def client_empty(empty_data_dir: Path) -> TestClient:
    from importlib import reload

    import star_crawl.web.app as app_module
    reload(app_module)
    return TestClient(app_module.app)
