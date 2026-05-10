# Tasks: Star-Graph

**Input**: Design documents from `specs/003-star-graph/`
**Prerequisites**: plan.md ✓ · spec.md ✓ · research.md ✓ · data-model.md ✓ · contracts/cli.md ✓ · contracts/graph-api.md ✓
**Depends on**: features 001 (corpus DB) and 002 (web UI shell).

**Tests**: INCLUDED — Constitution III mandates tests for extractor + PPMI math + clustering determinism.

**Organization**: Tasks grouped by user story (US1–US5). US1 + US2 are P1; ship together as MVP.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Add `graph` extra in `pyproject.toml`: `keybert`, `sentence-transformers`, `networkx`, `numpy`. Optional: `spacy` (for lemma).
- [ ] T002 Document model download behavior in `quickstart.md`: first `extract-keywords` invocation downloads `all-MiniLM-L6-v2` to `~/.cache/huggingface/`
- [ ] T003 [P] Create `src/star_crawl/graph/` package with `__init__.py`
- [ ] T004 [P] Create `configs/graph/` with empty `glossary.yaml`, `aliases.yaml`, `blacklist.yaml`, `cluster_labels.yaml` + a `README.md` explaining each
- [ ] T005 [P] Vendor frontend libs: download Cytoscape.js 3.x → `src/star_crawl/web/static/vendor/cytoscape.min.js`; cytoscape-fcose → `src/star_crawl/web/static/vendor/cytoscape-fcose.min.js`; record source URLs + versions in `static/vendor/README.md`
- [ ] T006 [P] Create `tests/graph/conftest.py` with fixture corpus: 30 mini-articles in `tests/fixtures/graph_corpus/` covering 3 known topical clusters (streaming, storage, mesh)

---

## Phase 2: Foundational (Blocking Prerequisites)

- [ ] T007 SQL migration `src/star_crawl/migrations/003_star_graph.sql` per `data-model.md`: `keywords`, `article_keywords`, `keyword_edges`, `clusters`, `graph_meta` tables + indexes + view `v_keyword_full`. Idempotent (`IF NOT EXISTS`)
- [ ] T008 [P] `src/star_crawl/graph/glossary.py`: load `configs/graph/glossary.yaml` (~500 tech terms seeded), `aliases.yaml`, `blacklist.yaml`. Build alias resolver (`postgres → postgresql`, `k8s → kubernetes`)
- [ ] T009 [P] `src/star_crawl/graph/normalize.py`: `normalize_term(text, *, lemma=True) -> str` — lowercase except short all-caps acronyms; lemmatize via spaCy when installed; apply alias map
- [ ] T010 [P] Seed `configs/graph/glossary.yaml` with ~500 tech terms from awesome-* lists (Python, Go, Kubernetes, databases, messaging, security)
- [ ] T011 [P] Seed `configs/graph/blacklist.yaml` with ~80 generic noise terms (team, engineer, system, post, ...)
- [ ] T012 [P] Seed `configs/graph/aliases.yaml` with ~40 canonical alias pairs
- [ ] T013 [P] `tests/graph/test_normalize.py`: round-trip cases — `K8s` → `kubernetes`, `Postgres` → `postgresql`, `JWT` stays `JWT`, lemma `databases` → `database`
- [ ] T014 [P] `tests/graph/test_glossary.py`: glossary load + alias resolution + blacklist exclusion

**Checkpoint**: Foundation ready — schema in place, glossary/alias/blacklist usable.

---

## Phase 3: User Story 1 — See the topic landscape (P1) 🎯 MVP part 1

**Goal**: Run `extract-keywords` then `build-graph`; open `/graph`; see an interactive force-directed network with multiple clusters.

**Independent Test**: Against fixture corpus, after extraction + build, `/graph.json` returns ≥ 50 nodes and ≥ 100 edges with ≥ 3 distinct cluster_ids; `/graph` HTML renders with inline JSON; visual inspection in browser shows clusters.

### Tests

- [ ] T015 [P] [US1] `tests/graph/test_extract.py`: against fixture corpus, KeyBERT extracts top-N candidates per article; assert known terms in glossary always present (`kafka`, `kubernetes`); blacklisted terms never present
- [ ] T016 [P] [US1] `tests/graph/test_extract_dedup.py`: same article extracted twice without `--rebuild` → no duplicate `article_keywords` rows
- [ ] T017 [P] [US1] `tests/graph/test_ppmi.py`: hand-computed pairs against tiny synthetic dataset; assert NPMI math matches reference values within 1e-6
- [ ] T018 [P] [US1] `tests/graph/test_pruning.py`: `min_doc_freq`, `min_co_count`, `min_npmi`, `max_edges_per_node` thresholds applied; node + edge counts match expected
- [ ] T019 [P] [US1] `tests/graph/test_cluster_determinism.py`: build graph with seed=42 twice → identical cluster assignments
- [ ] T020 [P] [US1] `tests/graph/test_routes_graph.py`: `/graph.json` returns Cytoscape format; ETag header set; `If-None-Match` returns 304; `/graph` page renders inline JSON

