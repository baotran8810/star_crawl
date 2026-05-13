---

description: "Task list for 004-obsidian-ui feature implementation"
---

# Tasks: Obsidian-style Web UI

**Input**: Design documents from `/specs/004-obsidian-ui/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included per Constitution III ("Test-First where it matters"). Server panel routes get pytest coverage; tab lifecycle, restore-after-reload, palette, theme, and monochrome graph each get one focused Playwright test. UI polish (spacing, exact px) is validated manually.

**Organization**: Grouped by user story. Foundational phase produces the empty shell that every story builds inside. After foundational, US1 (tabs) → US2 (tree) chain because the tree calls into the workspace open-tab API; US3 (monochrome graph), US4 (palette + shortcuts), US5 (theme) can run in parallel once foundational + US1 are done.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Different file, no dependency on incomplete in-phase work — can run in parallel.
- **[Story]**: Required on user-story phase tasks only.
- File paths are absolute from repo root.

## Path Conventions

- Server code: `src/star_crawl/web/`
- Client assets: `src/star_crawl/web/static/`
- Templates: `src/star_crawl/web/templates/`
- Tests: `tests/web/` (pytest) and `tests/web/e2e/` (Playwright)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Pure-CSS design tokens + bootstrap of the new static asset surface. No behaviour change yet.

- [X] T001 [P] Create `src/star_crawl/web/static/tokens.css` defining CSS variables for light + dark themes (color, spacing, radii, typography, graph palette) per research §R5, §R6, §R9
- [X] T002 [P] Add Inter (or system-ui) font stack and base typography rules to `src/star_crawl/web/static/tokens.css`
- [X] T003 [P] Create empty placeholder files: `src/star_crawl/web/static/shell.css`, `src/star_crawl/web/static/workspace.js`, `src/star_crawl/web/static/tree.js`, `src/star_crawl/web/static/palette.js`, `src/star_crawl/web/static/theme.js`, `src/star_crawl/web/static/shortcuts.js` (1-line headers each)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shell skeleton + every `/panel/...` route. Tabs do not yet work, tree is empty — but the routes exist, the layout grid is correct, and HTMX can fetch panel partials.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [X] T004 Create `src/star_crawl/web/templates/shell.html` — 4-cell grid (icon-rail / tree / main / right-panel-slot) + status-bar row; loads `tokens.css`, `shell.css`, `workspace.js`, `shortcuts.js`, `theme.js`, `tree.js`, `palette.js`
- [X] T005 [P] Create `src/star_crawl/web/templates/partials/icon_rail.html` (Sources · Graph · Runs · Search · Bookmarks; static icons + tooltip)
- [X] T006 [P] Create `src/star_crawl/web/templates/partials/tab_bar.html` (empty `<div role="tablist">` placeholder rendered server-side)
- [X] T007 [P] Create `src/star_crawl/web/templates/partials/status_bar.html` (project name slot, article count, source count, theme toggle button, settings cog)
- [X] T008 [P] Create `src/star_crawl/web/templates/partials/panel_unavailable.html` (inline error partial for dead tab targets per FR-021)
- [X] T009 [P] Write layout grid + icon rail + status bar styles in `src/star_crawl/web/static/shell.css` (collapsible tree, sticky status bar, tab bar overflow-x scroll)
- [X] T010 Create `src/star_crawl/web/routers/home.py` with `GET /` returning `shell.html`; status-bar context (article_count, source_count) loaded server-side via existing `get_conn`
- [X] T011 Create `src/star_crawl/web/routers/panels.py` exporting a `_render_panel(request, template_name, ctx)` helper that returns the content-only body when path starts with `/panel/`, else returns full `base.html`-wrapped response (back-compat per plan)
- [X] T012 Refactor `src/star_crawl/web/routers/articles.py` so `GET /articles/{id}` calls `_render_panel(...)`; add `GET /panel/article/{id}` sibling delegating to the same handler with panel flag
- [X] T013 Refactor `src/star_crawl/web/routers/runs.py` analogous to T012 for `/runs`, `/runs/{id}`; add `/panel/runs` and `/panel/run/{id}`
- [X] T014 Refactor `src/star_crawl/web/routers/sources.py` analogous to T012; add `/panel/source/{name}`
- [X] T015 Refactor `src/star_crawl/web/routers/search.py` analogous to T012; add `/panel/search`
- [X] T016 Refactor `src/star_crawl/web/routers/graph.py` analogous to T012; add `/panel/graph`
- [X] T017 Mount `home.py` and `panels.py` routers in `src/star_crawl/web/app.py` (with existing `auth_required` dependency)
- [X] T018 [P] Write `tests/web/test_panel_routes.py` — pytest asserting each `/panel/*` route returns 200 + the expected content-only signature element (`#article-body`, `.run-row`, etc.) and does NOT include the base nav header

**Checkpoint**: Visiting `/` shows the empty shell with all panels in place; `/panel/graph` returns just the graph chassis HTML. No tab interactions yet.

---

## Phase 3: User Story 1 — Side-by-side tabs with persistence (Priority: P1) 🎯 MVP

**Goal**: Open multiple corpus items as tabs, switch between them, reorder, close, restore after reload AND browser restart. Tabs persist via `localStorage`.

**Independent Test**: Open the graph tab + 2 article tabs from the tree (Phase 4 stub if tree not yet wired — use direct HTMX call in dev console for testing). Switch between them; observe scroll position preserved. Reload the page and confirm same tabs restored, active one focused. Close the last tab; confirm graph tab auto-opens (FR-021).

### Tests for User Story 1

- [X] T019 [P] [US1] Write `tests/web/e2e/test_workspace_tabs.py` — Playwright covering: open tab via JS API, switch via click, drag-reorder, close active tab, close last tab → auto-graph, reload preserves all open tabs and active tab. Mark expected-to-fail until implementation lands

### Implementation for User Story 1

- [X] T020 [P] [US1] Implement workspace state schema + validation in `src/star_crawl/web/static/workspace.js` per `contracts/workspace-state.md` (load/save under `star_crawl.workspace.v1`, version check, clamp/drop bad fields, default-state fallback)
- [X] T021 [P] [US1] Implement `TabManager` API in `src/star_crawl/web/static/workspace.js`: `openTab({kind, target_id, title, panel_url, focus})`, `closeTab(id)`, `activateTab(id)`, `reorderTab(id, newIndex)`, `getState()`. All emit the `workspace:*` events from `contracts/workspace-state.md`
- [X] T022 [US1] Render the tab bar from state in `workspace.js`: subscribe to `workspace:tab-opened|closed|activated|reordered` and rebuild `partials/tab_bar.html`'s contents (re-use server-rendered initial markup as the template). Tab DOM uses `role="tab"`, `aria-selected`, and `data-tab-id`
- [X] T023 [US1] Implement tab content lifecycle in `workspace.js`: on open, append `<section class="tab-panel" data-tab-id hidden>`; on activate, show + restore `scroll_y`; on hide, save `scroll_y`. Cytoscape-bearing panels are NOT destroyed on close — per research §R2 they remain in DOM until tab close, then are destroyed cleanly
- [X] T024 [US1] Wire HTMX `hx-ajax` call in `workspace.js` to load panel content into a freshly-opened tab's section (`htmx.ajax('GET', tab.panel_url, {target: section, swap: 'innerHTML'})`)
- [X] T025 [US1] Implement HTML5 drag-and-drop reorder on tab elements in `workspace.js` (dragstart records id, dragover highlights position, drop mutates state, re-renders)
- [X] T026 [US1] Implement workspace restore on page load in `workspace.js`: read state, rebuild tab bar, lazy-fetch each tab's panel content, restore active tab id, restore scroll positions. Auto-open default graph tab if state is empty or invalid (FR-021)
- [X] T027 [US1] Integrate `history.pushState({tabId})` on tab activate + `popstate` listener that calls `activateTab(detail.tabId)` (research §R3). Disable HTMX's `hx-push-url` everywhere inside the shell
- [X] T028 [US1] Add Cytoscape "preserve on hide" logic in `src/star_crawl/web/static/graph.js`: when the graph tab is activated, run `requestAnimationFrame(() => { cy.resize(); cy.viewport({zoom, pan}); })` reading from the tab's `graph_state` (research §R2)
- [X] T029 [US1] Persist graph zoom + pan + focused keyword into `tab.graph_state` in `src/star_crawl/web/static/graph.js` (listen for `cy.on('zoom pan tap')` and call `workspace.updateTabState(tabId, {graph_state})`)
- [X] T030 [US1] Coalesce localStorage writes via `requestIdleCallback` (or `setTimeout` fallback) per `contracts/workspace-state.md`; flush synchronously on tab-opened/tab-closed events
- [X] T031 [US1] Add inline unavailable handling in `workspace.js`: if a panel fetch returns 200 with `panel_unavailable.html` signature, show inline message + Close button; if fetch returns 4xx/5xx, render generic unavailable state with Close
- [X] T032 [US1] Wire scroll position saving to a `'scroll'` listener on each panel, throttled to ~150 ms

**Checkpoint**: US1 functional — tabs open, close, reorder, persist, restore, all panel routes serve content into tabs.

---

## Phase 4: User Story 2 — Tree navigation without page reload (Priority: P1)

**Goal**: Click items in the left navigation tree to open them as tabs. Tree shows Sources (→ Articles), Runs, Bookmarks stub, Saved Searches stub. Expand/collapse persists.

**Independent Test**: From the empty shell, click "Sources" header in tree → expand. Click a source → its articles appear nested. Click an article → opens as a new tab focused. Confirm no full-page reload (network shows only `/tree?...` and `/panel/article/...`). Reload page and confirm previously-expanded sections stay expanded.

### Tests for User Story 2

- [X] T033 [P] [US2] Write `tests/web/test_tree_endpoint.py` — pytest verifying `GET /tree` returns top-level sections, `GET /tree?section=sources&expand=true` includes article rows under each source, items carry `data-kind`, `data-target-id`, `data-panel-url`

### Implementation for User Story 2

- [X] T034 [P] [US2] Create `src/star_crawl/web/routers/tree.py` with `GET /tree` endpoint supporting `section` and `expand` query params per `contracts/panel-routes.md`. Pull sources / articles / runs from existing tables via read-only conn
- [X] T035 [US2] Mount `tree.py` in `src/star_crawl/web/app.py` (under `auth_required`)
- [X] T036 [P] [US2] Create `src/star_crawl/web/templates/partials/tree.html` rendering nested `<ul class="tree">` with `<li>` rows carrying `data-kind`, `data-target-id`, `data-panel-url`, expand-chevron for parents
- [X] T037 [P] [US2] Implement `src/star_crawl/web/static/tree.js`: expand/collapse on click of section/source headers (HTMX `hx-get="/tree?section=..."` swap into `<ul>`); leaf click → `workspace.openTab(...)` from data attrs; middle-click → `workspace.openTab({..., focus: false})`; Cmd/Ctrl-click → same
- [X] T038 [US2] Wire shell.html to load tree initially: `<div id="tree-root" hx-get="/tree" hx-trigger="load" hx-swap="innerHTML">`
- [X] T039 [US2] Persist `workspace.tree_collapsed` + `workspace.tree_expanded_sections` from `tree.js` via `workspace.setPreference(...)`; reapply on restore
- [X] T040 [US2] Add CSS rules in `shell.css` for auto-collapse at viewport < 900 px (`@media (max-width: 900px) { .tree { display: none; } }`); rail icon click toggles class
- [X] T041 [US2] Add Bookmarks placeholder section in `routers/tree.py` returning "Coming soon" empty-state row per research §R11

**Checkpoint**: US1 + US2 functional. From a clean browser the user can open the shell, expand Sources, click an article, see it open as a tab. Reload restores both the open tabs and the expanded tree sections.

---

## Phase 5: User Story 3 — Monochrome topic graph (Priority: P1)

**Goal**: Default graph view renders in a single grayscale palette (no cluster hues). Node size and position carry meaning. A tab-local toggle restores cluster colors. Dot-grid canvas background.

**Independent Test**: Open the graph tab from a fresh workspace (no saved preference). Confirm every node is rendered in the monochrome `--graph-node` palette — only lightness varies. Confirm the canvas background shows a subtle dot grid. Toggle "Cluster color" in the filter panel and confirm cluster hues return. Toggle off; confirm monochrome returns. Reload; confirm the toggle state persisted.

### Tests for User Story 3

- [X] T042 [P] [US3] Write `tests/web/e2e/test_graph_monochrome.py` — Playwright asserting: default workspace open → graph tab nodes share the monochrome hue (use computed `getComputedStyle` or canvas pixel sampling at known node positions); toggle cluster colors → distinct hues appear; reload → toggle state retained

### Implementation for User Story 3

- [X] T043 [P] [US3] Define `--graph-node`, `--graph-edge`, `--graph-node-faint`, `--canvas-bg`, `--canvas-dot` CSS variables for both light + dark themes in `src/star_crawl/web/static/tokens.css` (research §R5, §R6)
- [X] T044 [P] [US3] Add `.graph-canvas` dot-grid background-image rule in `src/star_crawl/web/static/shell.css` using the variables
- [X] T045 [US3] In `src/star_crawl/web/static/graph.js`, read `--graph-node` via `getComputedStyle` on graph tab init; compute per-node lightness offset = `f(log(doc_freq + 1))` mapped to ±15% via OKLCH-to-hex precompute (helper in `graph.js`)
- [X] T046 [US3] In `src/star_crawl/web/static/graph.js`, branch node fill: if `workspace.cluster_color_enabled === true` use `clusters.color` (existing path); else use the monochrome lightness-offset. Also branch edge color (gray neutral vs cluster source) and the existing `cross-cluster` class behavior
- [X] T047 [P] [US3] Add `<label class="toggle"><input type="checkbox" name="cluster_color"> Cluster color</label>` control inside the graph filter panel in `src/star_crawl/web/templates/graph.html` (or `partials/graph_filters.html` if extracted)
- [X] T048 [US3] Wire the toggle in `graph.js` to call `workspace.setPreference('cluster_color_enabled', value)` and emit `workspace:cluster-color-changed`; subscribe back to re-apply Cytoscape styles
- [X] T049 [US3] In `src/star_crawl/web/static/graph.js`, subscribe to `workspace:theme-changed` event and re-apply node/edge colors so the canvas tracks light/dark switch (research §R9)
- [X] T050 [US3] Verify the existing filter panel + keyword side panel layout works inside the tab container; adjust `graph.html` if column widths overflow the new shell main width

**Checkpoint**: US1 + US2 + US3 = P1 MVP shipable. Workspace shell with tabs, tree, and monochrome graph. Suggested point to deploy/demo.

---

## Phase 6: User Story 4 — Command palette + keyboard navigation (Priority: P2)

**Goal**: `Cmd/Ctrl+K` opens a palette. Two grouped lists: Objects (articles, runs, sources, keywords) and Workspace actions (Toggle theme, Toggle cluster colors, Close all tabs, Rebuild graph, Open Graph tab). Keyboard nav fully wired per `contracts/keyboard-shortcuts.md`.

**Independent Test**: From any workspace state, press `Cmd+K`. Confirm dialog opens with focus on input. Type a few characters; results filter. Use arrow keys to highlight; `Enter` activates. Press `Cmd+Enter` to open in new tab. Try the keyboard shortcuts (Alt+→, Cmd+W, Alt+1) — all should work without touching the mouse.

### Tests for User Story 4

- [X] T051 [P] [US4] Write `tests/web/e2e/test_command_palette.py` — Playwright covering: `Cmd+K` opens palette with focus; type → filter; arrow + Enter open in current tab; `Cmd+Enter` open in new tab; workspace action invocation (toggle theme via palette); `Esc` closes; `?` opens help overlay

### Implementation for User Story 4

- [X] T052 [P] [US4] Create `src/star_crawl/web/routers/palette.py` exporting `GET /palette/objects.json` per `contracts/panel-routes.md`. Pulls articles (id, title, source, published_at), sources (name, display_name, count), runs (id, source, status), keywords (id, display, doc_freq); returns flat JSON array `Cache-Control: private, max-age=60`
- [X] T053 [US4] Mount `palette.py` in `src/star_crawl/web/app.py`
- [X] T054 [P] [US4] Create `src/star_crawl/web/templates/partials/command_palette.html` — `<dialog id="palette">` with input, two grouped result lists (Workspace actions / Objects), keyboard hint footer
- [X] T055 [P] [US4] Implement `src/star_crawl/web/static/palette.js`: open via custom event `palette:open` (raised by shortcuts.js); lazy-fetch `/palette/objects.json` on first open; in-memory simple substring + Levenshtein ranker; render grouped results; activate calls `workspace.openTab(...)` (Enter active tab vs Cmd-Enter new tab) or workspace action functions
- [X] T056 [P] [US4] Implement `src/star_crawl/web/static/shortcuts.js` per `contracts/keyboard-shortcuts.md`: keymap registry, global keydown listener gated on workspace focus, ignoring inputs/textareas. Dispatch domain events (`palette:open`, `workspace:close-active-tab`, etc.) instead of inlining logic
- [X] T057 [US4] Wire help overlay in `palette.js` or new tiny `help.js`: `?` (or `Cmd+/`) opens a `<dialog>` listing all bindings from a single source-of-truth keymap
- [X] T058 [US4] Implement workspace action handlers in `workspace.js`: `closeAllTabs()`, `openDefaultTab()`, exposed for `palette.js` and shortcuts to call
- [X] T059 [US4] Wire `Rebuild graph` palette action to POST `/graph/rebuild` (existing endpoint per `routers/graph.py:181`) — preserves the existing user-triggered subprocess flow
- [X] T060 [US4] Add ARIA tablist roving focus on the tab bar elements per `contracts/keyboard-shortcuts.md` accessibility note

**Checkpoint**: Workspace fully keyboard-navigable. Power-user UX in place.

---

## Phase 7: User Story 5 — Theme toggle (light / dark / system) (Priority: P2)

**Goal**: Status-bar toggle switches the whole workspace — including the Cytoscape canvas — between light, dark, and (default) system. Choice persists across reloads.

**Independent Test**: With several tabs open including the graph, click theme toggle in status bar; observe entire chrome + graph canvas flip to dark palette in under 200 ms with no tab loss. Reload; confirm dark mode reapplied. Toggle back to light; confirm persisted choice. Open the workspace in a fresh profile with OS set to dark → confirm dark applied automatically before any toggle interaction.

### Tests for User Story 5

- [X] T061 [P] [US5] Write `tests/web/e2e/test_theme_toggle.py` — Playwright covering: click toggle → `<html data-theme>` flips → background changes → tabs intact; reload → choice persisted; emulate dark `prefers-color-scheme` first-visit → workspace opens dark

### Implementation for User Story 5

- [X] T062 [P] [US5] Implement `src/star_crawl/web/static/theme.js`: resolve `WorkspaceState.theme` against `matchMedia('(prefers-color-scheme: dark)')` for `"system"`; apply via `document.documentElement.dataset.theme = "light"|"dark"`; listen on `matchMedia.change` to react when system flips and user chose `"system"`
- [X] T063 [US5] Add the theme toggle button + label inside `src/star_crawl/web/templates/partials/status_bar.html` (cycles light → dark → system)
- [X] T064 [US5] Wire the toggle in `theme.js` → `workspace.setPreference('theme', next)` → emit `workspace:theme-changed`
- [X] T065 [US5] Subscribe `graph.js` to `workspace:theme-changed` (already added in T049); verify monochrome palette adapts correctly in both modes
- [X] T066 [US5] Ensure all CSS variables in `tokens.css` switch correctly via `[data-theme="dark"]` selector; check WCAG AA contrast on `--text` against `--bg`, `--surface`, `--canvas-bg`

**Checkpoint**: All 5 user stories functional. Workspace feels like a finished product.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, end-to-end validation, cleanups.

- [X] T067 [P] Update `README.md` "Web UI" section to point at the new shell + describe direct-URL back-compat
- [ ] T068 [P] Update `quickstart.md` if anything drifted during implementation
- [ ] T069 [P] Slim down `src/star_crawl/web/static/styles.css` — remove rules superseded by `tokens.css`/`shell.css`; keep only route-specific styles still needed
- [ ] T070 [P] Audit each new client module — confirm each ≤ 250 LOC per Constitution IV; split `graph.js` if it exceeded 400 LOC during US3 work
- [X] T071 Run the manual smoke check in `quickstart.md` step-by-step; capture screenshots for the PR
- [X] T072 Performance sweep: confirm tab-switch < 100 ms (SC-002), restore first paint < 800 ms (plan §performance goal), theme toggle < 200 ms (SC-006), palette first results < 150 ms; measure with the existing Playwright trace mode
- [X] T073 Accessibility sweep: tab through every interactive control, verify WCAG AA contrast in both themes, verify screen-reader-friendly ARIA on tabs + dialog + tree
- [X] T074 Run full test suite: `pytest tests/web/` + `pytest tests/web/e2e/`; all green
- [X] T075 Update `.specify/feature.json` and `CLAUDE.md` after merge — keep `feature_directory` pointing at the active or next feature

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: no dependencies. Can start immediately.
- **Phase 2 (Foundational)**: depends on Phase 1. Blocks every user story.
- **Phase 3 (US1)**: depends on Phase 2.
- **Phase 4 (US2)**: depends on **Phase 3** because the tree calls `workspace.openTab(...)`.
- **Phase 5 (US3)**: depends on Phase 2. Can run in parallel with Phase 3 (US1) and Phase 7 (US5) once foundational is done.
- **Phase 6 (US4)**: depends on Phase 3 (uses `workspace.openTab` + the workspace action handlers). Soft-depends on Phase 5 (cluster-color toggle) and Phase 7 (theme toggle) — palette wires those actions, but can stub if either lags.
- **Phase 7 (US5)**: depends on Phase 2. Can run fully in parallel with Phase 3/5.
- **Phase 8 (Polish)**: depends on all desired user stories being complete.

### Within each user story

- Tests are written first (per Phase 2 Constitution III) and expected to fail until implementation.
- Models / state schema → state-mutation API → UI rendering → events / integration.
- Inline error handling and accessibility are done within-story, not deferred to Polish.

### Critical path

`T001-T003 (Setup) → T004-T018 (Foundational) → T019-T032 (US1) → T033-T041 (US2) → T067-T075 (Polish)`

Parallel branches off the foundational checkpoint: `T042-T050 (US3)`, `T051-T060 (US4 — soft-depends on US1)`, `T061-T066 (US5)`.

---

## Parallel Examples

### Phase 1 (Setup) — all three in parallel

```text
T001 — Author tokens.css
T002 — Author Inter font stack in tokens.css (same file as T001 → actually NOT parallel; serialize)
T003 — Touch the 6 static placeholders (different files → parallel with T001/T002 once shared file lock cleared)
```

> Note: T001 + T002 both touch `tokens.css`; merge into one commit or run serially. T003 is independent.

### Phase 2 (Foundational) — fan out after T004

```text
After T004 (shell.html exists):
T005, T006, T007, T008, T009 — different files, all [P]
After T011 (panels helper exists):
T012, T013, T014, T015, T016 — each existing router refactor; same author for consistency but mechanically independent
```

### Phase 3 (US1)

```text
After T019 (test scaffold) + T020 (schema):
T021 — TabManager API (workspace.js)
T024 — HTMX wire (workspace.js — same file, serialize after T021)
T028 — Cytoscape preserve-on-hide (graph.js — parallel with T021)
T030 — Write coalescing (workspace.js — serialize)
```

### Cross-story (post-foundational, with 3 developers)

```text
Developer A → Phase 3 (US1) then Phase 4 (US2)
Developer B → Phase 5 (US3)
Developer C → Phase 7 (US5) then assist Phase 6 (US4)
```

---

## Implementation Strategy

### MVP First (Phases 1 → 2 → 3 only)

1. Complete Setup + Foundational.
2. Complete US1 (tabs + persistence).
3. **STOP and VALIDATE**: workspace shell with tabs that persist. Even with empty tree + colored graph, the core workspace experience is there.
4. Deploy / share / demo. This is genuinely useful as-is.

### Recommended P1 increment (Phases 1 → 2 → 3 → 4 → 5)

1. MVP above + tree (US2) + monochrome graph (US3).
2. **Deploy / demo**. This is the "full P1" cut that the spec is aimed at.

### P1+P2 = full feature (Phases 1 through 8)

1. P1 increment above.
2. Add command palette + keyboard (US4).
3. Add theme toggle (US5).
4. Polish phase.
5. Ship.

### Parallel team strategy

After T018 (foundational checkpoint), three streams can run in parallel:

- **Stream A**: US1 → US2 (sequential, same dev recommended for `workspace.js` ownership).
- **Stream B**: US3 (lives mostly inside `graph.js` + `tokens.css`).
- **Stream C**: US5 (small) then assist US4 (palette + shortcuts).

Stream A and Stream C can integrate at the workspace-event boundary; conflicts limited to `workspace.js` event consumers, easily merged.

---

## Notes

- [P] = different files / no in-phase dependency on incomplete tasks.
- Tests are scoped per Constitution III: lifecycle-critical browser flows + new server routes. UI polish is manual.
- Each phase ends in a Checkpoint where the increment is independently demoable.
- Workspace state lives only in the browser; constitution V is unaffected — no SQLite write surface added by this feature.
- All new files target ≤ 250 LOC (Constitution IV); split if a file approaches 400.
- Commit after each phase checkpoint at minimum. Smaller commits per task are encouraged.
