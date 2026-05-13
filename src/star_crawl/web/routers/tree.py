"""Navigation tree endpoint for the workspace shell.

Returns HTML partial fragments — the top-level tree on initial load, then
section-scoped children when the user expands a section.

Per `specs/004-obsidian-ui/contracts/panel-routes.md`.
"""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from star_crawl.web.deps import get_conn

router = APIRouter()

Section = Literal["sources", "runs", "bookmarks", "searches"]


@router.get("/tree")
async def tree(
    request: Request,
    section: str | None = Query(default=None),
    expand: bool = Query(default=False),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """Return the tree partial. With `section`, scopes to that branch only."""
    sources = _load_sources(conn)
    if section and section.startswith("sources/"):
        source_name = section.split("/", 1)[1]
        articles = _load_articles_for_source(conn, source_name)
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request,
            name="partials/tree_articles.html",
            context={"articles": articles, "source_name": source_name},
        )

    runs = _load_runs(conn) if (section in (None, "runs") or expand) else []
    if section == "sources":
        # Expand the whole sources subtree (each source's first articles).
        for src in sources:
            src["children"] = _load_articles_for_source(conn, src["name"], limit=20)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="partials/tree.html",
        context={
            "sources": sources,
            "runs": runs,
            "section": section,
            "expand": expand,
        },
    )


def _load_sources(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT name, display_name, article_count
             FROM sources WHERE article_count > 0
            ORDER BY article_count DESC, name"""
    ).fetchall()
    return [
        {
            "name": r["name"],
            "display_name": r["display_name"],
            "article_count": int(r["article_count"]),
            "children": [],
        }
        for r in rows
    ]


def _load_articles_for_source(
    conn: sqlite3.Connection, source_name: str, *, limit: int = 50
) -> list[dict]:
    rows = conn.execute(
        """SELECT id, title, published_at
             FROM articles WHERE source_name = ?
            ORDER BY published_at DESC NULLS LAST, id DESC
            LIMIT ?""",
        (source_name, limit),
    ).fetchall()
    return [
        {
            "id": int(r["id"]),
            "title": r["title"] or f"#{r['id']}",
            "published_at": r["published_at"],
        }
        for r in rows
    ]


def _load_runs(conn: sqlite3.Connection, *, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        """SELECT id, source_name, status, started_at, extracted_new, error_count
             FROM crawl_runs ORDER BY started_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [
        {
            "id": int(r["id"]),
            "source_name": r["source_name"],
            "status": r["status"],
            "started_at": r["started_at"],
            "extracted_new": int(r["extracted_new"]),
            "error_count": int(r["error_count"]),
        }
        for r in rows
    ]
