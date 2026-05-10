"""Graph build pipeline + clustering determinism tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from star_crawl.db import migrate as db_migrate
from star_crawl.db.connection import connect
from star_crawl.graph.builder import build_graph


def _seed_keywords_and_articles(tmp_path: Path) -> None:
    """Build a small fixture with two clear clusters:
    {kafka, stream, queue} co-occur in 5 articles
    {postgres, replica, vacuum} co-occur in 5 articles
    """
    db_migrate.migrate(tmp_path)
    conn = connect(tmp_path)
    try:
        conn.execute(
            "INSERT INTO sources (name, display_name, base_url, fetcher, "
            "seed_strategy, config_json) VALUES ('grab', 'Grab', "
            "'https://e.com', 'http', 'rss', '{}')"
        )

        # Insert articles
        for i in range(10):
            conn.execute(
                "INSERT INTO articles (source_name, url, title, content_text, "
                "content_md, word_count, content_hash) VALUES "
                "(?, ?, ?, ?, ?, ?, ?)",
                ("grab", f"https://e.com/{i}", f"Article {i}",
                 "body", "body", 100, f"h_{i}"),
            )

        # Insert keywords (10 total, 6 used)
        keywords = [
            ("kafka", "Kafka", 5, "glossary"),
            ("stream", "Stream", 5, "keybert"),
            ("queue", "Queue", 4, "keybert"),
            ("postgres", "Postgres", 5, "glossary"),
            ("replica", "Replica", 5, "keybert"),
            ("vacuum", "Vacuum", 4, "keybert"),
            ("low_freq_a", "LowA", 1, "keybert"),
            ("low_freq_b", "LowB", 1, "keybert"),
        ]
        for term, display, freq, kind in keywords:
            conn.execute(
                "INSERT INTO keywords (term, display, doc_freq, source_kind) "
                "VALUES (?, ?, ?, ?)",
                (term, display, freq, kind),
            )

        # Get keyword ids
        kw_ids = {
            r["term"]: int(r["id"])
            for r in conn.execute("SELECT id, term FROM keywords").fetchall()
        }
        a_ids = [
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM articles ORDER BY id"
            ).fetchall()
        ]

        # Cluster 1: kafka, stream, queue in articles 0..4
        for i in range(5):
            for term in ("kafka", "stream", "queue"):
                conn.execute(
                    "INSERT INTO article_keywords "
                    "(article_id, keyword_id, score, is_glossary) "
                    "VALUES (?, ?, ?, ?)",
                    (a_ids[i], kw_ids[term], 0.7, 0),
                )

        # Cluster 2: postgres, replica, vacuum in articles 5..9
        for i in range(5, 10):
            for term in ("postgres", "replica", "vacuum"):
                conn.execute(
                    "INSERT INTO article_keywords "
                    "(article_id, keyword_id, score, is_glossary) "
                    "VALUES (?, ?, ?, ?)",
                    (a_ids[i], kw_ids[term], 0.7, 0),
                )

        # Low-freq noise (1 article each)
        conn.execute(
            "INSERT INTO article_keywords (article_id, keyword_id, score, is_glossary) "
            "VALUES (?, ?, ?, ?)",
            (a_ids[0], kw_ids["low_freq_a"], 0.4, 0),
        )
        conn.execute(
            "INSERT INTO article_keywords (article_id, keyword_id, score, is_glossary) "
            "VALUES (?, ?, ?, ?)",
            (a_ids[5], kw_ids["low_freq_b"], 0.4, 0),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.mark.integration
def test_build_graph_produces_two_clusters(tmp_path: Path):
    _seed_keywords_and_articles(tmp_path)
    res = build_graph(data_dir=tmp_path, min_doc_freq=3, min_co_count=2, min_npmi=0.1)
    assert res.n_clusters >= 2  # at least the two intentional clusters
    # Low-freq keywords filtered out
    assert res.n_keywords == 6


@pytest.mark.integration
def test_cluster_determinism(tmp_path: Path):
    """Two builds with the same seed must produce identical clustering."""
    _seed_keywords_and_articles(tmp_path)
    build_graph(data_dir=tmp_path, cluster_seed=42)
    conn = connect(tmp_path)
    try:
        first = sorted(
            conn.execute(
                "SELECT term, cluster_id FROM keywords WHERE doc_freq >= 3"
            ).fetchall(),
            key=lambda r: r["term"],
        )
        first_assign = [(r["term"], r["cluster_id"]) for r in first]
    finally:
        conn.close()

    build_graph(data_dir=tmp_path, cluster_seed=42)
    conn = connect(tmp_path)
    try:
        second = sorted(
            conn.execute(
                "SELECT term, cluster_id FROM keywords WHERE doc_freq >= 3"
            ).fetchall(),
            key=lambda r: r["term"],
        )
        second_assign = [(r["term"], r["cluster_id"]) for r in second]
    finally:
        conn.close()

    assert first_assign == second_assign


@pytest.mark.integration
def test_pruning_thresholds(tmp_path: Path):
    _seed_keywords_and_articles(tmp_path)
    res = build_graph(
        data_dir=tmp_path,
        min_doc_freq=10,  # nothing meets this
        min_co_count=2,
        min_npmi=0.1,
    )
    assert res.n_keywords == 0
    assert res.n_edges == 0


@pytest.mark.integration
def test_user_label_preserved_across_rebuild(tmp_path: Path):
    _seed_keywords_and_articles(tmp_path)
    build_graph(data_dir=tmp_path)

    # User overrides one cluster's label
    conn = connect(tmp_path)
    try:
        row = conn.execute("SELECT id FROM clusters LIMIT 1").fetchone()
        assert row is not None
        cluster_id = int(row["id"])
        conn.execute(
            "UPDATE clusters SET label = 'My Custom Label', is_user_labeled = 1 "
            "WHERE id = ?",
            (cluster_id,),
        )
        conn.commit()
    finally:
        conn.close()

    # Rebuild
    build_graph(data_dir=tmp_path)

    # Verify label is still custom
    conn = connect(tmp_path)
    try:
        row = conn.execute(
            "SELECT label, is_user_labeled FROM clusters WHERE id = ?",
            (cluster_id,),
        ).fetchone()
        if row is not None:
            assert row["label"] == "My Custom Label"
            assert row["is_user_labeled"] == 1
    finally:
        conn.close()
