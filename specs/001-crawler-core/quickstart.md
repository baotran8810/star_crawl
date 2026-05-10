# Quickstart: Crawler Core

**Date**: 2026-05-10

## Prerequisites

- Python 3.11+
- `uv` (recommended) or `pip`

## Setup

```bash
# Clone and enter
cd star_crawl

# Install with uv (recommended)
uv venv
uv pip install -e ".[dev]"

# Initialize DB
star-crawl db migrate
```

## First crawl (Grab — easiest)

```bash
star-crawl run grab_engineering
```

Expected output (terminal):

```
Source             Status   Discovered  New  Dup  Errors  Duration
grab_engineering   ok          120       12   108    0      0:42

Wrote to data/articles.db
```

## Verify

```bash
star-crawl stats
# → Total: 12 articles · 1 source · last run 2 minutes ago

star-crawl db inspect run-history --source grab_engineering --limit 5
```

## Add a new source

1. Create `configs/sources/my_blog.yaml` matching the schema in `contracts/source-config.md`.
2. Validate: `star-crawl list-sources` (loader will reject invalid YAML with a clear error).
3. Crawl: `star-crawl run my_blog`.

## Crawl all configured sources

```bash
star-crawl run --all
```

Sources run sequentially by default. Per-source rate limits are independent; run-level concurrency stays bounded.

## Resume an interrupted crawl

Just rerun the same command. The frontier table tracks which URLs are pending.

```bash
star-crawl run uber_engineering    # Ctrl-C mid-run
star-crawl run uber_engineering    # picks up where it left off
```

## Re-fetch existing articles (after extractor improvement)

```bash
star-crawl refresh uber_engineering --since 2026-01-01
```

## Crawl a robots-blocked source (opt-in)

1. Set `policy.policy_opt_in: true` in that source's YAML.
2. Run with the matching CLI flag:

```bash
star-crawl run medium_graphql --allow-policy-blocked
```

Both gates are required. Either alone is rejected.

## Export

```bash
star-crawl export jsonl --out data/exports/all.jsonl
star-crawl export parquet --source uber_engineering --out data/exports/uber.parquet
```

## Tests

```bash
uv run pytest tests/                    # all
uv run pytest tests/unit/               # unit only
uv run pytest tests/integration/ -m extract  # extractor against fixtures
```

## Layout reminder

- Code: `src/star_crawl/`
- Source configs: `configs/sources/*.yaml`
- Tests + fixtures: `tests/`
- Crawled data: `data/articles.db` (gitignored)

## What this feature does NOT do

- No web UI (see feature 002).
- No keyword extraction or graph building (see feature 003).
- No paywall bypass beyond what an explicit opt-in source's adapter implements.
- No distributed crawl across hosts.
