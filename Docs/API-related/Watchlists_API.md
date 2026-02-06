# Watchlists API Cheat Sheet

Quick reference for recurring scraping (RSS or site lists) with runs, items, and outputs.

Auth:
- Single-user: `X-API-KEY: <key>`
- Multi-user: `Authorization: Bearer <token>`

Base path: `/api/v1/watchlists`

## Core concepts

- Source: a target to scrape (`rss` or `site`; `forum` is feature-flagged).
- Job: schedule + scope + filters that produce runs.
- Run: one execution of a job.
- Item: a scraped candidate (ingested, filtered, duplicate, or error).
- Output: rendered report from run items.
- Template: named output template (md/html).

## Endpoints

Sources:
- `POST /sources`
- `GET /sources`
- `GET /sources/{source_id}`
- `PATCH /sources/{source_id}`
- `DELETE /sources/{source_id}`
- `POST /sources/{source_id}/test` (preview without ingestion)
- `POST /sources/bulk` (bulk create)
- `GET /sources/export` (OPML)
- `POST /sources/import` (OPML)

Tags and groups:
- `GET /tags`
- `POST /groups`
- `GET /groups`
- `PATCH /groups/{group_id}`
- `DELETE /groups/{group_id}`

Jobs and filters:
- `POST /jobs`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `PATCH /jobs/{job_id}`
- `DELETE /jobs/{job_id}`
- `POST /jobs/{job_id}/preview`
- `PATCH /jobs/{job_id}/filters` (replace)
- `POST /jobs/{job_id}/filters:add` (append)

Runs:
- `POST /jobs/{job_id}/run`
- `GET /jobs/{job_id}/runs`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/details`
- `GET /runs/{run_id}/tallies.csv`
- `GET /runs/export.csv`
- `WS /runs/{run_id}/stream`

Items:
- `GET /items`
- `GET /items/{item_id}`
- `PATCH /items/{item_id}` (flagging)

Outputs:
- `POST /outputs`
- `GET /outputs`
- `GET /outputs/{output_id}`
- `GET /outputs/{output_id}/download`

Templates:
- `GET /templates`
- `GET /templates/{template_name}`
- `POST /templates` (create or update)
- `DELETE /templates/{template_name}`

## Minimal payloads

Create a source (RSS):
```json
{
  "name": "Example Feed",
  "url": "https://example.com/feed.xml",
  "source_type": "rss",
  "tags": ["news"]
}
```

Create a source (site + scrape rules):
```json
{
  "name": "Docs Changelog",
  "url": "https://docs.example.com/changelog",
  "source_type": "site",
  "settings": {
    "top_n": 10,
    "discover_method": "auto",
    "scrape_rules": {
      "list_url": "https://docs.example.com/changelog",
      "item_selector": ".entry",
      "title_selector": "h2 a",
      "link_selector": "h2 a",
      "summary_selector": ".summary",
      "date_selector": "time"
    }
  }
}
```

Create a job:
```json
{
  "name": "Docs updates",
  "scope": {"sources": [123]},
  "schedule_expr": "0 */6 * * *",
  "timezone": "UTC",
  "ingest_prefs": {"persist_to_media_db": true}
}
```

Trigger a run:
```json
{}
```

Preview candidates without ingestion:
```json
{}
```

## Filters (job-level)

Payload shape:
```json
{
  "filters": [
    {"type": "keyword", "action": "include", "value": {"keywords": ["llm", "ai"]}},
    {"type": "regex", "action": "exclude", "value": {"pattern": "sponsored"}}
  ],
  "require_include": true
}
```

Filter types: `keyword`, `author`, `date_range`, `regex`, `all`  
Actions: `include`, `exclude`, `flag`

## Include-only quick semantics

`require_include` can come from:
- Job filters payload (`job_filters.require_include`)
- Org/admin default (when the job value is unset)

Decision summary:

| Effective `require_include` | Any active include rule | Include match found | Result |
| --- | --- | --- | --- |
| `false` | no | n/a | Item may ingest unless excluded |
| `false` | yes | no | Item may ingest unless excluded |
| `false` | yes | yes | Item ingests (and can be flagged) |
| `true` | no | n/a | Item is filtered (include-only guard) |
| `true` | yes | no | Item is filtered |
| `true` | yes | yes | Item ingests (unless excluded by higher-priority rule) |

Notes:
- Exclude rules still win when they match.
- Invalid regex filters fail safely (no crash); include-only mode can still filter all items when no include matches.

## OPML import/export examples

Import OPML with optional defaults:
```bash
curl -X POST "$BASE/api/v1/watchlists/sources/import" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@subscriptions.opml" \
  -F "active=true" \
  -F "group_id=12" \
  -F "tags=research" \
  -F "tags=ai"
```

Export all sources as OPML:
```bash
curl "$BASE/api/v1/watchlists/sources/export" \
  -H "Authorization: Bearer $TOKEN" \
  -o watchlists_sources.opml
```

Export with filters (`group` supports repeated params for OR semantics):
```bash
curl "$BASE/api/v1/watchlists/sources/export?type=rss&tag=ai&group=12&group=19" \
  -H "Authorization: Bearer $TOKEN" \
  -o watchlists_rss_ai_groups_12_19.opml
```

Filter semantics for OPML export:
- Repeated `group` values are OR-ed.
- `tag` + `group` are combined with AND semantics.
- Unknown `group` ids return HTTP 200 with an empty OPML source list.

## Ingestion and persistence

- Watchlists always store run stats and scraped items in the Watchlists DB.
- Set `ingest_prefs.persist_to_media_db=true` to persist items into the Media DB.
- Items track status: `ingested`, `filtered`, `duplicate`, or `error`.

## Outputs

Create a report from a run:
```json
{
  "run_id": 456,
  "title": "Docs digest",
  "format": "md",
  "ingest_to_media_db": true
}
```

Outputs can render templates (Markdown or HTML). Set `template_name` to use a named template.

## Scrape rules quick notes

Supported fields include:
- `item_selector` / `entry_selector` (list entries)
- `title_selector` / `title_xpath`
- `link_selector` / `url_selector`
- `summary_selector` / `summary_xpath`
- `content_selector` / `content_xpath`
- `date_selector` / `published_xpath`
- `limit`, `pagination`, `alternates`

Full rules live in `tldw_Server_API/app/core/Watchlists/fetchers.py`.
