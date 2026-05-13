# Implementation Plan: Obsidian-style Web UI

**Branch**: `004-obsidian-ui` | **Date**: 2026-05-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/004-obsidian-ui/spec.md`

## Summary

Re-shell the existing web UI (FastAPI + Jinja + HTMX) into an Obsidian-style workspace: 48px icon rail, collapsible navigation tree (~280px), tabbed main area, status bar. Tabs persist across reloads and browser restarts via `localStorage`. Each existing route gains a panel-only variant that returns content without the outer chrome so it can be embedded inside a tab. The graph view loses its cluster colour by default and reads as a single monochrome network anchored on a dot-grid background; colours remain available behind a tab-local toggle. All client-side state and behaviour is hand-rolled in vanilla JS to honour the constitution's "no JS framework" rule. No new server dependencies are added.

## Technical Context

**Language/Version**: Python 3.11+ (server); ES2020 vanilla JS (client; no transpile).
**Primary Dependencies**:
- Server: existing FastAPI / Jinja / HTMX 1.9+ stack. No new dependencies.
- Client: existing Cytoscape.js 3.x + fcose (vendored). `htmx.org` already loaded for partials.
- No JS framework, no bundler — per Stack Constraint in `.specify/memory/constitution.md`.
**Storage**:
- Server: existing `data/articles.db` (read-only for this feature; no new tables).
- Client: `localStorage` for workspace state (open tabs, active tab, scroll/zoom per tab), theme preference, cluster-colour preference.
**Testing**:
- Python: `pytest` for new panel routes (HTTP shape + content).
- Browser: lightweight Playwright tests for tab lifecycle, restore-after-reload, theme toggle, command palette, monochrome graph render. Each test ≤ 30 s wall time.
**Target Platform**: Modern evergreen browsers on desktop (Chromium 120+, Firefox 120+, Safari 17+). Mobile is best-effort responsive (no native gestures).
**Project Type**: Web UI redesign — server-rendered shell + client-side enhancement. Pure UI; no business-logic change.
**Performance Goals**:
- Tab switch < 100 ms perceived (no re-fetch, no re-layout).
- First paint of restored workspace < 800 ms on a ~300-node graph.
- Theme toggle < 200 ms end-to-end.
- Command palette open + first results < 150 ms.
**Constraints**:
- No build step. All client code ships as plain `.js` / `.css` files served from `/static/`.
- Total added JS ≤ 30 KB unminified, ≤ 12 KB gzipped. Total added CSS ≤ 20 KB.
- Existing routes MUST keep working (back-compat: a request to `/articles/{id}` still renders a full page when called directly without the shell).
- Cytoscape instance is re-used across tab switches (`display:none` + `cy.resize()`); destroying and recreating is forbidden for the graph tab.
- All interactive controls reachable by keyboard; WCAG AA contrast for both themes.
**Scale/Scope**:
- ~6 new server endpoints (panel-only variants of existing pages + 1 tree endpoint).
- ~6 new client modules (tab manager, tree, command palette, theme, shortcuts, monochrome graph adapter).
- Workspace state envelope ≤ 8 KB serialized (10–20 tabs typical).

## Constitution Check

| Principle | Check | Status |
|---|---|---|
| **I. Source-Config First** | No new source-config surface. Existing source YAMLs untouched. | ✅ |
| **II. Polite-By-Default** | Feature does no network I/O against external origins. | ✅ |
| **III. Test-First (where it matters)** | Server panel routes get pytest coverage. Tab lifecycle + restore covered by Playwright tests. UI polish (spacing, exact px) validated manually. | ✅ |
| **IV. Many Small Files** | New client modules sized ≤ 250 LOC each (target). Status bar, tree, palette, theme split into separate files. Existing `graph.js` will be split into `graph-render.js` + `graph-tab.js` if it crosses 400 LOC after monochrome work. | ✅ |
| **V. SQLite Source of Truth** | No corpus state change. Workspace state lives in browser `localStorage` only — derived UI state, not corpus state. | ✅ |
| **VI. UI Writes Are Explicit and User-Triggered (v0.2.0)** | Tab open/close, theme toggle, cluster-colour toggle are local UI state, not corpus writes. No GET request mutates corpus. The existing "Rebuild graph" button (which DOES write corpus state on user click) stays as-is. | ✅ |
| **VII. Failure Visibility** | A tab pointing at a deleted run/article shows an inline unavailable state with the underlying URL and a Close button; failures do not silently disappear. | ✅ |

**Stack Constraint check**:
- "No build step" → all client code is plain ES2020 served directly from `/static/`. ✅
- "No JS framework, no bundler" → tab manager, palette, tree, theme controller all hand-rolled vanilla JS. HTMX (existing) is a hypermedia enhancer, not a framework. Cytoscape (existing) is a library. No Alpine / Vue / React / Svelte / etc. ✅
- "Server-rendered templates + progressive enhancement only" → tab content fetched as server-rendered HTML partials via HTMX `hx-get`; if JS is disabled the page still navigates per-route (degraded but functional). ✅

**Violations**: none.

## Project Structure

### Documentation (this feature)

```text
specs/004-obsidian-ui/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Workspace state schema + entities
├── quickstart.md        # Phase 1
└── contracts/
    ├── panel-routes.md           # /panel/* endpoint shapes
    ├── workspace-state.md        # localStorage JSON schema
    └── keyboard-shortcuts.md     # Key bindings
