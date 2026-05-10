"""Trafilatura primary extractor."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

import trafilatura
from trafilatura.metadata import extract_metadata

from star_crawl.core.schemas import Document


class TrafilaturaExtractor:
    def extract(self, html: str, url: str) -> Document | None:
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
            output_format="txt",
        )
        if not text:
            return None
        text = text.strip()
        if not text:
            return None

        md = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
            output_format="markdown",
        ) or text

        meta = extract_metadata(html, default_url=url)
        title = (meta.title if meta else None) or _fallback_title(html)
        if not title:
            return None

        author = meta.author if meta else None
        published_at = _parse_date(meta.date if meta else None)
        canonical_url = (meta.url if meta and meta.url and meta.url != url else None)
        word_count = len(text.split())

        content_hash = hashlib.sha256(_normalize_for_hash(text).encode("utf-8")).hexdigest()
        meta_dump = None
        if meta:
            try:
                meta_dump = json.dumps(meta.as_dict(), default=str)
            except Exception:
                meta_dump = None

        return Document(
            url=url,
            canonical_url=canonical_url,
            title=title.strip(),
            content_text=text,
            content_md=md.strip(),
            author=author,
            published_at=published_at,
            lang=None,  # set by language filter
            word_count=word_count,
            content_hash=content_hash,
            metadata_json=meta_dump,
        )


_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _fallback_title(html: str) -> str | None:
    m = _TITLE_RE.search(html)
    if m:
        return m.group(1).strip()
    return None


def _parse_date(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _normalize_for_hash(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())
