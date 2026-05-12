"""Star-graph routes."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from star_crawl.graph.repository import (
    GraphFilters,
    keyword_count,
    read_graph,
    read_keyword_panel,
    search_keywords,
    stale_status,
)
from star_crawl.web.deps import data_dir, get_conn

router = APIRouter()
EMPTY_THRESHOLD = 20

# Rebuild defaults — matches the latest CLI tuning so the UI button gives
# the same shape as `star-crawl extract-keywords && star-crawl build-graph`
REBUILD_BUILD_FLAGS = [
    "--min-doc-freq", "2",
    "--min-co-count", "1",
    "--min-npmi", "0.15",
    "--max-edges-per-node", "12",
]


def _star_crawl_cmd() -> list[str]:
    """Path to the star-crawl entry point in the current environment."""
    binary = shutil.which("star-crawl")
    if binary:
        return [binary]
    return [sys.executable, "-m", "star_crawl.cli"]


def _spawn_rebuild(env: dict) -> Path:
    """Spawn extract-keywords && build-graph in a single shell pipeline.

    Returns the log path so the UI can link to it. Detached, non-blocking.
    """
    log_path = Path(data_dir()) / "logs" / f"graph_rebuild_{int(time.time())}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fp = open(log_path, "wb")  # noqa: SIM115 — owned by subprocess

    base = _star_crawl_cmd()
    extract_cmd = base + ["extract-keywords"]
    build_cmd = base + ["build-graph", *REBUILD_BUILD_FLAGS]

    # Run as a small shell script so both phases execute in order.
    script = (
        f"set -e\n"
        f"echo '[rebuild] extract-keywords'\n"
        f"{' '.join(extract_cmd)}\n"
        f"echo '[rebuild] build-graph'\n"
        f"{' '.join(build_cmd)}\n"
        f"echo '[rebuild] done'\n"
    )
    subprocess.Popen(
        ["bash", "-c", script],
        env=env,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    return log_path


def _filters(
    source: list[str] | None = Query(default=None),
    since: str | None = None,
    until: str | None = None,
    min_freq: int = 2,
    min_npmi: float = 0.10,
    cluster: int | None = None,
    focus: int | None = None,
) -> GraphFilters:
    return GraphFilters(
        sources=source, since=since, until=until,
        min_freq=min_freq, min_npmi=min_npmi,
        cluster=cluster, focus=focus,
    )


@router.get("/graph")
async def graph_page(
    request: Request,
    filters: GraphFilters = Depends(_filters),
    conn: sqlite3.Connection = Depends(get_conn),
):
    templates = request.app.state.templates

    n_keywords = keyword_count(conn)
    if n_keywords < EMPTY_THRESHOLD:
        return templates.TemplateResponse(
            request=request,
            name="graph_empty.html",
            context={
                "n_keywords": n_keywords,
                "min_keywords": EMPTY_THRESHOLD,
            },
        )

    payload = read_graph(conn, filters)
    available_sources = conn.execute(
        """SELECT name, display_name, article_count FROM sources
           WHERE article_count > 0 ORDER BY article_count DESC"""
    ).fetchall()
    return templates.TemplateResponse(
        request=request,
        name="graph.html",
        context={
            "payload_json": json.dumps(payload),
            "meta": payload["meta"],
            "filters": filters,
            "available_sources": available_sources,
        },
    )


@router.get("/graph.json")
async def graph_json(
    request: Request,
    filters: GraphFilters = Depends(_filters),
    conn: sqlite3.Connection = Depends(get_conn),
):
    if keyword_count(conn) == 0 and stale_status(conn)["is_built"] is False:
        return JSONResponse(
            {"error": "graph not built — run star-crawl build-graph"},
            status_code=503,
        )
    payload = read_graph(conn, filters)
    return JSONResponse(payload)


@router.get("/keywords/search")
async def keywords_search(
    request: Request,
    q: str = "",
    conn: sqlite3.Connection = Depends(get_conn),
):
    """Type-ahead suggestion partial. Must precede /keywords/{kw_id}."""
    rows = search_keywords(conn, q, limit=10)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="partials/keyword_suggestions.html",
        context={"q": q, "results": rows},
    )


@router.get("/keywords/{kw_id}")
async def keyword_panel(
    kw_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
):
    """HTMX side-panel partial for a single keyword."""
    panel = read_keyword_panel(conn, kw_id)
    if panel is None:
        raise HTTPException(status_code=404, detail=f"keyword #{kw_id} not found")
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="partials/keyword_panel.html",
        context=panel,
    )


@router.post("/graph/rebuild")
async def rebuild_graph_now():
    """Trigger extract-keywords + build-graph as a detached subprocess.

    Constitution VI v0.2.0: explicit user-click, runs out-of-process so the
    request thread is never blocked. extract-keywords is idempotent — it
    skips articles that already have keyword links — so re-clicking after a
    minor crawl is safe and cheap.
    """
    env = dict(os.environ)
    env.setdefault("STAR_CRAWL_DATA_DIR", str(data_dir()))
    _spawn_rebuild(env)
    return RedirectResponse(url="/graph?rebuilding=1", status_code=303)
