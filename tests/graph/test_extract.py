"""Extract pipeline tests using a fake KeyBERT."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from star_crawl.db import migrate as db_migrate
from star_crawl.db.connection import connect
from star_crawl.graph import extract
from star_crawl.graph.glossary import Glossary
from star_crawl.graph.runner import extract_corpus


@dataclass
class FakeExtractor:
    """Returns scripted responses keyed by article body content."""

    responses: dict[str, list[tuple[str, float]]] = field(default_factory=dict)
    fallback: list[tuple[str, float]] = field(default_factory=list)
    calls: int = 0

    def extract(self, text: str) -> list[tuple[str, float]]:
        self.calls += 1
        for marker, resp in self.responses.items():
            if marker in text:
                return resp
        return list(self.fallback)


def _seed_corpus(tmp_path: Path) -> None:
    db_migrate.migrate(tmp_path)
    conn = connect(tmp_path)
    try:
        conn.execute(
            "INSERT INTO sources (name, display_name, base_url, fetcher, "
            "seed_strategy, config_json) VALUES (?, ?, ?, ?, ?, ?)",
            ("grab", "Grab", "https://example.com", "http", "rss", "{}"),
        )
        body_a = (
            "We use Kafka and Kubernetes for our event-driven pipeline. "
            "PostgreSQL stores everything else."
        )
        body_b = (
            "A piece about Postgres replication and backup strategies. "
            "No streaming here."
        )
        conn.execute(
            "INSERT INTO articles (source_name, url, title, content_text, "
            "content_md, word_count, content_hash, lang) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?)",
            ("grab", "https://e.com/a", "Kafka stuff", body_a, "body", 100, "h_a", "en"),
        )
        conn.execute(
            "INSERT INTO articles (source_name, url, title, content_text, "
            "content_md, word_count, content_hash, lang) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?)",
            ("grab", "https://e.com/b", "Other", body_b, "body", 100, "h_b", "en"),
        )
        conn.commit()
    finally:
        conn.close()


def _glossary() -> Glossary:
    return Glossary(
        display_by_term={
            "kafka": "Kafka",
            "kubernetes": "Kubernetes",
            "postgresql": "PostgreSQL",
        },
        aliases={"k8s": "kubernetes", "postgres": "postgresql"},
        blacklist={"team", "system"},
    )


@pytest.mark.integration
def test_glossary_hits_match_words(tmp_path: Path):
    g = _glossary()
    text = "We use K8s and PostgreSQL extensively. Postgres rocks."
    hits = extract.glossary_hits(text, g)
    terms = {h[0] for h in hits}
    # K8s isn't in the glossary directly — we matched glossary terms as-is.
    # 'PostgreSQL' is a glossary term so it appears.
    assert "PostgreSQL" in terms


@pytest.mark.integration
def test_merge_normalize_and_dedup(tmp_path: Path):
    g = _glossary()
    keybert = [("Kafka stream", 0.62), ("kubernetes", 0.55), ("system", 0.9), ("k8s", 0.40)]
    glossary = [("Kafka", 1.0), ("Kubernetes", 1.0)]
    merged = extract.merge_and_normalize(keybert, glossary, g)
    norms = {m[0]: m for m in merged}

    # 'system' blacklisted → dropped
    assert "system" not in norms
    # 'k8s' alias resolved to 'kubernetes' → unified with glossary hit
    assert "kubernetes" in norms
    assert norms["kubernetes"][3] in (extract.KIND_GLOSSARY, extract.KIND_BOTH)
    # 'kafka stream' normalized
    assert any(n.startswith("kafka") for n in norms)


@pytest.mark.integration
def test_extract_corpus_writes_keywords(tmp_path: Path):
    _seed_corpus(tmp_path)
    fake = FakeExtractor(
        responses={
            "Kafka stuff": [("event-driven pipeline", 0.71), ("stream", 0.55)],
            "Other": [("postgres replication", 0.61), ("backup strategies", 0.45)],
        }
    )
    stats = extract_corpus(
        extractor=fake, glossary=_glossary(), data_dir=tmp_path,
    )
    assert stats.articles_processed == 2
    assert stats.keywords_total > 0

    conn = connect(tmp_path)
    try:
        kws = {r["term"]: r for r in conn.execute("SELECT * FROM keywords").fetchall()}
        # Glossary hits present
        assert "kafka" in kws or "kubernetes" in kws or "postgresql" in kws
        # alias 'postgres' resolved → 'postgresql'
        assert "postgres" not in kws
        # blacklisted not present
        assert "team" not in kws and "system" not in kws

        link_count = conn.execute("SELECT COUNT(*) FROM article_keywords").fetchone()[0]
        assert link_count > 0
        # doc_freq updated
        nonzero = conn.execute(
            "SELECT COUNT(*) FROM keywords WHERE doc_freq > 0"
        ).fetchone()[0]
        assert nonzero > 0
    finally:
        conn.close()


@pytest.mark.integration
def test_extract_skip_already_processed(tmp_path: Path):
    _seed_corpus(tmp_path)
    fake = FakeExtractor(fallback=[("kafka stream", 0.6)])
    s1 = extract_corpus(extractor=fake, glossary=_glossary(), data_dir=tmp_path)
    initial_calls = fake.calls
    assert s1.articles_processed == 2

    # Second pass — should skip both articles
    s2 = extract_corpus(extractor=fake, glossary=_glossary(), data_dir=tmp_path)
    assert s2.articles_processed == 0
    # No additional calls because there's no work
    assert fake.calls == initial_calls


@pytest.mark.integration
def test_extract_rebuild_redoes_everything(tmp_path: Path):
    _seed_corpus(tmp_path)
    fake = FakeExtractor(fallback=[("kafka", 0.6)])
    extract_corpus(extractor=fake, glossary=_glossary(), data_dir=tmp_path)
    s2 = extract_corpus(
        extractor=fake, glossary=_glossary(), data_dir=tmp_path, rebuild=True,
    )
    assert s2.articles_processed == 2  # re-did both
