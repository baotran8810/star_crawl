# Contract: Web UI Routes

**Owner**: Web UI
**Version**: 0.1.0
**Base**: All routes under `/`. Read-only.

## Conventions

- Full-page request returns layout + content. HTMX request (header `HX-Request: true`) returns only the partial.
- `Cache-Control: no-store` on all dynamic endpoints. Static assets served with `max-age=86400, immutable` (filename hashing not used at this scale).
- All errors render an HTML error page; structured `{"error": "..."}` JSON only when `Accept: application/json`.

## Routes

### `GET /`

Home / dashboard.

**Response**: HTML page with totals, source cards (top 6), recent runs (top 5).

### `GET /sources`

All sources.

**Query params**: `category=<string>` (optional)

**Response**: HTML grid of source cards. Cards link to `/sources/{name}`.

### `GET /sources/{name}`

Article list for one source.

**Path**: `name` — must match an existing `sources.name`.

**Query params**:
- `page=<int>` (default 1, 1-indexed)
- `lang=<iso639-1>` (optional)
- `since=<YYYY-MM-DD>` (optional)
- `sort=published_at|title` (default `published_at`)
- `order=asc|desc` (default `desc`)

**Response**:
- Full request: HTML page with header + filter bar + article table + pagination.
- HTMX request (`HX-Request: true`): only the article table + pagination fragment.

**404**: Returned when `name` does not exist; HTML page explains the source is not configured.

### `GET /articles/{id}`

Article detail.

**Path**: `id` — integer.

**Response**: HTML page with rendered Markdown body + metadata sidebar.

**404**: Returned when ID does not exist; clear empty-state HTML page.

### `GET /articles/{id}/jsonld`

Raw JSON-LD payload for an article.

**Headers**:
- `Accept: text/html` (default) → pretty-printed HTML view.
- `Accept: application/ld+json` → raw JSON.

**404**: Same handling as above.

### `GET /search`

Full-text search.

**Query params**:
- `q=<string>` (required; empty → empty state)
- `source=<string>` (optional, filter to one source)
- `page=<int>` (default 1)

**Response**:
- Full: HTML page with search box (echoing `q`), filter chips, results.
- HTMX (live search, debounced 300ms keyup on the search input): fragment containing only the `<div id="results">` content.

**Empty results**: HTML state explaining "no matches for '<q>'", not a 404.

### `GET /runs`

Crawl history.

**Query params**:
- `source=<string>` (optional)
- `status=running|success|partial|failed` (optional)
- `since=<YYYY-MM-DD>` (default = last 7 days)

**Response**: HTML page with filter bar + run rows. Rows with `status=running` carry `hx-trigger="every 2s"` and `hx-get="/runs/{id}/progress"`.

### `GET /runs/{id}`

Run detail.

**Path**: `id` — integer.

**Response**: HTML page with stats strip, errors list, articles added by this run.

**404**: Same handling.

### `GET /runs/{id}/progress`

HTMX-only fragment for one run row (used by the polling loop).

**Response**: HTML fragment of one row.

**Lifecycle**: When `status` is terminal (`success | partial | failed`), the response fragment omits the `hx-trigger="every 2s"` attribute, ending the polling loop client-side.

### `GET /healthz`

Liveness check.

**Response**:

```json
{"status": "ok", "db": "ok", "schema_version": "<n>"}
```

Used by reverse proxies and `curl` smoke checks. Returns 503 if DB is unreachable.

### `GET /static/{path}`

Static asset (CSS, vendored HTMX, fonts).

## Authentication

When `STAR_CRAWL_AUTH=user:pass` is set in env, all routes (including `/healthz`) require HTTP basic auth. Without it, no auth and only `127.0.0.1` binding is allowed.

## Error responses

| Status | When |
|---|---|
| 200 | Normal success, including empty result sets |
| 304 | Static asset not modified |
| 401 | Auth required and missing/wrong credential |
| 404 | Path or ID does not exist |
| 422 | Query param failed validation (e.g., `since=garbage`) |
| 500 | Internal error — generic page; details in server log only |
| 503 | DB unreachable (used by `/healthz`) |

## Response time targets

| Route | p50 | p95 |
|---|---|---|
| `/` | 100ms | 250ms |
| `/sources` | 50ms | 150ms |
| `/sources/{name}` | 80ms | 250ms |
| `/articles/{id}` | 80ms | 250ms |
| `/search` | 150ms | 500ms |
| `/runs` | 80ms | 200ms |
| `/runs/{id}/progress` | 50ms | 100ms |

Measured against a 10k-article corpus on a 2023-class laptop.
