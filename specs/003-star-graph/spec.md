# Feature Specification: Star-Graph

**Feature Branch**: `003-star-graph`
**Created**: 2026-05-10
**Status**: Draft
**Input**: User description: "Build an interactive keyword network from the corpus: extract meaningful keywords from each article, derive a graph where nodes are keywords and edges are co-occurrence relationships, group related keywords into clusters, and present an explorable visualization that lets the user drill into any keyword to see the underlying articles."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the topic landscape of the whole corpus (Priority: P1)

A user has a corpus of hundreds or thousands of articles and wants a fast visual sense of what topics actually appear across them. They open the graph view; the interface presents an interactive network where each node represents a recurring keyword, the size of the node reflects how often it appears, edges connect keywords that frequently appear in the same articles, and color groups show distinct topic clusters that emerged automatically. With one glance the user can see, for example, that "Kafka", "stream", and "queue" form one cluster while "Postgres", "replica", and "vacuum" form another.

**Why this priority**: This is the core value of the feature — turning a flat list of articles into a navigable map of ideas. Without this, the rest of the feature has nothing to explore.

**Independent Test**: With a non-empty corpus, open the graph view and confirm the visualization renders, contains at least 50 nodes and at least 100 edges, and visibly groups related keywords into distinct color-coded clusters.

**Acceptance Scenarios**:

1. **Given** the corpus has at least 100 articles with extracted keywords, **When** the user opens the graph view, **Then** they see an interactive network with multiple visible clusters, where node size encodes how broadly a keyword appears.
2. **Given** the graph is rendered, **When** the user pans, zooms, or drags nodes, **Then** the layout responds smoothly without visible jitter or freezing.
3. **Given** two keywords appear in many of the same articles, **When** the user inspects them, **Then** there is a visibly stronger edge between them than between two weakly related keywords.

---

### User Story 2 - Drill from a topic into the articles behind it (Priority: P1)

A user notices an interesting cluster on the graph. They click a node — say, "Kafka". A side panel opens showing how many articles mention this keyword, which keywords it most strongly relates to (its closest neighbors with their relationship strength), and a list of recent articles where this keyword is prominent. From that list they jump straight to a specific article in the reader view.

**Why this priority**: Without drilldown, the graph is a pretty picture with no path back to the source material. Drilldown closes the loop from "interesting topic" to "article I'll read".

**Independent Test**: Click any visible node and confirm the side panel populates with the keyword name, article count, top neighbor list, and a list of articles. Click an article in the list and confirm it opens in the reader.

**Acceptance Scenarios**:

1. **Given** the graph is displayed, **When** the user clicks a node, **Then** a side panel shows the keyword's display name, total article count across the corpus, top related keywords with relationship strength, and at least the most recent few articles featuring it.
2. **Given** a keyword is selected, **When** the user activates one of the related keywords from the side panel, **Then** that keyword becomes the new focus and the side panel updates to it.
3. **Given** an article appears in the side panel, **When** the user activates it, **Then** they navigate to the full article in a way that preserves their place in the graph (they can return).

---

### User Story 3 - Narrow the graph to what I care about (Priority: P2)

A user is interested only in a subset of their corpus — for example, articles from a specific source over the last six months — and wants the graph to reflect only that subset. They use filters to scope by source, time range, minimum keyword frequency, and minimum relationship strength; the graph regenerates promptly to show only the relevant network.

**Why this priority**: A whole-corpus graph quickly becomes overwhelming. Filtering is what makes the feature usable for focused investigation.

**Independent Test**: Apply a source filter that excludes most of the corpus; confirm the graph regenerates with fewer nodes/edges that all derive from the included sources. Reset filters; confirm the full graph returns.

**Acceptance Scenarios**:

