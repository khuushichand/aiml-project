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
