# Quickstart: Obsidian-style Web UI

This is a UI-only feature. No new dependencies; no schema changes; nothing to migrate.

## Run the workspace

```bash
# Same as today
.venv/bin/python -m star_crawl.cli serve --port 8002
# Then open
open http://127.0.0.1:8002/
```

When `STAR_CRAWL_AUTH=user:pass` is set, the workspace is gated behind HTTP Basic — same
behaviour as the rest of the web UI.

## What you should see

1. **Icon rail** (48 px, left edge): Sources · Graph · Runs · Search · Bookmarks (empty).
2. **Tree panel** (~280 px, collapsible via `[` or the rail's chevron): Sources expanded by
   default with article counts.
3. **Tab bar** at the top of the main area. On first visit, one tab is open: **Topic graph**.
4. **Status bar** at the bottom: project name · article count · source count · theme toggle · settings.

Click an article in the tree → opens as a new tab. Click the graph tab → switches back. Middle-
click an article → opens in a background tab without losing focus. Drag tabs to reorder. Close
a tab with the `×` or `Mod+W`. Close the last tab → workspace auto-opens the graph tab again.

## Keep working with direct URLs

The shell at `/` is the new entry point. Old URLs still work without JavaScript:

| Direct URL | Behaviour |
|---|---|
| `/articles/123` | Renders the article inside `base.html` (no shell). |
| `/runs/7` | Renders the run inside `base.html`. |
| `/graph?min_freq=5` | Renders the graph inside `base.html`. |

Inside the workspace, the same content is loaded from the matching `/panel/...` partial:

| Inside the shell | Internal fetch |
|---|---|
| Open an article tab | `GET /panel/article/123` |
| Open a run tab | `GET /panel/run/7` |
| Open the graph tab | `GET /panel/graph?...` |

## Workspace state

Everything you see — tabs, active tab, graph zoom, theme, cluster-colour toggle — is stored
under one `localStorage` key:

```
star_crawl.workspace.v1
```

To reset the workspace (e.g., during development):

```js
// In the browser console
localStorage.removeItem('star_crawl.workspace.v1');
location.reload();
```

The validation pass tolerates partial corruption: bad fields fall back to defaults; an
unparseable payload triggers a fresh default state.

## Theme

Status-bar toggle flips between `light` and `dark`. The choice persists. On first visit with
no choice yet stored, the workspace honours `prefers-color-scheme`.

## Cluster colour on the graph

By default the graph is monochrome. To re-enable cluster colours:

1. Open the graph tab.
2. In the filter panel on the left, flip **Cluster colour** to on.

Or use the command palette (`Mod+K`) and run **Toggle cluster colours**. The setting persists
across reloads.

## Command palette

- Open: `Mod+K`.
- Two grouped sections: **Objects** (articles / runs / sources / keywords) and **Workspace actions**.
- `Enter` opens in the active tab; `Mod+Enter` opens in a new tab. Actions invoke immediately.
- The object index is fetched once per session from `/palette/objects.json`. After a crawl or
  graph rebuild, close+reopen the palette to refresh.

## Keyboard shortcuts at a glance

| Keys | Action |
|---|---|
| `Mod+K` | Command palette |
| `Mod+W` | Close active tab |
| `Alt+→` / `Alt+←` | Next / previous tab |
| `Alt+1`..`Alt+9` | Jump to tab N |
| `[` | Collapse/expand the tree |
| `?` | Show help overlay |

(The full list lives in `contracts/keyboard-shortcuts.md`.)

## Run the tests

```bash
# Server panel route tests
.venv/bin/pytest tests/web/test_panel_routes.py tests/web/test_tree_endpoint.py

# Browser flows (Playwright; chromium installed during the 002-uber-browser-fetcher work)
.venv/bin/pytest tests/web/e2e/
```

The Playwright suite boots a `uvicorn` instance on an auto-assigned port against a deterministic
fixture corpus shared with the existing graph tests.

## Smoke check (manual)

1. Open `/`. Confirm one default tab named "Topic graph" appears.
2. Open an article from the tree. Confirm a new tab appears and is focused.
3. Reload the page. Confirm both tabs are restored and the article tab is still focused.
4. Close the article tab. Confirm graph tab is focused.
5. Close the graph tab. Confirm a fresh graph tab auto-opens (FR-021).
6. Toggle dark mode. Confirm every panel — including the graph canvas — flips palette without
   losing tab state.
7. Open the palette (`Mod+K`), type a few characters of an article title, press `Mod+Enter`.
   Confirm it opens in a new background tab and the previously-active tab remains focused.

## Where to look in the code

| Concern | File |
|---|---|
| Shell layout | `src/star_crawl/web/templates/shell.html` |
| Design tokens (CSS variables) | `src/star_crawl/web/static/tokens.css` |
| Shell layout CSS | `src/star_crawl/web/static/shell.css` |
| Tab manager + localStorage | `src/star_crawl/web/static/workspace.js` |
| Command palette | `src/star_crawl/web/static/palette.js` |
| Theme controller | `src/star_crawl/web/static/theme.js` |
| Keyboard shortcuts | `src/star_crawl/web/static/shortcuts.js` |
| Tree interaction | `src/star_crawl/web/static/tree.js` |
| Panel route handlers | `src/star_crawl/web/routers/panels.py` |
| Tree endpoint | `src/star_crawl/web/routers/tree.py` |
| Graph monochrome adaptation | `src/star_crawl/web/static/graph.js` (existing, augmented) |