1. **Given** the graph view is open, **When** the user changes the source filter, **Then** the graph updates to show only keywords from articles of the selected sources.
2. **Given** the user adjusts a minimum-frequency or minimum-relationship-strength control, **When** the value changes, **Then** weaker nodes and edges are pruned from the view.
3. **Given** the user resets all filters, **When** the action completes, **Then** the original whole-corpus graph is restored.

---

### User Story 4 - Find a specific topic without scanning visually (Priority: P2)

A user knows the keyword they want to inspect (e.g., "raft consensus") and types it into a search box on the graph view. As they type, candidate matches appear; selecting one focuses the graph on that node and its immediate neighborhood, fading out the rest.

**Why this priority**: Visual hunting works for small graphs; for hundreds or thousands of nodes, search is essential.

**Independent Test**: Type a substring of a known keyword in the graph search; confirm matching candidates appear within a few keystrokes. Pick one; confirm the graph highlights that node and its immediate connections, and dims everything else.

**Acceptance Scenarios**:

1. **Given** the graph view is open, **When** the user types into the keyword search, **Then** matching keyword candidates are listed quickly under the input.
2. **Given** the user selects a candidate, **When** the selection is made, **Then** the graph centers on that node, its direct neighbors are emphasized, and unrelated nodes are visually de-emphasized.
3. **Given** a focused state is active, **When** the user clears the search, **Then** the full graph view returns.

---

### User Story 5 - Export a slice of the graph for outside use (Priority: P3)

An advanced user wants to take a filtered subgraph into another tool (for a study, a paper, a presentation, or further analysis). They configure the filters they want, then export the current view as a graph data file and as a static image suitable for a slide deck.

**Why this priority**: Useful for power users but not part of the core "explore the corpus" loop. Reasonable to ship after the main flow is in place.

**Independent Test**: Apply filters, request export, confirm a file is produced that captures exactly the visible nodes and edges with their attributes (size, cluster, weight) and that an image of the current rendering is also produced.

**Acceptance Scenarios**:

1. **Given** a filtered graph is on screen, **When** the user requests an export, **Then** a graph data file is produced containing only the currently visible nodes and edges with their attributes.
2. **Given** an export is requested, **When** an image option is selected, **Then** an image of the current rendering is produced at a resolution suitable for printing.

---

### Edge Cases

- **The corpus has too few articles to produce a meaningful graph** (e.g., under 20): the view shows a clear "not enough data" message rather than an empty canvas.
- **A keyword appears once or twice across the entire corpus** (rare term): such keywords are excluded from the default view to reduce noise; user can lower the threshold to see them.
- **Two keywords are aliases for the same concept** (e.g., "k8s" and "Kubernetes"): they are treated as a single node, not two weakly connected nodes.
- **Keyword extraction picks up generic noise** (e.g., "team", "engineer", "system"): such tokens are excluded by default; a user can inspect a noise list and adjust it.
- **The graph is very dense** (10,000+ edges before pruning): the view applies pruning to keep rendering responsive; the user can raise thresholds further if it's still too busy.
- **A user clicks a node but no articles back it** (extraction error or stale data): the side panel shows a clear message rather than an empty list with no explanation.
- **The corpus changes** (new articles added after the graph was built): the user has a clear way to know the graph is out-of-date and rebuild it.
- **Articles in non-English languages**: extraction either handles them or skips them with a recorded reason; mixed-language clusters do not silently mix unrelated terms.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST extract a small set of meaningful keywords for each article in the corpus, prioritizing technical and domain-specific terms over generic vocabulary.
- **FR-002**: System MUST normalize keyword variants so equivalent forms (case differences, common aliases, near-duplicates) are represented as a single node.
- **FR-003**: System MUST exclude generic high-frequency noise terms from the keyword set so the graph reflects substantive topics, not common filler.
- **FR-004**: System MUST associate every kept keyword with the articles in which it occurred, with enough precision to enable per-keyword article drilldown.
- **FR-005**: System MUST construct an undirected, weighted network where nodes are keywords and edges represent co-occurrence within the same articles, with edge weight reflecting the strength of the relationship rather than raw co-occurrence count.
- **FR-006**: System MUST detect and assign cluster groupings to keywords automatically, so that strongly related keywords share a cluster and weakly related keywords do not.
- **FR-007**: System MUST allow rebuilding the graph at any time so the network can stay current with the corpus.
- **FR-008**: System MUST expose the network through an interactive view that supports panning, zooming, dragging individual nodes, and selecting a node to see details.
- **FR-009**: System MUST encode keyword frequency in node size and cluster membership in node color so the user can read structure at a glance.
- **FR-010**: System MUST display, on selection of a node, the keyword's article count, its strongest neighbors with their relationship strength, and a list of articles containing it ordered with the most recent first.
- **FR-011**: System MUST allow navigation from any article in the side panel to that article's reader view.
- **FR-012**: System MUST allow filtering the graph by source, by time range of article publication, by minimum keyword frequency, and by minimum relationship strength.
- **FR-013**: System MUST allow searching nodes by keyword text and focusing the graph on a chosen node and its immediate neighborhood.
- **FR-014**: System MUST surface a clear "not enough data" or "needs rebuild" state when the graph is empty or stale rather than rendering a blank or misleading view.
- **FR-015**: System MUST allow the user to export a filtered subgraph as a structured graph data file and as a static image of the current rendering.
- **FR-016**: System MUST keep the graph rebuild process idempotent — repeated rebuilds with no change in the corpus produce the same network within randomness limits of any clustering step.
- **FR-017**: System MUST never re-fetch or re-crawl articles as part of building the graph; it MUST work entirely off existing corpus content.

