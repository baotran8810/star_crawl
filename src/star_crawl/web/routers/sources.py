"""Sources list + per-source article list."""

from __future__ import annotations

import math
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request

from star_crawl.web.deps import get_conn, is_htmx_request

router = APIRouter()
PAGE_SIZE = 25


@router.get("/sources")
async def list_sources(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    sources = conn.execute(
        """SELECT name, display_name, fetcher, seed_strategy,
                  article_count, last_crawled_at, policy_opt_in
             FROM sources ORDER BY article_count DESC"""
    ).fetchall()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request, name="sources.html", context={"sources": sources}
    )


@router.get("/sources/{name}/articles")
async def source_articles_column(
    name: str,
    request: Request,
    page: int = 1,
    conn: sqlite3.Connection = Depends(get_conn),
):
    """Finder column 2: list of articles for one source (HTMX target)."""
    src = conn.execute("SELECT * FROM sources WHERE name = ?", (name,)).fetchone()
    if src is None:
        raise HTTPException(status_code=404, detail=f"source '{name}' not configured")

    page = max(1, page)
    offset = (page - 1) * PAGE_SIZE
    total = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE source_name = ?", (name,),
    ).fetchone()[0]
    rows = conn.execute(
        """SELECT id, title, author, published_at, lang, word_count
             FROM articles WHERE source_name = ?
            ORDER BY published_at DESC, id DESC
            LIMIT ? OFFSET ?""",
        (name, PAGE_SIZE, offset),
    ).fetchall()
    pages = max(1, math.ceil(total / PAGE_SIZE))
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="partials/finder_articles.html",
        context={
            "source": src,
            "articles": rows,
            "page": page,
            "pages": pages,
            "total": total,
        },
    )


@router.get("/sources/{name}")
async def source_detail(
    name: str,
    request: Request,
    page: int = 1,
    lang: str | None = None,
    since: str | None = None,
    sort: str = "published_at",
    order: str = "desc",
    conn: sqlite3.Connection = Depends(get_conn),
):
    src = conn.execute("SELECT * FROM sources WHERE name = ?", (name,)).fetchone()
    if src is None:
        raise HTTPException(status_code=404, detail=f"source '{name}' not configured")

    if sort not in ("published_at", "title", "crawled_at", "word_count"):
        raise HTTPException(status_code=422, detail="invalid sort")
    order = "ASC" if order.lower() == "asc" else "DESC"

    where = ["source_name = ?"]
    params: list[object] = [name]
    if lang:
        where.append("lang = ?")
        params.append(lang)
    if since:
        try:
            date.fromisoformat(since)
        except ValueError:
            raise HTTPException(status_code=422, detail="since must be YYYY-MM-DD") from None
        where.append("(published_at >= ? OR (published_at IS NULL AND crawled_at >= ?))")
        params.extend([since, since])
    where_sql = " AND ".join(where)

    total = conn.execute(
        f"SELECT COUNT(*) FROM articles WHERE {where_sql}", params
    ).fetchone()[0]

    page = max(1, page)
    offset = (page - 1) * PAGE_SIZE
    rows = conn.execute(
        f"""SELECT id, title, author, published_at, lang, word_count
              FROM articles WHERE {where_sql}
             ORDER BY {sort} {order}, id DESC
             LIMIT ? OFFSET ?""",
        [*params, PAGE_SIZE, offset],
    ).fetchall()

    pages = max(1, math.ceil(total / PAGE_SIZE))
    templates = request.app.state.templates
    template_name = "partials/article_table.html" if is_htmx_request(request) else "source.html"
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={
            "source": src,
            "articles": rows,
            "page": page,
            "pages": pages,
            "total": total,
            "filters": {"lang": lang, "since": since, "sort": sort, "order": order.lower()},
        },
    )
