# star_crawl

Universal web crawler with content extraction. Targeting Uber · Grab · Gojek · Medium and tech blog ecosystem.

Output LLM-ready markdown / parquet. Plug-in architecture: thêm source mới = thêm 1 file YAML.

## Status

Planning phase. See [`PLAN.html`](./PLAN.html) for full architecture, source matrix, roadmap, and design decisions.

## Stack (planned)

- Python 3.11+
- `httpx` + `playwright` (fetchers)
- `trafilatura` + `readability-lxml` (extractors)
- `feedparser` (RSS discovery)
- SQLite frontier · JSONL/parquet sinks
- `typer` CLI

## Roadmap

| Phase | Deliverable | Time |
|---|---|---|
| P0 | Bootstrap (pyproject, schemas, config loader) | 0.5d |
| P1 | Grab Engineering — RSS adapter | 1d |
| P2 | Uber Engineering — pagination + JSON-LD | 1d |
| P3 | Gojek — browser fetcher (Vercel challenge) | 1.5d |
| P3.5 | First-party tech blogs (Netflix, Stripe, Cloudflare…) | 0.5d |
| P4 | Medium GraphQL adapter (opt-in, experimental) | 1.5d |
| P5 | Resume, dedup, parquet, polish | 1d |

## License

MIT (TBC)