### Implementation — extraction

- [ ] T021 [P] [US1] `src/star_crawl/graph/extract.py`: KeyBERT wrapper class — lazy-load `all-MiniLM-L6-v2`; `extract(article_text, top_n=15, ngram_range=(1,3), diversity=0.6, min_score=0.35) -> list[(term, score)]`
- [ ] T022 [P] [US1] `src/star_crawl/graph/extract.py`: glossary boost — exact-match scan over text; merge with KeyBERT output; tag `is_glossary` flag
- [ ] T023 [P] [US1] `src/star_crawl/graph/extract.py`: filter pipeline — apply blacklist, alias resolution, normalization
- [ ] T024 [P] [US1] `src/star_crawl/graph/extract.py`: batch encoder — process N articles per encode call (default 64) for throughput
- [ ] T025 [US1] `src/star_crawl/graph/extract.py`: write to `keywords` (upsert by `term`) + `article_keywords`; update `keywords.doc_freq` in single transaction per batch

### Implementation — graph build

- [ ] T026 [P] [US1] `src/star_crawl/graph/ppmi.py`: NPMI computation — `compute_npmi(co_count, df_a, df_b, n_articles) -> float`; positive-only output
- [ ] T027 [P] [US1] `src/star_crawl/graph/builder.py`: pairwise co-occurrence — for each article's keyword set, enumerate all `C(n,2)` pairs into a Counter
- [ ] T028 [P] [US1] `src/star_crawl/graph/builder.py`: pruning — apply `min_doc_freq`, `min_co_count`, `min_npmi`, `max_edges_per_node` per `contracts/cli.md`
- [ ] T029 [P] [US1] `src/star_crawl/graph/cluster.py`: build NetworkX graph from edges; run `nx.community.louvain_communities(G, resolution=1.0, seed=42)`; assign `cluster_id` to keywords
- [ ] T030 [P] [US1] `src/star_crawl/graph/cluster.py`: auto-label — for each cluster, take top-3 by `doc_freq`, format `"a · b · c"`; preserve `is_user_labeled=1` on rebuild
- [ ] T031 [P] [US1] `src/star_crawl/graph/cluster.py`: assign cluster colors — distinct OKLCH hues evenly spaced around the wheel
- [ ] T032 [US1] `src/star_crawl/graph/builder.py`: orchestrator `build_graph(thresholds)` — read `article_keywords`, build edges, prune, cluster, write `keyword_edges` + `clusters` + `graph_meta` row in single transaction
- [ ] T033 [P] [US1] `src/star_crawl/cli.py`: add `extract-keywords` command per `contracts/cli.md` (flags: source, since, rebuild, top-n, ngram, diversity, min-score, no-glossary, no-lemma, batch-size)
- [ ] T034 [P] [US1] `src/star_crawl/cli.py`: add `build-graph` command (flags: min-doc-freq, min-co-count, min-npmi, max-edges-per-node, cluster-resolution, cluster-seed)

### Implementation — render

- [ ] T035 [P] [US1] `src/star_crawl/graph/repository.py`: `read_graph(filters: GraphFilters) -> {nodes: [...], edges: [...], meta: {...}}` — Cytoscape format; respects all query params from `contracts/graph-api.md`
- [ ] T036 [P] [US1] `src/star_crawl/web/routers/graph.py`: `GET /graph` (HTML page) and `GET /graph.json` (JSON); ETag from `graph_meta.built_at + filter_hash`; 503 when no `graph_meta` rows
- [ ] T037 [P] [US1] `src/star_crawl/web/templates/graph.html`: full-page shell with sidebar filters + `<div id="cy">` canvas + side-panel placeholder; inline initial JSON; load Cytoscape + fcose from `/static/vendor/`
- [ ] T038 [P] [US1] `src/star_crawl/web/static/graph.js`: initialize Cytoscape with elements from inline JSON; declarative styling per `research.md` (size from `doc_freq`, color from `cluster.color`, edge width from `npmi`); register fcose layout; click handler triggers HTMX swap into `.keyword-panel`
- [ ] T039 [US1] Update `src/star_crawl/web/templates/base.html` nav to include `Graph` tab between `Sources` and `Runs`
- [ ] T040 [US1] Update `CLAUDE.md` to reference current plan path for star-graph after build

**Checkpoint**: US1 ships. The graph view renders and is interactive.

---

## Phase 4: User Story 2 — Drill into articles behind a topic (P1) 🎯 MVP part 2

**Goal**: Click a node → side panel shows article count, top neighbors, recent articles. Click an article → land in the reader.

