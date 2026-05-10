# Phase 0 Research: Star-Graph

**Date**: 2026-05-10

## Decisions

### Keyword extractor — `KeyBERT` (semantic) + tech glossary boost

- **Decision**: KeyBERT with `sentence-transformers` model `all-MiniLM-L6-v2`. Top 15 candidates per article with `keyphrase_ngram_range=(1,3)`, `use_mmr=true`, `diversity=0.6`. Then merge with exact-match hits from a curated tech glossary so known terms (e.g., "Kafka", "k8s") are never missed.
- **Rationale**: Pure rule-based extractors (RAKE, YAKE) miss context — they treat "service" the same in "service mesh" vs "customer service". KeyBERT's semantic similarity solves that. Glossary boost catches abbreviations and brand-named tools that BERT may not weight strongly.
- **Cost**: Model is 23MB, runs at ~50 articles/s on CPU. ~3 minutes for 10k articles. Acceptable for a one-shot batch job.
- **Alternatives**:
  - YAKE — fast (~500/s) and multilingual but lower quality on technical text.
  - LLM-based (Haiku / gpt-4o-mini) — best quality but ~$5–10 per 10k articles and rate-limited; deferred.
  - SpaCy NER + noun phrases — misses domain-specific terms, false positives on org names.

### Stopword + blacklist — extended noise list in YAML

- **Decision**: `configs/graph/blacklist.yaml` with ~80 generic terms (team, engineer, system, post, article, ...) plus standard NLTK English stopwords inside KeyBERT.
- **Rationale**: Tech blogs are heavily dominated by structural words. Without aggressive blacklisting the graph is unreadable.
- **Alternatives**: TF-IDF threshold instead of blacklist (less precise; still keeps "engineer" because it's everywhere).

### Normalization — case + lemma + alias

- **Decision**:
  1. Lowercase except for short all-caps acronyms (≤4 chars all-uppercase preserved: K8S → k8s yes, but JWT stays JWT).
  2. Lemmatize via spaCy `en_core_web_sm` (lazy import; optional — falls back to no-lemma if not installed).
  3. Apply alias map: e.g., `k8s ≡ kubernetes`, `postgres ≡ postgresql`. Aliases stored in `configs/graph/aliases.yaml`.
- **Rationale**: Without normalization, the graph has 4 nodes for the same concept ("k8s", "K8s", "Kubernetes", "kubernetes"), each with weak edges. Merging gives one strong node.
- **Alternatives**: Auto-cluster aliases via embedding similarity (deferred — risk of false merges).

### Edge weight — Normalized PMI (NPMI), positive only

- **Decision**: Compute NPMI per pair; keep edges with NPMI > 0.15 and co-occurrence count >= 2.
- **Rationale**: Raw co-occurrence is biased toward frequent words. PMI corrects but is unbounded and unstable for rare pairs. NPMI scales to [-1, 1], easy to threshold. Positive-only filters out negative associations (which would be weird in a tech corpus anyway).
- **Alternatives**:
  - Jaccard — symmetric and simple, but doesn't account for marginal frequencies.
  - Raw count — too biased toward "engineer / system" pairs.
  - Tf-idf cosine — overkill for sparse co-occurrence.

### Pruning — degree cap + min thresholds

- **Decision**: Per node, keep only the top-30 edges by weight. Globally, drop nodes with `doc_freq < 3`. Configurable via CLI flags.
- **Rationale**: Cytoscape renders ~5k nodes / 20k edges interactively on a 2023 laptop. Without per-node caps, hub nodes ("data", "code") generate hundreds of edges and choke layout.

### Clustering — Louvain, fixed seed

- **Decision**: `networkx.algorithms.community.louvain_communities` with `resolution=1.0` and `seed=42` for reproducibility.
- **Rationale**: Louvain is the best-known modularity-based community detection algorithm; near-optimal at this scale; available in stdlib networkx; deterministic with seed.
- **Alternatives**: Leiden (slightly better quality, requires `python-igraph` C extension); LabelProp (faster but less stable).

### Cluster auto-label — top-3 by `doc_freq`

- **Decision**: For each cluster, label with top-3 keywords by `doc_freq`, joined by " · ". Stored in a new `clusters(id, label, n_keywords)` table.
- **Rationale**: Simple, deterministic, usually meaningful. User can override via `configs/graph/cluster_labels.yaml` (post-build).
- **Alternatives**: LLM-based labeling (better quality, deferred).

### Visualization library — Cytoscape.js + fcose

- **Decision**: Cytoscape.js 3.x with the `fcose` layout extension. Vendored as static assets.
- **Rationale**: Best documented layout for force-directed graphs at this scale; declarative styling matches HTMX-flavored UI; ~80KB gzipped; no build step.
- **Alternatives**:
  - Sigma.js — faster GPU rendering at >10k nodes (not needed at our scale).
  - D3 — most flexible but most code.
  - vis-network — easier defaults, less stylable.

### Graph payload format — Cytoscape elements JSON

- **Decision**: `/graph.json` returns `{nodes: [...], edges: [...]}` with each node carrying `data: {id, display, doc_freq, cluster_id, color}` and each edge `data: {id, source, target, npmi}`.
- **Rationale**: Native Cytoscape format, no client-side adapter.

### Caching — ETag from `graph_meta.built_at`

- **Decision**: `/graph.json` carries `ETag: "<built_at_iso>"` header. Browser revalidates with `If-None-Match`; server returns 304 when fresh.
- **Rationale**: Graph payload is static between rebuilds, sometimes large. ETag avoids re-sending.

### Stale detection — articles count vs `graph_meta.n_articles`

- **Decision**: Web UI checks current `SELECT COUNT(*) FROM articles` vs the most recent `graph_meta.n_articles`. If delta > 5%, render a "stale — run `star-crawl build-graph`" banner above the canvas.
- **Rationale**: User needs to know to rebuild after a big crawl; cheap query at page load.

## Open questions resolved

- **Q**: Time-dimension (animate graph over time)? **A**: Out of scope for v1; possible follow-up. Adds 1d effort for a feature only some users want.
- **Q**: Export format? **A**: GraphML (Gephi-compatible) + PNG screenshot of current view. Both via CLI subcommand.
- **Q**: Should extraction skip non-English articles? **A**: Skip for v1 — silently in the run, with count reported in `graph_meta.notes`. Most articles in our default sources are English. Multilingual support is deferred.
- **Q**: How big should the glossary be? **A**: Start at ~500 entries seeded from awesome-* lists + manual curation. Iteratively grow when graph review reveals known-good terms missed.
- **Q**: Where do tech-glossary aliases come from? **A**: Manual file. Auto-discovery of aliases from corpus (via embedding clustering) is appealing but error-prone — defer.

## Out of scope (deferred)

- LLM-assisted keyword extraction.
- Time-evolution animation.
- Author-topic-source tripartite graph.
- LLM cluster labeling.
- Cross-source vs intra-source edge differentiation.
- Article recommendation paths through the graph.
