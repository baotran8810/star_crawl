"""Extractor protocol."""

from __future__ import annotations

from typing import Protocol

from star_crawl.core.schemas import Document


class ExtractionFailed(Exception):
    """Raised when no extractor (primary + fallback) produces usable content."""


class Extractor(Protocol):
    def extract(self, html: str, url: str) -> Document | None: ...
