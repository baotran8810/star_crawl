"""Load source configs from configs/sources/*.yaml.

Validates each YAML against SourceConfig. Filename must match `name`.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from star_crawl.core.schemas import SourceConfig

DEFAULT_CONFIG_DIR = Path("configs/sources")


class SourceLoadError(Exception):
    """Raised when a source YAML fails to load or validate."""


def load_all(config_dir: Path | None = None) -> dict[str, SourceConfig]:
    """Load every *.yaml file in config_dir into a SourceConfig dict.

    Raises SourceLoadError on the first invalid file with a clear message.
    """
    config_dir = config_dir or DEFAULT_CONFIG_DIR
    if not config_dir.exists():
        return {}

    out: dict[str, SourceConfig] = {}
    for path in sorted(config_dir.glob("*.yaml")):
        config = _load_one(path)
        out[config.name] = config
    return out


def load_one_by_name(name: str, config_dir: Path | None = None) -> SourceConfig:
    config_dir = config_dir or DEFAULT_CONFIG_DIR
    path = config_dir / f"{name}.yaml"
    if not path.exists():
        raise SourceLoadError(f"source config not found: {path}")
    return _load_one(path)


def _load_one(path: Path) -> SourceConfig:
    expected_name = path.stem
    raw_text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as e:
        raise SourceLoadError(f"{path}: invalid YAML: {e}") from e

    if not isinstance(data, dict):
        raise SourceLoadError(f"{path}: top-level YAML must be a mapping")

    if data.get("name") != expected_name:
        raise SourceLoadError(
            f"{path}: name in YAML ('{data.get('name')}') must match filename "
            f"('{expected_name}')"
        )

    try:
        return SourceConfig(**data)
    except ValidationError as e:
        raise SourceLoadError(f"{path}: validation failed:\n{e}") from e
