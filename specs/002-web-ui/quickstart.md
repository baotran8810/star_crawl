# Quickstart: Web UI

**Date**: 2026-05-10

## Prerequisites

- Feature 001 installed; `data/articles.db` exists with at least a few articles.
- Python 3.11+, `uv` (or `pip`).

## Setup

```bash
# (Re-use crawler env)
uv pip install -e ".[web]"

# Apply schema migration that adds FTS5 (idempotent)
star-crawl db migrate
```

## Run locally (default-safe)

```bash
star-crawl serve
# Listening on http://127.0.0.1:8000
```

Open the URL in your browser. With a populated corpus you should see the dashboard with totals and source cards.

## Common pages

- `/` — dashboard
- `/sources` — all sources
- `/sources/<name>` — article list for one source
- `/articles/<id>` — article reader
- `/search?q=<query>` — full-text search
- `/runs` — crawl history
- `/runs/<id>` — run detail with errors
- `/healthz` — liveness JSON

## Live search

Focus the header search box and start typing — results appear after a 300ms pause. Press `/` anywhere to focus the box.

## Watch a crawl run

In one shell:

```bash
star-crawl run uber_engineering
```

In your browser, open `/runs`. The in-progress run row updates every 2 seconds without manual refresh. When the run finishes, the row stops updating.

## Expose beyond localhost (advanced)

Default-safe: `serve` refuses non-loopback host without auth. To expose:

```bash
export STAR_CRAWL_AUTH="myuser:strongpassword"
star-crawl serve --host 0.0.0.0 --port 8000
```

Without `STAR_CRAWL_AUTH`, the `--host 0.0.0.0` argument is rejected with an actionable error message. Always run behind HTTPS terminator (Caddy, Cloudflare Tunnel) for any non-localhost binding.

## Tests

```bash
uv run pytest tests/web/                          # all web tests
uv run pytest tests/web/test_search.py            # FTS5 search behavior
uv run pytest tests/web/test_runs.py -k progress  # polling lifecycle
```

## Layout reminder

- App: `src/star_crawl/web/`
- Templates: `src/star_crawl/web/templates/` (with `partials/` for HTMX fragments)
- Static: `src/star_crawl/web/static/`
- Tests: `tests/web/`

## What this feature does NOT do

- No crawl triggering from the browser (CLI-only — see feature 001).
- No editing/annotating articles.
- No multi-user accounts; auth is single-credential.
- No client-side framework, no bundler.
