# Feature Specification: Obsidian-style Web UI

**Feature Branch**: `004-obsidian-ui`
**Created**: 2026-05-13
**Status**: Draft
**Input**: User description: "Rewrite the web UI as an Obsidian-style workspace: a narrow left icon rail, a collapsible navigation tree, a tabbed main area where articles, runs, search results, and the topic graph can be opened side-by-side, and a status bar at the bottom. Strip cluster colors from the graph so the visualisation reads as a single monochrome network — node size and position alone carry meaning."

## Clarifications

### Session 2026-05-13

- Q: Tab state phải sống đến đâu? → A: localStorage, persist qua browser restart trên cùng profile
- Q: Khi reload/restart, ngoài tab list còn gì restore? → A: Tab list + active tab + per-tab scroll position + graph zoom & focused node. Filter form values và search query KHÔNG restore.
- Q: Command palette tìm/chạy gì? → A: Cả objects (articles, runs, sources, keywords) lẫn workspace actions (Toggle theme, Close all tabs, Rebuild graph, Toggle cluster colors). Tách 2 nhóm trong palette UI.
- Q: Cluster-color toggle đặt ở đâu? → A: Trong filter panel của graph tab. Toggle là tab-local control, không phải global status-bar control. Vẫn callable qua command palette.
- Q: First visit (chưa có saved state) thấy gì? → A: Auto-open Graph tab làm tab mặc định. Áp dụng cả khi user đóng hết tab — workspace mở lại Graph thay vì để main area trống.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open multiple items side-by-side without losing context (Priority: P1)

A user is investigating a topic that touches several articles, a run, and a region of the graph at the same time. Rather than navigating away and losing each prior view, they open each item as its own tab in the main area: one tab for the graph, one for the article they were reading, one for the crawl run that produced it. They can switch between tabs instantly, and when they return tomorrow the same tabs are still open.

**Why this priority**: This is the defining capability of the redesign. Without persistent multi-pane navigation the rest of the UI changes are decorative.

**Independent Test**: Open the graph in a tab, open an article in a second tab, open a run in a third tab. Switch between them; confirm each tab preserves its scroll position and inner state (e.g., the graph keeps its current zoom). Reload the page; confirm the same three tabs are still open and the previously-active tab is focused.

**Acceptance Scenarios**:

1. **Given** the workspace is empty, **When** the user activates an item from the navigation tree, **Then** that item opens in a new tab and becomes the active tab.
2. **Given** several tabs are open, **When** the user clicks a tab in the tab bar, **Then** that tab becomes active and its content is shown without re-fetching.
3. **Given** a tab is no longer needed, **When** the user closes it via the close affordance or a keyboard shortcut, **Then** the tab is removed; if it was active, the most recently active remaining tab takes focus.
4. **Given** several tabs are open, **When** the user reloads the page, **Then** the same set of tabs is restored and the previously-active tab is selected.
5. **Given** the user middle-clicks (or Cmd/Ctrl-clicks) a navigation tree row, **When** the action is fired, **Then** the item opens in a new tab in the background without stealing focus.

---

### User Story 2 - Browse the corpus from a single tree without page reloads (Priority: P1)

A user wants to skim across the corpus by source, by run, and by recent activity from a single navigation surface. They expand a source in the tree to see its articles, click a run to see its outcome, and pin a saved search in the tree for later. Each action loads its content into a tab in the main area; nothing reloads the full page.

**Why this priority**: A persistent tree turns the corpus into a navigable knowledge base instead of a series of disconnected list pages. Without it, the tabbed workspace has no efficient way to surface things to open.

**Independent Test**: From the tree, expand a source node and confirm it lists that source's articles. Activate one; confirm it opens in a tab. Without reloading, switch the tree to "Runs", click a run; confirm it opens as a second tab. Confirm neither action caused a full page navigation.

**Acceptance Scenarios**:

1. **Given** the tree is visible, **When** the user expands a source node, **Then** its articles appear nested under it without a full-page reload.
2. **Given** the tree shows runs, **When** the user activates a run row, **Then** the run detail opens in a tab in the main area.
3. **Given** the tree panel takes up sidebar space, **When** the user collapses the tree, **Then** the main area expands to fill the freed width and the panel can be re-opened from the icon rail.
4. **Given** the user is mid-investigation and resizes the window, **When** the viewport shrinks below a small-screen threshold, **Then** the tree collapses automatically and remains reachable from the icon rail.

