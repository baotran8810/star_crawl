"""Pipeline orchestrator.

Frontier-based: discovery enqueues URLs into the SQLite `frontier` table,
the worker loop claims them one at a time. Crash-resumable: re-running the
same source picks up any unfinished run.
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

import httpx

from star_crawl.core import frontier
from star_crawl.core.policy import gate
from star_crawl.core.schemas import Document, RunResult, SourceConfig
from star_crawl.extractors.readability_x import ReadabilityExtractor
from star_crawl.extractors.trafilatura_x import TrafilaturaExtractor
from star_crawl.fetchers.http import HttpFetcher
from star_crawl.filters.lang import detect_language
from star_crawl.filters.quality import is_paywall, meets_minimum_length
from star_crawl.seeders.pagination import PaginationSeeder
from star_crawl.seeders.rss import RssSeeder
from star_crawl.seeders.sitemap import SitemapSeeder
from star_crawl.sinks import sqlite as sink

logger = logging.getLogger(__name__)


def _config_hash(source: SourceConfig) -> str:
    return hashlib.sha256(sink.serialize_config(source).encode()).hexdigest()[:16]


def _seeder_for(source: SourceConfig):
    if source.seed.strategy == "rss":
        return RssSeeder()
    if source.seed.strategy == "pagination":
        return PaginationSeeder()
    if source.seed.strategy == "sitemap":
        return SitemapSeeder()
    raise NotImplementedError(f"seed strategy '{source.seed.strategy}' not implemented")


def _fetcher_for(source: SourceConfig):
    if source.fetcher == "http":
        return HttpFetcher(default_rps=source.rate_limit.rps)
    if source.fetcher == "browser":
        from star_crawl.fetchers.browser import BrowserFetcher
        return BrowserFetcher()
    raise NotImplementedError(f"fetcher '{source.fetcher}' not implemented")


async def _seed_into_frontier(
    seeder, source: SourceConfig, run_id: int, data_dir: Path | None,
    *, skip_known: bool,
) -> tuple[int, int]:
    """Walk seeder; enqueue new URLs. Returns (discovered, already_known)."""
    discovered = 0
    already_known = 0
    conn = sink.open_writer(data_dir)
    try:
        async for url in seeder.seed(source):
            discovered += 1
            if skip_known and frontier.url_already_known(conn, source.name, url):
                already_known += 1
                continue
            frontier.enqueue(conn, run_id, source.name, url)
            if discovered % 50 == 0:
                conn.commit()
        conn.commit()
    finally:
        conn.close()
    return discovered, already_known


async def run_source(
    source: SourceConfig,
    *,
    data_dir: Path | None = None,
    allow_policy_blocked: bool = False,
    limit: int | None = None,
    skip_known: bool = True,
) -> RunResult:
    started = time.monotonic()
    allowed, reason = gate(source, allow_policy_blocked)

    conn = sink.open_writer(data_dir)
    try:
        sink.upsert_source(conn, source)
        existing = frontier.find_resumable_run(conn, source.name)
        if existing is not None:
            run_id = existing
            moved = frontier.reset_in_progress(conn, run_id)
            if moved:
                logger.info("resuming run #%d (reset %d in-progress URLs)", run_id, moved)
            resuming = True
        else:
            run_id = sink.start_run(conn, source, _config_hash(source))
            resuming = False
        conn.commit()
    finally:
        conn.close()

    if not allowed:
        logger.warning("skipping %s: %s", source.name, reason)
        conn = sink.open_writer(data_dir)
        try:
            sink.finish_run(conn, run_id, "skipped", 0, 0, 0, 0)
            conn.commit()
        finally:
            conn.close()
        return RunResult(
            source_name=source.name, run_id=run_id, status="skipped",
            duration_seconds=time.monotonic() - started,
        )

    seeder = _seeder_for(source)
    fetcher = _fetcher_for(source)
    primary = TrafilaturaExtractor()
    fallback = ReadabilityExtractor() if source.extract.fallback == "readability" else None

    discovered = 0
    new_count = 0
    dup_count = 0
    error_count = 0

    try:
        if not resuming:
            discovered, already_known = await _seed_into_frontier(
                seeder, source, run_id, data_dir, skip_known=skip_known,
            )
            dup_count += already_known
        else:
            conn = sink.open_writer(data_dir)
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM frontier WHERE run_id = ?", (run_id,)
                ).fetchone()
                discovered = int(row[0])
            finally:
                conn.close()

        if discovered == 0:
            logger.warning("source %s: zero URLs discovered", source.name)

        while True:
            if limit is not None and new_count >= limit:
                break

            conn = sink.open_writer(data_dir)
            try:
                claim = frontier.claim_next(conn, run_id)
                conn.commit()
            finally:
                conn.close()
            if claim is None:
                break

            frontier_id, url = claim
            outcome = await _process_url(
                url, source, fetcher, primary, fallback, run_id, data_dir,
            )

            conn = sink.open_writer(data_dir)
            try:
                if outcome == "new":
                    frontier.mark_done(conn, frontier_id)
                    new_count += 1
                elif outcome == "dup":
                    frontier.mark_done(conn, frontier_id)
                    dup_count += 1
                elif outcome == "skipped":
                    frontier.mark_skipped(conn, frontier_id, "filtered")
                else:
                    frontier.mark_failed(conn, frontier_id, outcome)
                    error_count += 1
                conn.commit()
            finally:
                conn.close()
    finally:
        await fetcher.aclose()

    if discovered == 0:
        status = "failed"
    elif error_count == 0 and new_count > 0:
        status = "success"
    elif new_count > 0:
        status = "partial"
    elif new_count == 0 and dup_count > 0 and error_count == 0:
        # All discovered URLs were already known — successful no-op
        status = "success"
    else:
        status = "failed"

    conn = sink.open_writer(data_dir)
    try:
        sink.finish_run(conn, run_id, status, discovered, new_count, dup_count, error_count)
        conn.commit()
    finally:
        conn.close()

    return RunResult(
        source_name=source.name, run_id=run_id, status=status,
        discovered=discovered, extracted_new=new_count, extracted_dup=dup_count,
        error_count=error_count, duration_seconds=time.monotonic() - started,
    )


async def _process_url(
    url: str, source: SourceConfig, fetcher, primary, fallback,
    run_id: int, data_dir: Path | None,
) -> str:
    try:
        result = await fetcher.fetch(url, source)
    except (httpx.HTTPError, RuntimeError) as e:
        _log_error_in_new_conn(data_dir, run_id, url, "fetch", str(e))
        return f"fetch error: {e}"

    if result.status >= 400:
        msg = f"HTTP {result.status}"
        _log_error_in_new_conn(data_dir, run_id, url, "fetch", msg)
        return msg

    doc = primary.extract(result.html, url)
    if doc is None and fallback is not None:
        doc = fallback.extract(result.html, url)
    if doc is None:
        _log_error_in_new_conn(data_dir, run_id, url, "extract", "all extractors empty")
        return "extract empty"

    if is_paywall(doc.content_text):
        _log_error_in_new_conn(data_dir, run_id, url, "paywall", "paywall marker detected")
        return "paywall"

    if not meets_minimum_length(doc.content_text, source.extract.min_word_count):
        _log_error_in_new_conn(
            data_dir, run_id, url, "quality",
            f"word_count={doc.word_count} < min={source.extract.min_word_count}",
        )
        return "quality"

    doc = doc.model_copy(update={"lang": detect_language(doc.content_text)})
    inserted = _insert_in_new_conn(data_dir, source, doc, run_id)
    return "new" if inserted else "dup"


def _insert_in_new_conn(data_dir, source, doc, run_id):
    conn = sink.open_writer(data_dir)
    try:
        ok = sink.insert_article(conn, source, doc, run_id)
        conn.commit()
        return ok
    finally:
        conn.close()


def _log_error_in_new_conn(data_dir, run_id, url, kind, message):
    conn = sink.open_writer(data_dir)
    try:
        sink.log_error(conn, run_id, url, kind, message)
        conn.commit()
    finally:
        conn.close()


async def run_all(
    sources: list[SourceConfig],
    *,
    data_dir: Path | None = None,
    allow_policy_blocked: bool = False,
    limit: int | None = None,
) -> list[RunResult]:
    results: list[RunResult] = []
    for source in sources:
        try:
            res = await run_source(
                source, data_dir=data_dir,
                allow_policy_blocked=allow_policy_blocked, limit=limit,
            )
            results.append(res)
        except Exception as e:
            logger.exception("source %s failed: %s", source.name, e)
            results.append(RunResult(
                source_name=source.name, run_id=0, status="failed", error_count=1,
            ))
    return results


async def refresh_articles(
    source: SourceConfig,
    *, data_dir: Path | None = None,
) -> RunResult:
    """Re-fetch articles already known for this source.

    Useful when the extractor has improved. Discovers via the same seeder
    and re-processes URLs even if they exist in `articles` already.
    """
    return await run_source(source, data_dir=data_dir, skip_known=False, limit=None)
