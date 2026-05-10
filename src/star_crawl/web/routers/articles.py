"""Article detail."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from star_crawl.web.deps import get_conn

router = APIRouter()


@router.get("/articles/{article_id}")
async def article_detail(
    article_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
):
    row = conn.execute(
        """SELECT a.*, s.display_name AS source_display_name
             FROM articles a JOIN sources s ON s.name = a.source_name
            WHERE a.id = ?""",
        (article_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"article #{article_id} not found")

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request, name="article.html", context={"article": row}
    )
