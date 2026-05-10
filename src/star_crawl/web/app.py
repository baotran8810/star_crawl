"""FastAPI app factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from star_crawl import __version__
from star_crawl.web.auth import auth_required
from star_crawl.web.markdown import render as md_render

WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="star_crawl",
        version=__version__,
        docs_url=None,
        redoc_url=None,
    )

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.filters["md"] = md_render

    app.state.templates = templates

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        if isinstance(resp, Response):
            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            resp.headers.setdefault("X-Frame-Options", "DENY")
            resp.headers.setdefault("Referrer-Policy", "same-origin")
            if not request.url.path.startswith("/static"):
                resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            # Return WWW-Authenticate header to trigger browser auth dialog
            return JSONResponse(
                {"error": exc.detail},
                status_code=exc.status_code,
                headers=exc.headers or {},
            )
        if exc.status_code == 404:
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context={"title": "Not found", "message": str(exc.detail or "Not found")},
                status_code=404,
            )
        return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        # FR-019: never leak internal trace to client
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "title": "Internal error",
                "message": "Something went wrong. Check server logs for details.",
            },
            status_code=500,
        )

    @app.get("/healthz", dependencies=[Depends(auth_required)])
    async def healthz(request: Request):
        from star_crawl.web.deps import get_conn

        try:
            gen = get_conn()
            conn = next(gen)
            try:
                version = conn.execute(
                    "SELECT MAX(version) FROM _schema_version"
                ).fetchone()[0]
            finally:
                gen.close()
            return JSONResponse(
                {"status": "ok", "db": "ok", "schema_version": version}
            )
        except Exception:
            return JSONResponse(
                {"status": "error", "db": "unreachable"},
                status_code=503,
            )

    # register routers
    from star_crawl.web.routers import articles, home, runs, search, sources

    app.include_router(home.router, dependencies=[Depends(auth_required)])
    app.include_router(sources.router, dependencies=[Depends(auth_required)])
    app.include_router(articles.router, dependencies=[Depends(auth_required)])
    app.include_router(search.router, dependencies=[Depends(auth_required)])
    app.include_router(runs.router, dependencies=[Depends(auth_required)])

    return app


app = create_app()
