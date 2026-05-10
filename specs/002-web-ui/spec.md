# Feature Specification: Web UI

**Feature Branch**: `002-web-ui`
**Created**: 2026-05-10
**Status**: Draft
**Input**: User description: "Read-only web interface for browsing the crawled corpus: dashboard with totals, list of sources, articles per source, article reader, full-text search, crawl history with live progress."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse the corpus visually (Priority: P1)

A user has a populated corpus and wants to read articles without using the command line. They open the local web interface in their browser, see an overview of how much content they have and where it came from, drill into a source, pick an article, and read it in a clean reader view with metadata visible alongside.

**Why this priority**: The reason to crawl is to read and reference. A visual reader is the most direct value the corpus can deliver.

**Independent Test**: With an existing corpus, open the web interface, click into a source, click into an article, and confirm the article renders cleanly with title, author, date, and source link visible.

**Acceptance Scenarios**:

1. **Given** the corpus contains articles from at least one source, **When** the user opens the home page, **Then** they see total article count, list of sources with per-source counts, and the timestamp of the most recent crawl.
2. **Given** a source has at least one article, **When** the user opens that source's page, **Then** they see a paginated, sortable list of articles with title, author, publish date, language, and word count.
3. **Given** an article is selected, **When** the user opens its detail page, **Then** they see the full article content rendered as readable formatted text, with a sidebar showing source URL, source name, publish date, crawl date, language, and content fingerprint.

---

### User Story 2 - Find articles by keyword (Priority: P1)

A user remembers reading something about a specific concept (e.g., "event-driven architecture") but doesn't remember which source or when. They type the phrase into the search box; the system returns matching articles within a fraction of a second, highlighting where the phrase appears in each match. They click a result and land directly on the article.

**Why this priority**: A growing corpus is unusable without search. Once content is more than a few dozen articles, browsing by source is too slow to find a specific idea.

**Independent Test**: With a corpus of at least 100 articles, type a known phrase that appears in at least 3 articles. Confirm at least those 3 results appear, ranked by relevance, with the matching phrase highlighted in a snippet.

**Acceptance Scenarios**:

1. **Given** the corpus is non-empty, **When** the user submits a search query, **Then** they see matching articles ordered by relevance with a snippet showing the query terms highlighted in context.
2. **Given** the search box is focused and the user is typing, **When** they pause briefly between keystrokes, **Then** the result list updates to reflect the current query without a full page reload.
3. **Given** search results are displayed, **When** the user filters by source, **Then** only matches from that source remain visible.
4. **Given** a query that matches nothing, **When** the user submits, **Then** they see a clear "no results" state with the query echoed back, not a blank page.

---

### User Story 3 - Watch a crawl run in progress (Priority: P2)

A user kicks off a long crawl from the command line and wants to monitor progress without watching the terminal. They open the runs page in the web interface and see the in-progress run with a live counter that updates while the crawl is running, plus the history of completed runs.

**Why this priority**: Observability without context-switching makes long crawls less stressful. Not strictly required for first usable release, but high-value once corpus building becomes routine.

**Independent Test**: Start a crawl from the command line, open the runs page, and confirm the in-progress run is visible with a counter that increases over time. Wait for the run to finish, refresh the page, and confirm it shows as complete with final counts.

**Acceptance Scenarios**:

1. **Given** a crawl run has started but not finished, **When** the user opens the runs page, **Then** they see the running entry highlighted, with discovered / extracted / error counts that update on a short interval without manual refresh.
2. **Given** a run has completed, **When** the user opens the runs page, **Then** the run is listed with status (success / partial / failed), duration, source, and counts.
3. **Given** a run is selected, **When** the user opens its detail page, **Then** they see the per-URL error log and the list of articles added by that run.

---

### User Story 4 - Use the interface safely on a personal machine (Priority: P2)

A user runs the interface on their laptop. By default, it is not reachable from the network — only the user can open it. If the user explicitly chooses to expose it (e.g., on a home server), they are prompted to set a credential before that becomes possible.

**Why this priority**: The corpus may include content under various policies; accidental exposure is a real risk on a casual install. Default-safe behavior matters.

**Independent Test**: Start the interface with default settings, confirm another device on the same network cannot reach it. Reconfigure to expose it without setting a credential, confirm the system either refuses or warns prominently.

**Acceptance Scenarios**:

1. **Given** the interface is started with default settings, **When** another machine on the network attempts to load it, **Then** the connection is refused.
2. **Given** the user starts the interface in exposed mode without configuring a credential, **When** the start-up sequence runs, **Then** the user is informed and required to either set a credential or revert to local-only mode.

---

