# Implementation Plan: Crawler Core

**Branch**: `001-crawler-core` | **Date**: 2026-05-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-crawler-core/spec.md`

## Summary

Multi-source crawler with declarative source configs, polite-by-default fetch policy, and clean content extraction into a single SQLite store. Pipeline: source config → URL discovery → polite fetch (HTTP or browser) → content + metadata extraction → dedup → SQLite. CLI-driven, resumable, idempotent.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `httpx[http2]` (HTTP fetch), `playwright` (browser fetch — only when source declares it), `trafilatura` (main extractor), `readability-lxml` (extractor fallback), `feedparser` (RSS/Atom seed), `pydantic` (schemas), `typer` (CLI), `rich` (terminal output), `pyyaml` (configs), `tldextract` (URL domain)
**Storage**: SQLite (stdlib `sqlite3`) with WAL mode. Single file at `data/articles.db`. Frontier in same DB but separate tables.
**Testing**: `pytest`, `pytest-asyncio`, `respx` (httpx mock), snapshot HTML fixtures in `tests/fixtures/<source>/`
**Target Platform**: macOS / Linux (developer machines + small VPS)
**Project Type**: CLI + library
**Performance Goals**: 1 rps default per domain · 5 concurrent fetches per run · ~1k articles processed in 30 min for typical first-party blog
**Constraints**: <500MB resident memory; survive interrupt without orphaning DB writes; no per-domain account state required for default sources
**Scale/Scope**: 10k articles target; 5–15 sources; 1 user

## Constitution Check

*GATE: Must pass before Phase 0. Re-check after Phase 1.*

| Principle | Check | Status |
|---|---|---|
| **I. Source-Config First** | Source-specific behavior in `configs/sources/*.yaml`; core code generic over `SourceConfig` schema | ✅ |
| **II. Polite-By-Default** | Default rate limit 1 rps; `respect_robots: true` default; opt-in flag `--allow-policy-blocked` for risky sources | ✅ |
| **III. Test-First** | Extractor and dedup logic mandate snapshot tests; CI fails if fixtures missing | ✅ |
| **IV. Many Small Files** | Layout below has 12 modules each ~150–300 LOC | ✅ |
| **V. SQLite as Source of Truth** | Articles, frontier, runs all in one `articles.db`; JSONL/parquet are exports | ✅ |
| **VI. Read-Only UI** | This feature is CLI-only; UI is feature 002 | ✅ (out of scope) |
| **VII. Failure Visibility** | `crawl_runs` table records per-URL errors; CLI summary shows non-zero error counts; zero-discovery raises warning | ✅ |

**Violations**: none.

## Project Structure

### Documentation (this feature)

```text
specs/001-crawler-core/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions
├── data-model.md        # Phase 1 — entities + DDL
├── quickstart.md        # Phase 1 — dev/run guide
└── contracts/
    ├── cli.md           # CLI command schemas
    └── source-config.md # YAML source-config schema
```

### Source Code (repository root)

```text
src/star_crawl/
├── core/
│   ├── schemas.py        # Pydantic: Document, Metadata, SourceConfig, RunResult
│   ├── frontier.py       # SQLite-backed URL queue + dedup
│   ├── pipeline.py       # Orchestrator — wires fetcher, extractor, sink
│   └── policy.py         # robots.txt + opt-in gating
├── fetchers/
│   ├── base.py           # Fetcher protocol
│   ├── http.py           # httpx async client + rate limit + retry
│   └── browser.py        # playwright-backed fetcher (lazy import)
├── seeders/
│   ├── base.py           # Seeder protocol
│   ├── pagination.py     # /page/N/ template
│   ├── rss.py            # feedparser
│   └── sitemap.py        # XML sitemap walker
├── extractors/
│   ├── base.py           # Extractor protocol
│   ├── trafilatura_x.py  # primary
│   ├── readability_x.py  # fallback
│   └── jsonld.py         # JSON-LD metadata enrichment
├── filters/
│   ├── lang.py           # language detect (langdetect)
│   ├── dedupe.py         # SHA-256 + canonical URL
│   └── quality.py        # min word count, paywall sniff
├── sinks/
│   ├── base.py           # Sink protocol
│   └── sqlite.py         # primary
├── sources/
│   └── loader.py         # load configs/sources/*.yaml → SourceConfig
└── cli.py                # typer entry: run, refresh, list-sources, stats

configs/sources/
├── grab_engineering.yaml
├── uber_engineering.yaml
├── gojek_engineering.yaml
├── firstparty_engineering.yaml
└── README.md             # how to add a source

tests/
├── fixtures/<source>/    # snapshot HTML per source
├── unit/                 # extractor, dedup, frontier
├── integration/          # full pipeline against fixtures
└── conftest.py
```

### Out of project (gitignored)

```text
data/
├── articles.db           # SQLite primary store
└── exports/              # JSONL / parquet
```

## Phase 0 — Research

See [research.md](./research.md). All NEEDS CLARIFICATION resolved before Phase 1.

## Phase 1 — Design

- **Data model**: see [data-model.md](./data-model.md). Tables: `sources`, `articles`, `crawl_runs`, `frontier`, `errors`. WAL mode.
- **Contracts**: CLI command schemas in [contracts/cli.md](./contracts/cli.md); source-config YAML schema in [contracts/source-config.md](./contracts/source-config.md).
- **Quickstart**: see [quickstart.md](./quickstart.md).

## Constitution Re-Check (post-design)

| Principle | Re-check after Phase 1 | Status |
|---|---|---|
| I — config first | Confirmed: `configs/sources/*.yaml` validated by `SourceConfig` Pydantic model | ✅ |
| II — polite default | Confirmed: defaults in schema set `rate_limit.rps=1`, `respect_robots=true`, `policy_opt_in=false` | ✅ |
| III — test-first | Confirmed: every extractor + dedup module pairs with `tests/unit/test_<module>.py` | ✅ |
| IV — small files | Confirmed: largest planned module `pipeline.py` ~280 LOC | ✅ |
| V — SQLite truth | Confirmed: no JSONL writes in default flow; `export` is opt-in command | ✅ |
| VI — UI scope | Confirmed: zero web/HTTP server code in this feature | ✅ |
| VII — failure visibility | Confirmed: `errors` table per-URL; CLI exit code non-zero on partial-fail | ✅ |

**Result**: PASS. Ready for `/speckit-tasks`.
