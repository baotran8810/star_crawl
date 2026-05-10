# Tasks: Crawler Core

**Input**: Design documents from `specs/001-crawler-core/`
**Prerequisites**: plan.md ✓ · spec.md ✓ · research.md ✓ · data-model.md ✓ · contracts/cli.md ✓ · contracts/source-config.md ✓

**Tests**: INCLUDED — Constitution III mandates snapshot tests for extractor + dedup logic.

**Organization**: Tasks are grouped by user story (US1–US4 from spec) so each story can be independently shipped as an MVP increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no dependency on incomplete tasks)
- **[Story]**: User-story label (US1, US2, US3, US4)
- All paths relative to repo root

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Initialize Python package layout: create `src/star_crawl/`, `tests/`, `configs/sources/`, `data/` and add `__init__.py` files
- [ ] T002 Create `pyproject.toml` with project metadata, Python 3.11+ requirement, base dependencies (httpx[http2], trafilatura, readability-lxml, feedparser, pydantic, typer, rich, pyyaml, langdetect, tldextract), `dev` extra (pytest, pytest-asyncio, respx, ruff, mypy), `browser` extra (playwright)
- [ ] T003 [P] Configure `ruff.toml` with line-length 100, isort enabled, target-version py311
- [ ] T004 [P] Configure `pytest.ini` with `asyncio_mode = auto`, markers (`unit`, `integration`, `extract`)
- [ ] T005 [P] Add `.gitignore` entries for `data/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`
- [ ] T006 [P] Create `tests/conftest.py` with shared fixtures: in-memory SQLite DB factory, sample HTML loader, frozen-time clock
- [ ] T007 Wire entry point: `[project.scripts] star-crawl = "star_crawl.cli:app"` in `pyproject.toml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ No user-story work can begin until this phase is complete.**

- [ ] T008 Implement Pydantic schemas in `src/star_crawl/core/schemas.py`: `SourceConfig`, `RateLimit`, `RetryPolicy`, `ExtractConfig`, `DedupConfig`, `PolicyConfig`, `BrowserConfig`, `Document`, `Metadata`, `RunResult` (mirrors `contracts/source-config.md` and `data-model.md`)
- [ ] T009 [P] Write SQL migration `src/star_crawl/migrations/001_initial.sql` with all 5 tables (`sources`, `articles`, `crawl_runs`, `frontier`, `errors`) per `data-model.md` DDL, plus PRAGMAs (WAL, foreign_keys)
- [ ] T010 [P] Write SQL migration `src/star_crawl/migrations/000_schema_version.sql` with `_schema_version` table (single row)
- [ ] T011 Implement `src/star_crawl/db/connection.py`: open/close SQLite, set WAL pragma, expose `get_conn(read_only=False)`
- [ ] T012 Implement `src/star_crawl/db/migrate.py`: scan migrations dir, apply pending in order, update `_schema_version`
- [ ] T013 [P] Implement `src/star_crawl/sources/loader.py`: scan `configs/sources/*.yaml`, validate via `SourceConfig`, return `dict[str, SourceConfig]`. Reject when filename ≠ `name`
- [ ] T014 [P] Implement `src/star_crawl/core/policy.py`: `RobotsChecker` using `urllib.robotparser`, per-domain cache, lookup `is_allowed(url, user_agent)`
- [ ] T015 Implement `src/star_crawl/cli.py` skeleton: typer app with `db migrate`, `db inspect`, `list-sources`, `stats` stub commands; wires logging level and `--data-dir`
- [ ] T016 [P] Test `tests/unit/test_schemas.py`: round-trip every example YAML in `contracts/source-config.md` through `SourceConfig`; assert validation rules (regex compile, name uniqueness, fetcher requires extras)
- [ ] T017 [P] Test `tests/unit/test_migrate.py`: idempotency — run migrations twice on temp DB, assert no error and final state stable
- [ ] T018 [P] Test `tests/unit/test_policy.py`: synthetic robots.txt blocks `star_crawl/0.1`; `is_allowed()` returns False

**Checkpoint**: Foundation ready. User story implementation can begin in parallel.

---

## Phase 3: User Story 1 — Pull a tech blog into local store (P1) 🎯 MVP

**Goal**: One CLI command pulls every discoverable article from one source into `data/articles.db`.

**Independent Test**: `star-crawl run grab_engineering` populates ≥ 50 articles with non-empty title/content/source attribution; spot-check 5 confirms boilerplate stripped.

### Tests (write FIRST, ensure they FAIL)

- [ ] T019 [P] [US1] Snapshot fixtures: `tests/fixtures/grab/index.html` + 3 article HTML files (capture from real Grab pages once, version-controlled)
- [ ] T020 [P] [US1] `tests/unit/test_seeders_rss.py`: feed XML → list of article URLs; respects `url_filter`
- [ ] T021 [P] [US1] `tests/unit/test_extractor_trafilatura.py`: each fixture article → assert title non-empty, word_count ≥ 100, no nav/footer text leaked
- [ ] T022 [P] [US1] `tests/unit/test_extractor_readability_fallback.py`: trafilatura empty → readability fills in; if both empty → raise `ExtractionFailed`
- [ ] T023 [P] [US1] `tests/unit/test_dedup.py`: same content via two URLs → single article row; second insert updates `crawled_at` only
- [ ] T024 [P] [US1] `tests/unit/test_jsonld.py`: fixture HTML with `<script type="application/ld+json">` → extract author + datePublished
- [ ] T025 [P] [US1] `tests/integration/test_pipeline_grab.py`: mock httpx with `respx`, run end-to-end against fixtures, assert N articles inserted

### Implementation

- [ ] T026 [P] [US1] `src/star_crawl/fetchers/base.py`: `Fetcher` Protocol with `async fetch(url) -> FetchResult`; `FetchResult(html, status, headers)`
- [ ] T027 [P] [US1] `src/star_crawl/fetchers/http.py`: httpx async client + per-domain semaphore + token-bucket rate limit + retry-with-backoff (3 attempts, honor Retry-After)
- [ ] T028 [P] [US1] `src/star_crawl/seeders/base.py`: `Seeder` Protocol with `async seed(source) -> AsyncIterator[str]`
- [ ] T029 [P] [US1] `src/star_crawl/seeders/rss.py`: `feedparser` adapter; emit URLs matching `url_filter`
- [ ] T030 [P] [US1] `src/star_crawl/extractors/base.py`: `Extractor` Protocol with `extract(html, url) -> Document | None`
- [ ] T031 [P] [US1] `src/star_crawl/extractors/trafilatura_x.py`: primary extractor; output Document(title, content_md, content_text, author, published_at, lang, word_count)
- [ ] T032 [P] [US1] `src/star_crawl/extractors/readability_x.py`: fallback extractor wrapping `readability-lxml`
- [ ] T033 [P] [US1] `src/star_crawl/extractors/jsonld.py`: parse JSON-LD blocks from HTML; merge into Document metadata
- [ ] T034 [P] [US1] `src/star_crawl/filters/dedupe.py`: SHA-256 of normalized text; `is_duplicate(content_hash)` against `articles.content_hash`
- [ ] T035 [P] [US1] `src/star_crawl/filters/lang.py`: `langdetect` wrapper; return `(lang, confidence)`; persist only if `confidence ≥ 0.9`
- [ ] T036 [P] [US1] `src/star_crawl/filters/quality.py`: reject if word_count < `min_word_count`; sniff paywall via marker phrases
- [ ] T037 [P] [US1] `src/star_crawl/sinks/base.py`: `Sink` Protocol with `async write(article: Document, run_id: int) -> ArticleId`
- [ ] T038 [P] [US1] `src/star_crawl/sinks/sqlite.py`: insert into `articles`; on dedup hit update `crawled_at`; track `errors` for failed extracts
- [ ] T039 [US1] `src/star_crawl/core/pipeline.py`: orchestrator wiring seeder → fetcher → extractor → filters → sink; depends on T026–T038
- [ ] T040 [US1] `src/star_crawl/cli.py`: implement `run <source>` command using pipeline; rich-rendered summary table per source
- [ ] T041 [US1] Create `configs/sources/grab_engineering.yaml` per the example in `contracts/source-config.md`
- [ ] T042 [US1] Validate end-to-end: against fixture HTML, assert ≥ 3 articles populated with all required metadata

**Checkpoint**: US1 fully functional. `star-crawl run grab_engineering` works against real Grab feed.

---

## Phase 4: User Story 2 — Add a new source without writing code (P2)

**Goal**: Drop a YAML file in `configs/sources/`; next run pulls from it. No code changes.

**Independent Test**: Add a new YAML for a different blog; `star-crawl list-sources` shows it; `star-crawl run <new-name>` produces articles.

### Tests

- [ ] T043 [P] [US2] `tests/integration/test_loader_validation.py`: malformed YAML, name mismatch with filename, regex doesn't compile → loader rejects with actionable message
- [ ] T044 [P] [US2] `tests/integration/test_pipeline_pagination.py`: pagination seeder against fixture index pages → URL list matches filter
- [ ] T045 [P] [US2] `tests/integration/test_pipeline_sitemap.py`: sitemap seeder against fixture XML → URL list

### Implementation

- [ ] T046 [P] [US2] `src/star_crawl/seeders/pagination.py`: walk `template.format(n=i)` for `range[0]..range[1]`; extract anchors matching `url_filter`
- [ ] T047 [P] [US2] `src/star_crawl/seeders/sitemap.py`: parse XML sitemap (with sitemap-index support if `follow_index=true`); emit URLs matching filter
- [ ] T048 [US2] Update `src/star_crawl/core/pipeline.py`: dispatch to seeder based on `seed.strategy`
- [ ] T049 [US2] `src/star_crawl/cli.py`: implement `list-sources` (table form) and `list-sources --json`
- [ ] T050 [US2] `src/star_crawl/cli.py`: implement `run --all`; iterate sources sequentially; aggregate summary table
- [ ] T051 [P] [US2] Create `configs/sources/uber_engineering.yaml` (pagination)
- [ ] T052 [P] [US2] Create `configs/sources/firstparty_engineering.yaml` (multi-feed RSS list)
- [ ] T053 [P] [US2] Add `configs/sources/README.md` documenting fields with examples

**Checkpoint**: US2 fully functional. Adding a source is a YAML-only change.

---

## Phase 5: User Story 3 — Resume an interrupted crawl (P2)

**Goal**: Killing a run mid-flight and restarting it picks up only pending URLs.

**Independent Test**: Start crawl, kill at 30% progress, restart same command; second run only processes URLs not in `frontier.state='done'`.

### Tests

- [ ] T054 [P] [US3] `tests/integration/test_resume.py`: simulate run with 100 URLs; mark 30 done, 5 in_progress, 65 pending in frontier; restart pipeline; assert only 70 URLs are fetched and 5 in_progress are retried
- [ ] T055 [P] [US3] `tests/unit/test_frontier_state_machine.py`: verify allowed transitions (pending → in_progress → done | failed; pending → skipped)

### Implementation

- [ ] T056 [P] [US3] `src/star_crawl/core/frontier.py`: SQLite-backed queue with `enqueue(url)`, `claim()` (state pending → in_progress), `mark_done(url)`, `mark_failed(url, error)`, `pending_count(run_id)`
- [ ] T057 [US3] Update `src/star_crawl/core/pipeline.py`: on start, look for unfinished `crawl_runs` for this source; if found, attach to that run instead of creating a new one
- [ ] T058 [US3] Add SIGINT/SIGTERM handler: mark in-progress URLs back to `pending` on graceful shutdown so they're not stuck
- [ ] T059 [US3] Update `src/star_crawl/cli.py`: print "resuming run #N (M pending)" message when picking up an unfinished run

**Checkpoint**: US3 fully functional. Crawls are restartable.

---

## Phase 6: User Story 4 — Paywalled source under explicit opt-in (P3)

**Goal**: Robots-blocked sources are skipped by default; explicit opt-in (config flag + CLI flag) is required to enable.

**Independent Test**: A source whose robots.txt blocks `star_crawl/0.1` is silently skipped on `run`; with `policy.policy_opt_in=true` + `--allow-policy-blocked`, it runs.

### Tests

- [ ] T060 [P] [US4] `tests/integration/test_policy_skip.py`: source with policy-blocked URL → run produces zero rows + clear stderr notice
- [ ] T061 [P] [US4] `tests/integration/test_policy_opt_in.py`: `policy_opt_in=true` + `--allow-policy-blocked` → run proceeds; warning emitted

### Implementation

- [ ] T062 [P] [US4] Update `src/star_crawl/core/policy.py`: add `gate(source_config, cli_flag) -> bool` enforcing both gates required
- [ ] T063 [US4] Update `src/star_crawl/core/pipeline.py`: call policy gate before discovery; on block, write zero-article run with status `skipped`
- [ ] T064 [US4] Update `src/star_crawl/cli.py`: add `--allow-policy-blocked` flag; emit visible warning when activated
- [ ] T065 [P] [US4] Document opt-in workflow in `configs/sources/README.md` with example

**Checkpoint**: US4 fully functional. Default-safe; explicit opt-in works.

---

## Phase 7: Browser fetcher (cross-cutting — needed once any source declares `fetcher: browser`)

- [ ] T066 [P] `src/star_crawl/fetchers/browser.py`: lazy-import playwright; chromium with stealth defaults; handles `wait_until` strategies; reuses single browser per run with new context per fetch
- [ ] T067 [P] `tests/integration/test_browser_fetcher.py` (marked `@pytest.mark.skip_if_no_playwright`): launch chromium against fixture page that requires JS; assert content extracted
- [ ] T068 [P] Create `configs/sources/gojek_engineering.yaml` (browser fetcher per the contract example)
- [ ] T069 Update `src/star_crawl/core/pipeline.py`: dispatch fetcher based on `source.fetcher`; lazy-init browser only when needed

---

## Phase 8: Polish & Cross-Cutting

- [ ] T070 [P] `src/star_crawl/cli.py`: implement `refresh <source> [--since DATE]` per `contracts/cli.md`
- [ ] T071 [P] `src/star_crawl/cli.py`: implement `stats` (totals + per-source counts) and `stats --json`
- [ ] T072 [P] `src/star_crawl/cli.py`: implement `db inspect run-history` and `db inspect errors`
- [ ] T073 [P] `src/star_crawl/cli.py`: implement `export jsonl` and `export parquet` (require `pyarrow` extra)
- [ ] T074 Implement structured logging via `--log-format json` flag; write to stderr
- [ ] T075 [P] Add CLI exit codes per `contracts/cli.md` (0 success, 1 partial, 2 failed, 3 config error)
- [ ] T076 [P] Detect "zero discovery" → emit warning, exit code 2
- [ ] T077 [P] Detect quality regression: if median word_count for run < 50% of source's historical median → warn
- [ ] T078 [P] `tests/integration/test_cli_smoke.py`: end-to-end against all 3+ source fixtures; assert summary table + exit codes
- [ ] T079 [P] Add `--limit N` CLI flag; pipeline stops after N new articles per source
- [ ] T080 [P] `tests/unit/test_rate_limit.py`: assert per-domain semaphore prevents bursts; token-bucket throttles to configured rps
- [ ] T081 [P] Coverage check: `pytest --cov=star_crawl --cov-fail-under=80` in CI script
- [ ] T082 Update `README.md` and `quickstart.md` with verified commands; remove anything that doesn't work end-to-end

---

## Dependencies graph

```
Setup (T001-T007)
       │
Foundational (T008-T018) — schemas, DB, loader, policy, CLI skeleton
       │
       ├──► US1 P1 MVP (T019-T042)  ◄── ship first
       │       │
       │       └──► US2 P2 (T043-T053) — pagination + sitemap + multi-source
       │       │
       │       └──► US3 P2 (T054-T059) — resume
       │       │
       │       └──► US4 P3 (T060-T065) — opt-in
       │
       ├──► Browser (T066-T069) — only when a source needs JS
       │
       └──► Polish (T070-T082) — after MVP
```

**Story independence**: US2, US3, US4 each depend on US1 (need a working pipeline) but **not on each other** — can be built in parallel by 3 contributors after Foundational + US1 done.

---

## Parallel execution examples

### After Foundational checkpoint, kick off US1 in parallel

```bash
# Terminal A — fixtures + tests
T019 + T020 + T021 + T022 + T023 + T024  # all [P], different files

# Terminal B — protocols + extractors
T026 + T030 + T031 + T032 + T033          # all [P], different files

# Terminal C — filters + sinks
T034 + T035 + T036 + T037 + T038          # all [P], different files

# Then merge into pipeline (T039) — sequential after the three groups
```

### After US1 ships, US2 + US3 + US4 in parallel

```bash
# Branch A: US2 (pagination/sitemap)
T046 + T047 + T051 + T052 + T053

# Branch B: US3 (resume)
T056 + T058

# Branch C: US4 (policy)
T062 + T065
```

---

## Implementation strategy

1. **Phase 1+2 first** (Setup + Foundational) — ~1 day. Without this, nothing else can start.
2. **Ship US1 alone as MVP** — ~2 days. End state: `star-crawl run grab_engineering` works against real Grab. Stop here, validate, then iterate.
3. **Add US2 next** — ~1 day. Once US2 lands, the project becomes "universal" — any new RSS/sitemap/pagination source is a YAML.
4. **Add US3 + US4** — ~1.5 days. These are quality-of-life and policy correctness; ship together.
5. **Browser fetcher (Phase 7)** — only when you need Gojek or another JS-rendered source. ~1 day.
6. **Polish (Phase 8)** — ongoing.

**Total**: ~6.5 days for everything. MVP (US1) in ~3 days from a clean repo.

---

## Format validation

All 82 tasks follow `- [ ] TXXX [P?] [USx?] Description with file path`. Setup/Foundational/Polish phases have no `[USx]` label. User-story phases all carry `[USx]`. Every implementation task names a concrete file path.
