"""Readability fallback extractor."""

from __future__ import annotations

import hashlib
import re

from bs4 import BeautifulSoup
from readability import Document as ReadabilityDoc

from star_crawl.core.schemas import Document


class ReadabilityExtractor:
    def extract(self, html: str, url: str) -> Document | None:
        try:
            doc = ReadabilityDoc(html)
            title = (doc.short_title() or doc.title() or "").strip()
            summary_html = doc.summary()
        except Exception:
            return None

        if not title or not summary_html:
            return None

        soup = BeautifulSoup(summary_html, "lxml")
        text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
        md = soup.get_text(separator="\n\n").strip()
        if not text:
            return None

        word_count = len(text.split())
        content_hash = hashlib.sha256(text.lower().encode("utf-8")).hexdigest()

        return Document(
            url=url,
            title=title,
            content_text=text,
            content_md=md,
            word_count=word_count,
            content_hash=content_hash,
        )
