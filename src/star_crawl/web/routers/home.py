"""Workspace shell (/) + legacy dashboard (/dashboard).

The shell at "/" is the new Obsidian-style entry point: empty chrome that
defers all content to client-side tab loading. The legacy dashboard remains
reachable at /dashboard for direct URL access and for the status-bar cog
shortcut.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from star_crawl.web.deps import get_conn

router = APIRouter()


@router.get("/")
async def shell(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    """Render the workspace shell. Tabs/content load via client-side fetches."""
    article_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    source_count = conn.execute(
        "SELECT COUNT(*) FROM sources WHERE article_count > 0"
    ).fetchone()[0]

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="shell.html",
        context={
            "project_name": "star_crawl",
            "article_count": article_count,
            "source_count": source_count,
        },
    )


@router.get("/dashboard")
async def dashboard(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    """Legacy dashboard — direct URL only, rendered inside base.html chrome."""
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
