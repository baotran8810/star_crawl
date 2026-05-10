PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    name              TEXT PRIMARY KEY,
    display_name      TEXT NOT NULL,
    base_url          TEXT NOT NULL,
    fetcher           TEXT NOT NULL,
    seed_strategy     TEXT NOT NULL,
    config_json       TEXT NOT NULL,
    policy_opt_in     INTEGER NOT NULL DEFAULT 0,
    last_crawled_at   TIMESTAMP,
    article_count     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name     TEXT NOT NULL REFERENCES sources(name),
    url             TEXT NOT NULL,
    canonical_url   TEXT,
    title           TEXT NOT NULL,
    content_text    TEXT NOT NULL,
    content_md      TEXT NOT NULL,
    author          TEXT,
    published_at    TIMESTAMP,
    crawled_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lang            TEXT,
    word_count      INTEGER NOT NULL,
    content_hash    TEXT NOT NULL UNIQUE,
    metadata_json   TEXT,
    first_run_id    INTEGER,
    UNIQUE(source_name, url)
);

CREATE INDEX IF NOT EXISTS idx_articles_source    ON articles(source_name);
CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_crawled   ON articles(crawled_at DESC);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name     TEXT NOT NULL REFERENCES sources(name),
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    status          TEXT NOT NULL,
    discovered      INTEGER NOT NULL DEFAULT 0,
    extracted_new   INTEGER NOT NULL DEFAULT 0,
    extracted_dup   INTEGER NOT NULL DEFAULT 0,
    error_count     INTEGER NOT NULL DEFAULT 0,
    config_hash     TEXT NOT NULL,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_source_started ON crawl_runs(source_name, started_at DESC);

CREATE TABLE IF NOT EXISTS frontier (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES crawl_runs(id) ON DELETE CASCADE,
    source_name     TEXT NOT NULL REFERENCES sources(name),
    url             TEXT NOT NULL,
    state           TEXT NOT NULL,
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    enqueued_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP,
    UNIQUE(source_name, url, run_id)
);
CREATE INDEX IF NOT EXISTS idx_frontier_state ON frontier(state, run_id);

CREATE TABLE IF NOT EXISTS errors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          INTEGER NOT NULL REFERENCES crawl_runs(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    kind            TEXT NOT NULL,
    message         TEXT NOT NULL,
    occurred_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_errors_run ON errors(run_id);
