# Phase 0 Research: Web UI

**Date**: 2026-05-10

## Decisions

### Server framework — `FastAPI`

- **Decision**: `FastAPI` for routes + `uvicorn` for ASGI server.
- **Rationale**: Async by default (matches crawler's runtime), great DX with type hints, integrates cleanly with Pydantic models from feature 001. Auto-docs via OpenAPI useful even for a single-user UI.
- **Alternatives**: `Flask` (sync, would require thread pool for SQLite contention); `Starlette` raw (less ergonomics, same async core); `Litestar` (newer, smaller community).

### Templating — `Jinja2`

- **Decision**: `Jinja2` server-rendered templates.
- **Rationale**: Battle-tested, no build step, works well with HTMX partials (same template engine for full and fragment responses).
- **Alternatives**: `htmy` (newer, less ergonomics), React/Vue (bundler required — violates "no build step" constraint).

### Interactivity — HTMX

- **Decision**: HTMX 2.x, vendored as static asset (not CDN at runtime, for offline-first).
- **Rationale**: Pagination, live search, and run progress polling all expressible as `hx-*` attributes. No JS framework, no transpilation. Minimal client-side JS surface.
- **Alternatives**: Vanilla JS for fetch (more code), Hotwire/Turbo (heavier and Rails-flavored), Alpine.js (overkill for our needs).

### Markdown rendering — `markdown-it-py` + `bleach`

- **Decision**: `markdown-it-py` (with `linkify`, `tables`, `footnote`, `anchor` plugins) → `bleach` sanitize → render in template.
- **Rationale**: Articles in `articles.content_md` are extractor output; treat as untrusted to avoid XSS via crafted source pages. `bleach` allows a known-safe tag/attr list.
- **Alternatives**: `mistune` (faster but lazier safety), `markdown` (slower), `cmark` C extension (build complexity).

### Search — SQLite FTS5

- **Decision**: FTS5 virtual table with content-shadowed config; triggers keep it in sync with `articles`. Use `bm25` ranking with column weights (title × 4 > content).
- **Rationale**: Built into SQLite, no extra dependency. p95 < 500ms easily achievable at 10k corpus. `snippet()` function gives highlighted excerpts for free.
- **Alternatives**: External index (`tantivy`, `meilisearch`) — overkill at this scale; `LIKE` queries — too slow above ~1000 articles.

### Live updates — HTMX polling

- **Decision**: HTMX `hx-trigger="every 2s"` on the in-progress run row, with the server sending the same fragment back. When status flips to terminal (`success/partial/failed`), the partial removes the polling attribute and the loop ends naturally.
- **Rationale**: No WebSocket complexity. Polling 2s is fine for ~1 user. Loop terminates server-side.
- **Alternatives**: Server-Sent Events (more code, marginal benefit), WebSocket (overkill, lifecycle management).

### Authentication — optional basic auth via env

- **Decision**: When `STAR_CRAWL_AUTH=user:pass` is set, all routes require HTTP basic auth. Otherwise, no auth.
- **Rationale**: Single-user system. Basic auth is fine over HTTPS-terminating reverse proxy. We refuse to bind non-loopback unless auth is set (constitution-flavored safety).
- **Alternatives**: Cookie sessions (more code), OAuth (overkill).

### Default bind — `127.0.0.1`

- **Decision**: `uvicorn` defaults to `127.0.0.1:8000`. The CLI `serve` subcommand refuses to set host to non-loopback unless `STAR_CRAWL_AUTH` is set.
- **Rationale**: Ships safe by default. User must opt into the security responsibility.

### CSS — single hand-rolled file

- **Decision**: Single `static/styles.css` using CSS custom properties, no preprocessor. Match design tokens already established in PLAN.html / WIREFRAMES.html.
- **Rationale**: No build step constitution constraint. Tokens already designed. Tailwind requires a build pipeline.

### Static asset serving — FastAPI mount

- **Decision**: `app.mount("/static", StaticFiles(...))`.
- **Rationale**: Stdlib-level. Cache-Control headers via middleware.

### Test client — `httpx.AsyncClient`

- **Decision**: `httpx.AsyncClient(transport=ASGITransport(app))` for route tests.
- **Rationale**: Real ASGI lifespan, accurate behavior. Drops in cleanly with `pytest-asyncio`.

## Open questions resolved

- **Q**: Should the UI ever trigger a crawl (e.g., a "refresh" button)? **A**: No — constitution VI. Crawls are CLI-only.
- **Q**: Should we store rendered Markdown HTML in DB? **A**: No, render on the fly. CPU is cheap; cache invalidation is annoying.
- **Q**: Light mode only or both? **A**: Both, follow `prefers-color-scheme` (matches PLAN.html convention). No theme switcher in v1.
- **Q**: Should `/articles/{id}/jsonld` return raw JSON-LD or pretty-printed HTML view? **A**: Both — content negotiation by `Accept` header. Default HTML.

## Out of scope (deferred)

- User accounts beyond single-tenant basic auth.
- Edit/annotate articles.
- Saved searches.
- Notification when a new crawl run completes.
- PWA / offline mode.
