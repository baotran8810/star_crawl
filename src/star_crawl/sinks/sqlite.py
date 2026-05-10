"""SQLite sink — write articles, runs, errors."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from star_crawl.core.schemas import Document, SourceConfig
from star_crawl.db.connection import connect


def upsert_source(conn: sqlite3.Connection, source: SourceConfig) -> None:
    """Insert or update the sources row from a SourceConfig."""
    config_json = source.model_dump_json()
    conn.execute(
        """
        INSERT INTO sources (name, display_name, base_url, fetcher, seed_strategy,
                             config_json, policy_opt_in)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            display_name=excluded.display_name,
            base_url=excluded.base_url,
            fetcher=excluded.fetcher,
            seed_strategy=excluded.seed_strategy,
            config_json=excluded.config_json,
            policy_opt_in=excluded.policy_opt_in
        """,
        (
            source.name,
            source.display_name,
            str(source.base_url),
            source.fetcher,
            source.seed.strategy,
            config_json,
            int(source.policy.policy_opt_in),
        ),
    )


def start_run(
    conn: sqlite3.Connection,
    source: SourceConfig,
    config_hash: str,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO crawl_runs (source_name, started_at, status, config_hash)
        VALUES (?, ?, 'running', ?)
        """,
        (source.name, datetime.now(timezone.utc).isoformat(), config_hash),
    )
    run_id = cur.lastrowid
    if run_id is None:
        raise RuntimeError("failed to obtain crawl_run id")
    return int(run_id)


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    discovered: int,
    extracted_new: int,
    extracted_dup: int,
    error_count: int,
) -> None:
    conn.execute(
        """
        UPDATE crawl_runs
           SET finished_at = ?, status = ?,
               discovered = ?, extracted_new = ?,
               extracted_dup = ?, error_count = ?
         WHERE id = ?
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            status,
            discovered,
            extracted_new,
            extracted_dup,
            error_count,
            run_id,
        ),
    )

    conn.execute(
        """
        UPDATE sources
           SET last_crawled_at = ?,
               article_count = (SELECT COUNT(*) FROM articles WHERE source_name = sources.name)
         WHERE name = (SELECT source_name FROM crawl_runs WHERE id = ?)
        """,
        (datetime.now(timezone.utc).isoformat(), run_id),
    )


def insert_article(
    conn: sqlite3.Connection,
    source: SourceConfig,
    doc: Document,
    run_id: int,
) -> bool:
    """Insert an article. Returns True on new row, False on dup (already present)."""
    try:
        conn.execute(
            """
            INSERT INTO articles
                (source_name, url, canonical_url, title, content_text, content_md,
                 author, published_at, lang, word_count, content_hash, metadata_json,
                 first_run_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.name,
                doc.url,
                doc.canonical_url,
                doc.title,
                doc.content_text,
                doc.content_md,
                doc.author,
                doc.published_at.isoformat() if doc.published_at else None,
                doc.lang,
                doc.word_count,
                doc.content_hash,
                doc.metadata_json,
                run_id,
            ),
        )
        return True
    except sqlite3.IntegrityError:
        # dup by content_hash or (source, url) — touch crawled_at on dup
        conn.execute(
            "UPDATE articles SET crawled_at = ? WHERE content_hash = ? OR (source_name = ? AND url = ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                doc.content_hash,
                source.name,
                doc.url,
            ),
        )
        return False


def log_error(
    conn: sqlite3.Connection,
    run_id: int,
    url: str,
    kind: str,
    message: str,
) -> None:
    conn.execute(
        "INSERT INTO errors (run_id, url, kind, message) VALUES (?, ?, ?, ?)",
        (run_id, url, kind, message[:1000]),
    )


def open_writer(data_dir: Path | None = None) -> sqlite3.Connection:
    return connect(data_dir)


def serialize_config(source: SourceConfig) -> str:
    return json.dumps(source.model_dump(mode="json"), sort_keys=True)
