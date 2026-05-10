"""Home / dashboard route."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from star_crawl.web.deps import get_conn

router = APIRouter()


@router.get("/")
async def home(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    sources = conn.execute(
        """SELECT name, display_name, article_count, last_crawled_at
           FROM sources ORDER BY article_count DESC LIMIT 6"""
    ).fetchall()
    runs = conn.execute(
        """SELECT id, source_name, started_at, finished_at, status,
                  discovered, extracted_new, error_count
             FROM crawl_runs ORDER BY started_at DESC LIMIT 5"""
    ).fetchall()
    last_run = runs[0] if runs else None

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "total_articles": total,
            "sources": sources,
            "recent_runs": runs,
            "last_run": last_run,
        },
    )
