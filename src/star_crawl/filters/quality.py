"""Quality filter — paywall sniff + min word count."""

from __future__ import annotations

PAYWALL_MARKERS = (
    "subscribe to read",
    "this story is exclusive to",
    "members-only story",
    "create an account to read",
    "sign in to continue",
    "you have read your free",
)


def is_paywall(text: str) -> bool:
    haystack = text.lower()[:4000]
    return any(marker in haystack for marker in PAYWALL_MARKERS)


def meets_minimum_length(text: str, min_word_count: int) -> bool:
    return len(text.split()) >= min_word_count
