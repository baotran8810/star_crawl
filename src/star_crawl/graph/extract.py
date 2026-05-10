"""Keyword extraction: KeyBERT semantic + tech-glossary boost.

KeyBERT is lazy-loaded so the default install doesn't pull
sentence-transformers. Tests inject a fake extractor via the protocol.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable
from typing import Protocol

from star_crawl.graph.glossary import Glossary
from star_crawl.graph.normalize import display_for, normalize

DEFAULT_MODEL = "all-MiniLM-L6-v2"
KIND_KEYBERT = "keybert"
KIND_GLOSSARY = "glossary"
KIND_BOTH = "both"

# Match a single token boundary so "react" doesn't pick up "reaction"
_GLOSSARY_RE_CACHE: dict[str, re.Pattern] = {}


class CandidateExtractor(Protocol):
    """Strategy interface — KeyBERT in production, fake in tests."""

    def extract(self, text: str) -> list[tuple[str, float]]: ...


class KeyBertExtractor:
    """Lazy-imports KeyBERT + sentence-transformers on first use."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_MODEL,
        top_n: int = 15,
        ngram_range: tuple[int, int] = (1, 3),
        diversity: float = 0.6,
        min_score: float = 0.35,
    ) -> None:
        self.model_name = model_name
        self.top_n = top_n
        self.ngram_range = ngram_range
        self.diversity = diversity
        self.min_score = min_score
        self._kw = None

    def _model(self):
        if self._kw is None:
            try:
                from keybert import KeyBERT
            except ImportError as e:
                raise RuntimeError(
                    "extract requires the [graph] extra. "
                    "Install with `pip install -e '.[graph]'`."
                ) from e
            self._kw = KeyBERT(model=self.model_name)
        return self._kw

    def extract(self, text: str) -> list[tuple[str, float]]:
        if not text or len(text) < 100:
            return []
        kw = self._model()
        out = kw.extract_keywords(
            text,
            keyphrase_ngram_range=self.ngram_range,
            top_n=self.top_n,
            use_mmr=True,
            diversity=self.diversity,
            stop_words="english",
        )
        return [(term, float(score)) for term, score in out if score >= self.min_score]


def glossary_hits(text: str, glossary: Glossary) -> list[tuple[str, float]]:
    """Exact, word-boundary, case-insensitive match for every glossary term."""
    if not text:
        return []
    found: list[tuple[str, float]] = []
    haystack = text
    for term in glossary.display_by_term:
        # Special case: terms like "C++" can't use \b directly
        pattern = _GLOSSARY_RE_CACHE.get(term)
        if pattern is None:
            escaped = re.escape(term)
            # Use lookbehind/lookahead for non-word-char boundaries
            pattern = re.compile(rf"(?<![\w-]){escaped}(?![\w-])", re.IGNORECASE)
            _GLOSSARY_RE_CACHE[term] = pattern
        if pattern.search(haystack):
            # Score 1.0 — glossary hits are guaranteed
            found.append((glossary.display_by_term[term], 1.0))
    return found


def merge_and_normalize(
    keybert_pairs: list[tuple[str, float]],
    glossary_pairs: list[tuple[str, float]],
    glossary: Glossary,
) -> list[tuple[str, str, float, str]]:
    """Combine extractor outputs and normalize.

    Returns list of (normalized_term, display, score, source_kind).
    Glossary hits override KeyBERT scores when they collide; source_kind
    becomes 'both' when present in both lists.
    """
    keybert_terms: dict[str, tuple[str, float]] = {}
    for raw, score in keybert_pairs:
        norm = normalize(raw, glossary)
        if norm is None:
            continue
        # Keep best score per normalized term
        if norm not in keybert_terms or keybert_terms[norm][1] < score:
            keybert_terms[norm] = (raw, score)

    glossary_terms: dict[str, tuple[str, float]] = {}
    for raw, score in glossary_pairs:
        norm = normalize(raw, glossary)
        if norm is None:
            continue
        glossary_terms[norm] = (raw, score)

    all_keys = set(keybert_terms) | set(glossary_terms)
    out: list[tuple[str, str, float, str]] = []
    for term in all_keys:
        raw_form = (
            glossary_terms.get(term, (None,))[0]
            or keybert_terms.get(term, (term,))[0]
        )
        display = display_for(term, raw_form, glossary)

        if term in glossary_terms and term in keybert_terms:
            kind = KIND_BOTH
            score = max(glossary_terms[term][1], keybert_terms[term][1])
        elif term in glossary_terms:
            kind = KIND_GLOSSARY
            score = glossary_terms[term][1]
        else:
            kind = KIND_KEYBERT
            score = keybert_terms[term][1]
        out.append((term, display, score, kind))
    return out


def upsert_keyword(
    conn: sqlite3.Connection,
    *,
    term: str,
    display: str,
    source_kind: str,
) -> int:
    """Insert keyword if new, return its id. Update display + source_kind on collision."""
    row = conn.execute(
        "SELECT id, source_kind FROM keywords WHERE term = ?", (term,)
    ).fetchone()
    if row is None:
        cur = conn.execute(
            """INSERT INTO keywords (term, display, source_kind, doc_freq)
               VALUES (?, ?, ?, 0)""",
            (term, display, source_kind),
        )
        return int(cur.lastrowid)

    existing_kind = row["source_kind"] if isinstance(row, sqlite3.Row) else row[1]
    new_kind = _merge_kind(existing_kind, source_kind)
    conn.execute(
        "UPDATE keywords SET source_kind = ?, display = ? WHERE id = ?",
        (new_kind, display, row[0]),
    )
    return int(row[0])


def _merge_kind(a: str, b: str) -> str:
    if a == b:
        return a
    return KIND_BOTH


def link_article_keywords(
    conn: sqlite3.Connection,
    article_id: int,
    pairs: Iterable[tuple[str, str, float, str]],
) -> int:
    """Insert article_keywords rows. Returns count inserted."""
    inserted = 0
    for term, display, score, kind in pairs:
        kw_id = upsert_keyword(conn, term=term, display=display, source_kind=kind)
        try:
            conn.execute(
                """INSERT INTO article_keywords
                       (article_id, keyword_id, score, is_glossary)
                   VALUES (?, ?, ?, ?)""",
                (article_id, kw_id, score, int(kind != KIND_KEYBERT)),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            # Already linked — keep existing
            continue
    return inserted


def update_doc_freq(conn: sqlite3.Connection) -> None:
    """Recompute keywords.doc_freq from article_keywords."""
    conn.execute(
        """UPDATE keywords
              SET doc_freq = (
                  SELECT COUNT(*) FROM article_keywords WHERE keyword_id = keywords.id
              )"""
    )
