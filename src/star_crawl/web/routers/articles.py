"""Article detail."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from star_crawl.graph.repository import (
    has_extracted_keywords,
    read_article_keywords,
    read_related_articles,
)
from star_crawl.web.deps import get_conn
from star_crawl.web.routers.panels import is_panel_request, redirect_to_shell

router = APIRouter()


@router.get("/articles/{article_id}/preview")
async def article_preview(
    article_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
):
    """Finder column 3: condensed preview panel for one article.

    Also surfaces this article's keywords (from `article_keywords`) and
    other articles ranked by shared-keyword overlap, so the reader can
    pivot from one piece to related ideas.
    """
    row = conn.execute(
        """SELECT a.*, s.display_name AS source_display_name
             FROM articles a JOIN sources s ON s.name = a.source_name
            WHERE a.id = ?""",
        (article_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"article #{article_id} not found")

    keywords = read_article_keywords(conn, article_id)
    related = read_related_articles(conn, article_id, limit=8) if keywords else []

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="partials/article_preview.html",
        context={
            "article": row,
            "keywords": keywords,
            "related": related,
            "has_keywords": bool(keywords),
        },
    )


@router.get("/articles/{article_id}/keywords")
async def article_keywords_partial(
    article_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
):
    """HTMX partial — just the keywords + related-articles section."""
    keywords = read_article_keywords(conn, article_id)
    needs_extract = not keywords and not has_extracted_keywords(conn, article_id)
    related = read_related_articles(conn, article_id, limit=8) if keywords else []
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="partials/article_keywords.html",
        context={
            "keywords": keywords,
            "related": related,
            "needs_extract": needs_extract,
            "article_id": article_id,
        },
    )


@router.get("/articles/{article_id}")
async def article_detail(
    article_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
):
    if not is_panel_request(request):
        return redirect_to_shell(request)
    row = conn.execute(
        """SELECT a.*, s.display_name AS source_display_name
             FROM articles a JOIN sources s ON s.name = a.source_name
            WHERE a.id = ?""",
        (article_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"article #{article_id} not found")

    keywords = read_article_keywords(conn, article_id)
    related = read_related_articles(conn, article_id, limit=8) if keywords else []

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="article.html",
        context={"article": row, "keywords": keywords, "related": related},
    )


# Workspace-shell panel variant — same handler, different URL prefix.
# Template's conditional extends switches to _panel_base.html based on path.
router.add_api_route("/panel/article/{article_id}", article_detail, methods=["GET"])
