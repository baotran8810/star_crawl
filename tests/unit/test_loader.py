"""Source loader tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from star_crawl.sources.loader import SourceLoadError, load_all, load_one_by_name

GRAB_YAML = """\
name: grab_engineering
display_name: Grab Engineering
base_url: https://engineering.grab.com
fetcher: http
seed:
  strategy: rss
  url: https://engineering.grab.com/feed.xml
url_filter: '^https://engineering\\.grab\\.com/[^/]+$'
"""


@pytest.fixture
def configs(tmp_path: Path) -> Path:
    d = tmp_path / "configs"
    d.mkdir()
    (d / "grab_engineering.yaml").write_text(GRAB_YAML, encoding="utf-8")
    return d


@pytest.mark.unit
def test_load_all(configs: Path):
    sources = load_all(configs)
    assert "grab_engineering" in sources
    assert sources["grab_engineering"].fetcher == "http"


@pytest.mark.unit
def test_load_one_by_name(configs: Path):
    s = load_one_by_name("grab_engineering", configs)
    assert s.name == "grab_engineering"


@pytest.mark.unit
def test_missing_source(configs: Path):
    with pytest.raises(SourceLoadError, match="not found"):
        load_one_by_name("nonexistent", configs)


@pytest.mark.unit
def test_filename_must_match_name(tmp_path: Path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "wrong_filename.yaml").write_text(GRAB_YAML, encoding="utf-8")
    with pytest.raises(SourceLoadError, match="must match filename"):
        load_all(configs)


@pytest.mark.unit
def test_invalid_yaml_rejected(tmp_path: Path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "broken.yaml").write_text("name: broken\n  bad: indent: nope", encoding="utf-8")
    with pytest.raises(SourceLoadError, match="invalid YAML"):
        load_all(configs)


@pytest.mark.unit
def test_empty_dir_returns_empty(tmp_path: Path):
    out = load_all(tmp_path / "does_not_exist")
    assert out == {}
