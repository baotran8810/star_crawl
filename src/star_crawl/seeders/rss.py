"""RSS / Atom feed seeder."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import feedparser
import httpx

from star_crawl.core.schemas import SourceConfig
from star_crawl.seeders.base import matches_filter


class RssSeeder:
    """Discover article URLs from an RSS or Atom feed."""

    async def seed(self, source: SourceConfig) -> AsyncIterator[str]:
        if source.seed.strategy != "rss":
            raise ValueError(f"RssSeeder used for non-rss strategy: {source.seed.strategy}")
        if source.seed.url is None:
            raise ValueError("rss seed requires url")

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": source.policy.user_agent},
        ) as client:
            resp = await client.get(str(source.seed.url))
            resp.raise_for_status()
            text = resp.text

        # feedparser is sync; offload so async event loop is not blocked
        feed = await asyncio.to_thread(feedparser.parse, text)
        for entry in feed.entries:
            link = entry.get("link")
            if not link:
                continue
            if matches_filter(link, source):
                yield link
