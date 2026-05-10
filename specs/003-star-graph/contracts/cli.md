# Contract: Star-Graph CLI

**Owner**: Star-Graph
**Version**: 0.1.0
**Adds to**: `star-crawl` CLI (feature 001).

## Commands

### `extract-keywords`

Run keyword extraction on articles in the corpus.

```
star-crawl extract-keywords                    # all articles not yet processed
star-crawl extract-keywords --source uber_engineering
star-crawl extract-keywords --rebuild          # truncate + redo all
star-crawl extract-keywords --since 2026-01-01
```

**Options**:

| Flag | Default | Description |
|---|---|---|
| `--source NAME` | all | Restrict to one source |
| `--since YYYY-MM-DD` | none | Only articles published on or after |
| `--rebuild` | `false` | Truncate `keywords` + `article_keywords` first |
| `--top-n INT` | 15 | Top-N keyword candidates per article from KeyBERT |
| `--ngram-min INT` | 1 | KeyBERT lower n-gram bound |
| `--ngram-max INT` | 3 | KeyBERT upper n-gram bound |
| `--diversity FLOAT` | 0.6 | KeyBERT MMR diversity |
| `--min-score FLOAT` | 0.35 | Drop candidates below this cosine similarity |
| `--no-glossary` | `false` | Skip glossary boost |
| `--no-lemma` | `false` | Skip spaCy lemmatization (faster, less canonical) |
| `--batch-size INT` | 64 | Articles per encode batch |
| `--data-dir PATH` | `./data` | Override DB location |

**First-run note**: On first invocation, the embedding model (~80MB) is downloaded to `~/.cache/huggingface/`. Stored, not re-downloaded.

**Exit codes**: 0 success, 1 partial (some articles failed extraction), 3 config error.

**Output**:

```
extracted: 247 articles · 3,128 unique keywords (1,402 from glossary, 1,726 from KeyBERT)
skipped:   12 (lang != en) · 3 (empty body)
duration:  2:14
```

### `build-graph`

Build the co-occurrence graph from existing `article_keywords`.

```
star-crawl build-graph
star-crawl build-graph --min-doc-freq 5 --min-npmi 0.2
```

**Options**:

| Flag | Default | Description |
|---|---|---|
| `--min-doc-freq INT` | 3 | Drop keywords appearing in fewer articles |
| `--min-co-count INT` | 2 | Drop pairs co-occurring in fewer articles |
| `--min-npmi FLOAT` | 0.15 | Drop edges with NPMI below this |
| `--max-edges-per-node INT` | 30 | Cap edges per node, kept top-N by NPMI |
| `--cluster-resolution FLOAT` | 1.0 | Louvain resolution; lower = bigger clusters |
| `--cluster-seed INT` | 42 | Random seed for reproducible clustering |
| `--data-dir PATH` | `./data` | Override DB location |

**Output**:

```
graph: 482 keywords · 1,134 edges · 7 clusters
clusters: streaming (kafka·queue·stream) · storage (postgres·replica·vacuum) · ...
written: graph_meta row id=4
```

### `graph` (subgroup)

Inspection and export.

#### `graph stats`

Print summary of the latest build.

```
star-crawl graph stats
star-crawl graph stats --json
```

#### `graph top`

Top keywords.

```
star-crawl graph top --by doc_freq --limit 30
star-crawl graph top --by degree   --limit 30
star-crawl graph top --cluster 3   --by doc_freq
```

#### `graph cluster`

Inspect one cluster.

```
star-crawl graph cluster 3            # shows label + member keywords
star-crawl graph cluster --list       # all clusters with labels
```

#### `graph neighbors`

Top neighbors of a keyword.

```
star-crawl graph neighbors kafka --limit 10
```

Output:

```
kafka  (cluster: streaming · 142 articles · degree 38)
  stream     0.71
  queue      0.62
  k8s        0.41
  grpc       0.38
  ...
```

#### `graph relabel`

Override an auto-labeled cluster.

```
star-crawl graph relabel 3 "Event Streaming"
```

Sets `clusters.is_user_labeled = 1` so subsequent rebuilds preserve the override.

#### `graph export`

```
star-crawl graph export graphml --out data/exports/graph.gml
star-crawl graph export json    --out data/exports/graph.json     # Cytoscape format
star-crawl graph export png     --out data/exports/graph.png      # static screenshot via headless browser (requires playwright)
```

## Idempotency

- `extract-keywords` (no `--rebuild`) is idempotent: re-running with no new articles produces zero change.
- `build-graph` is idempotent given the same inputs and seed.
- `extract-keywords --rebuild` is destructive — confirm prompt unless `--yes` passed.

## Error handling

- An article whose extraction throws (e.g., empty after normalization) is logged but does not abort the batch.
- A model download failure is fatal; CLI exits with actionable message ("check internet, try `huggingface-cli download <model>` manually").
- A graph build attempted before any `extract-keywords` run exits with exit code 3 and a clear message.
