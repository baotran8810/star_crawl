# Contract: Crawler CLI

**Owner**: Crawler Core
**Version**: 0.1.0

## Entry point

```
star-crawl <command> [options]
```

Implemented by `typer` in `src/star_crawl/cli.py`.

## Commands

### `run`

Crawl one or more sources.

```
star-crawl run <source-name>           # one source
star-crawl run --all                    # every source in configs/sources/
star-crawl run --all --parallel-sources 3
```

**Options**:

| Flag | Default | Description |
|---|---|---|
| `--data-dir PATH` | `./data` | Where `articles.db` lives |
| `--rate-rps FLOAT` | from config | Override per-source rps |
| `--allow-policy-blocked` | `false` | Bypass robots/policy gate (per-source must also opt-in) |
| `--dry-run` | `false` | Discover URLs only, don't fetch |
| `--limit N` | unbounded | Stop after N new articles per source |
| `--quiet` | `false` | Suppress per-URL progress |

**Exit codes**:

| Code | Meaning |
|---|---|
| 0 | All sources succeeded with zero errors |
| 1 | One or more sources had errors but produced articles (status `partial`) |
| 2 | One or more sources produced zero articles (status `failed`) |
| 3 | Configuration error (missing source, invalid YAML, etc.) before any fetch |

**Output (stdout)**: Rich-rendered summary table per source:

```
Source             Status   Discovered  New  Dup  Errors  Duration
grab_engineering   ok          120       12   108    0      0:42
uber_engineering   partial     198       12   184    2      3:12
```

### `refresh`

Re-fetch existing articles (e.g., when extractor improved).

```
star-crawl refresh <source-name>
star-crawl refresh --since 2026-01-01
```

### `list-sources`

Print all configured sources with their loaded configs.

```
star-crawl list-sources
star-crawl list-sources --json
```

### `stats`

Print corpus stats.

```
star-crawl stats              # totals + per-source counts
star-crawl stats --json
```

### `export`

Derive JSONL or parquet from SQLite.

```
star-crawl export jsonl --out data/exports/all.jsonl
star-crawl export parquet --out data/exports/all.parquet --source uber_engineering
```

### `db migrate`

Run pending schema migrations.

```
star-crawl db migrate
star-crawl db migrate --check    # exit 0 if up-to-date, 1 if pending
```

### `db inspect`

Read-only DB queries for ops.

```
star-crawl db inspect run-history --source uber_engineering --limit 10
star-crawl db inspect errors --run 42
```

## Global options

| Flag | Description |
|---|---|
| `--config-dir PATH` | Override `configs/sources/` location |
| `--log-level LEVEL` | `debug` / `info` (default) / `warn` / `error` |
| `--version` | Print version and exit |
| `--help` | Show help |

## Logging

- Default log level: `info`.
- Logs go to stderr; CLI summary tables go to stdout (so they are pipeable).
- Structured JSON logs available via `--log-format json` for downstream tools.

## Idempotency contract

- `run <source>` repeated immediately MUST be a no-op (zero new articles, zero errors) for any source whose feed/sitemap has not changed.
- `run` interrupted (Ctrl-C, kill -TERM) MUST leave the DB in a consistent state — no half-written articles, frontier state recoverable.
- `refresh` MUST replace existing rows in-place; the article ID is stable across refreshes.

## Backward compatibility

- Schema migrations: forward-only. Each migration carries an upgrade SQL block; downgrade is not supported.
- CLI flags: deprecation requires one minor-version warning before removal.
- Source config schema: additive changes only; required fields cannot be added without a major version bump and migration of existing YAMLs.
