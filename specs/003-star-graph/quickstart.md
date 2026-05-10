# Quickstart: Star-Graph

**Date**: 2026-05-10

## Prerequisites

- Features 001 and 002 installed.
- A populated corpus — at least 100 articles for a meaningful graph.

## Setup

```bash
# Install with the graph extras
uv pip install -e ".[graph]"

# Optional: install spaCy English model for lemmatization
python -m spacy download en_core_web_sm

# Apply migrations (adds keywords / article_keywords / keyword_edges tables)
star-crawl db migrate
```

## First-time graph build

```bash
# 1. Extract keywords (downloads embedding model on first run, ~80MB)
star-crawl extract-keywords --all

# 2. Build the graph
star-crawl build-graph

# 3. Inspect from CLI
star-crawl graph stats
```

Expected output:

```
graph: 482 keywords · 1,134 edges · 7 clusters
clusters:
  3 — Event Streaming    (kafka · stream · queue · ...)
  5 — Storage             (postgres · replica · vacuum · ...)
  7 — Service Mesh        (istio · envoy · grpc · ...)
  ...
```

## Browse the graph in the UI

```bash
star-crawl serve
# → http://127.0.0.1:8000
```

Click the `Graph` tab.

- **Node** — keyword. Larger = appears in more articles. Color = cluster.
- **Edge** — co-occurrence. Thicker = stronger relationship (NPMI).
- **Click a node** — side panel opens with top neighbors and recent articles.
- **Type in the search box** — type-ahead suggestions; pick one to focus.
- **Filter sidebar** — restrict by source, time range, min frequency, min NPMI.

## Inspect from CLI

```bash
star-crawl graph top --by doc_freq --limit 30      # most prevalent keywords
star-crawl graph top --by degree   --limit 30      # most-connected hubs
star-crawl graph cluster 3                          # show one cluster
star-crawl graph neighbors kafka --limit 10         # neighbors of one keyword
```

## Override an auto-cluster label

If the auto-label is unhelpful:

```bash
star-crawl graph relabel 3 "Event Streaming"
```

Subsequent rebuilds preserve user-set labels.

## Update the glossary

Edit `configs/graph/glossary.yaml`. Add tech terms you want guaranteed to be picked up. Then:

```bash
star-crawl extract-keywords --rebuild       # ensure new glossary terms are matched
star-crawl build-graph
```

## Refresh after a new crawl

```bash
star-crawl run --all                # crawl new articles
star-crawl extract-keywords          # delta only — fast
star-crawl build-graph               # always full rebuild — fast
```

The web UI shows a "graph stale" banner when the corpus has grown more than 5% since the last build.

## Export

```bash
star-crawl graph export graphml --out data/exports/graph.graphml
star-crawl graph export json --out data/exports/graph.cy.json
star-crawl graph export png  --out data/exports/graph.png
```

PNG export uses headless playwright; requires the browser fetcher's chromium install.

## Tests

```bash
uv run pytest tests/graph/                          # all graph tests
uv run pytest tests/graph/test_extract.py           # extractor against fixture corpus
uv run pytest tests/graph/test_ppmi.py              # weighting math
uv run pytest tests/graph/test_cluster.py           # deterministic clustering
uv run pytest tests/graph/test_routes.py            # /graph.json + /keywords/*
```

## Layout reminder

- Code: `src/star_crawl/graph/` + `src/star_crawl/web/routers/graph.py`
- Templates: `src/star_crawl/web/templates/graph.html`
- Vendored JS: `src/star_crawl/web/static/vendor/cytoscape.min.js`, `cytoscape-fcose.min.js`
- Configs: `configs/graph/{glossary,aliases,blacklist,cluster_labels}.yaml`
- Tests: `tests/graph/`

## What this feature does NOT do

- Does not crawl or fetch — works only off existing corpus.
- Does not call out to LLMs.
- Does not animate the graph over time (deferred).
- Does not auto-discover aliases (requires manual `aliases.yaml` for now).
- Does not provide multilingual support beyond English (non-en articles are skipped during extraction).
