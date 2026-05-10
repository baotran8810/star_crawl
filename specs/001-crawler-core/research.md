# Phase 0 Research: Crawler Core

**Date**: 2026-05-10

## Decisions

### Content extractor — `trafilatura` primary, `readability-lxml` fallback

- **Decision**: Use `trafilatura` as the primary main-content extractor; fall back to `readability-lxml` only when `trafilatura` returns empty.
- **Rationale**: `trafilatura` is a multi-stage extractor (its own heuristic + jusText + readability fallback internally) and benchmarks at F1 = 0.958, the best of open-source options. It outputs metadata (title, author, date) without separate parsing.
- **Alternatives**: `newspaper4k` (good for metadata, weaker body extraction), Mozilla Readability port (less robust on tech blogs), `boilerpy3` (older, less maintained).

### HTTP client — `httpx` over `aiohttp`

- **Decision**: `httpx[http2]` async client.
- **Rationale**: Cleaner sync/async parity; HTTP/2 by default; `respx` makes test mocking trivial. Per-source rate limit implemented via per-domain semaphore + token bucket.
- **Alternatives**: `aiohttp` (faster, but worse test ergonomics), `requests` (sync only, blocks on slow sources).

### Browser fetcher — `playwright` (lazy import)

- **Decision**: Import `playwright` only when a source's config sets `fetcher: browser`. Default install does not require Chromium.
- **Rationale**: Chromium is a 250MB dependency; most sources do not need it. Lazy load keeps the default install small.
- **Alternatives**: `selenium` (heavier API), `pyppeteer` (unmaintained), `curl-impersonate` (no JS execution).

### Discovery seeders — pagination, RSS, sitemap

- **Decision**: Three first-class seeders, picked per source via YAML.
- **Rationale**: Covers >90% of tech blogs verified during planning. Adding a new strategy = one module + one config field.
- **Alternatives**: Generic link-following crawler (too noisy, hard to bound).

### Dedup — content fingerprint over URL

- **Decision**: Dedup via SHA-256 of normalized text (lowercased, whitespace-collapsed, leading/trailing trimmed). Store both URL and `content_hash`. Canonical URL recorded if `<link rel="canonical">` present.
- **Rationale**: Same article often appears under multiple URLs (tracking params, syndication). URL-only dedup misses these. Content-hash is robust and cheap.
- **Alternatives**: MinHash for near-dup (overkill for v1; deferred), URL-only (insufficient).

### Storage — SQLite WAL

- **Decision**: One database file `data/articles.db` with WAL journal mode. All tables (articles, crawl_runs, frontier, errors, sources) co-located.
- **Rationale**: Single file simplifies backup. WAL allows concurrent reads (web UI) while crawler writes. Constitution V mandates this.
- **Alternatives**: Postgres (overkill at scale; deferred), DuckDB (good for analytics, weaker for writes), plain JSONL (loses query speed).

### Robots.txt — `urllib.robotparser` (stdlib)

- **Decision**: Use stdlib `urllib.robotparser`; cache per-domain for the run lifetime.
- **Rationale**: Sufficient for modern robots.txt; no extra dependency. Covers the user-agent matching constitution principle II requires.
- **Alternatives**: `reppy` (more complete but extra dep), hand-roll (waste of time).

### Rate limiting — token-bucket per domain

- **Decision**: Per-domain semaphore (concurrency cap) + token-bucket (rps cap). Both configured in `SourceConfig.rate_limit`.
- **Rationale**: Concurrency alone allows bursts; rps alone allows pile-up. Both together = deterministic politeness.

### Retry policy — exponential backoff with jitter

- **Decision**: 3 retries on 429, 5xx, network errors. Backoff `2^n + jitter(0, 1)` seconds; cap at 30s. Honor `Retry-After` header when present.
- **Rationale**: Standard pattern; low complexity.

### Language detection — `langdetect` (lazy)

- **Decision**: `langdetect` (Python port of Google's library). Run on extracted text; store result on article.
- **Rationale**: Sufficient accuracy for English / non-English split. ~5ms per article. Lazy-import to keep default install lean.
- **Alternatives**: `lingua-py` (more accurate, heavier).

### CLI framework — `typer`

- **Decision**: `typer` for CLI; `rich` for terminal output.
- **Rationale**: Declarative, type-hint driven. Good help auto-gen. `rich` makes the per-run summary readable.
- **Alternatives**: Stdlib `argparse` (verbose), `click` (typer wraps it; less ergonomic).

### Async runtime — `asyncio` stdlib

- **Decision**: stdlib asyncio with `anyio`-style structured concurrency where helpful (e.g., `asyncio.TaskGroup` available in 3.11+).
- **Rationale**: No extra runtime; 3.11+ has TaskGroup; widely understood.

## Open questions resolved

- **Q**: Should `--all` run all sources concurrently or sequentially? **A**: Sequentially per default (politeness across origins still bounded; simpler error attribution). Future flag `--parallel-sources N` if needed.
- **Q**: Where do `data/` files live? **A**: Repo-relative `./data/`, gitignored. Override via `--data-dir`.
- **Q**: Does the crawler need a daemon mode? **A**: No. Schedule via cron + `star-crawl run --all`.

## Out of scope (deferred)

- Distributed crawling across hosts.
- LLM-assisted extraction.
- Postgres backend.
- Near-duplicate detection (MinHash/SimHash).
- Streaming sink (Kafka, etc.).
