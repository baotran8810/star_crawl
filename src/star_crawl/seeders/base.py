"""Seeder protocol — discovers article URLs for a source."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Protocol

from star_crawl.core.schemas import SourceConfig


class Seeder(Protocol):
    async def seed(self, source: SourceConfig) -> AsyncIterator[str]: ...


def matches_filter(url: str, source: SourceConfig) -> bool:
    return re.match(source.url_filter, url) is not None
