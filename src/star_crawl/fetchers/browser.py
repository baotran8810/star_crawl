"""Browser fetcher backed by Playwright.

Lazy-imports playwright so the default install footprint stays small.
Used only when a source declares fetcher: browser.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from star_crawl.core.schemas import DEFAULT_USER_AGENT, FetchResult, SourceConfig

if TYPE_CHECKING:
    from playwright.async_api import Browser, Playwright


# Realistic Chrome UA used when source policy keeps the project default.
# Anti-bot systems (Cloudflare, Uber's def.uber.com, etc.) flag uncommon UAs.
_REALISTIC_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Substrings in a final URL that indicate an anti-bot interstitial.
_CHALLENGE_MARKERS = ("/challenge", "cf-chl", "captcha", "/cdn-cgi/")


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
        ua = source.policy.user_agent
        if ua == DEFAULT_USER_AGENT:
            ua = _REALISTIC_UA
        context = await browser.new_context(
            user_agent=ua,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/Los_Angeles",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
            },
        )
        try:
            page = await context.new_page()
            try:
                response: Any = await page.goto(
                    url,
                    wait_until=source.browser.wait_until,
                    timeout=source.browser.timeout_ms,
                )
                status = response.status if response else 200
                headers = dict(response.headers) if response else {}

                # If we landed on an anti-bot interstitial, wait for it to clear.
                final_url = page.url
                target_host = urlparse(url).hostname
                if _looks_like_challenge(final_url, target_host):
                    try:
                        await page.wait_for_url(
                            lambda u: not _looks_like_challenge(u, target_host),
                            timeout=source.browser.timeout_ms,
                        )
                    except Exception:
                        # Fall through with whatever HTML we have; pipeline will
                        # log it as a quality/extract error.
                        pass
                    final_url = page.url

                html = await page.content()
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


def _looks_like_challenge(current_url: str, target_host: str | None) -> bool:
    if any(marker in current_url for marker in _CHALLENGE_MARKERS):
        return True
    # Off-host redirect to a sibling subdomain on the SAME registered domain
    # (e.g. www.uber.com → def.uber.com) is the typical anti-bot pattern.
    parsed = urlparse(current_url)
    if target_host and parsed.hostname and parsed.hostname != target_host:
        if _same_etld_plus_one(parsed.hostname, target_host):
            return True
    return False


def _same_etld_plus_one(host_a: str, host_b: str) -> bool:
    """Crude eTLD+1 comparison — last two labels match (good enough for blog hosts)."""
    a = host_a.lower().split(".")[-2:]
    b = host_b.lower().split(".")[-2:]
    return a == b and len(a) == 2
