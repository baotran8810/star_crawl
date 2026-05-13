# star_crawl

Universal web crawler with content extraction. Targeting Uber · Grab · Gojek · Medium and the tech blog ecosystem.

Output: SQLite (canonical) + derived JSONL/parquet exports. Plug-in architecture: thêm source mới = thêm 1 file YAML.

## Status

Four features delivered (see `specs/`):

1. **001-crawler-core** — Multi-source crawler + SQLite store (HTTP + Playwright browser fetchers, RSS / sitemap / pagination seeders, trafilatura + readability extractors, dedup, frontier resume).
2. **002-web-ui** — Read-only browse, FTS5 search, per-source page, run history with live progress.
3. **003-star-graph** — Keyword extraction (KeyBERT default, opt-in LLM via 9router/mimo) + co-occurrence graph (NPMI + Louvain clustering) + interactive Cytoscape view with drilldown.
4. **004-obsidian-ui** — Obsidian-style workspace shell: tabbed main, navigation tree, command palette, light/dark theme, monochrome graph mode. Tabs persist across browser restarts via `localStorage`.

## Run

```bash
# Crawl one source
.venv/bin/python -m star_crawl.cli run uber_engineering

# Crawl every source
.venv/bin/python -m star_crawl.cli run --all

# Extract keywords + build graph
.venv/bin/python -m star_crawl.cli extract-keywords           # KeyBERT (free, local)
.venv/bin/python -m star_crawl.cli extract-keywords --method llm    # LLM via 9router
.venv/bin/python -m star_crawl.cli build-graph

# Web UI
STAR_CRAWL_AUTH=admin:secret \
.venv/bin/python -m star_crawl.cli serve --port 8002
open http://127.0.0.1:8002/
```

### Web UI — Workspace shell

The root path `/` renders an Obsidian-style workspace:

- **Icon rail** (left, 48 px) — Sources · Graph · Runs · Search · Bookmarks
- **Navigation tree** (collapsible, 280 px) — expandable sources → articles, recent runs
- **Tabbed main area** — open multiple articles / runs / graph side-by-side
- **Status bar** (bottom) — project name · article count · source count · theme toggle

Open new tabs via tree click (middle-click for background). Drag tab edges to reorder. Close with `×` or `Cmd-W`. Closing the last tab auto-opens a fresh Graph tab.

Keyboard:

| Shortcut | Action |
|---|---|
| `Cmd/Ctrl-K` | Command palette (search + workspace actions) |
| `Cmd/Ctrl-W` | Close active tab |
| `Cmd/Ctrl-Shift-W` | Close all tabs |
| `Alt-→` / `Alt-←` | Next / previous tab |
| `Alt-1`..`Alt-9` | Jump to tab N |
| `Alt-Shift-→/←` | Reorder active tab |
| `[` | Toggle navigation tree |
| `?` or `Cmd-/` | Help overlay |

Direct URLs still work (legacy chrome): `/dashboard`, `/articles/{id}`, `/runs`, `/runs/{id}`, `/sources`, `/sources/{name}`, `/graph`, `/search?q=...`. Internally the same handlers also serve content-only `/panel/...` variants used inside workspace tabs.

State (open tabs, active tab, theme, cluster-color preference, graph zoom + pan per tab) lives in `localStorage` under key `star_crawl.workspace.v1`. To reset:

```js
localStorage.removeItem('star_crawl.workspace.v1');
location.reload();
```

## Stack

- **Python 3.11+**
- Fetchers: `httpx` + `playwright` (browser fetcher used for anti-bot sources like Uber)
- Extractors: `trafilatura` + `readability-lxml` for content, `keybert` + optional LLM for keywords
- Discovery: `feedparser` (RSS), sitemap parser, pagination crawler
- Graph: `networkx` (Louvain + degree), Cytoscape.js with fcose layout (vendored)
- Storage: SQLite (WAL) — single source of truth
- Web: FastAPI + Jinja + HTMX (server-rendered) + vanilla JS workspace shell (no framework, no bundler)
- CLI: `typer`

## Constitution

Read `.specify/memory/constitution.md` for the seven core principles. The most operational:

- Adding a source = adding a YAML, not editing code (`configs/sources/*.yaml`).
- The crawler is polite by default (rate limits, `robots.txt`, no scheduled writes from the UI).
- Long-running operations run **out of process** — the web UI never blocks a request thread on a crawl.
- Files stay under 400 lines (800 hard ceiling).
- No JS framework / no bundler in the web UI.

## License

MIT (TBC)
