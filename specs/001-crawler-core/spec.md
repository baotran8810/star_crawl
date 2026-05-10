# Feature Specification: Crawler Core

**Feature Branch**: `001-crawler-core`
**Created**: 2026-05-10
**Status**: Draft
**Input**: User description: "Multi-source web crawler that fetches articles from configurable sources (Uber, Grab, Gojek, Medium, first-party tech blogs), extracts clean main content + metadata, deduplicates, and stores in a single-file database for downstream browsing, search, and analysis."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pull a tech blog into local store (Priority: P1)

A user wants to build a personal corpus of high-quality engineering articles. They run one command pointing at a known engineering blog. The system discovers article URLs from that source, fetches each article politely (respecting rate limits), extracts the main content while removing navigation, ads, and other boilerplate, captures metadata (title, author, publish date, language), and persists everything in a local store the user can read or query later.

**Why this priority**: Without this, nothing else exists. This is the minimum viable product — a single-source pipeline end-to-end.

**Independent Test**: Run the crawler against a single blog (e.g., Grab Engineering), then query the store and confirm at least 50 articles are present, each with non-empty title, content, and source attribution. Spot-check 5 articles to confirm boilerplate has been stripped and metadata is correct.

**Acceptance Scenarios**:

1. **Given** an empty store and a configured source pointing to a blog index, **When** the user runs the crawl command, **Then** the system fetches every discoverable article on that source, stores extracted content with metadata, and reports a per-source summary (articles new / updated / errors).
2. **Given** the same source has been crawled before, **When** the user runs the crawl again, **Then** previously seen articles are skipped (no duplicate rows), and only newly published articles are added.
3. **Given** an article URL returns a temporary error (5xx, timeout), **When** the crawler encounters it, **Then** the request is retried with exponential backoff up to a configured limit, and the final outcome is recorded; one failure does not abort the run.

---

### User Story 2 - Add a new source without writing code (Priority: P2)

A user discovers a new tech blog they want included. They add one configuration file describing how to discover and identify articles on that site, and the next run pulls articles from the new source automatically.

**Why this priority**: This is what makes the crawler "universal" rather than hardcoded. Without it, every new source requires a code change.

**Independent Test**: Drop a new source config file into the configs directory, run the crawler with no other changes, and confirm articles from that source appear in the store with correct attribution.

**Acceptance Scenarios**:

1. **Given** a config file defining a new source with a discovery strategy (sitemap, paginated index, or RSS feed) and URL filter pattern, **When** the user runs the crawler, **Then** the system loads the config, discovers article URLs that match the filter, and processes them with the same pipeline as built-in sources.
2. **Given** a config that selects the wrong fetcher (e.g., simple HTTP for a JavaScript-rendered site), **When** the run produces empty content for most articles, **Then** the system reports a clear quality warning and does not silently fill the store with empty articles.

---

### User Story 3 - Resume a run that was interrupted (Priority: P2)

A user runs a long crawl, then closes their laptop. When they run the same command later, the crawler picks up where it left off rather than starting over or duplicating work.

**Why this priority**: A full corpus crawl can take hours. Restartability is essential for usability and for sources that occasionally rate-limit.

**Independent Test**: Start a crawl on a large source, kill the process mid-run, restart it, and confirm the second run only processes URLs not already completed in the first.

**Acceptance Scenarios**:

1. **Given** a crawl that was interrupted before completion, **When** the user runs the same crawl command again, **Then** the system resumes from the persisted queue state without reprocessing URLs already completed.
2. **Given** a URL was attempted and failed with a permanent error (4xx other than 429), **When** the user resumes, **Then** the URL is not retried automatically, but is visible in run history for manual review.

---

### User Story 4 - Crawl a paywalled source under explicit opt-in (Priority: P3)

An advanced user wants to include a source that has a paywall and explicit anti-AI directives in its policy file. They opt-in via a clearly named flag and accept the risks; the crawler proceeds via a dedicated adapter. Without the flag, the source is never crawled.

**Why this priority**: Necessary for some users, but must be off by default for legal and ethical reasons. Default-safe behavior is more important than coverage.

**Independent Test**: Run the standard crawl command with the paywalled source listed; confirm no articles from that source enter the store. Run again with the explicit opt-in flag; confirm articles do enter the store and a clear warning was emitted.

**Acceptance Scenarios**:

1. **Given** a paywalled source is listed in the corpus configuration but the opt-in flag is absent, **When** the user runs a crawl, **Then** the source is skipped entirely with a one-line notice explaining how to enable it.
2. **Given** the opt-in flag is set, **When** the run starts, **Then** a visible warning describes the policy implications and the run proceeds.

---

### Edge Cases

