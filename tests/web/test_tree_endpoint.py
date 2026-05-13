"""US2 — /tree endpoint shape."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_tree_root_returns_sections(client: TestClient) -> None:
    resp = client.get("/tree")
    assert resp.status_code == 200
    body = resp.text
    assert 'data-section="sources"' in body
    assert 'data-section="runs"' in body
    assert 'data-section="bookmarks"' in body


def test_tree_root_includes_source_rows(client: TestClient) -> None:
    resp = client.get("/tree")
    body = resp.text
    # Fixture seeds 2 sources
    assert 'data-kind="source"' in body
    assert 'data-target-id="uber_engineering"' in body
    assert 'data-panel-url="/panel/source/uber_engineering"' in body


def test_tree_expand_sources_inlines_articles(client: TestClient) -> None:
    resp = client.get("/tree?section=sources&expand=true")
    body = resp.text
    assert 'data-kind="article"' in body
    assert 'data-panel-url="/panel/article/' in body


def test_tree_expand_one_source(client: TestClient) -> None:
    resp = client.get("/tree?section=sources/uber_engineering")
    body = resp.text
    assert 'tree-children' in body
    assert 'data-kind="article"' in body
    # Scope: no <ul class="tree"> wrapper here, just the children fragment
    assert 'data-section=' not in body


def test_tree_runs_section_includes_run_rows(client: TestClient) -> None:
    resp = client.get("/tree")
    body = resp.text
    assert 'data-kind="run"' in body