```

### Source code

```text
src/star_crawl/web/
├── app.py                              # mount new routers
├── routers/
│   ├── home.py                         # new: serves the shell at "/"
│   ├── tree.py                         # new: /tree partial
│   ├── panels.py                       # new: /panel/{kind}/{id?} dispatch
│   ├── articles.py                     # existing + /panel variant
│   ├── runs.py                         # existing + /panel variant
│   ├── sources.py                      # existing + /panel variant
│   ├── search.py                       # existing + /panel variant
│   ├── graph.py                        # existing + /panel variant
│   └── ...
├── templates/
│   ├── shell.html                      # new: full workspace shell, served at "/"
│   ├── base.html                       # kept for direct routes (back-compat)
│   ├── tokens.html                     # new: CSS-variable tokens partial
│   ├── partials/
│   │   ├── icon_rail.html              # new
│   │   ├── tree.html                   # new (rebuilt under /tree)
│   │   ├── tab_bar.html                # new (server-rendered initial state)
│   │   ├── status_bar.html             # new
│   │   ├── panel_unavailable.html      # new (for dead tab targets)
│   │   ├── command_palette.html        # new (overlay markup)
│   │   └── ...                         # existing partials
│   ├── graph.html                      # existing → wrapped as panel
│   ├── article.html                    # existing → wrapped as panel
│   ├── run.html                        # existing → wrapped as panel
│   ├── source.html                     # existing → wrapped as panel
│   ├── runs.html                       # existing → wrapped as panel
│   └── search.html                     # existing → wrapped as panel
└── static/
    ├── tokens.css                      # new: light + dark CSS variables
    ├── shell.css                       # new: icon rail, tree, tab bar, status bar, layout grid
    ├── styles.css                      # existing — slim down, route-specific styles only
    ├── workspace.js                    # new: TabManager, localStorage, restore on load
    ├── shortcuts.js                    # new: keyboard binding registry
    ├── palette.js                      # new: command-palette overlay
    ├── theme.js                        # new: light/dark toggle + system preference
    ├── tree.js                         # new: expand/collapse, HTMX integration
    ├── graph.js                        # existing — split if grows past 400 LOC
    └── ...                             # vendor/ unchanged
```

**Tests**

```text
tests/web/
├── test_panel_routes.py                # pytest: each /panel/* returns 200 + correct partial
├── test_tree_endpoint.py               # pytest: /tree shape with empty + populated corpus
└── e2e/
    ├── test_workspace_tabs.py          # Playwright: open, close, reorder, restore on reload
    ├── test_command_palette.py         # Playwright: cmd-K, search, action invocation
    ├── test_theme_toggle.py            # Playwright: light/dark switch, persistence
    └── test_graph_monochrome.py        # Playwright: default monochrome, toggle restores color
```

**Structure Decision**:
Web-only refactor — no new top-level project. All work lives under `src/star_crawl/web/` and `tests/web/`. Existing route handlers gain `panel_*` siblings under the same router files (sourced from request header `HX-Workspace-Panel: 1` or the literal `/panel/...` path prefix — both paths land at the same Jinja partial). The "shell" (icon rail + tree + tab bar + main + status bar) is served exclusively by `home.py`, which is mounted at `/`. Old top-level routes (`/articles/{id}`, `/runs/{id}`, etc.) keep responding with the full `base.html` layout for direct URL access — they are NOT folded into the shell so that bookmarks, search-engine landing pages, and external links continue to work without JavaScript.

## Complexity Tracking

No Constitution violations.

| Concern | Why | Mitigation |
|---|---|---|
| Adding ~6 small JS files | Keeps each module focused per Principle IV | All ≤ 250 LOC; loaded with `<script defer>`, no bundler needed |
| Re-using Cytoscape instance across tab hides | Avoid 1–2s relayout on every tab switch | Hidden tab's container stays in DOM with `display:none`; `cy.resize()` runs on tab activate inside `requestAnimationFrame` |
| Two layout paths (shell `/` vs. legacy direct `/articles/{id}`) | Back-compat with existing bookmarks | Documented in `quickstart.md`; covered by panel route tests asserting both code paths render the same content body |
