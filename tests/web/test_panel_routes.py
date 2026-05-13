"""Panel route smoke tests.

Each /panel/* endpoint must:
  1. Respond 200.
  2. Render the content-only fragment — NO <html>, NO topnav, NO base.html chrome.
  3. Render the same signature elements as its non-panel sibling.

Per `specs/004-obsidian-ui/contracts/panel-routes.md`.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _assert_panel_shape(body: str) -> None:
    """A panel body must not include the base shell or any topnav markup."""
    assert "<!DOCTYPE html>" not in body, "panel must not render full document"
    assert "class=\"topnav\"" not in body, "panel must not include base topnav"
    assert "<title>" not in body, "panel must not include <title>"


def test_root_renders_shell(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "<!DOCTYPE html>" in body
    assert 'body class="shell"' in body
    assert "icon-rail" in body
    assert "tab-bar" in body
    assert "status-bar" in body


def test_dashboard_renders_legacy(client: TestClient) -> None:
    """The old dashboard is still reachable at /dashboard with base.html chrome."""
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "class=\"topnav\"" in resp.text


def test_panel_graph_is_content_only(client: TestClient) -> None:
    resp = client.get("/panel/graph")
    assert resp.status_code == 200
    _assert_panel_shape(resp.text)
    # Either the populated chassis (graph-shell) or the empty-state appears,
    # depending on whether the test corpus has a built graph.
    assert "graph-shell" in resp.text or "empty-state" in resp.text


def test_panel_runs_is_content_only(client: TestClient) -> None:
    resp = client.get("/panel/runs")
    assert resp.status_code == 200
    _assert_panel_shape(resp.text)


def test_panel_run_detail_is_content_only(client: TestClient) -> None:
    # Fixture seeds at least one run with id=1
    resp = client.get("/panel/run/1")
    assert resp.status_code == 200
    _assert_panel_shape(resp.text)


def test_panel_article_is_content_only(client: TestClient) -> None:
    resp = client.get("/panel/article/1")
    assert resp.status_code == 200
    _assert_panel_shape(resp.text)


def test_panel_sources_is_content_only(client: TestClient) -> None:
    resp = client.get("/panel/sources")
    assert resp.status_code == 200
    _assert_panel_shape(resp.text)


def test_panel_source_detail_is_content_only(client: TestClient) -> None:
    resp = client.get("/panel/source/uber_engineering")
    assert resp.status_code == 200
    _assert_panel_shape(resp.text)


def test_panel_search_is_content_only(client: TestClient) -> None:
    resp = client.get("/panel/search?q=test")
    assert resp.status_code == 200
    _assert_panel_shape(resp.text)


def test_legacy_routes_still_have_chrome(client: TestClient) -> None:
    """Direct URL access (not /panel/) keeps full base.html layout."""
    for path in ("/articles/1", "/runs/1", "/sources", "/sources/uber_engineering",
                 "/graph", "/runs", "/search?q=test"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"
        assert "class=\"topnav\"" in resp.text, f"{path} missing topnav"
