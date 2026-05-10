"""Language detection filter."""

from __future__ import annotations

from langdetect import DetectorFactory, detect_langs

DetectorFactory.seed = 0  # deterministic results


def detect_language(text: str, *, min_confidence: float = 0.9) -> str | None:
    """Detect ISO-639-1 language code; return None if confidence < threshold."""
    snippet = text[:5000]  # avoid running over giant articles
    try:
        candidates = detect_langs(snippet)
    except Exception:
        return None
    if not candidates:
        return None
    top = candidates[0]
    if top.prob >= min_confidence:
        return top.lang
    return None
