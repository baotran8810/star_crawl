"""Unit tests for SourceConfig validation rules."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from star_crawl.core.schemas import SourceConfig


def _grab_dict() -> dict:
    return {
        "name": "grab_engineering",
        "display_name": "Grab Engineering",
        "base_url": "https://engineering.grab.com",
        "fetcher": "http",
        "seed": {
            "strategy": "rss",
            "url": "https://engineering.grab.com/feed.xml",
        },
        "url_filter": r"^https://engineering\.grab\.com/[^/]+$",
    }


def _uber_dict() -> dict:
    return {
        "name": "uber_engineering",
        "display_name": "Uber Engineering",
        "base_url": "https://www.uber.com/us/en/blog/engineering/",
        "fetcher": "http",
        "seed": {
            "strategy": "pagination",
            "template": "https://www.uber.com/us/en/blog/engineering/page/{n}/",
            "range": [1, 63],
        },
        "url_filter": r"^https://www\.uber\.com/us/en/blog/[^/]+/$",
    }


@pytest.mark.unit
def test_grab_rss_loads_with_defaults():
    src = SourceConfig(**_grab_dict())
    assert src.name == "grab_engineering"
    assert src.fetcher == "http"
    assert src.rate_limit.rps == 1.0
    assert src.policy.respect_robots is True
    assert src.policy.policy_opt_in is False


@pytest.mark.unit
def test_uber_pagination_loads():
    src = SourceConfig(**_uber_dict())
    assert src.seed.strategy == "pagination"
    assert src.seed.range == (1, 63)


@pytest.mark.unit
def test_pagination_requires_template_with_n():
    bad = _uber_dict()
    bad["seed"]["template"] = "https://example.com/page/N/"  # no {n}
    with pytest.raises(ValidationError):
        SourceConfig(**bad)


@pytest.mark.unit
def test_pagination_requires_range_length_two():
    bad = _uber_dict()
    bad["seed"]["range"] = [1]
    with pytest.raises(ValidationError):
        SourceConfig(**bad)


@pytest.mark.unit
def test_rss_requires_url():
    bad = _grab_dict()
    bad["seed"].pop("url")
    with pytest.raises(ValidationError):
        SourceConfig(**bad)


@pytest.mark.unit
def test_url_filter_must_compile():
    bad = _grab_dict()
    bad["url_filter"] = "[invalid("
    with pytest.raises(ValidationError):
        SourceConfig(**bad)


@pytest.mark.unit
def test_name_pattern_enforced():
    bad = _grab_dict()
    bad["name"] = "Grab-Engineering"  # uppercase + dash
    with pytest.raises(ValidationError):
        SourceConfig(**bad)


@pytest.mark.unit
def test_rps_must_be_positive():
    bad = _grab_dict()
    bad["rate_limit"] = {"rps": 0.0}
    with pytest.raises(ValidationError):
        SourceConfig(**bad)
