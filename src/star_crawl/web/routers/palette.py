"""Command palette object index.

Returns a flat JSON array of palette-searchable items (articles, sources,
runs, keywords) loaded once per session by `palette.js`.

Per `specs/004-obsidian-ui/contracts/panel-routes.md`.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from star_crawl.web.deps import get_conn

router = APIRouter()


@router.get("/palette/objects.json")
async def objects(conn: sqlite3.Connection = Depends(get_conn)):
    """Flat list of {kind, id, label, subtitle, panel_url} rows."""
    rows: list[dict] = []

    for r in conn.execute(
        """SELECT a.id, a.title, a.source_name, a.published_at
             FROM articles a ORDER BY a.id DESC LIMIT 5000"""
    ).fetchall():
        rows.append({
            "kind": "article",
            "id": int(r["id"]),
            "label": r["title"] or f"#{r['id']}",
            "subtitle": f'{r["source_name"]} · {(r["published_at"] or "")[:10]}',
            "panel_url": f'/panel/article/{int(r["id"])}',
        })

    for r in conn.execute(
        """SELECT name, display_name, article_count FROM sources
            WHERE article_count > 0 ORDER BY article_count DESC"""
    ).fetchall():
        rows.append({
            "kind": "source",
            "id": r["name"],
            "label": r["display_name"],
            "subtitle": f'{int(r["article_count"])} articles',
            "panel_url": f'/panel/source/{r["name"]}',
        })

    for r in conn.execute(
        """SELECT id, source_name, status, extracted_new, error_count, started_at
             FROM crawl_runs ORDER BY id DESC LIMIT 200"""
    ).fetchall():
        rows.append({
            "kind": "run",
            "id": int(r["id"]),
            "label": f'Run #{int(r["id"])}',
            "subtitle": (
                f'{r["source_name"]} · {r["status"]} · '
                f'+{int(r["extracted_new"])} new'
                + (f' / {int(r["error_count"])}e' if r["error_count"] else '')
            ),
            "panel_url": f'/panel/run/{int(r["id"])}',
        })

    for r in conn.execute(
        """SELECT id, display, doc_freq FROM keywords
            WHERE doc_freq >= 2 ORDER BY doc_freq DESC LIMIT 2000"""
    ).fetchall():
        rows.append({
            "kind": "keyword",
            "id": int(r["id"]),
            "label": r["display"],
            "subtitle": f'doc_freq={int(r["doc_freq"])}',
            "panel_url": None,
        })

    return JSONResponse(
        rows,
        headers={"Cache-Control": "private, max-age=60"},
    )
