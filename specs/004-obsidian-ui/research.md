# Research: Obsidian-style Web UI

Resolves the technical unknowns and "best-practice" questions raised by `plan.md`. Each section follows the
**Decision / Rationale / Alternatives considered** shape.

## R1. Client-side state without a framework

**Decision**: Hand-roll a vanilla-JS module `workspace.js` that owns a single mutable `state` object and emits
`workspace:tab-opened`, `workspace:tab-closed`, `workspace:tab-activated`, `workspace:state-restored` custom
events on `document`. Persist `state` to `localStorage` under key `star_crawl.workspace.v1`.

**Rationale**:
- Constitution forbids JS frameworks and bundlers.
- The state model is small (≤ 20 tabs, scalar prefs); no reactive system needed.
- Custom events are first-class browser API, no library required, and inter-op cleanly with HTMX
  (HTMX itself dispatches events the same way).
- Versioned key (`v1`) lets us evolve the schema with explicit migration logic later.

**Alternatives considered**:
- **Alpine.js** — rejected as a "JS framework" per the constitution's stack constraint. Borderline
  ("rugged minimal" framework) but excluded to avoid future drift.
- **Stimulus** — same reasoning; framework-shaped.
- **Pure HTMX with `hx-trigger=load`** — insufficient: no place to hold open-tab list, tab restore on
  reload, or graph zoom serialization without server round-trips.
- **Server-side session storing tab state** — heavier; introduces a write surface that conflicts with
  the single-user, no-account assumption.

## R2. Tab content fetch + Cytoscape instance preservation

**Decision**: Each tab is a `<section class="tab-panel" data-tab-id="…">` inside the main area. Initial
content is fetched via `htmx.ajax('GET', panelUrl, {target: panel, swap: 'innerHTML'})`. Tab switch sets
`display:none` on the leaving panel and `display:block` on the entering one. The graph tab keeps its
Cytoscape instance alive across switches; on activate, `requestAnimationFrame(() => { cy.resize();
cy.fit(undefined, padding); })` re-syncs after the container regains dimensions.

**Rationale**:
- Avoids the ~1–2 s fcose re-layout cost on every tab switch (SC-002 demands < 100 ms).
- Keeps DOM count linear in number of tabs but bounded — typical session is 5–10 tabs.
- Cytoscape's `cy.resize()` is the documented recovery for "container changed size while hidden".

**Alternatives considered**:
- **Destroy + recreate Cytoscape on each visit** — rejected: blows SC-002, also re-runs Louvain or
  triggers a re-fetch.
- **Single panel that swaps innerHTML** — rejected: loses scroll position, loses graph instance, can't
  show side-by-side history.

## R3. HTMX history + browser back/forward

**Decision**: Disable HTMX's URL push (`hx-push-url="false"`) for in-tab content loads. The workspace
itself owns history: `workspace.js` calls `history.pushState({tabId})` on tab activate. Browser back/forward
listen on `popstate` and re-activate the corresponding tab via the in-memory state. URL path stays at `/`;
tab focus is encoded in the history entry's `state` only.

**Rationale**:
- Lets back/forward feel like browser-native navigation between tabs without changing the URL bar.
- Avoids ugly URLs that would arise from packing the open-tab list into a query string.
- Does not interfere with deep-linking to legacy routes (`/articles/{id}` etc.) — those open a fresh
  window/tab outside the shell.

**Alternatives considered**:
- **Encode tabs in URL hash (`#tabs=…`)** — explicitly rejected during clarify (Q1 chose localStorage).
- **No history integration** — rejected: users expect back to undo a tab switch; without it, back
  exits the workspace.

## R4. Command palette without a framework

**Decision**: Custom overlay component (`palette.js`) opened by `Ctrl/Cmd+K`. UI is a `<dialog>` element
styled with shell tokens. Two index sources fetched lazily on first open:

1. `/palette/objects.json` (server endpoint, ~50–500 KB depending on corpus) — flat list of `{kind, id,
   label, subtitle}` for articles (id+title), sources, runs, keywords.
2. `palette.js` static array of workspace actions (Toggle theme, Toggle cluster colors, Close all tabs,
   Rebuild graph, Open Graph tab).

Ranking: simple case-insensitive substring + Levenshtein-distance tiebreaker (hand-rolled, ~30 LOC).
Results grouped under "Workspace actions" then "Objects".

**Rationale**:
- The object index is cheap to compute server-side from existing tables; loading it once per session is
  trivial compared to the alternatives.
- A simple ranker is enough at corpus sizes ≤ 50k items; fuse.js-class libraries are overkill here.
- `<dialog>` provides focus trap, ESC close, and ARIA semantics for free.

**Alternatives considered**:
- **Live server-side search via HTMX (`hx-trigger=keyup`)** — adds 50–150 ms per keystroke; palette
  feels laggy. Rejected.
- **kbar.dev / ninja-keys component** — React or web-component with framework leanings; rejected per
  constitution.

## R5. Dot-grid background for the graph canvas

**Decision**: CSS-only repeating linear-gradient on the `.graph-canvas` element:

```css
background:
  radial-gradient(circle, var(--canvas-dot) 1px, transparent 1.5px) 0 0 / 24px 24px,
  var(--canvas-bg);
```

In light theme: `--canvas-bg: #fafaf9`, `--canvas-dot: #d6d3d1`.
In dark theme: `--canvas-bg: #1c1917`, `--canvas-dot: #44403c`.

