"""Load + use glossary, aliases, blacklist YAML files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_DIR = Path("configs/graph")


@dataclass(frozen=True)
class Glossary:
    """Tech terms always extracted (exact match, case-insensitive)."""

    # display form per normalized term: "kubernetes" → "Kubernetes"
    display_by_term: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, str] = field(default_factory=dict)
    blacklist: set[str] = field(default_factory=set)

    @property
    def terms(self) -> set[str]:
        return set(self.display_by_term)

    def resolve(self, raw_term: str) -> str:
        """Lowercase + alias resolution."""
        norm = raw_term.lower().strip()
        return self.aliases.get(norm, norm)

    def display_for(self, term: str) -> str:
        """Pretty form for normalized term, falling back to title-case."""
        return self.display_by_term.get(term, term)

    def is_blacklisted(self, term: str) -> bool:
        return term in self.blacklist


def load(config_dir: Path | None = None) -> Glossary:
    """Read all 3 YAML files; missing files are tolerated."""
    config_dir = config_dir or DEFAULT_CONFIG_DIR
    return Glossary(
        display_by_term=_load_glossary(config_dir / "glossary.yaml"),
        aliases=_load_aliases(config_dir / "aliases.yaml"),
        blacklist=_load_blacklist(config_dir / "blacklist.yaml"),
    )


def _load_glossary(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    terms = raw.get("terms") or []
    out: dict[str, str] = {}
    for entry in terms:
        if not isinstance(entry, str):
            continue
        display = entry.strip()
        if not display:
            continue
        out[display.lower()] = display
    return out


def _load_aliases(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    aliases = raw.get("aliases") or {}
    return {str(k).lower().strip(): str(v).lower().strip() for k, v in aliases.items()}


def _load_blacklist(path: Path) -> set[str]:
    if not path.exists():
        return set()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    terms = raw.get("terms") or []
    return {str(t).lower().strip() for t in terms if t}