---

### User Story 3 - Read a monochrome topic graph as one coherent network (Priority: P1)

A user opens the graph view and sees a single grayscale network rather than a coloured cluster mosaic. Node size still encodes how broadly a keyword appears; layout still separates regions; but no cluster colours overlay the canvas. The user can still recognise communities — they appear as denser regions of nodes — and clicking any node still drills into the keyword in a side panel as before.

**Why this priority**: The current cluster colours create a busy mosaic that competes with the structure itself. A monochrome reading favours position and size as the carriers of meaning, in line with the Obsidian aesthetic the user has chosen.

**Independent Test**: Open the graph view; confirm every node is rendered in a single grayscale palette (no hue variation between clusters). Confirm node size still varies by keyword frequency and edges are visibly thinner/lighter than nodes. Click a node and confirm the side panel still surfaces neighbours and articles.

**Acceptance Scenarios**:

1. **Given** the graph is rendered, **When** the user inspects any two nodes, **Then** they share the same hue (only lightness varies, if at all) and any sense of cluster separation comes from layout density, not colour.
2. **Given** the user clicks a node, **When** the node is selected, **Then** it is visibly emphasised (e.g., border, halo, or size shift), with the rest of the graph faded — without re-introducing cluster colours.
3. **Given** the user enables the optional "show clusters" affordance, **When** the affordance is on, **Then** cluster colours return as a toggle, leaving monochrome as the default state.
4. **Given** the canvas background previously was a flat colour, **When** the redesigned graph renders, **Then** it presents as a subtle dot grid that anchors panning and zooming.

---

### User Story 4 - Move between tabs and open things by keyboard (Priority: P2)

A user who prefers the keyboard navigates the workspace without touching the mouse. They open a command palette to jump to an article by title, switch between tabs with a shortcut, close the current tab with another, and trigger a quick filter on the graph without leaving the main area.

**Why this priority**: This is what makes the workspace feel like a real tool rather than a styled web page. It can ship after the visible scaffold (Stories 1–3) is in place.

**Independent Test**: From an empty workspace, press the command palette shortcut, type a few characters of an article title, select a match; confirm it opens in a new tab. Use the next-tab and close-tab shortcuts; confirm each behaves as expected.

**Acceptance Scenarios**:

1. **Given** the workspace is focused, **When** the user invokes the command palette, **Then** a search overlay appears that can match articles, runs, sources, and keywords across the corpus.
2. **Given** multiple tabs are open, **When** the user presses the next-tab shortcut, **Then** focus advances to the next tab in order, wrapping at the end.
3. **Given** a tab is active, **When** the user presses the close-tab shortcut, **Then** that tab closes and the most recently active remaining tab takes focus.
4. **Given** the user is on the graph tab, **When** they press the focus-filter shortcut, **Then** the filter input takes focus without the user having to mouse over the panel.

---

### User Story 5 - Switch the whole workspace between light and dark theme (Priority: P2)

A user works in low light and prefers a dark interface. From a control in the status bar at the bottom of the workspace they toggle between light and dark mode. The change applies instantly to every panel — tree, tabs, main content, and the graph — without losing tab state.

**Why this priority**: Dark mode is expected baseline for a workspace tool, but is decoupled from the core navigation model. It can ship in parallel with or after the rest.

**Independent Test**: With several tabs open including the graph, toggle dark mode from the status bar; confirm every panel including the graph canvas switches palette and the tabs remain open with no loss of state. Toggle back and confirm the original palette returns.

**Acceptance Scenarios**:

1. **Given** the workspace is in light mode with tabs open, **When** the user toggles dark mode, **Then** the entire interface — chrome and all open panels — adopts the dark palette while preserving tab state.
2. **Given** the user has previously chosen dark mode, **When** they reload the page, **Then** the workspace reopens in dark mode.
3. **Given** the user has not chosen a theme, **When** the workspace loads on a system set to dark mode, **Then** the workspace honours that system preference.

---

### Edge Cases

