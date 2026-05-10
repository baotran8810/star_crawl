"""Pipeline orchestrator: seeder → fetcher → extractor → filters → sink."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from pathlib import Path

import httpx

from star_crawl.core.policy import gate
from star_crawl.core.schemas import Document, RunResult, SourceConfig
from star_crawl.extractors.readability_x import ReadabilityExtractor
from star_crawl.extractors.trafilatura_x import TrafilaturaExtractor
from star_crawl.fetchers.http import HttpFetcher
from star_crawl.filters.lang import detect_language
from star_crawl.filters.quality import is_paywall, meets_minimum_length
from star_crawl.seeders.rss import RssSeeder
from star_crawl.sinks import sqlite as sink

logger = logging.getLogger(__name__)


def _config_hash(source: SourceConfig) -> str:
    return hashlib.sha256(sink.serialize_config(source).encode()).hexdigest()[:16]


async def run_source(
    source: SourceConfig,
    *,
    data_dir: Path | None = None,
    allow_policy_blocked: bool = False,
    limit: int | None = None,
) -> RunResult:
    """Crawl one source end-to-end. Returns RunResult."""
    started = time.monotonic()
    allowed, reason = gate(source, allow_policy_blocked)

    conn = sink.open_writer(data_dir)
    try:
        sink.upsert_source(conn, source)
        run_id = sink.start_run(conn, source, _config_hash(source))
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
    fetcher = HttpFetcher(default_rps=source.rate_limit.rps)
    primary = TrafilaturaExtractor()
    fallback = ReadabilityExtractor() if source.extract.fallback == "readability" else None

    discovered = 0
    new_count = 0
    dup_count = 0
    error_count = 0

    try:
        async for url in seeder.seed(source):
            if limit is not None and new_count >= limit:
                break
            discovered += 1
            try:
                result = await fetcher.fetch(url, source)
            except httpx.HTTPError as e:
                _log_error_in_new_conn(data_dir, run_id, url, "fetch", str(e))
                error_count += 1
                continue

            if result.status >= 400:
                _log_error_in_new_conn(
                    data_dir, run_id, url, "fetch", f"HTTP {result.status}"
                )
                error_count += 1
                continue

            doc = primary.extract(result.html, url)
            if doc is None and fallback is not None:
                doc = fallback.extract(result.html, url)
            if doc is None:
                _log_error_in_new_conn(
                    data_dir, run_id, url, "extract", "all extractors empty"
                )
                error_count += 1
                continue

            if is_paywall(doc.content_text):
                _log_error_in_new_conn(
                    data_dir, run_id, url, "paywall", "paywall marker detected"
                )
                error_count += 1
                continue

            if not meets_minimum_length(doc.content_text, source.extract.min_word_count):
                _log_error_in_new_conn(
                    data_dir,
                    run_id,
                    url,
                    "quality",
                    f"word_count={doc.word_count} < min={source.extract.min_word_count}",
                )
                error_count += 1
                continue

            doc = doc.model_copy(update={"lang": detect_language(doc.content_text)})

            inserted = _insert_in_new_conn(data_dir, source, doc, run_id)
            if inserted:
                new_count += 1
            else:
                dup_count += 1
    finally:
        await fetcher.aclose()

    if error_count == 0 and new_count > 0:
        status = "success"
    elif new_count > 0:
        status = "partial"
    elif discovered == 0:
        status = "failed"
    else:
        status = "failed"

    conn = sink.open_writer(data_dir)
    try:
        sink.finish_run(conn, run_id, status, discovered, new_count, dup_count, error_count)
        conn.commit()
    finally:
        conn.close()

    return RunResult(
        source_name=source.name,
        run_id=run_id,
        status=status,
        discovered=discovered,
        extracted_new=new_count,
        extracted_dup=dup_count,
        error_count=error_count,
        duration_seconds=time.monotonic() - started,
    )


def _seeder_for(source: SourceConfig):
    if source.seed.strategy == "rss":
        return RssSeeder()
    raise NotImplementedError(
        f"seed strategy '{source.seed.strategy}' not yet implemented in CP2"
    )


def _insert_in_new_conn(
    data_dir: Path | None, source: SourceConfig, doc: Document, run_id: int
) -> bool:
    conn = sink.open_writer(data_dir)
    try:
        ok = sink.insert_article(conn, source, doc, run_id)
        conn.commit()
        return ok
    finally:
        conn.close()


def _log_error_in_new_conn(
    data_dir: Path | None, run_id: int, url: str, kind: str, message: str
) -> None:
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
    """Run sources sequentially (politeness across origins)."""
    results: list[RunResult] = []
    for source in sources:
        try:
            res = await run_source(
                source,
                data_dir=data_dir,
                allow_policy_blocked=allow_policy_blocked,
                limit=limit,
            )
            results.append(res)
        except Exception as e:
            logger.exception("source %s failed: %s", source.name, e)
            results.append(
                RunResult(
                    source_name=source.name,
                    run_id=0,
                    status="failed",
                    error_count=1,
                )
            )
    return results
