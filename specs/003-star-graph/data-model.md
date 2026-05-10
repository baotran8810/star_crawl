# Phase 1 Data Model: Star-Graph

**Date**: 2026-05-10
**DB**: Same `data/articles.db`. This feature adds three core tables, one audit table, one read-side view.

## Entity overview

```
articles 1 ── ∞ article_keywords ∞ ── 1 keywords
                                       │
                                       │ 1 ── ∞ keyword_edges (pairwise)
                                       │
                                       │ ∞ ── 1 clusters
graph_meta — append-only audit log per build
```

## DDL

```sql
-- 1. keywords: master list, dedupe alias-resolved
CREATE TABLE keywords (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    term        TEXT NOT NULL UNIQUE,           -- normalized (lower / lemma)
    display     TEXT NOT NULL,                  -- pretty form (Kubernetes)
    doc_freq    INTEGER NOT NULL DEFAULT 0,     -- articles containing it
    source_kind TEXT NOT NULL,                  -- 'keybert' | 'glossary' | 'both'
    cluster_id  INTEGER REFERENCES clusters(id),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_keywords_doc_freq ON keywords(doc_freq DESC);
CREATE INDEX idx_keywords_cluster  ON keywords(cluster_id);

-- 2. article_keywords: many-to-many with score
CREATE TABLE article_keywords (
    article_id   INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    keyword_id   INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    score        REAL    NOT NULL,              -- KeyBERT cosine 0..1, glossary-only = 1.0
    is_glossary  INTEGER NOT NULL DEFAULT 0,    -- 1 if matched from glossary
    PRIMARY KEY (article_id, keyword_id)
);
CREATE INDEX idx_ak_keyword ON article_keywords(keyword_id);
CREATE INDEX idx_ak_article ON article_keywords(article_id);

-- 3. keyword_edges: undirected pairwise, weighted
CREATE TABLE keyword_edges (
    src_id   INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    dst_id   INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    co_count INTEGER NOT NULL,                  -- articles containing both
    npmi     REAL    NOT NULL,                  -- normalized PMI in [0,1]
    PRIMARY KEY (src_id, dst_id),
    CHECK (src_id < dst_id)                     -- canonical: only store one direction
);
CREATE INDEX idx_edges_npmi    ON keyword_edges(npmi DESC);
CREATE INDEX idx_edges_dst     ON keyword_edges(dst_id);

-- 4. clusters: groups discovered by Louvain
CREATE TABLE clusters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    label       TEXT NOT NULL,                  -- auto-label: top-3 keywords " · " joined
    n_keywords  INTEGER NOT NULL,
    color       TEXT NOT NULL,                  -- HSL or oklch string for UI
    is_user_labeled INTEGER NOT NULL DEFAULT 0  -- 1 if user overrode auto-label
);

-- 5. graph_meta: audit log, one row per build
CREATE TABLE graph_meta (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    built_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    n_articles   INTEGER NOT NULL,              -- snapshot of article count at build
    n_keywords   INTEGER NOT NULL,
    n_edges      INTEGER NOT NULL,
    n_clusters   INTEGER NOT NULL,
    config_hash  TEXT NOT NULL,                 -- SHA-256 of glossary+aliases+blacklist+thresholds
    notes        TEXT
);
CREATE INDEX idx_graph_meta_built ON graph_meta(built_at DESC);

-- 6. Convenience view used by web layer
CREATE VIEW v_keyword_full AS
    SELECT
        k.id,
        k.term,
        k.display,
        k.doc_freq,
        k.cluster_id,
        c.label  AS cluster_label,
        c.color  AS cluster_color,
        (SELECT COUNT(*) FROM keyword_edges
         WHERE src_id = k.id OR dst_id = k.id) AS degree
    FROM keywords k
    LEFT JOIN clusters c ON c.id = k.cluster_id;
```

## Validation rules

- `keywords.term` MUST be already normalized (lowercase except acronyms, lemmatized if available, alias-resolved). The normalization layer is the only writer that creates rows in this table.
- `keywords.doc_freq` MUST equal `(SELECT COUNT(*) FROM article_keywords WHERE keyword_id = keywords.id)`. Maintained by `builder.py` after batch insert.
- `keyword_edges.src_id < dst_id`: enforced by CHECK; the application MUST swap before insert.
- `keyword_edges.npmi` MUST be in `[0, 1]`; negative or NaN values rejected.
- `clusters.color` MUST be a valid CSS color string consumable by Cytoscape.

## State / lifecycle

- **First build**: `extract-keywords --all` populates `keywords` + `article_keywords`. Then `build-graph` populates `keyword_edges` + `clusters` + writes a `graph_meta` row.
- **Incremental update**: `extract-keywords` (without `--rebuild`) processes only articles not yet in `article_keywords`. `build-graph` always rebuilds edges/clusters from scratch (cheap at this scale; consistency more important).
- **Rebuild from scratch**: `extract-keywords --rebuild` truncates `article_keywords` + `keywords` first.
- **Delete**: `articles` deletion cascades to `article_keywords`. `keywords` rows are not auto-deleted when their last `article_keywords` row goes — they're left orphaned and cleaned up at next `build-graph`.

## Stale detection (read by web layer)

```sql
-- "Is the graph stale?"
SELECT
    (SELECT COUNT(*) FROM articles)                    AS current_articles,
    (SELECT n_articles FROM graph_meta
       ORDER BY built_at DESC LIMIT 1)                AS last_build_articles,
    (SELECT built_at FROM graph_meta
       ORDER BY built_at DESC LIMIT 1)                AS last_built_at;
```

If `current_articles - last_build_articles >= 5%` of `current_articles`, web UI shows "stale — run `star-crawl build-graph`" banner.

## Migration

`003_star_graph.sql` in `src/star_crawl/migrations/`. Idempotent via `CREATE TABLE IF NOT EXISTS`.

## Sizing estimate

For 10k articles:

- `article_keywords`: ~10k × 15 = 150k rows × ~50 bytes ≈ 7.5 MB
- `keywords`: ~3k rows × ~120 bytes ≈ 350 KB
- `keyword_edges` (after pruning): ~5–10k rows × ~40 bytes ≈ 400 KB
- `clusters`: ~10–20 rows ≈ negligible
- `graph_meta`: < 100 rows ever ≈ negligible

Total feature footprint ≈ 9 MB on top of the corpus. Comfortable.
