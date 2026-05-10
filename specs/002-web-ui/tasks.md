# Tasks: Web UI

**Input**: Design documents from `specs/002-web-ui/`
**Prerequisites**: plan.md ✓ · spec.md ✓ · research.md ✓ · data-model.md ✓ · contracts/routes.md ✓
**Depends on**: feature 001 (crawler-core) — `data/articles.db` exists with the schema from `specs/001-crawler-core/data-model.md`.

**Tests**: INCLUDED — Constitution III mandates tests for FTS5 search behavior, route behavior, polling lifecycle.

**Organization**: Tasks grouped by user story (US1–US4). US1 + US2 are both P1; ship them together as the MVP.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Add `web` extra in `pyproject.toml`: `fastapi`, `uvicorn[standard]`, `jinja2`, `markdown-it-py`, `linkify-it-py`, `mdit-py-plugins`, `bleach`, `python-multipart`, `aiosqlite`
- [ ] T002 Add `dev` extras for web: `httpx[asgi]` (for test client), `pytest-httpx`
- [ ] T003 [P] Create `src/star_crawl/web/` package layout: `app.py`, `deps.py`, `auth.py`, `routers/`, `templates/`, `templates/partials/`, `static/`, `static/vendor/`
- [ ] T004 [P] Vendor static assets: download HTMX 2.x → `src/star_crawl/web/static/vendor/htmx.min.js`; record source URL + version in `static/vendor/README.md`
- [ ] T005 [P] Create `tests/web/` directory with `conftest.py` exposing `app_client` fixture (httpx ASGITransport against the FastAPI app, populated test DB)

---

## Phase 2: Foundational (Blocking Prerequisites)

- [ ] T006 Write SQL migration `src/star_crawl/migrations/002_fts5.sql` per `data-model.md`: FTS5 virtual table on (title, content_text), three triggers (ai/ad/au), one-time backfill INSERT
- [ ] T007 [P] `src/star_crawl/web/deps.py`: read-only DB connection factory using `file:data/articles.db?mode=ro` URI; FastAPI dependency `get_conn()` yielding connection
- [ ] T008 [P] `src/star_crawl/web/auth.py`: read `STAR_CRAWL_AUTH=user:pass` env; if set, install HTTPBasic dependency on all routes; if not, no-op dependency
- [ ] T009 [P] `src/star_crawl/web/app.py`: FastAPI factory `create_app()`; mounts `/static`; registers Jinja2 environment; lifespan opens/closes DB pool; exception handlers for 404/422/500 returning HTML
- [ ] T010 [P] Add `serve` command to `src/star_crawl/cli.py`: starts uvicorn; refuses non-loopback host unless `STAR_CRAWL_AUTH` set (emit actionable error); flags `--host`, `--port`
- [ ] T011 [P] Create `src/star_crawl/web/templates/base.html`: minimal HTML5 shell, top nav (Dashboard · Sources · Runs), header search box, dark/light auto via `prefers-color-scheme`; pulls `static/styles.css` and `static/vendor/htmx.min.js`
- [ ] T012 [P] Create `src/star_crawl/web/static/styles.css` using OKLCH design tokens consistent with `PLAN.html`/`WIREFRAMES.html`
- [ ] T013 [P] `tests/web/test_app_smoke.py`: app starts; `/healthz` returns 200 with `{status: ok}`; `/static/styles.css` returns 200 with `Cache-Control` header
- [ ] T014 [P] `tests/web/test_auth.py`: with `STAR_CRAWL_AUTH=user:pass` set, requests without auth get 401; with correct auth pass; without env set no auth required
- [ ] T015 [P] `tests/web/test_serve_safety.py`: `star-crawl serve --host 0.0.0.0` without `STAR_CRAWL_AUTH` exits non-zero with clear message

**Checkpoint**: Foundation ready — app boots, auth gating works, default-loopback enforced.

---

## Phase 3: User Story 1 — Browse the corpus visually (P1) 🎯 MVP part 1

**Goal**: Open the UI in a browser, see totals + sources + recent runs; click into a source, see article list; click an article, read it.

**Independent Test**: With a populated DB, `/`, `/sources`, `/sources/<name>`, and `/articles/<id>` all render; an article shows its content + sidebar metadata.

### Tests

- [ ] T016 [P] [US1] `tests/web/test_home.py`: `/` returns 200 with totals computed from test DB; HTML contains `total_articles`, source count, recent runs section
- [ ] T017 [P] [US1] `tests/web/test_sources.py`: `/sources` lists all sources; `/sources/<name>` paginates; `?lang=en` filters; `?since=2026-01-01` filters; non-existent source → 404 HTML page
- [ ] T018 [P] [US1] `tests/web/test_articles.py`: `/articles/<id>` renders Markdown body + sidebar; non-existent ID → 404 HTML page; XSS in fixture content is sanitized (no `<script>` in output)
- [ ] T019 [P] [US1] `tests/web/test_partials.py`: HTMX request (`HX-Request: true` header) to `/sources/<name>?page=2` returns only the table partial, not the layout

