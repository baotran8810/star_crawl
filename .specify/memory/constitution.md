# star_crawl Constitution

**Version**: 0.2.0
**Ratified**: 2026-05-10 · **Amended**: 2026-05-11
**Scope**: Personal corpus tooling — crawl, store, browse, analyze tech-blog content.

## Core Principles

### I. Source-Config First

Adding or changing a source MUST be a configuration change, not a code change. Source-specific behavior (discovery strategy, URL filter, fetcher type, rate limits, opt-in flags) lives in YAML. Core code stays generic.

*Rationale*: The whole point of a "universal" crawler is that the long tail of sources doesn't accumulate as conditional code paths.

### II. Polite-By-Default

The crawler MUST default to behavior that does not get the user's IP banned, does not violate published policies, and does not flood any single origin. Risky sources (paywall bypass, robots-blocked targets) MUST require an explicit, named opt-in flag — never enabled by environment variable or hidden default.

*Rationale*: A crawler that needs babysitting to be safe is unsafe in practice.

### III. Test-First (Where It Matters)

Extraction logic, edge-case handling (paywall, empty body, redirect-to-login), and dedup logic MUST be covered by tests with snapshot HTML fixtures. UI markup and rendering correctness are validated by lower-fidelity tests; visual polish is validated manually.

*Rationale*: Most regressions in scrapers are silent — empty content stored without error. Tests are the only defense.

### IV. Many Small Files

Files SHOULD stay under 400 lines; 800 is a hard ceiling. Modules cohere by feature/domain (fetchers, extractors, sinks, sources), not by type (utils.py, helpers.py).

*Rationale*: Long files in scraper codebases become impossible to safely refactor when sites change.

### V. SQLite as Single Source of Truth

The article store is the canonical state. JSONL, parquet, and any future export are *derived*. The database MUST use WAL mode so the crawler can write while the web UI reads.

*Rationale*: Avoids the "what's the truth — the JSONL or the database?" question that makes export-first pipelines brittle.

### VI. UI Writes Are Explicit and User-Triggered (revised v0.2.0)

The web interface MAY write corpus state, but ONLY in direct response to an
explicit user action (form submit, button click). The UI MUST NOT:

- Mutate state on a `GET` request,
- Run a crawl on schedule, cron, or page load,
- Persist any change without the user actively confirming.

Long-running operations (e.g., crawls) MUST run **out-of-process** (subprocess
or worker) so the web request thread is never blocked, and progress MUST be
observable on the existing `/runs` page.

*Rationale (revised)*: The original read-only rule was a safety policy, not a
goal in itself. The real safety property is "no surprise writes." A button the
user clicks on a button labelled `Run` is not a surprise — and forcing CLI-only
for routine operations creates friction without protecting anything.

*What stays banned*: implicit writes, auto-crawls on page load, write-on-GET.

### VII. Failure Visibility

A run that hits errors MUST surface them — per-URL errors, quality regressions, and zero-discovery results MUST NOT be silently absorbed into "success" status.

*Rationale*: Silent failure in scrapers = months of hidden data loss before someone notices.

## Stack Constraints

- **Language**: Python 3.11+ for all components.
- **Storage**: SQLite (single file) for primary store.
- **Testing**: `pytest` + snapshot HTML fixtures.
- **Linting**: `ruff` (format + lint).
- **No build step** for the web UI: server-rendered templates + progressive enhancement only. No JS framework, no bundler.

## Workflow

- Specs live in `specs/<NNN>-<feature>/`. Each spec is technology-agnostic.
- Plans (`/speckit-plan`) translate specs into stack choices and project structure.
- Tasks (`/speckit-tasks`) decompose plans into actionable units.
- A spec or its plan MUST NOT prescribe a stack the constitution forbids without amending the constitution first.

## Constitution Amendment

Any change to this document requires a commit with rationale in the message and a corresponding bump of the version field above.
