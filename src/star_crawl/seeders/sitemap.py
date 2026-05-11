"""Sitemap seeder — walks XML sitemaps and sitemap-index files."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from bs4 import BeautifulSoup

from star_crawl.core.schemas import SourceConfig
from star_crawl.seeders.base import matches_filter


class SitemapSeeder:
    async def seed(self, source: SourceConfig) -> AsyncIterator[str]:
        if source.seed.strategy != "sitemap":
            raise ValueError(
                f"SitemapSeeder used for non-sitemap strategy: {source.seed.strategy}"
            )
        if source.seed.url is None:
            raise ValueError("sitemap seed requires url")

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": source.policy.user_agent,
                "Accept": "application/xml, text/xml, application/rss+xml, */*;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
            },
        ) as client:
            seen: set[str] = set()
            async for url in self._walk(
                client, str(source.seed.url), source.seed.follow_index
            ):
                if url in seen:
                    continue
                seen.add(url)
                if matches_filter(url, source):
                    yield url

    async def _walk(
        self,
        client: httpx.AsyncClient,
        url: str,
        follow_index: bool,
    ) -> AsyncIterator[str]:
        try:
            resp = await client.get(url)
        except httpx.HTTPError:
            return
        if resp.status_code != 200:
            return

        soup = BeautifulSoup(resp.text, "xml")

        # sitemap-index? recurse if allowed
        if soup.find("sitemapindex") and follow_index:
            for sm in soup.find_all("sitemap"):
                loc = sm.find("loc")
                if loc and loc.text.strip():
                    async for inner in self._walk(client, loc.text.strip(), follow_index):
                        yield inner
            return

        # urlset
        for u in soup.find_all("url"):
            loc = u.find("loc")
            if loc and loc.text.strip():
                yield loc.text.strip()
