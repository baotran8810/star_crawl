"""Paginated index seeder.

Walks pages `template.format(n=i)` for i in range[0]..range[1] inclusive,
extracts <a href> links, yields URLs that match the source's url_filter.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from star_crawl.core.schemas import SourceConfig
from star_crawl.seeders.base import matches_filter


class PaginationSeeder:
    async def seed(self, source: SourceConfig) -> AsyncIterator[str]:
        if source.seed.strategy != "pagination":
            raise ValueError(
                f"PaginationSeeder used for non-pagination strategy: {source.seed.strategy}"
            )
        if not source.seed.template or "{n}" not in source.seed.template:
            raise ValueError("pagination seed requires template with '{n}' placeholder")
        if not source.seed.range or len(source.seed.range) != 2:
            raise ValueError("pagination seed requires range [start, end]")

        start, end = source.seed.range
        seen: set[str] = set()

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": source.policy.user_agent},
        ) as client:
            empty_streak = 0
            for n in range(start, end + 1):
                index_url = source.seed.template.format(n=n)
                try:
                    resp = await client.get(index_url)
                except httpx.HTTPError:
                    continue
                if resp.status_code != 200:
                    # 404 ⇒ ran past the last page; stop early
                    if resp.status_code == 404:
                        break
                    continue

                page_yielded = 0
                for url in _extract_links(resp.text, base_url=str(resp.url)):
                    if url in seen:
                        continue
                    if not matches_filter(url, source):
                        continue
                    seen.add(url)
                    page_yielded += 1
                    yield url

                # If two consecutive pages produce no new links, treat as end-of-feed
                if page_yielded == 0:
                    empty_streak += 1
                    if empty_streak >= 2:
                        break
                else:
                    empty_streak = 0


def _extract_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        out.append(urljoin(base_url, href))
    return out
