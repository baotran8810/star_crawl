"""US1 — Side-by-side tabs with persistence.

Covers the spec's Independent Test for User Story 1:
  - default tab auto-opens
  - clicking a tree row opens a tab
  - reload preserves tabs + active tab
  - close all tabs → auto-opens default graph

Run via:
  .venv/bin/pytest tests/web/e2e/test_workspace_tabs.py
"""

from __future__ import annotations

import json


def _state(page):
    return json.loads(page.evaluate("JSON.stringify(window.workspace.getState())"))


def test_fresh_visit_auto_opens_graph(page, server_url):
    page.goto(server_url + "/", wait_until="networkidle")
    page.evaluate("localStorage.removeItem('star_crawl.workspace.v1')")
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1500)
    s = _state(page)
    assert len(s["tabs"]) == 1
    assert s["tabs"][0]["kind"] == "graph"
    assert s["active_tab_id"] == s["tabs"][0]["id"]


def test_open_tab_from_tree(page):
    page.click('li[data-target-id="1"][data-kind="run"]')
    page.wait_for_timeout(700)
    s = _state(page)
    kinds = [t["kind"] for t in s["tabs"]]
    assert "run" in kinds
    # active tab is the newly opened one
    active = next(t for t in s["tabs"] if t["id"] == s["active_tab_id"])
    assert active["kind"] == "run"


def test_reload_restores_tabs(page, server_url):
    page.click('li[data-target-id="1"][data-kind="run"]')
    page.wait_for_timeout(400)
    page.evaluate(
        "window.workspace.openTab({kind:'article',target_id:'1',"
        "title:'Article 1',panel_url:'/panel/article/1'})"
    )
    page.wait_for_timeout(400)
    before = _state(page)
    assert len(before["tabs"]) == 3

    page.reload(wait_until="networkidle")
    page.wait_for_timeout(1500)
    after = _state(page)
    assert len(after["tabs"]) == 3
    assert after["active_tab_id"] == before["active_tab_id"]
    # DOM stays in sync
    assert page.evaluate("document.querySelectorAll('.tab').length") == 3


def test_close_all_tabs_reopens_graph(page):
    page.click('li[data-target-id="1"][data-kind="run"]')
    page.wait_for_timeout(400)
    page.evaluate(
        "window.workspace.openTab({kind:'article',target_id:'1',"
        "title:'Article 1',panel_url:'/panel/article/1'})"
    )
    page.wait_for_timeout(400)
    # Snapshot original tab ids; close them all by id (closing the last one
    # triggers FR-021 auto-graph, which appends a *new* tab whose id is NOT
    # in the snapshot).
    original_ids = [t["id"] for t in _state(page)["tabs"]]
    assert len(original_ids) == 3
    for tid in original_ids:
        page.click(f'[data-close="{tid}"]')
        page.wait_for_timeout(250)
    s = _state(page)
    assert len(s["tabs"]) == 1, f"expected 1 tab after close-all, got {len(s['tabs'])}"
    assert s["tabs"][0]["kind"] == "graph"
    assert s["tabs"][0]["id"] not in original_ids


def test_switch_tab_via_click(page):
    page.click('li[data-target-id="1"][data-kind="run"]')
    page.wait_for_timeout(400)
    page.evaluate(
        "window.workspace.openTab({kind:'article',target_id:'1',"
        "title:'Article 1',panel_url:'/panel/article/1'})"
    )
    page.wait_for_timeout(400)
    s = _state(page)
    graph_id = next(t["id"] for t in s["tabs"] if t["kind"] == "graph")
    page.click(f'.tab[data-tab-id="{graph_id}"]')
    page.wait_for_timeout(300)
    s2 = _state(page)
    assert s2["active_tab_id"] == graph_id
