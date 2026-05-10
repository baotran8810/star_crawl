-- FTS5 virtual table for article search (web UI)

CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    title,
    content_text,
    content=articles,
    content_rowid=id,
    tokenize='porter unicode61 remove_diacritics 1'
);

CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
    INSERT INTO articles_fts(rowid, title, content_text)
    VALUES (new.id, new.title, new.content_text);
END;

CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, content_text)
    VALUES ('delete', old.id, old.title, old.content_text);
END;

CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
    INSERT INTO articles_fts(articles_fts, rowid, title, content_text)
    VALUES ('delete', old.id, old.title, old.content_text);
    INSERT INTO articles_fts(rowid, title, content_text)
    VALUES (new.id, new.title, new.content_text);
END;

-- Backfill on first apply (no-op when articles is empty)
INSERT INTO articles_fts(rowid, title, content_text)
    SELECT id, title, content_text FROM articles
    WHERE id NOT IN (SELECT rowid FROM articles_fts);