### Implementation

- [ ] T020 [P] [US1] `src/star_crawl/web/routers/home.py`: `GET /` route; queries totals + recent runs per `data-model.md`; renders `home.html`
- [ ] T021 [P] [US1] `src/star_crawl/web/routers/sources.py`: `GET /sources` (grid) and `GET /sources/{name}` (paginated table with filter/sort)
- [ ] T022 [P] [US1] `src/star_crawl/web/routers/articles.py`: `GET /articles/{id}` (full page) + `GET /articles/{id}/jsonld` (HTML or JSON via `Accept`)
- [ ] T023 [P] [US1] `src/star_crawl/web/markdown.py`: helper wrapping `markdown-it-py` (with linkify, tables, footnote, anchor) → bleach.clean with safe tag/attr allowlist → return SafeString
- [ ] T024 [P] [US1] Templates: `home.html`, `sources.html`, `source.html`, `article.html` — server-rendered, `{% extends 'base.html' %}`
- [ ] T025 [P] [US1] Partials: `partials/article_table.html`, `partials/source_card.html`, `partials/run_row.html`
- [ ] T026 [US1] Wire all three routers into `app.py`; add `pagination` helper for source detail
- [ ] T027 [US1] Empty-state handling: when corpus has zero articles, home page shows "no articles yet" with `star-crawl run --all` instruction (per FR-017 + edge case)

**Checkpoint**: US1 ships. User can browse the corpus visually.

---

## Phase 4: User Story 2 — Find articles by keyword (P1) 🎯 MVP part 2

**Goal**: Type a query in the search box; matching articles appear ranked by relevance with snippet highlights.

**Independent Test**: With a corpus of ≥ 100 articles, search a known phrase appearing in ≥ 3 articles; assert ≥ 3 results returned with the phrase highlighted in snippets.

### Tests

- [ ] T028 [P] [US2] `tests/web/test_search_fts.py`: insert fixture articles; query exact phrase → assert hit count + snippet contains `<mark>`; query with no match → "no results" empty state
- [ ] T029 [P] [US2] `tests/web/test_search_filter.py`: `?source=uber_engineering` restricts results
- [ ] T030 [P] [US2] `tests/web/test_search_live.py`: HTMX request returns only `#results` fragment; debounce attribute present in full-page HTML
- [ ] T031 [P] [US2] `tests/web/test_search_perf.py`: with 5k synthetic articles, search query returns in p95 < 500ms (use `time.perf_counter()`); fail with actionable message if not
- [ ] T032 [P] [US2] `tests/web/test_search_special_chars.py`: query with FTS5 syntax characters (`"`, `*`, `(`, `)`) → either treated as plain text or applied per docs; never returns 500

### Implementation

- [ ] T033 [P] [US2] `src/star_crawl/web/routers/search.py`: `GET /search` route; FTS5 query with `bm25(articles_fts, 4.0, 1.0)` rank; `snippet(...)` for highlighted excerpts
- [ ] T034 [P] [US2] `src/star_crawl/web/search_query.py`: parse user query → safe FTS5 MATCH expression; escape special chars when needed
- [ ] T035 [P] [US2] Templates: `search.html` (full page) and `partials/search_results.html` (HTMX target)
- [ ] T036 [US2] Header search box wires `hx-trigger="keyup changed delay:300ms"`, `hx-get="/search"`, `hx-target="#results"`; `/` keyboard shortcut focuses input
- [ ] T037 [US2] Empty-query state: redirect to `/search` with empty result list (not 422)
- [ ] T038 [US2] No-results state: render with friendly message echoing the query

**Checkpoint**: US2 ships. MVP (US1 + US2) is complete — corpus is browseable and searchable.

---

## Phase 5: User Story 3 — Watch a crawl run in progress (P2)

**Goal**: Open `/runs` while a crawl is running; see counts updating without manual refresh.

**Independent Test**: Insert a `crawl_runs` row with `status='running'` + a frontier with mixed states; load `/runs`; the row carries the `hx-trigger="every 2s"`; updating the row's counts in DB makes the next poll show new numbers; setting status to `success` removes the trigger.

### Tests

- [ ] T039 [P] [US3] `tests/web/test_runs.py`: `/runs` lists all runs with status pills; `/runs/{id}` shows stats strip + errors + new articles
- [ ] T040 [P] [US3] `tests/web/test_runs_progress.py`: GET `/runs/{id}/progress` returns single-row HTML fragment; while `status='running'`, fragment carries `hx-trigger="every 2s"`; once status terminal, fragment omits the trigger (poll loop ends)
- [ ] T041 [P] [US3] `tests/web/test_runs_filters.py`: `?status=failed` and `?source=...` and `?since=...` filters work

### Implementation

