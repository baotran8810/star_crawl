"""Pydantic schemas for star_crawl.

Source configs (loaded from configs/sources/*.yaml) and runtime documents.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

DEFAULT_USER_AGENT = (
    "star_crawl/0.1 (+https://github.com/baotran8810/star_crawl)"
)

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]+$")


class RateLimit(BaseModel):
    rps: float = 1.0
    concurrency: int = 5
    per_domain: bool = True

    @field_validator("rps")
    @classmethod
    def _rps_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("rate_limit.rps must be > 0")
        return v

    @field_validator("concurrency")
    @classmethod
    def _concurrency_min(cls, v: int) -> int:
        if v < 1:
            raise ValueError("rate_limit.concurrency must be >= 1")
        return v


class RetryPolicy(BaseModel):
    max_attempts: int = 3
    backoff_base: float = 2.0
    backoff_cap: float = 30.0
    honor_retry_after: bool = True


class ExtractConfig(BaseModel):
    primary: Literal["trafilatura", "readability"] = "trafilatura"
    fallback: Literal["trafilatura", "readability", "none"] = "readability"
    parse_jsonld: bool = True
    min_word_count: int = 100


class DedupConfig(BaseModel):
    enabled: bool = True
    use_canonical_url: bool = True


class PolicyConfig(BaseModel):
    respect_robots: bool = True
    user_agent: str = DEFAULT_USER_AGENT
    policy_opt_in: bool = False


class BrowserConfig(BaseModel):
    stealth: bool = True
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "networkidle"
    timeout_ms: int = 30000


class SeedConfig(BaseModel):
    strategy: Literal["pagination", "rss", "sitemap"]
    template: str | None = None
    range: tuple[int, int] | None = None
    url: HttpUrl | None = None
    follow_index: bool = True

    @model_validator(mode="after")
    def _validate_combo(self) -> SeedConfig:
        if self.strategy == "pagination":
            if not self.template or "{n}" not in self.template:
                raise ValueError("seed.strategy=pagination requires template containing '{n}'")
            if not self.range or len(self.range) != 2:
                raise ValueError("seed.strategy=pagination requires range of length 2")
            if self.range[0] > self.range[1]:
                raise ValueError("seed.range must satisfy start <= end")
        elif self.strategy in ("rss", "sitemap") and not self.url:
            raise ValueError(f"seed.strategy={self.strategy} requires url")
        return self


class SourceConfig(BaseModel):
    """Source declaration loaded from configs/sources/<name>.yaml."""

    name: str
    display_name: str
    base_url: HttpUrl
    fetcher: Literal["http", "browser"] = "http"
    seed: SeedConfig
    url_filter: str
    rate_limit: RateLimit = Field(default_factory=RateLimit)
    retry: RetryPolicy = Field(default_factory=RetryPolicy)
    extract: ExtractConfig = Field(default_factory=ExtractConfig)
    dedup: DedupConfig = Field(default_factory=DedupConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    categories: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not NAME_PATTERN.match(v):
            raise ValueError(f"name must match {NAME_PATTERN.pattern}")
        return v

    @field_validator("url_filter")
    @classmethod
    def _validate_regex(cls, v: str) -> str:
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"url_filter is not a valid regex: {e}") from e
        return v


class Document(BaseModel):
    """Extracted article ready for sink."""

    url: str
    canonical_url: str | None = None
    title: str
    content_text: str
    content_md: str
    author: str | None = None
    published_at: datetime | None = None
    lang: str | None = None
    word_count: int
    content_hash: str
    metadata_json: str | None = None  # raw JSON-LD + extras


class FetchResult(BaseModel):
    """Result returned by a Fetcher."""

    url: str
    status: int
    html: str
    headers: dict[str, str] = Field(default_factory=dict)
    final_url: str | None = None  # after redirects


class RunResult(BaseModel):
    """End-of-run summary surfaced to CLI / DB."""

    source_name: str
    run_id: int
    status: Literal["success", "partial", "failed", "skipped"]
    discovered: int = 0
    extracted_new: int = 0
    extracted_dup: int = 0
    error_count: int = 0
    duration_seconds: float = 0.0
