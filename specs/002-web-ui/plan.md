# Implementation Plan: Web UI

**Branch**: `002-web-ui` | **Date**: 2026-05-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/002-web-ui/spec.md`

## Summary

Read-only browser interface for the corpus produced by feature 001. Server-rendered Jinja2 templates over FastAPI, with HTMX for partial updates (pagination, live search, run progress). No build step. No JS framework. Default-bound to `127.0.0.1`; exposing requires explicit credential.

## Technical Context

**Language/Version**: Python 3.11+ (same runtime as crawler — shared codebase)
**Primary Dependencies**: `fastapi`, `uvicorn[standard]`, `jinja2`, `markdown-it-py` (with `linkify-it-py`, `mdit-py-plugins`), `bleach` (HTML sanitize), `python-multipart`. Frontend: HTMX 2 (CDN, no build).
**Storage**: SQLite (read-only mode via `mode=ro&immutable=0` URI), same `data/articles.db` from feature 001. FTS5 virtual table added by migration in this feature.
**Testing**: `pytest` + `httpx.AsyncClient` test client + `pytest-asyncio`. Snapshot tests for rendered HTML partials.
**Target Platform**: Local laptop primary; small VPS secondary (with auth).
**Project Type**: Web service
**Performance Goals**: Search p95 < 500ms for 10k corpus · article render < 1s · run-progress refresh interval 2s
**Constraints**: No outbound network from web process; all data from local SQLite. No persistent state except session cookie when auth enabled. Memory < 200MB resident.
**Scale/Scope**: 10k articles · single user · ~10 routes

## Constitution Check

| Principle | Check | Status |
|---|---|---|
| **I. Source-Config First** | UI consumes source registry; does not introduce source-specific UI code | ✅ |
| **II. Polite-By-Default** | Not applicable — UI does no fetching | n/a |
| **III. Test-First** | Route tests + partial-render snapshot tests required for every endpoint | ✅ |
| **IV. Many Small Files** | 10 routes split across 5 router modules; templates one-per-page | ✅ |
| **V. SQLite as Source of Truth** | Read-only access; FTS5 virtual table backed by triggers on `articles` | ✅ |
| **VI. Read-Only UI** | No POST endpoints touching corpus; all corpus data immutable from UI | ✅ |
| **VII. Failure Visibility** | Run page exposes per-URL errors and partial-success states | ✅ |

**Violations**: none.

## Project Structure

### Documentation (this feature)

```text
specs/002-web-ui/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # FTS5 + read-only views
├── quickstart.md        # Phase 1
└── contracts/
    └── routes.md        # All HTTP routes + response shapes
```

### Source code

```text
src/star_crawl/
├── web/
│   ├── app.py              # FastAPI factory: middleware, lifespan, router mount
│   ├── deps.py             # DB connection (read-only), auth, request helpers
│   ├── auth.py             # Optional basic auth from env
│   ├── routers/
│   │   ├── home.py         # GET /
│   │   ├── sources.py      # GET /sources, /sources/{name}
│   │   ├── articles.py     # GET /articles/{id}, /articles/{id}/jsonld
│   │   ├── search.py       # GET /search
│   │   └── runs.py         # GET /runs, /runs/{id}, /runs/{id}/progress
│   ├── templates/
│   │   ├── base.html
│   │   ├── home.html
│   │   ├── sources.html
│   │   ├── source.html
│   │   ├── article.html
│   │   ├── search.html
│   │   ├── runs.html
│   │   ├── run.html
│   │   └── partials/       # HTMX target fragments
│   │       ├── article_table.html
│   │       ├── search_results.html
│   │       └── run_row.html
│   └── static/
│       ├── styles.css      # CSS custom properties + grid layout
│       └── htmx.min.js     # vendored HTMX (no CDN at runtime)
└── cli.py                  # adds: star-crawl serve
```

## Phase 0 — Research

See [research.md](./research.md).

## Phase 1 — Design

- **FTS5 schema**: see [data-model.md](./data-model.md).
- **Routes contract**: see [contracts/routes.md](./contracts/routes.md).
- **Quickstart**: see [quickstart.md](./quickstart.md).

## Constitution Re-Check (post-design)

| Principle | Re-check | Status |
|---|---|---|
| I — config first | UI shows whatever sources exist; no hardcoded source lists | ✅ |
| III — test-first | Each router has paired `tests/web/test_<router>.py` | ✅ |
| IV — small files | Largest planned module `routers/runs.py` ~180 LOC | ✅ |
| V — SQLite truth | Confirmed: read-only URI; FTS5 maintained by triggers, not app code | ✅ |
| VI — read-only UI | Zero state-mutation routes; FastAPI app exposes only GET | ✅ |
| VII — failure visibility | `/runs/{id}` endpoint exposes errors table verbatim | ✅ |

**Result**: PASS. Ready for `/speckit-tasks`.