**Independent Test**: Click any node in `/graph`; assert side panel populates with keyword name, article count, ≥ 3 neighbors with NPMI values, ≥ 3 article links pointing to `/articles/<id>`.

### Tests

- [ ] T041 [P] [US2] `tests/graph/test_keyword_panel.py`: `GET /keywords/{id}` returns HTML fragment with name, doc_freq, top-N neighbors (sorted by NPMI desc), top-M recent articles
- [ ] T042 [P] [US2] `tests/graph/test_keyword_panel_404.py`: non-existent keyword id → friendly fragment, not stack trace

### Implementation

- [ ] T043 [P] [US2] `src/star_crawl/graph/repository.py`: `read_keyword_panel(keyword_id) -> dict` — keyword info + top neighbors via `keyword_edges` + recent articles via `article_keywords` join `articles` ordered by `published_at DESC`
- [ ] T044 [P] [US2] `src/star_crawl/web/routers/graph.py`: `GET /keywords/{id}` returns HTML partial
- [ ] T045 [P] [US2] `src/star_crawl/web/templates/partials/keyword_panel.html`: render per `contracts/graph-api.md` — display name, neighbors with `hx-get="/keywords/{id}"`, articles linking to `/articles/{id}`
- [ ] T046 [US2] `src/star_crawl/web/static/graph.js`: on node click, HTMX `hx-get="/keywords/{id}" hx-target=".keyword-panel" hx-swap="outerHTML"`; clicking neighbor in panel swaps panel + focuses graph on new node

**Checkpoint**: US2 ships. MVP (US1 + US2) — full graph + drilldown to articles.

---

## Phase 5: User Story 3 — Filter the graph (P2)

**Goal**: Sidebar filter changes (source, time, min_freq, min_npmi) regenerate the graph live.

**Independent Test**: Toggle a source filter; `/graph.json?source=...` returns subset of nodes/edges; reset → original returns.

### Tests

- [ ] T047 [P] [US3] `tests/graph/test_filters.py`: each filter param (`source`, `since`, `until`, `min_freq`, `min_npmi`, `cluster`, `focus`) reduces the result correctly; combined filters compose
- [ ] T048 [P] [US3] `tests/graph/test_focus.py`: `?focus=<keyword_id>` returns only that node + first-degree neighbors

### Implementation

- [ ] T049 [P] [US3] `src/star_crawl/graph/repository.py`: extend `read_graph()` to honor all filter params; SQL composes filters dynamically
- [ ] T050 [P] [US3] `src/star_crawl/web/templates/graph.html`: filter sidebar with HTMX-bound checkboxes/sliders; on change, `hx-get="/graph.json?<params>"`; client JS receives JSON and calls `cy.json({elements: ...})` to re-render
- [ ] T051 [P] [US3] `src/star_crawl/web/static/graph.js`: handle filter response — diff old/new node sets; smooth fade-in/fade-out of changed nodes (avoid full layout reset)

**Checkpoint**: US3 ships. Filtered graph regenerates in under 3 seconds for typical corpus.

---

## Phase 6: User Story 4 — Find a specific topic (P2)

**Goal**: Type a keyword in graph search; matching candidates appear; selecting one focuses the graph.

**Independent Test**: Type substring of a known keyword; suggestions list ≥ 1 match within 100ms; selecting it dims unrelated nodes and centers on the chosen one.

### Tests

- [ ] T052 [P] [US4] `tests/graph/test_keyword_search.py`: `GET /keywords/search?q=<substr>` returns ≤ 10 matches, ranked by `doc_freq` desc; empty `q` returns empty list
- [ ] T053 [P] [US4] `tests/graph/test_keyword_search_perf.py`: with 3k keywords, `/keywords/search?q=ka` p95 < 100ms

### Implementation

- [ ] T054 [P] [US4] `src/star_crawl/graph/repository.py`: `search_keywords(q, limit=10) -> list[Keyword]` — LIKE `%q%` on `term` ordered by `doc_freq DESC`
- [ ] T055 [P] [US4] `src/star_crawl/web/routers/graph.py`: `GET /keywords/search` returns HTML fragment list
- [ ] T056 [P] [US4] `src/star_crawl/web/templates/partials/keyword_suggestions.html`
- [ ] T057 [US4] `src/star_crawl/web/static/graph.js`: focus mode — when a keyword is picked, fade `.faded` class on non-neighbors; pan/zoom to node; clear search → unset `.faded`
- [ ] T058 [US4] Wire HTMX `hx-trigger="keyup changed delay:200ms"` on graph search input → `hx-get="/keywords/search"` → render suggestions fragment

**Checkpoint**: US4 ships. Type-ahead + focus mode work.

---

## Phase 7: User Story 5 — Export a slice (P3)

