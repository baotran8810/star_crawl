"""Export the graph as GraphML, Cytoscape JSON, or PNG screenshot."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from contextlib import closing
from pathlib import Path
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


def to_cytoscape_json(payload: dict[str, Any], out: Path) -> int:
    """Write a Cytoscape elements JSON file. Returns bytes written."""
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    out.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def to_graphml(payload: dict[str, Any], out: Path) -> int:
    """Write a GraphML file compatible with Gephi. Returns bytes written."""
    out.parent.mkdir(parents=True, exist_ok=True)
    g = nx.Graph()
    for node in payload.get("nodes", []):
        data = node["data"]
        g.add_node(
            data["id"],
            term=data.get("term", ""),
            display=data.get("display", ""),
            doc_freq=int(data.get("doc_freq", 0)),
            cluster_id=int(data.get("cluster_id", 0)),
            cluster_label=str(data.get("cluster_label", "")),
            color=str(data.get("color", "")),
        )
    for edge in payload.get("edges", []):
        data = edge["data"]
        g.add_edge(
            data["source"],
            data["target"],
            co_count=int(data.get("co_count", 0)),
            npmi=float(data.get("npmi", 0.0)),
            weight=float(data.get("npmi", 0.0)),  # Gephi convention
        )

    nx.write_graphml(g, out)
    return out.stat().st_size


def to_png(
    server_url: str,
    query_string: str,
    out: Path,
    *,
    viewport_width: int = 1280,
    viewport_height: int = 800,
    wait_after_load_ms: int = 1500,
) -> int:
    """Render /graph in a headless browser and screenshot the canvas.

    Requires the [browser] extra (playwright). Returns bytes written.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise RuntimeError(
            "graph export png requires the [browser] extra: "
            "pip install -e '.[browser]' && playwright install chromium"
        ) from e

    async def _shoot() -> None:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": viewport_width, "height": viewport_height},
                )
                page = await context.new_page()
                url = f"{server_url.rstrip('/')}/graph"
                if query_string:
                    url += "?" + query_string.lstrip("?")
                await page.goto(url, wait_until="networkidle")
                # Wait for fcose to settle
                await page.wait_for_timeout(wait_after_load_ms)
                # Screenshot the canvas element specifically
                canvas = await page.query_selector("#cy")
                if canvas is None:
                    # Empty-state page (no #cy) — full-page fallback
                    await page.screenshot(path=str(out), full_page=True)
                else:
                    await canvas.screenshot(path=str(out))
            finally:
                await browser.close()

    asyncio.run(_shoot())
    return out.stat().st_size


def find_free_port() -> int:
    """Find an available TCP port for spinning up a temporary server."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
