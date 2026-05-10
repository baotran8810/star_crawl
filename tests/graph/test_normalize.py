"""Normalization rules tests."""

from __future__ import annotations

import pytest

from star_crawl.graph.glossary import Glossary
from star_crawl.graph.normalize import normalize


def _gl(blacklist=()):
    return Glossary(
        display_by_term={"kubernetes": "Kubernetes", "kafka": "Kafka"},
        aliases={"k8s": "kubernetes", "postgres": "postgresql"},
        blacklist=set(blacklist),
    )


@pytest.mark.unit
def test_basic_lowercase():
    g = _gl()
    assert normalize("Kafka", g) == "kafka"
    assert normalize("KAFKA", g) == "kafka"


@pytest.mark.unit
def test_alias_resolved_after_normalize():
    g = _gl()
    assert normalize("K8s", g) == "kubernetes"
    assert normalize("Postgres", g) == "postgresql"


@pytest.mark.unit
def test_blacklist_drops():
    g = _gl(blacklist=["team", "system"])
    assert normalize("team", g) is None
    assert normalize("System", g) is None
    assert normalize("kafka", g) == "kafka"


@pytest.mark.unit
def test_short_input_dropped():
    g = _gl()
    assert normalize("a", g) is None
    assert normalize("", g) is None
    assert normalize(" ", g) is None


@pytest.mark.unit
def test_whitespace_normalized():
    g = _gl()
    assert normalize("   apache   kafka   ", g) == "apache kafka"
