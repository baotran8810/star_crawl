"""Term normalization: case + alias resolution.

Lowercase except short all-caps acronyms (≤4 chars all-uppercase).
Resolves alias map. Lemmatization deferred (optional, hot-loadable).
"""

from __future__ import annotations

import re

from star_crawl.graph.glossary import Glossary

_WHITESPACE = re.compile(r"\s+")


def normalize(raw: str, glossary: Glossary) -> str | None:
    """Normalize a candidate keyword. Returns None if it should be dropped."""
    cleaned = _WHITESPACE.sub(" ", raw).strip()
    if not cleaned or len(cleaned) < 2:
        return None

    # Lowercase except short all-caps acronyms (≤4 chars, all uppercase)
    if cleaned.isupper() and len(cleaned) <= 4:
        normalized = cleaned.lower()  # store lowercase for unique key
    else:
        normalized = cleaned.lower()

    # Apply alias resolution
    resolved = glossary.aliases.get(normalized, normalized)

    # Drop blacklisted
    if glossary.is_blacklisted(resolved):
        return None

    return resolved


def display_for(term: str, raw_form: str, glossary: Glossary) -> str:
    """Choose display form: glossary > original casing > title case."""
    if term in glossary.display_by_term:
        return glossary.display_by_term[term]
    # If raw form is "K8s" or similar (mixed case), preserve it
    raw = raw_form.strip()
    if raw.lower() == term and raw != raw.lower():
        return raw
    return term
