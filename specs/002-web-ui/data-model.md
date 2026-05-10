# Phase 1 Data Model: Web UI

**Date**: 2026-05-10
**DB**: Same `data/articles.db` as feature 001. This feature adds an FTS5 virtual table and supporting triggers. Read-only access from the web process.

## What this feature adds

```sql
-- 1. FTS5 virtual table (full-text search)
CREATE VIRTUAL TABLE articles_fts USING fts5(
    title,
    content_text,
    content=articles,
    content_rowid=id,
    tokenize='porter unicode61 remove_diacritics 1'
);

-- 2. Triggers to keep articles_fts in sync with articles
CREATE TRIGGER articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, content_text)
    VALUES (new.id, new.title, new.content_text);
END;

CREATE TRIGGER articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, content_text)
    VALUES ('delete', old.id, old.title, old.content_text);
END;

CREATE TRIGGER articles_au AFTER UPDATE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, content_text)
    VALUES ('delete', old.id, old.title, old.content_text);
    INSERT INTO articles_fts(rowid, title, content_text)
    VALUES (new.id, new.title, new.content_text);
END;

-- 3. One-time backfill (during migration)
INSERT INTO articles_fts(rowid, title, content_text)
    SELECT id, title, content_text FROM articles;
```

## Read-only views consumed by routes

These are not new tables — they are query patterns the routers rely on. Documented here as the "read contract" the web layer expects from the underlying schema.

### Home view

```sql
-- Totals
SELECT COUNT(*) AS total_articles, COUNT(DISTINCT source_name) AS source_count
FROM articles;

-- Per-source counts
SELECT source_name, article_count, last_crawled_at
FROM sources
ORDER BY article_count DESC;

-- Recent runs (last 10)
SELECT id, source_name, started_at, finished_at, status,
       discovered, extracted_new, error_count,
       (julianday(COALESCE(finished_at, CURRENT_TIMESTAMP)) - julianday(started_at)) * 86400 AS duration_seconds
FROM crawl_runs
ORDER BY started_at DESC
LIMIT 10;
```

### Source detail (paginated)

```sql
SELECT id, title, author, published_at, lang, word_count
FROM articles
WHERE source_name = ?
  AND (? IS NULL OR published_at >= ?)
  AND (? IS NULL OR lang = ?)
ORDER BY published_at DESC
LIMIT ? OFFSET ?;
```

### Article detail

```sql
SELECT a.*, s.display_name AS source_display_name
FROM articles a
JOIN sources s ON s.name = a.source_name
WHERE a.id = ?;
```

### Search

```sql
SELECT
    a.id,
    a.source_name,
    a.title,
    a.published_at,
    a.word_count,
    snippet(articles_fts, 1, '<mark>', '</mark>', '…', 12) AS snippet,
    bm25(articles_fts, 4.0, 1.0) AS rank
FROM articles_fts
JOIN articles a ON a.id = articles_fts.rowid
WHERE articles_fts MATCH ?
  AND (? IS NULL OR a.source_name = ?)
ORDER BY rank
LIMIT ? OFFSET ?;
```

### Run progress (live)

```sql
SELECT
    cr.id,
    cr.status,
    cr.discovered,
    cr.extracted_new,
    cr.error_count,
    (SELECT COUNT(*) FROM frontier WHERE run_id = cr.id AND state = 'in_progress') AS in_flight
FROM crawl_runs cr
WHERE cr.id = ?;
```

## DB connection mode

- Web process opens SQLite with `file:data/articles.db?mode=ro`.
- Crawler process owns the writer. WAL mode (set by feature 001) lets reader and writer coexist.
- Connection pooling via `aiosqlite` if needed; otherwise a single connection per request is fine at this scale.

## Migration

`002_fts5.sql` in `src/star_crawl/migrations/`. Idempotent (uses `IF NOT EXISTS` where possible; FTS5 table creation guarded). Re-runnable after schema bump in feature 003.

## Indexing notes

- FTS5 table has its own internal indexes. No need to add `CREATE INDEX` for it.
- BM25 column weights `(4.0, 1.0)` for `(title, content_text)` based on the rule of thumb that title matches are 3-4× more salient than body matches.
- Snippet length 12 tokens — short enough to fit two lines on the result card.

## Constraints

- Web process MUST NOT issue any `INSERT`/`UPDATE`/`DELETE`. Enforced by `mode=ro` URI; double-checked by integration test that asserts every router returns the same DB row count it observed at request start.
