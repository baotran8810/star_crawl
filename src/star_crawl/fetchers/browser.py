"""Browser fetcher backed by Playwright.

Lazy-imports playwright so the default install footprint stays small.
Used only when a source declares fetcher: browser.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from star_crawl.core.schemas import FetchResult, SourceConfig

if TYPE_CHECKING:
    from playwright.async_api import Browser, Playwright


class BrowserFetcher:
    """Single shared Playwright browser; new context per fetch for isolation."""

    def __init__(self) -> None:
        self._pw: "Playwright | None" = None
        self._browser: "Browser | None" = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self, source: SourceConfig) -> "Browser":
        async with self._lock:
            if self._browser is None:
                try:
                    from playwright.async_api import async_playwright
                except ImportError as e:
                    raise RuntimeError(
                        "browser fetcher requires the [browser] extra. "
                        "Install with `pip install -e .[browser]` and run "
                        "`playwright install chromium`."
                    ) from e

                self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch(headless=True)
            return self._browser

    async def fetch(self, url: str, source: SourceConfig) -> FetchResult:
        browser = await self._ensure_browser(source)
        context = await browser.new_context(user_agent=source.policy.user_agent)
        try:
            page = await context.new_page()
            try:
                response: Any = await page.goto(
                    url,
                    wait_until=source.browser.wait_until,
                    timeout=source.browser.timeout_ms,
                )
                html = await page.content()
                status = response.status if response else 200
                final_url = page.url
                headers = dict(response.headers) if response else {}
            finally:
                await page.close()
        finally:
            await context.close()

        return FetchResult(
            url=url,
            status=status,
            html=html,
            headers=headers,
            final_url=final_url,
        )

    async def aclose(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None