- [ ] T042 [P] [US3] `src/star_crawl/web/routers/runs.py`: `GET /runs`, `GET /runs/{id}`, `GET /runs/{id}/progress`
- [ ] T043 [P] [US3] Templates: `runs.html`, `run.html`, `partials/run_row.html`
- [ ] T044 [US3] In `partials/run_row.html`, render `hx-trigger` only when `status == 'running'`; templating ensures the loop is server-controlled
- [ ] T045 [US3] On `runs.html`, in-progress rows include the polling fragment that reuses `partials/run_row.html`

**Checkpoint**: US3 ships. Live progress observable in browser.

---

## Phase 6: User Story 4 — Use the interface safely (P2)

**Goal**: Default-bound to loopback; non-loopback bind requires `STAR_CRAWL_AUTH`. Confirmed in T015 (foundational); this phase adds the documentation + UX polish.

### Tests

- [ ] T046 [P] [US4] `tests/web/test_serve_safety_advanced.py`: `--host 0.0.0.0` without auth → exit 3 with stderr "exposed mode requires STAR_CRAWL_AUTH=..."; with auth → starts and binds
- [ ] T047 [P] [US4] `tests/web/test_security_headers.py`: response carries `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`

### Implementation

- [ ] T048 [P] [US4] `src/star_crawl/web/app.py`: add security headers middleware
- [ ] T049 [P] [US4] Update `quickstart.md` with the exposed-mode workflow + example reverse-proxy config (Caddy snippet)
- [ ] T050 [P] [US4] In CLI, when `STAR_CRAWL_AUTH` is set, log "auth: enabled (user=<masked>)" at startup so user sees confirmation

**Checkpoint**: US4 ships. Safe-by-default, opt-in exposure with auth.

---

## Phase 7: Polish & Cross-Cutting

- [ ] T051 [P] `tests/web/test_404.py`: every route variant with non-existent IDs returns the friendly HTML 404, not stack traces
- [ ] T052 [P] `tests/web/test_500_handler.py`: deliberate exception in route → 500 page returns; assert response body does **NOT** contain `Traceback`, file system paths (`/usr/`, `src/star_crawl/`), or the raised exception's class name. Verify only the user-facing error template is rendered. (Tightened per FR-019 — internal stack traces must never reach the client.)
- [ ] T053 [P] Render performance: profile `/sources/<name>` and `/search` against 10k-article fixture; capture timing in `tests/web/test_perf.py` with hard p95 thresholds
- [ ] T054 [P] Mobile: verify article reader page works on 375px viewport (test via Playwright snapshot if feasible; otherwise manual checklist)
- [ ] T055 [P] Empty-state polish: every list/grid view shows actionable message when empty
- [ ] T056 [P] Accessibility: every form input has a label; nav has `aria-label`; color contrast meets WCAG AA in both light and dark modes
- [ ] T057 [P] `Cache-Control: max-age=86400, immutable` on `/static/vendor/*`; `no-store` on dynamic routes
- [ ] T058 [P] Coverage check: `pytest --cov=star_crawl.web --cov-fail-under=80`
- [ ] T059 Update `README.md` and `quickstart.md` with verified `serve` flow

---

## Dependencies graph

```
Setup (T001-T005)
       │
Foundational (T006-T015) — FTS5 migration, app factory, auth, base template
       │
       ├──► US1 P1 (T016-T027) ─┐
       │                         ├──► MVP ships
       ├──► US2 P1 (T028-T038) ─┘
       │
       ├──► US3 P2 (T039-T045) — live progress
       │
       ├──► US4 P2 (T046-T050) — security polish
       │
       └──► Polish (T051-T059)
```

US1 and US2 are independent — both ship together as MVP. US3 and US4 each independent of US1/US2.

---

## Parallel execution examples

After Foundational (T006–T015) lands, three parallel streams:

```bash
# Stream A — US1 routers + templates (browse)
T020 + T021 + T022 + T024 + T025  # all [P], different files

# Stream B — US2 search (FTS5 + live)
T033 + T034 + T035                 # all [P], different files

# Stream C — US3 runs
T042 + T043                        # both [P], different files
```

Tests T016–T019, T028–T032, T039–T041 all parallelizable across these streams.

---

## Implementation strategy

1. **Setup + Foundational** (T001–T015) — ~1 day. App boots, auth works, base template renders, FTS5 migration applied.
2. **US1 + US2 = MVP** (T016–T038) — ~1.5 days, parallelized. End state: open `/`, browse + search the corpus.
3. **US3 live progress** (T039–T045) — ~0.5 day.
4. **US4 safety polish** (T046–T050) — ~0.3 day.
5. **Polish** (T051–T059) — ~0.5 day.

**Total**: ~4 days. MVP (browse + search) in ~2.5 days.

---

## Format validation

All 59 tasks follow `- [ ] TXXX [P?] [USx?] Description with file path`. Setup/Foundational/Polish phases have no story label. User-story phases all carry `[USx]`. Every implementation task names a concrete file path.
