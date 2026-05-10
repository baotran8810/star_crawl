"""Extractor tests against fixture HTML."""

from __future__ import annotations

from pathlib import Path

import pytest

from star_crawl.extractors.readability_x import ReadabilityExtractor
from star_crawl.extractors.trafilatura_x import TrafilaturaExtractor

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _grab_html() -> str:
    return (FIXTURES / "grab" / "sample_article.html").read_text(encoding="utf-8")


@pytest.mark.unit
def test_trafilatura_extracts_grab_article():
    html = _grab_html()
    doc = TrafilaturaExtractor().extract(html, "https://engineering.grab.com/sample")
    assert doc is not None
    assert "real-time event pipeline" in doc.title.lower()
    assert "kafka" in doc.content_text.lower()
    assert doc.word_count >= 100
    assert doc.content_hash  # SHA-256 produced
    # boilerplate stripped
    assert "all rights reserved" not in doc.content_text.lower()
    assert "another article" not in doc.content_text.lower()


@pytest.mark.unit
def test_readability_fallback_extracts_grab_article():
    html = _grab_html()
    doc = ReadabilityExtractor().extract(html, "https://engineering.grab.com/sample")
    assert doc is not None
    assert doc.title
    assert "kafka" in doc.content_text.lower()


@pytest.mark.unit
def test_extractors_return_none_on_garbage():
    garbage = "<html><body></body></html>"
    assert TrafilaturaExtractor().extract(garbage, "https://example.com") is None


@pytest.mark.unit
def test_dedup_via_content_hash():
    html = _grab_html()
    a = TrafilaturaExtractor().extract(html, "https://engineering.grab.com/a")
    b = TrafilaturaExtractor().extract(html, "https://engineering.grab.com/b")
    assert a is not None and b is not None
    # same body → same hash even if URLs differ
    assert a.content_hash == b.content_hash
