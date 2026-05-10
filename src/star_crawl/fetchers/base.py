"""Fetcher protocol — strategy interface for HTTP / browser fetchers."""

from __future__ import annotations

from typing import Protocol

from star_crawl.core.schemas import FetchResult, SourceConfig


class Fetcher(Protocol):
    async def fetch(self, url: str, source: SourceConfig) -> FetchResult: ...

    async def aclose(self) -> None: ...
