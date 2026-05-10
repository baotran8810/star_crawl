# Source configurations

Drop a YAML file here with `name` matching the filename (no `.yaml`).
Loader validates against `SourceConfig` (see
`src/star_crawl/core/schemas.py`) and surfaces clear errors.

## Schema

See [`specs/001-crawler-core/contracts/source-config.md`](../../specs/001-crawler-core/contracts/source-config.md)
for the full schema.

## Examples in this directory

| File | Strategy | Fetcher | Notes |
|---|---|---|---|
| `grab_engineering.yaml` | rss | http | First-party feed, easiest target |
| `uber_engineering.yaml` | pagination | http | Walks `/page/N/` 1..63 |
| `cloudflare_blog.yaml` | rss | http | First-party feed |
| `netflix_techblog.yaml` | rss | http | Medium custom-domain feed (RSS is full-content) |

## Running a robots-blocked source

Some sources disallow our user-agent in their `robots.txt`. By default the
crawler skips them silently. To opt in:

1. Set `policy.policy_opt_in: true` in that source's YAML.
2. Run with `star-crawl run <name> --allow-policy-blocked`.

Both gates are required. Either alone is rejected. We do this so a single
careless config edit can't get your IP banned.