**Goal**: Export currently filtered graph as GraphML (Gephi) and PNG screenshot.

**Independent Test**: After applying filters, run `star-crawl graph export graphml` → file produced contains exactly the filtered nodes/edges with attributes.

### Tests

- [ ] T059 [P] [US5] `tests/graph/test_export_graphml.py`: export against fixture graph; load result via `networkx.read_graphml`; node/edge counts match; attributes (display, doc_freq, cluster_id, npmi) present
- [ ] T060 [P] [US5] `tests/graph/test_export_json.py`: exported JSON parses; matches `/graph.json` shape

### Implementation

- [ ] T061 [P] [US5] `src/star_crawl/graph/export.py`: `to_graphml(graph_data) -> str` and `to_cytoscape_json(graph_data) -> str`
- [ ] T062 [P] [US5] `src/star_crawl/graph/export.py`: `to_png(graph_data, *, headless_browser) -> bytes` — launches playwright, navigates to a hidden page that renders Cytoscape with the data, screenshots the canvas
- [ ] T063 [P] [US5] `src/star_crawl/cli.py`: `graph export graphml|json|png --out <path>` subcommand
- [ ] T064 [P] [US5] Document export workflow in `quickstart.md`

**Checkpoint**: US5 ships. Power-user export available.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T065 [P] `src/star_crawl/cli.py`: `graph stats`, `graph top --by`, `graph cluster`, `graph neighbors` per `contracts/cli.md`
- [ ] T066 [P] `src/star_crawl/cli.py`: `graph relabel <cluster_id> <label>` — set `clusters.label` and `is_user_labeled=1`
- [ ] T067 [P] Stale banner: `src/star_crawl/web/templates/graph.html` shows banner if `(current_articles - last_build_articles) / current_articles > 0.05`; queries one row from `graph_meta` at request time
- [ ] T068 [P] `tests/graph/test_stale_banner.py`: simulate corpus growth +10% over last build → banner present; +1% → absent
- [ ] T069 [P] Skip non-English articles during extraction; record count in `graph_meta.notes`
- [ ] T070 [P] Coverage check: `pytest --cov=star_crawl.graph --cov-fail-under=80`
- [ ] T071 [P] Performance smoke test: extract on 100-article fixture corpus completes in < 10s on a 2023 laptop CPU
- [ ] T072 [P] Performance smoke test: build-graph on 1k-article synthetic dataset completes in < 30s
- [ ] T073 [P] Render performance: with 5k synthetic nodes / 10k edges, fcose layout settles in < 5s on the page; pan/zoom no visible lag (manual)
- [ ] T074 Update `README.md` and `quickstart.md` with the verified extract → build → serve workflow
- [ ] T075 Update `CLAUDE.md` to point active plan reference to whichever feature is being worked next

---

## Dependencies graph

```
Setup (T001-T006)
       │
Foundational (T007-T014) — schema, glossary, aliases, blacklist, normalize
       │
       ├──► US1 P1 extract+build+render (T015-T040) ─┐
       │                                              ├──► MVP ships
       └──► US2 P1 drilldown (T041-T046) ────────────┘
                  │
                  ├──► US3 P2 filters (T047-T051)
                  ├──► US4 P2 search (T052-T058)
                  └──► US5 P3 export (T059-T064)
                              │
                              └──► Polish (T065-T075)
```

Note: US3, US4, US5 each independent of one another; can be parallelized after MVP.

---

## Parallel execution examples

After Foundational, three streams in parallel for US1:

```bash
# Stream A — extraction
T021 + T022 + T023 + T024  # all [P]

# Stream B — graph build
T026 + T027 + T028 + T029 + T030 + T031  # all [P]

# Stream C — render
T035 + T036 + T037 + T038                 # all [P]
```

Tests T015–T020 all parallelizable. Pin model download in CI cache.

After MVP, US3 + US4 + US5 in parallel branches.

---

## Implementation strategy

1. **Setup + Foundational** (T001–T014) — ~0.5 day. Schema migration + glossary seeding + normalization layer.
2. **US1 + US2 = MVP** (T015–T046) — ~3 days. Extraction + graph build + Cytoscape render + drilldown. End state: open `/graph`, click around, drill to articles.
3. **US3 filters** (T047–T051) — ~0.7 day.
4. **US4 search/focus** (T052–T058) — ~0.5 day.
5. **US5 export** (T059–T064) — ~0.5 day.
6. **Polish** (T065–T075) — ~0.8 day.

**Total**: ~6 days. MVP (interactive graph + drilldown) in ~3.5 days from a populated corpus.

---

## Format validation

All 75 tasks follow `- [ ] TXXX [P?] [USx?] Description with file path`. Setup/Foundational/Polish phases have no story label. User-story phases all carry `[USx]`. Every implementation task names a concrete file path.
