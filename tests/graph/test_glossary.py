"""Glossary loader + alias + blacklist tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from star_crawl.graph import glossary as gl


GLOSSARY_YAML = """
terms:
  - Kafka
  - Kubernetes
  - PostgreSQL
"""

ALIASES_YAML = """
aliases:
  k8s: kubernetes
  postgres: postgresql
"""

BLACKLIST_YAML = """
terms:
  - team
  - system
"""


@pytest.fixture
def conf_dir(tmp_path: Path) -> Path:
    (tmp_path / "glossary.yaml").write_text(GLOSSARY_YAML, encoding="utf-8")
    (tmp_path / "aliases.yaml").write_text(ALIASES_YAML, encoding="utf-8")
    (tmp_path / "blacklist.yaml").write_text(BLACKLIST_YAML, encoding="utf-8")
    return tmp_path


@pytest.mark.unit
def test_load_glossary(conf_dir: Path):
    g = gl.load(conf_dir)
    assert "kafka" in g.terms
    assert g.display_for("kafka") == "Kafka"
    assert g.display_for("kubernetes") == "Kubernetes"


@pytest.mark.unit
def test_alias_resolution(conf_dir: Path):
    g = gl.load(conf_dir)
    assert g.resolve("k8s") == "kubernetes"
    assert g.resolve("K8S") == "kubernetes"
    assert g.resolve("postgres") == "postgresql"
    assert g.resolve("kafka") == "kafka"


@pytest.mark.unit
def test_blacklist_membership(conf_dir: Path):
    g = gl.load(conf_dir)
    assert g.is_blacklisted("team")
    assert g.is_blacklisted("system")
    assert not g.is_blacklisted("kafka")


@pytest.mark.unit
def test_missing_files_tolerated(tmp_path: Path):
    g = gl.load(tmp_path / "nonexistent")
    assert g.terms == set()
    assert g.aliases == {}
    assert g.blacklist == set()
