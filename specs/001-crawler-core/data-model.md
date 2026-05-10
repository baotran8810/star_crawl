# Phase 1 Data Model: Crawler Core

**Date**: 2026-05-10
**DB**: SQLite (WAL mode), single file `data/articles.db`.

## Entity overview

```
sources       1 ─── ∞   articles
sources       1 ─── ∞   crawl_runs
crawl_runs    1 ─── ∞   articles  (run that first ingested it)
crawl_runs    1 ─── ∞   errors
articles      1 ─── ∞   frontier  (per source, pre-fetch)
```

## DDL

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

-- 1. sources: registry from configs/sources/*.yaml
CREATE TABLE sources (
    name              TEXT PRIMARY KEY,           -- matches YAML filename
    display_name      TEXT NOT NULL,
    base_url          TEXT NOT NULL,
    fetcher           TEXT NOT NULL,              -- 'http' | 'browser'
    seed_strategy     TEXT NOT NULL,              -- 'pagination' | 'rss' | 'sitemap'
    config_json       TEXT NOT NULL,              -- full SourceConfig serialized
    policy_opt_in     INTEGER NOT NULL DEFAULT 0,
    last_crawled_at   TIMESTAMP,
    article_count     INTEGER NOT NULL DEFAULT 0  -- denormalized counter
);

-- 2. articles: extracted content
CREATE TABLE articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name     TEXT NOT NULL REFERENCES sources(name),
    url             TEXT NOT NULL,
    canonical_url   TEXT,
    title           TEXT NOT NULL,
    content_text    TEXT NOT NULL,                -- plain text, normalized
    content_md      TEXT NOT NULL,                -- markdown
    author          TEXT,
    published_at    TIMESTAMP,
    crawled_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lang            TEXT,                         -- ISO 639-1
    word_count      INTEGER NOT NULL,
    content_hash    TEXT NOT NULL UNIQUE,         -- SHA-256 of normalized content
    metadata_json   TEXT,                         -- JSON-LD raw + extras
    first_run_id    INTEGER REFERENCES crawl_runs(id),
    UNIQUE(source_name, url)
);
CREATE INDEX idx_articles_source        ON articles(source_name);
CREATE INDEX idx_articles_published     ON articles(published_at DESC);
CREATE INDEX idx_articles_crawled       ON articles(crawled_at DESC);

-- 3. crawl_runs: one row per CLI invocation per source
CREATE TABLE crawl_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name     TEXT NOT NULL REFERENCES sources(name),
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    status          TEXT NOT NULL,               -- 'running' | 'success' | 'partial' | 'failed'
    discovered      INTEGER NOT NULL DEFAULT 0,
    extracted_new   INTEGER NOT NULL DEFAULT 0,
    extracted_dup   INTEGER NOT NULL DEFAULT 0,
    error_count     INTEGER NOT NULL DEFAULT 0,
    config_hash     TEXT NOT NULL,               -- hash of source config at run time
    notes           TEXT
);
CREATE INDEX idx_runs_source_started ON crawl_runs(source_name, started_at DESC);

-- 4. frontier: per-run URL queue (also used for cross-run dedup of seen URLs)
CREATE TABLE frontier (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES crawl_runs(id) ON DELETE CASCADE,
    source_name     TEXT NOT NULL REFERENCES sources(name),
    url             TEXT NOT NULL,
    state           TEXT NOT NULL,               -- 'pending' | 'in_progress' | 'done' | 'failed' | 'skipped'
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    enqueued_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP,
    UNIQUE(source_name, url, run_id)
);
CREATE INDEX idx_frontier_state ON frontier(state, run_id);

-- 5. errors: per-URL failure log
CREATE TABLE errors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES crawl_runs(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    kind            TEXT NOT NULL,               -- 'fetch' | 'extract' | 'paywall' | 'timeout' | 'cf_block' | 'parse'
    message         TEXT NOT NULL,
    occurred_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_errors_run ON errors(run_id);
```

## Validation rules (enforced in pipeline, not DDL)

- `articles.title` must be non-empty after trim; if extractor returns empty title → article rejected, error logged.
- `articles.content_text` must be ≥ `min_word_count` (default 100); below threshold → article rejected with `quality` error kind.
- `articles.content_hash` collision = duplicate; second occurrence updates `articles.crawled_at` only, no new row.
- `articles.published_at` accepts ISO 8601 or RFC 822; if unparseable, set NULL.
- `articles.lang`: only persist if detector confidence ≥ 0.9; otherwise NULL.
- A source whose config sets `policy_opt_in: false` (or unset) and whose robots.txt disallows the configured user-agent: skip the entire source, write zero rows.

## State transitions

- `crawl_runs.status`: `running → success` (zero errors), `running → partial` (>0 errors but >0 articles), `running → failed` (zero articles + any error).
- `frontier.state`: `pending → in_progress → done` (success path), `in_progress → failed` (after retries exhausted), `pending → skipped` (URL filter excluded after enqueue, e.g., from sitemap).

## Migrations

- Schema versioning: single `_schema_version` table with one row.
- Migrations: hand-written `migrate.py` running ordered SQL files in `src/star_crawl/migrations/NNN_*.sql`. No Alembic — overkill for SQLite single-file.

## Indexing / query plan notes

- Most-common UI query: `SELECT * FROM articles WHERE source_name = ? ORDER BY published_at DESC LIMIT N OFFSET M` — covered by `idx_articles_published` + `idx_articles_source`.
- Most-common dedup query: `SELECT 1 FROM articles WHERE content_hash = ?` — primary key on UNIQUE.
- Most-common run-detail query: `SELECT * FROM errors WHERE run_id = ?` — covered by `idx_errors_run`.
