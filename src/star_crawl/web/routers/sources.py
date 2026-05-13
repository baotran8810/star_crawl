"""Sources list + per-source article list + add/run actions."""

from __future__ import annotations

import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import yaml
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from star_crawl.core.schemas import SourceConfig
from star_crawl.sinks.sqlite import upsert_source
from star_crawl.sources.loader import SourceLoadError, load_one_by_name
from star_crawl.web.deps import data_dir, get_conn, is_htmx_request
from star_crawl.web.routers.panels import is_panel_request, redirect_to_shell

router = APIRouter()
PAGE_SIZE = 25
CONFIG_DIR = Path("configs/sources")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]+$")


# ───────────────────────────── READ ─────────────────────────────


@router.get("/sources")
async def list_sources(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    if not is_panel_request(request):
        return redirect_to_shell(request)
    sources = conn.execute(
        """SELECT name, display_name, fetcher, seed_strategy,
                  article_count, last_crawled_at, policy_opt_in
             FROM sources ORDER BY article_count DESC"""
    ).fetchall()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request, name="sources.html", context={"sources": sources}
    )


@router.get("/sources/new")
async def source_new_form(request: Request):
    """Render the 'add source' form."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request, name="source_new.html",
        context={"form": {}, "errors": {}, "general_error": None},
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
    if not is_panel_request(request):
        return redirect_to_shell(request)
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


# ───────────────────────── WRITE (Constitution v0.2.0) ─────────────────────────


@router.post("/sources")
async def create_source(
    request: Request,
    name: str = Form(...),
    display_name: str = Form(...),
    base_url: str = Form(...),
    fetcher: str = Form("http"),
    seed_strategy: str = Form(...),
    seed_url: str = Form(""),
    seed_template: str = Form(""),
    seed_range_start: int = Form(1),
    seed_range_end: int = Form(10),
    url_filter: str = Form(...),
):
    """Create a new source. Writes both YAML and DB row in one user action."""
    errors: dict[str, str] = {}
    form_data = {
        "name": name, "display_name": display_name, "base_url": base_url,
        "fetcher": fetcher, "seed_strategy": seed_strategy,
        "seed_url": seed_url, "seed_template": seed_template,
        "seed_range_start": seed_range_start, "seed_range_end": seed_range_end,
        "url_filter": url_filter,
    }

    # Basic field validation
    if not NAME_RE.match(name):
        errors["name"] = "must match [a-z][a-z0-9_]+"
    if (CONFIG_DIR / f"{name}.yaml").exists():
        errors["name"] = f"a source named '{name}' already exists"
    if not display_name.strip():
        errors["display_name"] = "required"
    try:
        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            errors["base_url"] = "must be a full http(s) URL"
    except Exception:
        errors["base_url"] = "must be a valid URL"
    if fetcher not in ("http", "browser"):
        errors["fetcher"] = "must be http or browser"
    if seed_strategy not in ("rss", "pagination", "sitemap"):
        errors["seed_strategy"] = "must be rss, pagination, or sitemap"

    # Strategy-specific
    yaml_seed: dict = {"strategy": seed_strategy}
    if seed_strategy in ("rss", "sitemap"):
        if not seed_url:
            errors["seed_url"] = "required for rss / sitemap"
        else:
            yaml_seed["url"] = seed_url
    elif seed_strategy == "pagination":
        if not seed_template or "{n}" not in seed_template:
            errors["seed_template"] = "must contain '{n}' placeholder"
        else:
            yaml_seed["template"] = seed_template
        if seed_range_start > seed_range_end:
            errors["seed_range_end"] = "must be ≥ start"
        else:
            yaml_seed["range"] = [seed_range_start, seed_range_end]

    try:
        re.compile(url_filter)
    except re.error as e:
        errors["url_filter"] = f"invalid regex: {e}"

    if errors:
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request, name="source_new.html",
            context={"form": form_data, "errors": errors, "general_error": None},
            status_code=422,
        )

    # Build YAML payload and validate via SourceConfig
    yaml_payload: dict = {
        "name": name,
        "display_name": display_name,
        "base_url": base_url,
        "fetcher": fetcher,
        "seed": yaml_seed,
        "url_filter": url_filter,
    }
    try:
        cfg = SourceConfig(**yaml_payload)
    except ValidationError as e:
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request, name="source_new.html",
            context={"form": form_data, "errors": {}, "general_error": str(e)},
            status_code=422,
        )

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    yaml_path = CONFIG_DIR / f"{name}.yaml"
    yaml_path.write_text(
        yaml.safe_dump(yaml_payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    # Mirror into the sources table immediately so the row shows up in /sources
    # without waiting for the first crawl. Web process opens read-only by
    # default; use a separate writer connection.
    from star_crawl.db.connection import connect as db_connect
    conn = db_connect(data_dir())
    try:
        upsert_source(conn, cfg)
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url="/sources", status_code=303)


@router.post("/sources/{name}/run")
async def run_source_now(name: str):
    """Trigger a crawl for one source as a detached subprocess.

    Constitution VI (v0.2.0): explicit, user-clicked. skip_known=True is the
    default in the pipeline, so already-crawled articles are NOT re-fetched.
    """
    # Validate the source actually exists (404 if not configured)
    try:
        load_one_by_name(name, CONFIG_DIR)
    except SourceLoadError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None

    # Find the star-crawl entry point. Same venv as the web server.
    binary = shutil.which("star-crawl")
    if not binary:
        # Fallback: invoke via the running Python
        cmd = [sys.executable, "-m", "star_crawl.cli", "run", name]
    else:
        cmd = [binary, "run", name]

    env = dict(os.environ)
    # Make sure subprocess sees the same data dir as the web layer
    env.setdefault("STAR_CRAWL_DATA_DIR", str(data_dir()))

    # Detach so the response returns immediately
    log_path = Path(data_dir()) / "logs" / f"run_{name}_{int(time.time())}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fp = open(log_path, "wb")  # noqa: SIM115 — kept open for subprocess lifetime
    subprocess.Popen(
        cmd,
        env=env,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    return RedirectResponse(url="/runs", status_code=303)


# Workspace-shell panel variants.
router.add_api_route("/panel/sources", list_sources, methods=["GET"])
router.add_api_route("/panel/source/{name}", source_detail, methods=["GET"])
