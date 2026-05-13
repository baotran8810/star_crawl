"""Full-text search via SQLite FTS5."""

from __future__ import annotations

import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from star_crawl.web.deps import get_conn, is_htmx_request

router = APIRouter()


def _safe_match(q: str) -> str:
    """Build a safe FTS5 MATCH expression from user input.

    FTS5 special characters can crash the parser. Strip non-word chars
    except spaces, then OR-combine each token. Returns "" when q is empty.
    """
    cleaned = re.sub(r"[^\w\s\-]", " ", q.strip())
    tokens = [t for t in cleaned.split() if len(t) >= 2]
    if not tokens:
        return ""
    # AND-join with quotes so multi-word phrases work
    return " ".join(f'"{t}"' for t in tokens)


@router.get("/search")
async def search(
    request: Request,
    q: str = "",
    source: str | None = None,
    page: int = 1,
    conn: sqlite3.Connection = Depends(get_conn),
):
    page = max(1, page)
    page_size = 20
    offset = (page - 1) * page_size

    match_expr = _safe_match(q)
    rows: list[sqlite3.Row] = []
    total = 0

    if match_expr:
        params: list[object] = [match_expr]
        where_extra = ""
        if source:
            where_extra = "AND a.source_name = ?"
            params.append(source)

        total = conn.execute(
            f"""SELECT COUNT(*) FROM articles_fts
                  JOIN articles a ON a.id = articles_fts.rowid
                 WHERE articles_fts MATCH ? {where_extra}""",
            params,
        ).fetchone()[0]

        rows = conn.execute(
            f"""SELECT a.id, a.source_name, a.title, a.published_at, a.word_count,
                       snippet(articles_fts, 1, '<mark>', '</mark>', '…', 12) AS snippet,
                       bm25(articles_fts, 4.0, 1.0) AS rank
                  FROM articles_fts
                  JOIN articles a ON a.id = articles_fts.rowid
                 WHERE articles_fts MATCH ? {where_extra}
                 ORDER BY rank
                 LIMIT ? OFFSET ?""",
            [*params, page_size, offset],
        ).fetchall()

    sources = conn.execute(
        """SELECT s.name, s.display_name, COUNT(a.id) AS n
             FROM sources s
             LEFT JOIN articles a ON a.source_name = s.name
            GROUP BY s.name ORDER BY n DESC"""
    ).fetchall() if match_expr else []

    templates = request.app.state.templates
    template = "partials/search_results.html" if is_htmx_request(request) else "search.html"
    return templates.TemplateResponse(
        request=request,
        name=template,
        context={
            "q": q,
            "results": rows,
            "total": total,
            "selected_source": source,
            "sources": sources,
            "page": page,
            "page_size": page_size,
        },
    )


# Workspace-shell panel variant.
router.add_api_route("/panel/search", search, methods=["GET"])
