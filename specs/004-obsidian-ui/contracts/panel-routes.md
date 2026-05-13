# Contract: Panel routes

The shell at `/` loads tab content by fetching server-rendered HTML partials from `/panel/...`
routes. Each `/panel/...` route mirrors an existing top-level route but returns ONLY the inner
content fragment (no `<html>`, no nav, no scripts). Existing top-level routes continue to render
the full `base.html` layout for direct, JS-less, or external-link access.

All routes inherit the existing `auth_required` dependency from `src/star_crawl/web/auth.py`.

## Conventions

- All `/panel/...` responses return `text/html; charset=utf-8` with status `200`.
- Response body is a single root element that the client inserts via `hx-swap="innerHTML"` into
  the tab's panel container.
- 4xx is rendered as a tiny inline error partial (`templates/partials/panel_unavailable.html`).
- Cache headers: `Cache-Control: private, no-store`. Content depends on session auth + corpus.

## Endpoints

### `GET /` — Workspace shell

| | |
|---|---|
| **Purpose** | Render the empty shell with icon rail, tree, tab bar, status bar. Boots `workspace.js` which restores tabs from localStorage. |
| **Response** | Full `shell.html` template. Server does NOT know which tabs the client will restore. |
| **Auth** | yes |

### `GET /tree` — Navigation tree partial

| | |
|---|---|
| **Purpose** | Return the tree under the icon rail. Used both on initial load and on lazy-section expand. |
| **Query** | `section`: optional, one of `sources`, `runs`, `bookmarks`, `searches`. Omit to fetch the top level. `expand=true`: include first-level children of every section. |
| **Response** | `<ul class="tree">…</ul>` partial. Items carry `data-panel-url`, `data-kind`, `data-target-id`. |
| **Examples** | `/tree` · `/tree?section=sources&expand=true` · `/tree?section=sources/uber_engineering` (returns articles under that source) |

### `GET /panel/graph` — Graph panel

| | |
|---|---|
| **Purpose** | Return the graph view's HTML chassis (filter panel + canvas + keyword side panel). Reuses existing `templates/graph.html` body. |
| **Query** | All existing graph filters: `min_freq`, `min_npmi`, `source`, `since`, `until`, `cluster`, `focus`. Same semantics as today. |
| **Response** | Graph chassis. Cytoscape boot happens client-side via existing `graph.js`. |

### `GET /panel/article/{article_id}` — Article reader panel

| | |
|---|---|
| **Purpose** | Render an article's body, metadata, and keyword chips. Reuses `templates/article.html` body. |
| **Path param** | `article_id` integer. |
| **404 behaviour** | Returns 200 with `panel_unavailable.html` partial — never bubbles a 404 into the workspace. |

### `GET /panel/run/{run_id}` — Run detail panel

| | |
|---|---|
| **Purpose** | Render a crawl run's status, errors, and new articles. Reuses `templates/run.html` body. |
| **Path param** | `run_id` integer. |

### `GET /panel/source/{source_name}` — Source detail panel

| | |
|---|---|
| **Purpose** | Render a source's configuration summary + recent articles. Reuses `templates/source.html` body. |
| **Path param** | `source_name` slug. |

### `GET /panel/runs` — Runs list panel

| | |
|---|---|
| **Purpose** | Render the full runs list. Reuses `templates/runs.html` body. Live progress polling for running rows still works via the existing `/runs/{id}/progress` partial. |
| **Query** | `source`, `status`, `since` — same as `/runs`. |

### `GET /panel/search` — Search panel

| | |
|---|---|
| **Purpose** | Render the search form + results. Reuses `templates/search.html` body. |
| **Query** | `q` — search query. Empty `q` shows the search form alone. |

### `GET /palette/objects.json` — Command-palette object index

| | |
|---|---|
| **Purpose** | Flat list of palette-searchable corpus objects. Loaded once per session. |
| **Response** | `application/json` array of `{kind, id, label, subtitle, panel_url}` rows. |
| **Caching** | `Cache-Control: private, max-age=60`. Refetched if the user reopens the palette after a Rebuild. |
| **Shape** | <br/>`{ kind: "article", id: 123, label: "Apache Hudi at Uber", subtitle: "uber_engineering · 2024-08-12", panel_url: "/panel/article/123" }` <br/> `{ kind: "run", id: 7, label: "Run #7", subtitle: "uber_engineering · partial · 140 new", panel_url: "/panel/run/7" }` <br/>`{ kind: "source", id: "uber_engineering", label: "Uber Engineering", subtitle: "226 articles", panel_url: "/panel/source/uber_engineering" }` <br/>`{ kind: "keyword", id: 691, label: "Go", subtitle: "doc_freq=116", panel_url: null }`  |

> Keywords have `panel_url: null` because activating a keyword in the palette should focus it on
> the active (or newly-opened) graph tab via `workspace.js`, not open its own panel.

## Auth & rate

- All endpoints require auth (HTTP Basic if `STAR_CRAWL_AUTH` is set).
- No new rate limits — corpus is single-user.

## Errors

| Code | When | Body |
|---|---|---|
| 200 | Normal | The panel partial. |
| 401 | Missing/wrong creds | HTMX surfaces via the existing auth path; no shell-specific handling. |
| 404 | Item exists in path but route mistyped | Standard FastAPI 404. Should not happen in practice. |
| 422 | Bad query param shape (e.g., bad date) | Standard FastAPI validation error. Workspace shows the body inline. |

Item-missing cases (article id no longer present, run deleted) return **200 + an inline
unavailable partial**, not 404. This keeps the tab in the workspace with a clear close action,
per FR-021.

## Back-compat

Top-level routes — `/articles/{id}`, `/runs/{id}`, `/sources/{name}`, `/runs`, `/search`, `/graph` —
keep their existing behaviour and `base.html` layout. They share the same handler body as the
`/panel/...` variant via a small `_render_panel(request, template_body, ctx)` helper that picks the
right layout based on the path prefix.
