"""Integration tests for pagination + sitemap seeders."""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from star_crawl.core.schemas import SourceConfig
from star_crawl.seeders.pagination import PaginationSeeder
from star_crawl.seeders.sitemap import SitemapSeeder

INDEX_PAGE_1 = """
<html><body>
<a href="/blog/zero-growth-stack/">Zero growth</a>
<a href="/blog/five-layers-cloud/">Five layers</a>
<a href="/about">About</a>
<a href="/blog/engineering/page/2/">Next</a>
</body></html>
"""

INDEX_PAGE_2 = """
<html><body>
<a href="/blog/ansible-automation/">Ansible</a>
<a href="/blog/bank-grade-privacy/">Privacy</a>
</body></html>
"""

INDEX_PAGE_3_EMPTY = "<html><body><p>End.</p></body></html>"


@pytest.mark.integration
def test_pagination_seeder_walks_pages_and_filters():
    cfg = SourceConfig(
        name="uber_engineering",
        display_name="Uber",
        base_url="https://www.uber.com/us/en/blog/engineering/",
        fetcher="http",
        seed={
            "strategy": "pagination",
            "template": "https://www.uber.com/us/en/blog/engineering/page/{n}/",
            "range": [1, 5],
        },
        url_filter=r"^https://www\.uber\.com/blog/[^/]+/$",
        policy={"respect_robots": False},
    )

    async def _go():
        with respx.mock(assert_all_called=False) as router:
            router.get(
                "https://www.uber.com/us/en/blog/engineering/page/1/"
            ).mock(return_value=httpx.Response(200, text=INDEX_PAGE_1))
            router.get(
                "https://www.uber.com/us/en/blog/engineering/page/2/"
            ).mock(return_value=httpx.Response(200, text=INDEX_PAGE_2))
            router.get(
                "https://www.uber.com/us/en/blog/engineering/page/3/"
            ).mock(return_value=httpx.Response(200, text=INDEX_PAGE_3_EMPTY))
            router.get(
                "https://www.uber.com/us/en/blog/engineering/page/4/"
            ).mock(return_value=httpx.Response(200, text=INDEX_PAGE_3_EMPTY))

            urls = []
            seeder = PaginationSeeder()
            async for u in seeder.seed(cfg):
                urls.append(u)
            return urls

    urls = asyncio.run(_go())
    # Both pages with content yielded their blog links;
    # /about excluded by url_filter, two empty pages stop pagination early.
    assert any("zero-growth" in u for u in urls)
    assert any("ansible" in u for u in urls)
    assert not any("/about" in u for u in urls)
    assert len(urls) == 4


SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>https://example.com/sitemap-blog.xml</loc></sitemap>
</sitemapindex>
"""

SITEMAP_BLOG = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://example.com/blog/post-1</loc></url>
<url><loc>https://example.com/blog/post-2</loc></url>
<url><loc>https://example.com/about</loc></url>
</urlset>
"""


@pytest.mark.integration
def test_sitemap_seeder_follows_index_and_filters():
    cfg = SourceConfig(
        name="example_eng",
        display_name="Ex",
        base_url="https://example.com",
        fetcher="http",
        seed={"strategy": "sitemap", "url": "https://example.com/sitemap.xml"},
        url_filter=r"^https://example\.com/blog/.+",
        policy={"respect_robots": False},
    )

    async def _go():
        with respx.mock(assert_all_called=False) as router:
            router.get("https://example.com/sitemap.xml").mock(
                return_value=httpx.Response(200, text=SITEMAP_INDEX,
                                            headers={"content-type": "application/xml"})
            )
            router.get("https://example.com/sitemap-blog.xml").mock(
                return_value=httpx.Response(200, text=SITEMAP_BLOG,
                                            headers={"content-type": "application/xml"})
            )
            urls = []
            seeder = SitemapSeeder()
            async for u in seeder.seed(cfg):
                urls.append(u)
            return urls

    urls = asyncio.run(_go())
    assert "https://example.com/blog/post-1" in urls
    assert "https://example.com/blog/post-2" in urls
    assert "https://example.com/about" not in urls