### Key Entities

- **Keyword**: A normalized term that appears with sufficient frequency and substance across the corpus. Carries a display form, a frequency, a cluster assignment, and the set of articles in which it appears.
- **Relationship**: An undirected, weighted association between two keywords reflecting how strongly they co-occur, after normalization.
- **Cluster**: A group of keywords that emerged together from the relationship structure, carrying a label that gives the user a hint about what the cluster is about.
- **Graph Build**: A snapshot of when the network was last constructed, used to inform the user when the view is current versus stale.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a corpus of at least 1,000 articles, the user can identify at least 5 meaningful, named topic clusters within 30 seconds of opening the graph view.
- **SC-002**: At least 80% of cluster assignments, on inspection by a domain-aware user, are coherent (i.e. the keywords in a cluster are recognizably related).
- **SC-003**: Generic noise terms account for under 5% of the visible nodes in the default view.
- **SC-004**: The graph view remains interactive (pan/zoom/drag without visible lag) for graphs of up to several thousand visible nodes after default pruning.
- **SC-005**: Drilling from a node click to the underlying article list takes under one second.
- **SC-006**: Applying a source or time filter regenerates the visible graph in under three seconds for typical corpus sizes.
- **SC-007**: A user who knows the exact keyword can locate and focus on its node in the graph in under five seconds via search.
- **SC-008**: When the corpus changes, the user is informed the graph is stale within one click of opening the graph view.

## Assumptions

- The corpus already exists and is populated by the crawler feature; this feature does not crawl or fetch.
- The user is comfortable with the idea that automatic keyword extraction is approximate; the goal is signal, not perfect labelling.
- The corpus is dominated by technical English content; multilingual support is best-effort, and exotic-language clusters may be coarser.
- The graph is built on demand, not continuously; users expect to rebuild explicitly after large corpus additions.
- The view runs in a modern browser on the same machine as the corpus, accessing it locally.
- Cluster labels, when needed, can be auto-derived from cluster membership and may be later overridden by user edits; auto-labels need not be perfect.
- Export formats targeted are widely understood graph data formats and standard raster images; bespoke or proprietary formats are out of scope.
- Privacy considerations for the crawled content are inherited from the crawler feature; this feature does not introduce additional content beyond what is already in the corpus.
