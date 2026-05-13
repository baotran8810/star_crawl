# Data Model: Obsidian-style Web UI

This feature introduces **no new SQLite tables** and changes no existing tables. All persistent
data is in the browser's `localStorage`, keyed under `star_crawl.workspace.v1`. The contract for
that envelope is described in [`contracts/workspace-state.md`](./contracts/workspace-state.md);
this file describes the entities at the conceptual level.

## Entities (client-side, browser-local)

### WorkspaceState

Root entity. Versioned envelope.

| Field | Type | Constraints |
|---|---|---|
| `schema_version` | integer | Currently `1`. Bumped on incompatible schema changes; missing or unknown values reset state to default. |
| `tabs` | ordered list of `Tab` | 0 … 50 entries. Order is the visual order in the tab bar. |
| `active_tab_id` | string \| null | MUST match one `tabs[*].id`, or be `null` only if `tabs` is empty (which triggers FR-021 auto-open). |
| `theme` | `"light" \| "dark" \| "system"` | Default `"system"`. |
| `cluster_color_enabled` | boolean | Default `false`. Controls graph monochrome vs colored. |
| `tree_collapsed` | boolean | Default `false`. Whether the navigation tree panel is hidden. |
| `tree_expanded_sections` | array of section ids | E.g., `["sources", "runs"]`. Default `["sources"]`. |
| `updated_at` | ISO-8601 string | Updated on every state mutation. Used only for debugging. |

### Tab

A live reference to one corpus object plus its ephemeral viewing state.

| Field | Type | Constraints |
|---|---|---|
| `id` | string | Client-generated UUIDv4 (or `crypto.randomUUID()`). Stable for tab lifetime. |
| `kind` | `"article" \| "run" \| "source" \| "search" \| "graph"` | Determines which panel route to fetch. |
| `target_id` | string \| null | Identifier within `kind`. For `graph`, `null`. For `article`, the article id. For `search`, the URL-encoded query. |
| `title` | string | Human label shown in the tab. Short — truncates at ~30 chars. |
| `panel_url` | string | The `/panel/...` URL to fetch initial content. Pre-computed so the tab can restore without route logic. |
| `scroll_y` | integer | Pixels. Restored on tab activate. |
| `graph_state` | object \| null | Present only if `kind == "graph"`. See **GraphTabState**. |
| `created_at` | ISO-8601 string | For ordering and debug. |

### GraphTabState

Ephemeral state local to a graph tab. Restored on tab activate AND on workspace restore.

| Field | Type | Constraints |
|---|---|---|
| `zoom` | number | Cytoscape zoom level (e.g., `0.4`–`3.0`). |
| `pan_x` / `pan_y` | number | Cytoscape pan coordinates (px). |
| `focused_kw_id` | integer \| null | Currently focus-locked keyword (matches `keywords.id`); `null` means no focus. |
| `min_freq` | integer | Last filter value (default 3). NOT restored on browser restart per clarify Q2. |
| `min_npmi` | number | Last filter value (default 0.15). NOT restored on browser restart per clarify Q2. |

> Per Clarification Q2: `min_freq` and `min_npmi` ARE preserved within a session (in-memory), but
> are NOT restored from localStorage. On restart, the graph tab opens with default filters.

### ThemePreference (logical view)

Derived from `WorkspaceState.theme`. Resolved at runtime:
- `"light"` → `light`
- `"dark"` → `dark`
- `"system"` → matches `prefers-color-scheme` at load time and live-updates on system change.

### ClusterColourPreference (logical view)

Derived from `WorkspaceState.cluster_color_enabled`. Independent of theme.

### NavigationTreeNode (server-side render, not persisted)

Server returns the tree as HTML partial; client only persists which sections are expanded
(see `WorkspaceState.tree_expanded_sections`). For completeness the server-side row shape is:

| Field | Type | Notes |
|---|---|---|
| `id` | string | E.g., `"sources/uber_engineering"` or `"runs/7"`. |
| `kind` | enum | `"section" \| "source" \| "run" \| "article" \| "search"`. |
| `label` | string | Display text. |
| `meta` | string \| null | E.g., article count, run status. Rendered as `<small class="muted">`. |
| `panel_url` | string \| null | Where activation should target. Null for sections (toggle expand instead). |
| `children` | array of node | Nested list. Empty by default; expanded sections fetch lazily. |

## Lifecycle & transitions

### Tab open

```
event: tree click | palette select | middle-click
inputs: kind, target_id
state change: append Tab to tabs; set active_tab_id = new.id
side effects: HTMX fetch panel_url into the new tab's panel container
```

### Tab close

```
event: tab X click | Cmd-W | "Close all tabs" palette action
state change: remove Tab from tabs;
              if active, set active_tab_id = previous-most-recent tab id (or null if empty)
              if tabs becomes empty: auto-open default graph tab (FR-021)
side effects: destroy DOM panel container; Cytoscape instance survives if it's the graph tab being kept
```

### Tab activate

```
event: tab click | Alt+N | popstate from history
state change: active_tab_id = id
side effects:
  - leaving panel: display:none, save scroll_y to its Tab
  - entering panel: display:block, restore scroll_y, dispatch 'workspace:tab-activated' event
  - if entering tab is graph: cy.resize() then cy.viewport({zoom, pan}) inside rAF
```

### Workspace restore (on page load)

```
read localStorage[star_crawl.workspace.v1]
if missing or schema_version != 1: initialize default with one graph Tab
for each Tab in tabs:
  render its panel container under the main area, hidden
  HTMX fetch panel_url into its container
  on load complete: apply scroll_y; if graph, apply graph_state
activate the saved active_tab_id (or first if not found)
```

### Theme change

```
event: status-bar toggle | palette action | system prefers-color-scheme change
state change: WorkspaceState.theme updated
side effects:
  - set document <html data-theme="…">
  - for each open graph tab: re-apply cytoscape node colors that reference CSS vars
```

### Cluster colour change

```
event: graph filter panel toggle | palette action
state change: cluster_color_enabled
side effects:
  - for each open graph tab: re-apply node colors
  - re-render legend in graph keyword side panel (show vs hide swatch column)
```

## Validation rules (enforced by `workspace.js` on read)

1. `tabs.length` ≤ 50. If exceeded on read (corrupted state), keep first 50.
2. `active_tab_id` MUST exist in `tabs[*].id`; otherwise set to first tab id or null.
3. Each `Tab.kind` MUST be in the allowed enum; unknown kinds are dropped silently and logged to console.
4. `Tab.panel_url` MUST be a relative URL starting with `/panel/`; absolute or external URLs are dropped.
5. `Tab.scroll_y` clamped to `[0, 100000]`.
6. `GraphTabState.zoom` clamped to `[0.1, 5.0]` (matches cytoscape minZoom/maxZoom).
7. Persistence write coalesced via `requestIdleCallback` (or `setTimeout(write, 250)` fallback) to avoid
   thrashing localStorage on rapid scroll.

## Relationship to existing tables

This feature reads — never writes — from `articles`, `sources`, `runs`, `keywords`,
`article_keywords`, `keyword_edges`, `clusters`, `graph_meta`. All access goes through existing
read-only SQLite connections (`web/deps.py:get_conn` with `mode=ro` URI). No schema migration is
included or required.