### Edge Cases

- **Article content is extremely long** (e.g., 30,000+ words): the reader view loads quickly and remains scrollable without freezing the interface.
- **Search query has special characters or operators**: the system either treats them as plain text or applies them as documented; it never returns an error to the user.
- **A corpus has zero articles** (fresh install): the interface displays a clear empty state explaining how to populate the corpus instead of an error.
- **A run was killed without proper shutdown** (process crashed): the runs page does not show it as "running forever" — the state is recoverable.
- **A user opens the same article on two devices** (rare, but possible on shared install): both display the same content; this is a read-only interface, no editing conflict can occur.
- **An article was crawled in a non-English language**: the reader view still renders correctly with appropriate character encoding and the language tag visible.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST present a home view summarizing total articles, number of sources, count of articles per source, and the time of the most recent crawl run.
- **FR-002**: System MUST present a list of all configured sources with per-source counts and the timestamp of each source's last successful crawl.
- **FR-003**: System MUST present a paginated list of articles for a given source, displaying at least title, author, publish date, language, and word count per row.
- **FR-004**: System MUST allow users to filter the article list of a given source by date range, by language, and by category if categories exist for that source.
- **FR-005**: System MUST allow users to sort the article list by publish date or by title, ascending or descending.
- **FR-006**: System MUST present a detail view for any article that renders the extracted content in a readable, formatted layout.
- **FR-007**: System MUST present a metadata panel alongside each article showing source URL, source name, publish date, crawl date, language, and content fingerprint.
- **FR-008**: System MUST provide full-text search across article title and body across all sources, returning ranked results in well under one second for a corpus of at least 10,000 articles.
- **FR-009**: System MUST highlight matched query terms within snippets of the content for each search result.
- **FR-010**: System MUST update search results as the user types, without requiring a full page reload, after a short debounce.
- **FR-011**: System MUST allow the user to filter search results by source.
- **FR-012**: System MUST display the history of crawl runs, including in-progress runs that update visibly without manual refresh.
- **FR-013**: System MUST display per-run detail including status, duration, counts, per-URL error log, and the list of articles added by that run.
- **FR-014**: System MUST be read-only with respect to corpus content; the interface MUST NOT trigger crawls or edit articles.
- **FR-015**: System MUST refuse external network connections by default; exposing the interface beyond the local machine MUST require an explicit configuration step.
- **FR-016**: System MUST require a user-configured credential whenever the interface is exposed beyond the local machine.
- **FR-017**: System MUST display a clear empty state when the corpus has no articles, instead of an error or a blank page.
- **FR-018**: System MUST tolerate articles in any UTF-8 language and render them without character-set artifacts.
- **FR-019**: System MUST surface a clear, non-leaky error page when an article ID does not exist; internal stack traces MUST NOT be shown.
- **FR-020**: System MUST be navigable on a phone screen at minimum for reading articles; full feature parity on mobile is not required.

### Key Entities

- **View**: Each top-level page the user navigates to (home, sources, source detail, article detail, search results, runs, run detail).
- **Search Query**: The user-entered text plus optional filters (source) that produces a ranked result list with snippets.
- **Crawl Run Snapshot**: The state of a single run as displayed in the interface — its current counts, status, and recent activity, refreshed periodically while in progress.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can find an article by remembered phrase in under 30 seconds across a corpus of 1,000+ articles.
- **SC-002**: A search query returns ranked results in under 500 milliseconds at the 95th percentile for a corpus of up to 10,000 articles.
- **SC-003**: Article detail pages render in under one second from click to readable content for at least 95% of articles.
- **SC-004**: A user reading a long article (10,000+ words) experiences no perceptible scroll lag.
- **SC-005**: When a crawl run is in progress, the runs page reflects current counts within at most a few seconds of actual state, without manual refresh.
- **SC-006**: With default settings on a personal machine, the interface is unreachable from another device on the same network 100% of the time.
- **SC-007**: A user encountering an empty corpus or a missing article ID sees an actionable message rather than a blank or error page.

## Assumptions

- The interface runs on the same machine as the corpus database, accessing it directly; remote-database access is out of scope.
- Crawls are started from the command line; in-browser crawl triggering is intentionally excluded to keep the interface read-only.
- The user has a modern browser; legacy browser support is not required.
- The corpus is small enough that paginated lists with sensible page sizes are sufficient; infinite scroll is not required.
- Markdown rendering of article content uses safe-by-default rules; arbitrary HTML from articles is sanitized before display.
- Authentication, when required, is single-user; team-style access control is out of scope.
- The interface is a complement to the command-line crawler, not a replacement; both are expected to coexist.
