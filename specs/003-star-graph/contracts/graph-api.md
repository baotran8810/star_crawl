# Contract: Graph Web API

**Owner**: Star-Graph
**Version**: 0.1.0
**Mounted under**: Web UI app (feature 002).

## Routes

### `GET /graph`

The graph page (HTML shell).

**Query params**: same as `/graph.json` — they're rendered as initial state (so a deep link works).

**Response**: Full HTML page containing:
- Top-nav (extends feature 002's nav with a `Graph` tab).
- Filter sidebar (source checkboxes, time range picker, min-frequency slider, min-NPMI slider, layout selector).
- Canvas `<div id="cy">` for Cytoscape.
- Empty side panel (populated by HTMX after node click).
- Inline JSON with the initial graph payload (so first paint doesn't need a second request).

**Stale banner**: If the latest `graph_meta.n_articles` is more than 5% behind current `articles` count, an in-page banner appears: "Graph is N articles behind. Run `star-crawl build-graph` to refresh."

### `GET /graph.json`

The graph payload in Cytoscape elements format.

**Query params**:

| Param | Type | Default | Description |
|---|---|---|---|
| `source` | repeatable | none (= all) | Source name filter |
| `since` | YYYY-MM-DD | none | Only articles published on or after |
| `until` | YYYY-MM-DD | none | Only articles published on or before |
| `min_freq` | int | 3 | Hide nodes with `doc_freq` below |
| `min_npmi` | float | 0.15 | Hide edges with `npmi` below |
| `cluster` | int | none | Restrict to one cluster |
| `focus` | int (keyword id) | none | Return only the keyword + its first-degree neighbors |

**Response** (200 OK, `Content-Type: application/json`):

```json
{
  "nodes": [
    {
      "data": {
        "id": "k_42",
        "term": "kafka",
        "display": "Kafka",
        "doc_freq": 142,
        "cluster_id": 3,
        "cluster_label": "Event Streaming",
        "color": "oklch(72% 0.16 250)",
        "degree": 38
      }
    }
  ],
  "edges": [
    {
      "data": {
        "id": "e_42_98",
        "source": "k_42",
        "target": "k_98",
        "co_count": 23,
        "npmi": 0.71
      }
    }
  ],
  "meta": {
    "built_at": "2026-05-09T22:14:00Z",
    "n_articles_at_build": 1247,
    "n_articles_now": 1247,
    "filters_applied": {
      "source": null,
      "since": null,
      "min_freq": 3,
      "min_npmi": 0.15
    }
  }
}
```

**Caching**: ETag header set to `"<built_at_iso>:<filter_hash>"`. Clients use `If-None-Match` for revalidation; server returns 304 when unchanged.

**Errors**:
- 422 — invalid query parameters (e.g., `since=garbage`).
- 503 — graph not yet built (no `graph_meta` rows). Body: `{"error": "graph not built — run star-crawl build-graph"}`.

### `GET /keywords/{id}`

Side panel partial — used by HTMX on node click.

**Path**: `id` — keyword integer ID.

**Response** (HTML fragment):

```html
<div class="keyword-panel">
  <h3>Kafka</h3>
  <p class="meta">streaming cluster · 142 articles · degree 38</p>

  <h4>Top neighbors</h4>
  <ul>
    <li><a hx-get="/keywords/98" ...>stream <span>0.71</span></a></li>
    ...
  </ul>

  <h4>Recent articles</h4>
  <ul>
    <li><a href="/articles/8f3a">Realtime Routing Costs <em>uber · 2026-04-28</em></a></li>
    ...
  </ul>
</div>
```

The neighbor links carry `hx-get="/keywords/{id}" hx-target=".keyword-panel" hx-swap="outerHTML"` so clicking a neighbor swaps the panel without a full page reload.

**404**: When `id` does not match a keyword, return an HTML fragment with a clear "keyword not found" message (not a JSON error — this is an HTMX target).

### `GET /keywords/search`

Type-ahead suggestion.

**Query**: `q=<string>` (case-insensitive prefix or substring match against `keywords.term`).

**Response** (HTML fragment, list of `<li>`):

```html
<ul class="kw-suggestions">
  <li hx-get="/keywords/42" ...>kafka <span>(142)</span></li>
  <li hx-get="/keywords/87" ...>kafka-streams <span>(34)</span></li>
  ...
</ul>
```

**Limit**: top 10 matches, ranked by `doc_freq` descending.

**Empty `q`**: returns empty `<ul>`.

## Auth

Same as feature 002 — when `STAR_CRAWL_AUTH` is set, all routes require basic auth.

## Performance targets

| Route | p50 | p95 |
|---|---|---|
| `/graph` (full page, with inline JSON) | 200ms | 500ms |
| `/graph.json` (no filters) | 100ms | 300ms |
| `/graph.json` (filtered) | 150ms | 400ms |
| `/keywords/{id}` | 50ms | 150ms |
| `/keywords/search` | 30ms | 100ms |

Measured against a 10k-article corpus / ~3k keywords / ~10k edges.

## Read-only guarantee

These routes MUST NOT modify any DB state. Verified by integration test asserting row counts don't change across all routes.
