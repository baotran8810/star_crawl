"""HTTP fetcher — httpx async client with per-domain rate limit + retry."""

from __future__ import annotations

import asyncio
import random
import time
from collections import defaultdict
from urllib.parse import urlparse

import httpx

from star_crawl.core.schemas import FetchResult, SourceConfig


class _TokenBucket:
    """Simple token bucket: replenish at `rps` tokens/sec, max=burst."""

    def __init__(self, rps: float, burst: int = 1) -> None:
        self.rps = rps
        self.capacity = max(1, burst)
        self.tokens = float(self.capacity)
        self.updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rps)
                self.updated = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = max(0.0, (1.0 - self.tokens) / self.rps)
                await asyncio.sleep(wait)


class HttpFetcher:
    """Async HTTP fetcher with per-domain rate limit + concurrency caps."""

    def __init__(self, *, default_rps: float = 1.0) -> None:
        self._client: httpx.AsyncClient | None = None
        self._default_rps = default_rps
        self._buckets: dict[str, _TokenBucket] = {}
        self._semaphores: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(5)
        )

    def _client_or_init(self, source: SourceConfig) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                follow_redirects=True,
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"User-Agent": source.policy.user_agent},
            )
        return self._client

    def _bucket(self, source: SourceConfig, url: str) -> _TokenBucket:
        key = self._key(source, url)
        if key not in self._buckets:
            self._buckets[key] = _TokenBucket(source.rate_limit.rps)
        return self._buckets[key]

    def _semaphore(self, source: SourceConfig, url: str) -> asyncio.Semaphore:
        key = self._key(source, url)
        if key not in self._semaphores:
            self._semaphores[key] = asyncio.Semaphore(source.rate_limit.concurrency)
        return self._semaphores[key]

    @staticmethod
    def _key(source: SourceConfig, url: str) -> str:
        if source.rate_limit.per_domain:
            return urlparse(url).netloc
        return source.name

    async def fetch(self, url: str, source: SourceConfig) -> FetchResult:
        client = self._client_or_init(source)
        sem = self._semaphore(source, url)
        bucket = self._bucket(source, url)

        last_err: Exception | None = None
        for attempt in range(1, source.retry.max_attempts + 1):
            async with sem:
                await bucket.acquire()
                try:
                    resp = await client.get(url)
                except httpx.HTTPError as e:
                    last_err = e
                    await self._backoff(attempt, source, retry_after=None)
                    continue

            if resp.status_code == 429 or resp.status_code >= 500:
                retry_after = self._parse_retry_after(resp)
                await self._backoff(attempt, source, retry_after=retry_after)
                continue

            return FetchResult(
                url=url,
                status=resp.status_code,
                html=resp.text,
                headers=dict(resp.headers),
                final_url=str(resp.url),
            )

        raise httpx.HTTPError(
            f"fetch failed after {source.retry.max_attempts} attempts: {last_err}"
        )

    async def _backoff(
        self,
        attempt: int,
        source: SourceConfig,
        retry_after: float | None,
    ) -> None:
        if retry_after is not None and source.retry.honor_retry_after:
            wait = min(retry_after, source.retry.backoff_cap)
        else:
            wait = min(
                source.retry.backoff_base ** attempt + random.uniform(0, 1),
                source.retry.backoff_cap,
            )
        await asyncio.sleep(wait)

    @staticmethod
    def _parse_retry_after(resp: httpx.Response) -> float | None:
        ra = resp.headers.get("Retry-After")
        if not ra:
            return None
        try:
            return float(ra)
        except ValueError:
            return None

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
