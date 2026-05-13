"""Crawl run history + run detail + live progress polling."""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request

from star_crawl.web.deps import get_conn

router = APIRouter()


@router.get("/runs")
async def list_runs(
    request: Request,
    source: str | None = None,
    status: str | None = None,
    since: str | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
):
    where = []
    params: list[object] = []
    if source:
        where.append("source_name = ?")
        params.append(source)
    if status:
        if status not in ("running", "success", "partial", "failed", "skipped"):
            raise HTTPException(422, detail="invalid status")
        where.append("status = ?")
        params.append(status)
    if since:
        try:
            date.fromisoformat(since)
        except ValueError:
            raise HTTPException(422, detail="since must be YYYY-MM-DD") from None
        where.append("started_at >= ?")
        params.append(since)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    runs = conn.execute(
        f"""SELECT cr.id, cr.source_name, cr.started_at, cr.finished_at,
                   cr.status, cr.discovered, cr.extracted_new,
                   cr.extracted_dup, cr.error_count,
                   s.display_name AS source_display,
                   (julianday(COALESCE(cr.finished_at, CURRENT_TIMESTAMP))
                    - julianday(cr.started_at)) * 86400 AS duration_seconds
              FROM crawl_runs cr
              JOIN sources s ON s.name = cr.source_name
              {where_sql}
             ORDER BY cr.started_at DESC LIMIT 200""",
        params,
    ).fetchall()

    sources = conn.execute("SELECT name, display_name FROM sources").fetchall()

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="runs.html",
        context={
            "runs": runs,
            "sources": sources,
            "filters": {"source": source, "status": status, "since": since},
        },
    )


@router.get("/runs/{run_id}")
async def run_detail(
    run_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
):
    run = conn.execute(
        """SELECT cr.*, s.display_name AS source_display,
                  (julianday(COALESCE(cr.finished_at, CURRENT_TIMESTAMP))
                   - julianday(cr.started_at)) * 86400 AS duration_seconds
             FROM crawl_runs cr
             JOIN sources s ON s.name = cr.source_name
            WHERE cr.id = ?""",
        (run_id,),
    ).fetchone()
    if run is None:
        raise HTTPException(status_code=404, detail=f"run #{run_id} not found")

    errors = conn.execute(
        """SELECT url, kind, message, occurred_at FROM errors
            WHERE run_id = ? ORDER BY occurred_at LIMIT 200""",
        (run_id,),
    ).fetchall()
    new_articles = conn.execute(
        """SELECT id, title, published_at, word_count, content_hash
             FROM articles WHERE first_run_id = ?
            ORDER BY published_at DESC LIMIT 50""",
        (run_id,),
    ).fetchall()

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="run.html",
        context={
            "run": run,
            "errors": errors,
            "new_articles": new_articles,
        },
    )


@router.get("/runs/{run_id}/progress")
async def run_progress_partial(
    run_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
):
    """HTMX-only: returns one row's worth of HTML for the run.

    When status is terminal, the returned partial omits the polling
    attribute so the loop ends client-side.
    """
    run = conn.execute(
        """SELECT cr.id, cr.source_name, cr.started_at, cr.finished_at,
                  cr.status, cr.discovered, cr.extracted_new,
                  cr.extracted_dup, cr.error_count,
                  s.display_name AS source_display,
                  (julianday(COALESCE(cr.finished_at, CURRENT_TIMESTAMP))
                   - julianday(cr.started_at)) * 86400 AS duration_seconds
             FROM crawl_runs cr
             JOIN sources s ON s.name = cr.source_name
            WHERE cr.id = ?""",
        (run_id,),
    ).fetchone()
    if run is None:
        raise HTTPException(status_code=404, detail=f"run #{run_id} not found")

    counts = dict(
        conn.execute(
            """SELECT state, COUNT(*) FROM frontier
                WHERE run_id = ?
                GROUP BY state""",
            (run_id,),
        ).fetchall()
    )
    in_flight = counts.get("in_progress", 0)
    live = {
        "done": counts.get("done", 0),
        "failed": counts.get("failed", 0),
        "skipped": counts.get("skipped", 0),
        "pending": counts.get("pending", 0),
        "total": sum(counts.values()),
    }

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="partials/run_row.html",
        context={"run": run, "in_flight": in_flight, "live": live},
    )


# Workspace-shell panel variants.
router.add_api_route("/panel/runs", list_runs, methods=["GET"])
router.add_api_route("/panel/run/{run_id}", run_detail, methods=["GET"])
