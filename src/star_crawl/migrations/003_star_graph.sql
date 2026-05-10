-- Star-graph schema: keywords, article_keywords, keyword_edges, clusters, graph_meta

CREATE TABLE IF NOT EXISTS keywords (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    term        TEXT NOT NULL UNIQUE,
    display     TEXT NOT NULL,
    doc_freq    INTEGER NOT NULL DEFAULT 0,
    source_kind TEXT NOT NULL,
    cluster_id  INTEGER,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_keywords_doc_freq ON keywords(doc_freq DESC);
CREATE INDEX IF NOT EXISTS idx_keywords_cluster  ON keywords(cluster_id);

CREATE TABLE IF NOT EXISTS article_keywords (
    article_id   INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    keyword_id   INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    score        REAL    NOT NULL,
    is_glossary  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (article_id, keyword_id)
);
CREATE INDEX IF NOT EXISTS idx_ak_keyword ON article_keywords(keyword_id);
CREATE INDEX IF NOT EXISTS idx_ak_article ON article_keywords(article_id);

CREATE TABLE IF NOT EXISTS clusters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    label           TEXT NOT NULL,
    n_keywords      INTEGER NOT NULL,
    color           TEXT NOT NULL,
    is_user_labeled INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS keyword_edges (
    src_id   INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    dst_id   INTEGER NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
    co_count INTEGER NOT NULL,
    npmi     REAL    NOT NULL,
    PRIMARY KEY (src_id, dst_id),
    CHECK (src_id < dst_id)
);
CREATE INDEX IF NOT EXISTS idx_edges_npmi ON keyword_edges(npmi DESC);
CREATE INDEX IF NOT EXISTS idx_edges_dst  ON keyword_edges(dst_id);

CREATE TABLE IF NOT EXISTS graph_meta (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    built_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    n_articles   INTEGER NOT NULL,
    n_keywords   INTEGER NOT NULL,
    n_edges      INTEGER NOT NULL,
    n_clusters   INTEGER NOT NULL,
    config_hash  TEXT NOT NULL,
    notes        TEXT
);
CREATE INDEX IF NOT EXISTS idx_graph_meta_built ON graph_meta(built_at DESC);

-- Convenience view for the web UI
DROP VIEW IF EXISTS v_keyword_full;
CREATE VIEW v_keyword_full AS
    SELECT
        k.id, k.term, k.display, k.doc_freq, k.cluster_id,
        c.label  AS cluster_label,
        c.color  AS cluster_color,
        (SELECT COUNT(*) FROM keyword_edges
         WHERE src_id = k.id OR dst_id = k.id) AS degree
    FROM keywords k
    LEFT JOIN clusters c ON c.id = k.cluster_id;