- **A tab points at an item that no longer exists** (e.g., a run was deleted, an article URL was renamed): the tab renders an inline "this item is no longer available" state instead of erroring; the user can close it.
- **The user opens dozens of tabs**: the tab bar scrolls horizontally rather than overflowing; older tabs stay reachable from a dropdown.
- **The graph tab is open but never activated this session**: its canvas is not laid out until first activation; first activation triggers layout once with a brief loading state.
- **Two devices share the same browser profile**: tab restore is per-browser-session, not per-server; this is acceptable and expected.
- **The corpus is empty**: the navigation tree shows a guided empty state inviting the user to configure a source, rather than a blank panel.
- **The user has no saved tab state** (first-ever visit, or every tab was just closed): the workspace opens (or stays) with one default tab — the topic graph — rather than an empty main area.
- **The graph in monochrome mode is hard to read on certain monitors**: the user can fall back to the cluster-colour toggle without losing any other workspace state.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST present a workspace shell composed of a narrow vertical icon rail on the left, an adjacent collapsible navigation tree, a main area with a tab bar above its content, and a status bar pinned to the bottom.
- **FR-002**: System MUST let the user open any first-class corpus item (an article, a run, a source view, a search result, or the topic graph) as a tab in the main area.
- **FR-003**: System MUST preserve, for each open tab, its scroll position and its inner ephemeral state (e.g., graph zoom and focused node, search query and filters) for as long as the tab is open within the active workspace session.
- **FR-003a**: Across reloads and browser restarts, the restored state per tab MUST include at minimum: scroll position, and — for the topic graph tab — current zoom level and currently focused node. Transient form values (filter sliders, search query input) MAY be reset on restore; this is acceptable.
- **FR-004**: System MUST persist the set of open tabs and the currently active tab across page reloads AND browser restarts on the same browser profile, restoring them on the next visit.
- **FR-005**: System MUST support opening an item in the background ("new tab without focusing") via a secondary activation gesture (middle-click or Cmd/Ctrl-click on a tree row or link).
- **FR-006**: System MUST allow the user to close a tab, reorder tabs by dragging, and switch tabs by direct click as well as by keyboard shortcut.
- **FR-007**: System MUST display, in the navigation tree, a hierarchical view that groups items by section (Sources, Runs, Bookmarks, Saved Searches), where each section can be expanded or collapsed independently and the tree itself can be hidden via the icon rail.
- **FR-008**: System MUST load content into a tab without performing a full page navigation; URL changes that drive sharable state MAY happen via in-history updates but MUST NOT discard other open tabs.
- **FR-009**: System MUST render the topic graph in a single monochrome palette by default, with cluster grouping reduced to a layout signal rather than a colour signal; the data model behind clusters is unchanged.
- **FR-010**: System MUST provide a clearly labelled toggle to re-enable cluster colours on the graph, located within the graph tab's filter panel (not in the global status bar), defaulting to off; the choice MUST persist across page reloads and browser restarts and also be invokable from the command palette.
- **FR-011**: System MUST emphasise the canvas of the graph as the central object — using a subtle dot-grid background and de-emphasised chrome — so the user's attention is drawn to the network and not the surrounding panel.
- **FR-012**: System MUST give edges visually less weight than nodes (thinner, lower-contrast) so the network reads as nodes connected by faint relationships, not as a mesh that dominates.
- **FR-013**: System MUST scale node size by keyword frequency in a way that makes the most prominent hubs unmistakably larger than mid-tier nodes, without making small nodes invisibly small.
- **FR-014**: System MUST reveal a node's label progressively — small nodes show their label only on hover or at higher zoom; large nodes show their label at default zoom — so the canvas stays legible at every scale.
- **FR-015**: System MUST keep all existing graph interactions working unchanged inside the new tab container (hover emphasis, click-to-focus, double-click-empty-to-fit, keyword side panel, filter panel).
- **FR-016**: System MUST offer a command-palette overlay reachable by keyboard shortcut that surfaces TWO grouped result kinds:
  1. **Objects** — articles by title, sources by name, runs by id/date, keywords by term. Selecting an object activates it in the active tab, or in a new tab on a modifier press.
  2. **Workspace actions** — at minimum: Toggle theme, Toggle cluster colors, Close all tabs, Rebuild graph. Selecting an action invokes it immediately without opening a tab.
  The two groups MUST be visually separated within the palette so the user can tell objects from actions at a glance.
