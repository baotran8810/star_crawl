"""robots.txt and policy gating.

Constitution principle II — polite-by-default. A source whose robots.txt
disallows our user-agent is skipped unless BOTH the source config and the
CLI explicitly opt in.

Implementation note: `urllib.robotparser` has a built-in fetcher that's
brittle on modern sites (no compression, no system TLS, no Accept header).
We use httpx to fetch then hand the text to RobotFileParser.parse(), which
is robust.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from star_crawl.core.schemas import SourceConfig

logger = logging.getLogger(__name__)


class RobotsChecker:
    """Per-domain robots.txt cache + lookup."""

    def __init__(self) -> None:
        self._cache: dict[str, RobotFileParser | _AllowAll] = {}

    def is_allowed(self, url: str, user_agent: str) -> bool:
        domain = self._domain(url)
        rp = self._cache.get(domain)
        if rp is None:
            rp = self._fetch(domain, user_agent)
            self._cache[domain] = rp
        return rp.can_fetch(user_agent, url)

    @staticmethod
    def _fetch(domain: str, user_agent: str) -> RobotFileParser | "_AllowAll":
        """Fetch robots.txt via httpx (so SSL + gzip Just Work)."""
        url = f"{domain}/robots.txt"
        try:
            resp = httpx.get(
                url,
                timeout=10.0,
                follow_redirects=True,
                headers={
                    "User-Agent": user_agent,
                    "Accept": "text/plain, */*",
                },
            )
        except httpx.HTTPError as e:
            logger.debug("robots fetch failed for %s: %s — allowing", domain, e)
            return _AllowAll()

        if resp.status_code in (401, 403):
            # 401/403 on robots.txt = treat as "everything disallowed" per RFC
            rp = RobotFileParser()
            rp.disallow_all = True
            return rp
        if resp.status_code >= 400:
            # 404 / 5xx → permissive (standard practice)
            return _AllowAll()

        rp = RobotFileParser()
        rp.parse(resp.text.splitlines())
        return rp

    @staticmethod
    def _domain(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"


class _AllowAll:
    """Fallback when robots.txt is unreachable or returns 4xx (non-403)."""

    def can_fetch(self, user_agent: str, url: str) -> bool:
        return True


def gate(source: SourceConfig, allow_policy_blocked_flag: bool) -> tuple[bool, str | None]:
    """Decide whether to crawl a source.

    Returns (allowed, reason). When allowed is False, reason explains why.
    Both source.policy.policy_opt_in and the CLI flag must be true to
    bypass a robots-block; either alone is rejected.
    """
    if not source.policy.respect_robots:
        return True, None

    checker = RobotsChecker()
    base_url = str(source.base_url)
    if checker.is_allowed(base_url, source.policy.user_agent):
        return True, None

    if source.policy.policy_opt_in and allow_policy_blocked_flag:
        return True, "policy-blocked but explicit opt-in"

    if source.policy.policy_opt_in and not allow_policy_blocked_flag:
        return False, (
            f"source '{source.name}' is policy-opt-in in YAML but missing "
            f"--allow-policy-blocked CLI flag"
        )

    return False, (
        f"source '{source.name}' is disallowed by robots.txt for user-agent "
        f"'{source.policy.user_agent}'"
    )
