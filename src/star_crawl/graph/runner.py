"""Orchestrate keyword extraction over the corpus."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from star_crawl.db.connection import connect
from star_crawl.graph import extract
from star_crawl.graph.glossary import Glossary
from star_crawl.graph.glossary import load as load_glossary

logger = logging.getLogger(__name__)


@dataclass
class ExtractStats:
    articles_processed: int = 0
    articles_skipped: int = 0
    keywords_total: int = 0
    keywords_glossary: int = 0
    keywords_keybert: int = 0


def extract_corpus(
    *,
    extractor: extract.CandidateExtractor,
    glossary: Glossary | None = None,
    config_dir: Path | None = None,
    data_dir: Path | None = None,
    source: str | None = None,
    rebuild: bool = False,
    only_lang: str | None = "en",
) -> ExtractStats:
    """Run keyword extraction over articles not yet processed (or all if rebuild).

    `extractor` is the strategy — KeyBertExtractor in production,
    fake in tests. Pass an empty Glossary to disable boost.
    """
    glossary = glossary or load_glossary(config_dir)
    stats = ExtractStats()

    conn = connect(data_dir)
    try:
        if rebuild:
            conn.execute("DELETE FROM article_keywords")
            conn.execute("DELETE FROM keywords")
            conn.commit()

        # Fetch articles needing extraction
        params: list[object] = []
        where = []
        if source:
            where.append("a.source_name = ?")
            params.append(source)
        if only_lang:
            where.append("(a.lang = ? OR a.lang IS NULL)")
            params.append(only_lang)
        if not rebuild:
            where.append(
                "NOT EXISTS (SELECT 1 FROM article_keywords WHERE article_id = a.id)"
            )
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        rows = conn.execute(
            f"""SELECT a.id, a.title, a.content_text, a.lang
                  FROM articles a {where_sql}
                 ORDER BY a.id""",
            params,
        ).fetchall()

        for r in rows:
            text = (r["title"] or "") + "\n\n" + (r["content_text"] or "")
            if r["lang"] and r["lang"] != "en":
                stats.articles_skipped += 1
                continue
            kb_pairs = extractor.extract(text)
            gl_pairs = extract.glossary_hits(text, glossary)
            merged = extract.merge_and_normalize(kb_pairs, gl_pairs, glossary)
            extract.link_article_keywords(conn, int(r["id"]), merged)

            stats.articles_processed += 1
            for term, _, _, kind in merged:
                stats.keywords_total += 1
                if kind == extract.KIND_KEYBERT:
                    stats.keywords_keybert += 1
                else:
                    stats.keywords_glossary += 1

            if stats.articles_processed % 25 == 0:
                conn.commit()

        conn.commit()
        extract.update_doc_freq(conn)
        conn.commit()
    finally:
        conn.close()

    return stats
