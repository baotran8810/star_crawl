"""robots.txt and policy gating.

Constitution principle II — polite-by-default. A source whose robots.txt
disallows our user-agent is skipped unless BOTH the source config and the
CLI explicitly opt in.
"""

from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from star_crawl.core.schemas import SourceConfig


class RobotsChecker:
    """Per-domain robots.txt cache + lookup."""

    def __init__(self) -> None:
        self._cache: dict[str, RobotFileParser] = {}

    def is_allowed(self, url: str, user_agent: str) -> bool:
        domain = self._domain(url)
        rp = self._cache.get(domain)
        if rp is None:
            rp = RobotFileParser()
            rp.set_url(f"{domain}/robots.txt")
            try:
                rp.read()
            except Exception:
                # Network failure or 404 — be permissive (most sites)
                rp = _AllowAll()
            self._cache[domain] = rp
        return rp.can_fetch(user_agent, url)

    @staticmethod
    def _domain(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"


class _AllowAll:
    """Fallback when robots.txt cannot be fetched — permit everything."""

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