- **Source's discovery strategy returns zero URLs**: report this clearly; do not silently mark the run successful with zero articles.
- **An article page redirects to login or paywall preview**: classify as "blocked" rather than "extracted with empty content"; do not store empty rows.
- **Duplicate content under different URLs** (canonical vs. tracking-param URL, or republished cross-site): detect via content hash and store only one row, with both URLs recorded.
- **A site changes its DOM and content extraction quality drops**: report a quality regression metric (e.g., median word count per article dropped > 50%) so the user can investigate before publishing the corpus.
- **A source enforces aggressive rate limiting (429)**: respect the response, back off, and allow the run to either complete more slowly or stop early with a clear status — never get the user's IP banned.
- **An article is republished or edited after it was first crawled**: the user can re-fetch existing articles via an explicit refresh action; default behavior does not re-fetch.
- **Mixed languages within a single source**: detect language per article and store it; do not assume all articles in one source share a language.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept source definitions through configuration files; adding or modifying a source MUST NOT require code changes.
- **FR-002**: System MUST support at least three discovery strategies: paginated index, RSS/Atom feed, and sitemap.
- **FR-003**: System MUST support both server-rendered (HTML returned by initial response) and client-rendered (content requires a real browser) sources, and select the appropriate fetch strategy per source configuration.
- **FR-004**: System MUST honor each source's robots policy by default; a source MUST be skipped automatically when the policy disallows crawling for the configured user agent unless the user explicitly opts in for that source.
- **FR-005**: System MUST apply per-source rate limiting and retry-with-backoff so that a single run never overwhelms a target site or causes the user's IP to be banned under normal operation.
- **FR-006**: System MUST extract a clean main content body, free of site navigation, ads, social-share widgets, related-article blocks, and footer boilerplate.
- **FR-007**: System MUST extract metadata for each article — at minimum: source, original URL, title, author when available, publish date when available, language, word count, and the time the article was crawled.
- **FR-008**: System MUST detect and skip duplicates within a single crawl run and across runs, using a content fingerprint independent of URL.
- **FR-009**: System MUST persist crawl progress so an interrupted run can be resumed; the user MUST NOT have to manually pick up where they left off.
- **FR-010**: System MUST record every crawl run with start time, end time, source, status (success / partial / failed), counts (discovered, new, updated, errors), and a list of per-URL errors with cause.
- **FR-011**: System MUST allow per-source filtering of articles by URL pattern so unrelated pages on the same domain (e.g., careers, terms) are not included.
- **FR-012**: System MUST tolerate single-article failures without aborting the rest of the run.
- **FR-013**: System MUST emit a per-run summary readable in a terminal that shows what was added, what was skipped, and what failed.
- **FR-014**: System MUST classify a fetched page that contains a paywall, login wall, or empty body as "blocked" rather than storing an empty article.
- **FR-015**: System MUST gate any source whose published policy disallows the crawler behind an explicit user opt-in flag, with a visible warning when activated.
- **FR-016**: System MUST detect when a source's discovery yields zero URLs and surface this as a warning rather than silent success.
- **FR-017**: System MUST allow on-demand re-fetch of one or more existing articles when explicitly requested; default repeat runs MUST NOT re-fetch articles already present.

### Key Entities

- **Source**: A named, configured origin of articles. Carries discovery strategy, fetch strategy, URL filter, rate limits, and policy flags.
- **Article**: A single piece of long-form content extracted from one URL on one source. Carries source, URL, title, author, publish date, language, word count, content (clean text and structured form), content fingerprint, and crawl timestamp.
- **Crawl Run**: One execution of the crawler against one or more sources at a point in time. Carries timing, status, counts, and a list of per-URL errors.
- **Frontier Entry**: A queued URL waiting to be processed within a run, with attempt count and last error so resumption is deterministic.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from empty store to a corpus of at least 1,000 articles spanning 5+ sources in a single afternoon of unattended runs.
- **SC-002**: At least 95% of articles extracted from any first-party blog source contain a non-empty title, content body, and language tag.
- **SC-003**: Re-running a crawl that previously completed adds zero duplicate articles to the store.
- **SC-004**: An interrupted crawl, when resumed, processes only URLs not already completed in the prior attempt — no observable rework.
- **SC-005**: Adding a new source by configuration alone (no code change) takes a user under 15 minutes for a typical RSS-backed blog.
- **SC-006**: A source whose policy disallows the crawler is never crawled by default; activating it requires an explicit opt-in step the user cannot trigger by accident.
- **SC-007**: A run that hits sustained rate limiting (HTTP 429) on a source slows down or terminates cleanly without the user's IP being blocked.

## Assumptions

- The user runs the crawler on a personal machine or a single server; horizontal scaling across nodes is out of scope for this feature.
- The corpus is for personal research, learning, and (optionally) downstream analysis; redistribution is not part of this spec and is the user's responsibility.
- Network access is available and reasonably stable; transient network errors are expected and handled, but extended offline operation is out of scope.
- Sources publish reasonable amounts of content per month (single-digit hundreds); the system is not optimized for streaming web-scale crawling.
- English is the dominant language across configured sources; detection and storage of language is required, but advanced multilingual normalization is not.
- A single-file local database is sufficient for the corpus size; migrating to a server database is out of scope here but should remain possible later.
- The user is comfortable running command-line tools; a graphical interface is the responsibility of a separate feature.