- **FR-017**: System MUST provide a theme toggle in the status bar that switches the entire workspace — including the graph canvas — between light and dark palettes, persisting the choice across reloads.
- **FR-018**: System MUST honour the operating system's prefers-color-scheme on a first visit if the user has not yet expressed a preference.
- **FR-019**: System MUST surface, in the status bar, lightweight metadata about the workspace state — at minimum the corpus name/project, the article count, and the number of configured sources — without competing with the main area for attention.
- **FR-020**: System MUST degrade gracefully on narrower viewports — at small widths the navigation tree auto-collapses to icons, the status bar can compress, and tabs scroll horizontally rather than wrapping into the canvas.
- **FR-021**: System MUST never leave the workspace in an empty-main-area state: on a fresh visit with no saved tabs, OR when the user closes the last open tab, the system MUST auto-open the topic graph as a single default tab. Inside any tab whose underlying item no longer exists, the system MUST render an inline unavailable-state instead of blank panels or hard errors.
- **FR-022**: System MUST preserve the current basic authentication model — the entire workspace remains gated behind the existing optional credentials; the redesign does not introduce a new auth surface.

### Key Entities

- **Workspace State**: The set of currently open tabs (in order), the active tab, and the user's theme + cluster-colour preferences. Lives in the browser; persists across reloads.
- **Tab**: A live reference to a corpus item plus its ephemeral viewing state (scroll position, graph zoom and focus, filter values). Created on open, destroyed on close.
- **Navigation Tree Node**: A row in the sidebar tree that either expands into more rows (Sources → Articles, etc.) or activates an item into a tab. Carries a label, a kind, and an identifier.
- **Theme Preference**: Light, dark, or system-default. Persists per browser.
- **Cluster Colour Preference**: On or off. Persists per browser. Independent of theme.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user, given a populated corpus, can open three different items into tabs and switch between them within 30 seconds of arriving on the workspace.
- **SC-002**: Switching between two already-open tabs occurs in under 100 ms with no visible re-fetch or relayout.
- **SC-003**: Reopening the workspace after a reload OR a browser restart (same profile) restores the previous set of open tabs and the active tab with 100% fidelity.
- **SC-004**: At default zoom on a graph of ~300 nodes, no more than 15 labels are visible simultaneously, so the canvas reads without text overlap.
- **SC-005**: On the same graph, the size ratio between the largest hub and the median node is at least 3:1, so hubs are unmistakable.
- **SC-006**: Toggling between light and dark mode completes in under 200 ms and leaves all open tabs intact, including the graph canvas.
- **SC-007**: At a viewport width of 1024 px, every workspace control — tabs, tree toggle, command palette, theme toggle — remains reachable without horizontal page scrolling.
- **SC-008**: At a viewport width of 600 px, the workspace remains usable with the tree auto-collapsed to icons, tabs horizontally scrollable, and the active tab content readable.

## Assumptions

- The web UI is rendered server-side as today (FastAPI + Jinja + HTMX) and remains so; the redesign introduces lightweight client-side state for tabs and theme but does not migrate to a single-page app framework.
- The existing route surface (articles, sources, runs, search, graph, keyword panel) is reused; each route gains a panel-only variant that can be embedded inside a tab without the outer chrome.
- Tab state lives in the browser (persistent local storage on the user's profile, surviving browser restarts). Cross-device or cross-browser-profile sync is out of scope.
- The optional cluster colour toggle uses the same palette as the current implementation; no new colour design system is introduced for it.
- Keyboard shortcuts are documented but do not need to be user-rebindable in this feature; a future preferences pane can revisit that.
- The status bar is informational; it does not host primary actions beyond the theme toggle.
- The redesign does not change the data model — clusters, keywords, edges, articles, and runs stay as they are; only their presentation changes.
- The redesign does not change the existing single-user authentication model. Multi-user accounts, per-user persisted state, and shared workspaces are explicitly out of scope.
- Mobile-native gestures (long-press, swipe-to-close-tab) are out of scope; small-viewport degradation aims for legibility, not full mobile parity.
- Accessibility targets WCAG AA contrast in both themes and full keyboard reachability for all interactive controls; assistive-tech tab announcements rely on standard ARIA tab patterns.
