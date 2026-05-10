"""Star-graph routes."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from star_crawl.graph.repository import (
    GraphFilters,
    keyword_count,
    read_graph,
    read_keyword_panel,
    search_keywords,
    stale_status,
)
from star_crawl.web.deps import get_conn

router = APIRouter()
EMPTY_THRESHOLD = 20


def _filters(
    source: list[str] | None = Query(default=None),
    since: str | None = None,
    until: str | None = None,
    min_freq: int = 3,
    min_npmi: float = 0.15,
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
    return templates.TemplateResponse(
        request=request,
        name="graph.html",
        context={
            "payload_json": json.dumps(payload),
            "meta": payload["meta"],
            "filters": filters,
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
