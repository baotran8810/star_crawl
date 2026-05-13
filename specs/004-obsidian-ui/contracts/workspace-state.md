# Contract: Workspace state (localStorage)

The entire workspace state lives under a single `localStorage` key:

```
star_crawl.workspace.v1
```

Value is a JSON-encoded `WorkspaceState` object. The schema is versioned via the key suffix so a
breaking change can introduce `star_crawl.workspace.v2` without colliding.

## Schema (informal — JSON)

```jsonc
{
  "schema_version": 1,                       // integer; must equal 1 for this version
  "tabs": [                                  // ordered list, length 0..50
    {
      "id": "f2e7…-uuidv4",                  // crypto.randomUUID()
      "kind": "graph",                       // "article" | "run" | "source" | "search" | "graph"
      "target_id": null,                     // string | null
      "title": "Topic graph",
      "panel_url": "/panel/graph",
      "scroll_y": 0,
      "graph_state": {                       // present only when kind == "graph"
        "zoom": 1.0,
        "pan_x": 0,
        "pan_y": 0,
        "focused_kw_id": null
      },
      "created_at": "2026-05-13T14:30:00Z"
    }
  ],
  "active_tab_id": "f2e7…-uuidv4",           // matches one tabs[*].id, or null when tabs is empty
  "theme": "system",                         // "light" | "dark" | "system"
  "cluster_color_enabled": false,            // boolean
  "tree_collapsed": false,                   // boolean
  "tree_expanded_sections": ["sources"],     // array of section ids
  "updated_at": "2026-05-13T14:30:00Z"
}
```

## Default state (no saved state, or version mismatch)

```jsonc
{
  "schema_version": 1,
  "tabs": [
    {
      "id": "<fresh-uuid>",
      "kind": "graph",
      "target_id": null,
      "title": "Topic graph",
      "panel_url": "/panel/graph",
      "scroll_y": 0,
      "graph_state": { "zoom": 1.0, "pan_x": 0, "pan_y": 0, "focused_kw_id": null },
      "created_at": "<now>"
    }
  ],
  "active_tab_id": "<fresh-uuid>",
  "theme": "system",
  "cluster_color_enabled": false,
  "tree_collapsed": false,
  "tree_expanded_sections": ["sources"],
  "updated_at": "<now>"
}
```

## Validation (on read)

`workspace.js` MUST run a validation pass before accepting a stored payload. If any rule fails,
the offending field is replaced with its default and the resulting state is re-written. If the
top-level shape is unparseable, the default state replaces it entirely.

| Rule | If violated |
|---|---|
| `schema_version === 1` | Reset to default. |
| `Array.isArray(tabs) && tabs.length <= 50` | Truncate to first 50; if not an array, replace with default tabs. |
| `tabs[*].kind ∈ {article, run, source, search, graph}` | Drop the offending tab. |
| `tabs[*].panel_url startsWith "/panel/"` | Drop the offending tab. |
| `active_tab_id ∈ tabs[*].id` OR `(tabs.length === 0 && active_tab_id === null)` | Reset to first tab id, or null. |
| `theme ∈ {light, dark, system}` | Reset to `"system"`. |
| `0.1 <= graph_state.zoom <= 5.0` | Clamp to range. |

## Write coalescing

Writes happen via `workspace.requestPersist()`, which schedules a `requestIdleCallback`
(fallback `setTimeout(_, 250)`). Multiple mutations within the window collapse to one write.
Direct synchronous writes are used only for the `tab-opened` and `tab-closed` events so a tab
created moments before a navigation event is not lost.

## Events emitted by `workspace.js`

All events bubble on `document`. `detail` is the workspace event payload.

| Event | When | `detail` |
|---|---|---|
| `workspace:tab-opened` | After a new tab is added | `{ tab }` |
| `workspace:tab-closed` | After a tab is removed | `{ tab_id, was_active }` |
| `workspace:tab-activated` | After active_tab_id changes | `{ tab_id, prev_tab_id }` |
| `workspace:tab-reordered` | After drag-and-drop | `{ tab_id, new_index }` |
| `workspace:state-restored` | After initial load | `{ tab_count, restored_from_storage: boolean }` |
| `workspace:theme-changed` | After theme mutation | `{ theme }` (the persisted value, not resolved) |
| `workspace:cluster-color-changed` | After toggle | `{ enabled: boolean }` |

External modules subscribe via `document.addEventListener('workspace:…', e => …)`.

## Backwards compatibility & migration

- Future schema bumps create `star_crawl.workspace.v2`. The previous key is deleted only when the
  v2 module loads successfully and writes a fresh value, so a downgrade still has v1 data.
- This feature does NOT migrate older keys (none exist). The validation pass guarantees that any
  payload is safe to load regardless of corruption.

## Size budget

- Typical session ≤ 4 KB. Hard cap ≤ 100 KB at 50 tabs with full graph_state. Far under the
  ~5 MB browser localStorage cap.