**Rationale**:
- Zero JavaScript cost.
- Renders crisp at any device-pixel-ratio.
- Subtle enough not to compete with nodes (FR-011).

**Alternatives considered**:
- **SVG `<pattern>` background** — equivalent visually but heavier markup.
- **Cytoscape grid plugin** — not maintained, ties decoration to canvas redraw cycle.

## R6. Monochrome graph palette + size scale

**Decision**:
- Each node gets a single base color from `--graph-node` (light: `#3f3f46`, dark: `#a1a1aa`).
- A per-node lightness offset based on `log(doc_freq + 1)` so hubs are slightly darker (light theme)
  / lighter (dark theme). Range: ±15% lightness via OKLCH stored as hex post-conversion.
- Node size remains `sqrt(doc_freq)`-scaled — already implemented after the prior graph review.
- When cluster-colour toggle is ON, the existing `clusters.color` palette is applied as before.

**Rationale**:
- Single hue keeps the canvas reading as "one network" (FR-009).
- Lightness offset gives hubs perceptual weight beyond size alone.
- Lightness-based encoding survives WCAG-AA contrast checks in both themes when background dot-grid
  is at the chosen lightness.

**Alternatives considered**:
- **All nodes identical color** — readable but flatter; hubs only differ by size.
- **Reverse the toggle default (color ON)** — clarify Q4 fixed default OFF.

## R7. Keyboard shortcuts that don't collide with the browser

**Decision**: Use `Ctrl/Cmd+K` (palette), `Ctrl/Cmd+W` close current tab (with `preventDefault` and
documentation that this overrides the browser's close-tab — acceptable inside an app shell), `Alt+1..9`
jump to tab N (uncollided), `Alt+ArrowLeft/Right` previous / next tab. `?` opens a help overlay listing
all bindings. Theme toggle has NO global shortcut — only the status-bar button + palette action — to
avoid surprise.

**Rationale**:
- These mirror Obsidian's bindings, which is the design north star.
- `Cmd+W` overriding browser close-tab is a known cost; users opening the workspace are committing to
  an app-shell context.
- `?` is a long-standing convention from GitHub / Gmail.

**Alternatives considered**:
- **`Cmd+T` to open new tab** — collides with browser; rejected.
- **`Cmd+Shift+P` for palette** — works (VS Code) but `Cmd+K` is one fewer key. Both work; one
  shortcut suffices for v1.

## R8. Drag-to-reorder tabs

**Decision**: HTML5 drag-and-drop API on tab elements. `draggable="true"` on each tab; `dragstart`
records the tab id; `dragover` on neighbors highlights the drop position; `drop` moves the tab id in
the workspace state array and re-renders the tab bar.

**Rationale**:
- Native browser API — no library.
- Accessibility: pair with `Alt+Shift+ArrowLeft/Right` for keyboard reorder.

**Alternatives considered**:
- **Pointer event-based drag with manual positioning** — more code, no benefit at this scale.
- **No drag, keyboard reorder only** — fails Obsidian feel; rejected.

## R9. Theme detection + system preference

**Decision**: `theme.js` listens to `matchMedia('(prefers-color-scheme: dark)')` and to the manual
toggle. On load: if `localStorage.theme` is set, honour it; else honour system. Applied by toggling
`<html data-theme="light|dark">`; all colors flow from CSS variables that read off this attribute.
Cytoscape style refresh: on theme change, `cy.style().selector('node').style({'background-color':
getComputedStyle(...)} ).update()` — re-reads the CSS variable since Cytoscape's canvas does not
auto-track CSS variable changes.

**Rationale**:
- Honours OS preference on first visit (FR-018), persists user override (FR-017).
- One source of truth for color (CSS vars) keeps the system DRY across HTML + canvas.

**Alternatives considered**:
- **Two stylesheet swap** — works but doubles asset load; rejected.
- **Cytoscape internal theming via tag-based selectors** — possible but verbose; the JS-driven style
  patch is ~15 LOC.

## R10. Test strategy without ballooning CI cost

**Decision**:
- Server panel routes: pytest, share fixtures with existing tests, assert HTTP 200 + presence of a
  signature element (`#article-body`, `.run-row`, etc.).
- Browser flows: 4 Playwright tests, each pinned to a deterministic corpus (the existing fixture
  database extended with 3 articles + 1 run if needed). All run headless against
  `uvicorn star_crawl.web.app:app --port=:auto`.
- No visual regression in CI for v1; manual screenshot review during PR.

**Rationale**:
- Constitution III: "Test-First (where it matters)." UI polish is explicitly excluded; tab lifecycle
  + restore are exactly the "where it matters" cases for a workspace.
- Playwright is the existing project standard (see `tests/` already containing pytest).

**Alternatives considered**:
- **Cypress** — second testing tool; no benefit over Playwright we already have.
- **Skip browser tests, manual only** — restore-after-reload is the kind of bug that drifts silently;
  worth automating.

## R11. Out of scope (explicitly deferred)

- **Bookmarks**: spec mentions Bookmarks as a tree section but no entity / persistence exists. The
  icon rail will show the affordance with an empty-state "Coming soon" panel; data model is reserved
  for a future feature.
- **Per-user accounts / shared workspaces**: explicit in spec assumptions. Single browser-local state.
- **Mobile-native gestures**: spec defers; responsive layout only.
- **User-rebindable shortcuts**: spec defers; v1 is fixed.
- **Visual regression in CI**: cost vs. value not worth it for a personal tool at this stage.
