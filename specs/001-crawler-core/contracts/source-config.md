# Contract: Source Config (YAML)

**Owner**: Crawler Core
**Version**: 0.1.0
**Validated by**: `SourceConfig` Pydantic model in `src/star_crawl/core/schemas.py`.

## Schema

```yaml
# configs/sources/<name>.yaml

name: <string>                       # REQUIRED — must match filename
display_name: <string>               # REQUIRED — for UI/CLI output
base_url: <url>                      # REQUIRED — e.g., https://engineering.grab.com

fetcher: http | browser              # REQUIRED — http unless site needs JS

seed:
  strategy: pagination | rss | sitemap   # REQUIRED
  # one of the following blocks REQUIRED:
  template: <url>                    # for pagination, with {n} placeholder
  range: [<int>, <int>]              # for pagination, inclusive
  url: <url>                         # for rss / sitemap
  follow_index: <bool>               # default true — for sitemap with index files

url_filter: <regex>                  # REQUIRED — anchor-matched against discovered URLs

rate_limit:
  rps: <float>                       # default 1.0
  concurrency: <int>                 # default 5
  per_domain: <bool>                 # default true

retry:
  max_attempts: <int>                # default 3
  backoff_base: <float>              # default 2.0 (seconds)
  backoff_cap: <float>               # default 30.0
  honor_retry_after: <bool>          # default true

extract:
  primary: trafilatura | readability  # default trafilatura
  fallback: trafilatura | readability | none  # default readability
  parse_jsonld: <bool>               # default true
  min_word_count: <int>              # default 100

dedup:
  enabled: <bool>                    # default true
  use_canonical_url: <bool>          # default true

policy:
  respect_robots: <bool>             # default true
  user_agent: <string>               # default "star_crawl/0.1 (+https://github.com/.../star_crawl)"
  policy_opt_in: <bool>              # default false — must be true to crawl robots-blocked sources

browser:                             # only honored when fetcher: browser
  stealth: <bool>                    # default true
  wait_until: load | domcontentloaded | networkidle  # default networkidle
  timeout_ms: <int>                  # default 30000

categories:                          # optional taxonomy hints; non-authoritative
  - <string>
```

## Validation rules

1. `name` must match `^[a-z][a-z0-9_]+$` and be unique across configs.
2. `name` must equal the YAML filename (without `.yaml`).
3. `seed.strategy = pagination` requires `template` containing `{n}` and `range` of length 2.
4. `seed.strategy = rss | sitemap` requires `url` and ignores `template`/`range`.
5. `url_filter` must compile as a Python regex.
6. `rate_limit.rps > 0`, `concurrency >= 1`.
7. If `policy.respect_robots = true` and the configured user-agent is disallowed by the live robots.txt, the loader MUST set the runtime flag `policy_blocked = true`. The CLI MUST refuse to run unless `policy.policy_opt_in = true` AND `--allow-policy-blocked` is passed.
8. `fetcher: browser` requires `playwright` extra installed; loader emits an actionable error if missing.

## Example — Grab (RSS)

```yaml
name: grab_engineering
display_name: Grab Engineering
base_url: https://engineering.grab.com
fetcher: http
seed:
  strategy: rss
  url: https://engineering.grab.com/feed.xml
url_filter: '^https://engineering\.grab\.com/[^/]+$'
rate_limit:
  rps: 2.0
  concurrency: 5
categories: [engineering, data-science]
```

## Example — Uber (pagination)

```yaml
name: uber_engineering
display_name: Uber Engineering
base_url: https://www.uber.com/us/en/blog/engineering/
fetcher: http
seed:
  strategy: pagination
  template: https://www.uber.com/us/en/blog/engineering/page/{n}/
  range: [1, 63]
url_filter: '^https://www\.uber\.com/us/en/blog/[^/]+/$'
rate_limit:
  rps: 1.0
  concurrency: 5
extract:
  parse_jsonld: true
```

## Example — Gojek (browser)

```yaml
name: gojek_engineering
display_name: Gojek
base_url: https://www.gojek.io/blog
fetcher: browser
seed:
  strategy: pagination
  template: https://www.gojek.io/blog?page={n}
  range: [1, 99]
url_filter: '^https://www\.gojek\.io/blog/[^/]+'
rate_limit:
  rps: 0.5
  concurrency: 2
browser:
  stealth: true
  wait_until: networkidle
```

## Forward-compat

- New fields MUST be optional with defaults so old YAMLs keep loading.
- Removing a field requires a deprecation warning for one minor version, then a migration script.
- Renaming a field MUST preserve the old name as an alias for one minor version.
