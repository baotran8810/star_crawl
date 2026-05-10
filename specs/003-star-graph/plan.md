# Implementation Plan: Star-Graph

**Branch**: `003-star-graph` | **Date**: 2026-05-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/003-star-graph/spec.md`

## Summary

Build a keyword co-occurrence network from the corpus produced by feature 001, expose it via the web UI from feature 002. Two CLI commands (`extract-keywords`, `build-graph`) populate three new tables; one new web route (`/graph`) renders an interactive Cytoscape.js view that drills back to articles. No re-fetching of source content.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- Extraction: `keybert`, `sentence-transformers` (model `all-MiniLM-L6-v2`, ~80MB), optional `spacy[en_core_web_sm]` for lemmatization, `langdetect` (already from feature 001).
- Graph build: `networkx` (Louvain via `networkx.algorithms.community.louvain_communities`), `numpy` (transitively).
- Web rendering: Cytoscape.js 3.x (vendored, no CDN at runtime), `fcose` layout extension (vendored).
**Storage**: Same `data/articles.db`. Three new tables (`keywords`, `article_keywords`, `keyword_edges`) + `graph_meta` audit table.
**Testing**: `pytest` with a small fixture corpus of ~30 articles; deterministic seed for clustering tests.
**Target Platform**: Same as feature 001/002.
**Project Type**: CLI extension + web extension (no new project).
**Performance Goals**: Extract ≥ 50 articles/s on CPU · build graph for 10k articles in < 60s · render 5k visible nodes interactively.
**Constraints**: Default install MUST NOT pull the embedding model (lazy download on first `extract-keywords`). Memory < 1GB during extraction batch. No GPU required.
**Scale/Scope**: 10k articles → ~3k unique keywords → ~5–10k edges after pruning → ~7–15 clusters.

## Constitution Check

| Principle | Check | Status |
|---|---|---|
| **I. Source-Config First** | Glossary, alias map, blacklist, pruning thresholds all live in YAML in `configs/graph/`; no hardcoded lists in code | ✅ |
| **II. Polite-By-Default** | This feature does no network I/O — works only off existing corpus | ✅ |
| **III. Test-First** | Extractor tests against fixture corpus; PPMI calculation has unit tests; clustering test uses fixed seed | ✅ |
| **IV. Many Small Files** | 8 modules avg ~200 LOC | ✅ |
| **V. SQLite as Source of Truth** | All graph state in DB tables; nothing materialized to disk | ✅ |
| **VI. Read-Only UI** | Graph build runs via CLI, never via browser; UI only reads | ✅ |
| **VII. Failure Visibility** | `graph_meta` table records every build with config_hash + counts; UI shows "stale" banner when content_hash of articles ≠ build's snapshot | ✅ |

**Violations**: none.

**Note on dependency size**: The embedding model (~80MB) is lazy-downloaded on first invocation, not at install time. Default install size remains under 200MB. Documented in quickstart.

## Project Structure

### Documentation (this feature)

```text
specs/003-star-graph/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # 3 tables + meta + DDL
├── quickstart.md        # Phase 1
└── contracts/
    ├── cli.md           # extract-keywords, build-graph, graph subcommands
    └── graph-api.md     # /graph.json, /keywords/{id}, /keywords/search
```

### Source code

```text
src/star_crawl/
├── graph/
│   ├── extract.py          # KeyBERT + glossary boost + normalize
│   ├── glossary.py         # load configs/graph/glossary.yaml, alias map, blacklist
│   ├── normalize.py        # casing, lemmatize, alias resolution
│   ├── ppmi.py             # NPMI computation, pruning thresholds
│   ├── cluster.py          # Louvain + cluster auto-label
│   ├── builder.py          # build-graph orchestrator (writes 3 tables + meta)
│   └── repository.py       # read-side queries for web routes
├── web/routers/
│   └── graph.py            # GET /graph, /graph.json, /keywords/{id}, /keywords/search
├── web/templates/
│   ├── graph.html
│   └── partials/
│       └── keyword_panel.html
├── web/static/vendor/
│   ├── cytoscape.min.js
│   └── cytoscape-fcose.min.js
└── cli.py                  # add: extract-keywords, build-graph, graph (subgroup)

configs/graph/
├── glossary.yaml           # ~500 tech terms
├── aliases.yaml            # k8s ≡ kubernetes, postgres ≡ postgresql, …
├── blacklist.yaml          # generic noise: team, system, engineer, …
└── README.md
```

## Phase 0 — Research

See [research.md](./research.md).

## Phase 1 — Design

- **Data model**: see [data-model.md](./data-model.md).
- **CLI contract**: see [contracts/cli.md](./contracts/cli.md).
- **Web API contract**: see [contracts/graph-api.md](./contracts/graph-api.md).
- **Quickstart**: see [quickstart.md](./quickstart.md).

## Constitution Re-Check (post-design)

| Principle | Re-check | Status |
|---|---|---|
| I — config first | Confirmed: tech glossary + aliases + blacklist all YAML; pruning thresholds in CLI flags or YAML | ✅ |
| III — test-first | Confirmed: extractor tested against `tests/fixtures/graph_corpus/` (30 mini-articles); cluster test uses fixed `random_state` | ✅ |
| IV — small files | Confirmed: largest planned module `builder.py` ~280 LOC | ✅ |
| V — SQLite truth | Confirmed: all graph state in DB; client-side cache invalidated by `graph_meta.built_at` ETag | ✅ |
| VI — read-only UI | Confirmed: web route only reads tables; build is CLI-only | ✅ |
| VII — failure visibility | Confirmed: `graph_meta` records `n_articles` at build time; UI compares with current article count → "stale" badge | ✅ |

**Result**: PASS. Ready for `/speckit-tasks`.
