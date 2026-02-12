# Watchlists ⟷ Subscriptions Migration Runbook

Audience: Backend + Ops
Status: Draft (v0.2.x codebase)
Updated: 2026-02-12

Related
- Primary PRD: `Docs/Product/Watchlist_PRD.md`
- Bridge PRD: `Docs/Product/Watchlists_Subscriptions_Bridge_PRD.md`
- Filter schema: `Docs/Product/Watchlists_Filters.md`
- API implementation: `tldw_Server_API/app/api/v1/endpoints/watchlists.py`

---

## 1) Scope & Context

This runbook guides migration from legacy “SUBS” (Subscriptions) planning/assets to the current Watchlists module. It covers source import (RSS incl. YouTube-as-RSS), job creation, initial runs, optional outputs, and migration of Import Rules to job-level filters.

Key decisions (from Bridge PRD):
- Model YouTube channels/playlists as RSS feeds (`source_type=rss`).
- Carry SUBS Import Rules forward as job-level filters.
- Keep OPML import/export in scope for Watchlists sources.

Note: The current API supports sources, groups/tags, jobs, runs, items, outputs, templates, OPML import/export, and explicit job-filters endpoints.

## 2) Preconditions

- Version: tldw_server v0.2.x with Watchlists endpoints enabled.
- AuthNZ: single-user API key or multi-user JWT configured.
- Backups: snapshot per-user DBs (`<USER_DB_BASE_DIR>/<user_id>/Media_DB_v2.db`) and app state. `USER_DB_BASE_DIR` is defined in `tldw_Server_API.app.core.config` (defaults to `Databases/user_databases/` under the project root); override via environment variable or `Config_Files/config.txt` as needed.
- Test env: perform migration in staging before production.
- Dependencies: ffmpeg installed; outbound HTTP allowed for feeds/sites.

## 3) Inventory SUBS Sources

Gather source URLs (RSS feeds; YouTube as RSS if possible) and any grouping/tags. If you have OPML already, you can import it directly in Step 5B; otherwise prepare a JSON mapping for bulk import.

Example minimal CSV (for your reference):
```
name,url,tags
AI Research,https://example.com/feed.xml,"ai;research"
Tech News,https://news.example.com/rss,"tech;daily"
```

## 4) Prepare Import Payloads

JSON for bulk sources (usable now):
```
{
  "sources": [
    {"name": "AI Research", "url": "https://example.com/feed.xml", "source_type": "rss", "active": true, "tags": ["ai", "research"]},
    {"name": "Tech News",  "url": "https://news.example.com/rss",  "source_type": "rss", "active": true, "tags": ["tech", "daily"]}
  ]
}
```

OPML (usable now):
```
<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <body>
    <outline text="AI Research" title="AI Research" type="rss" xmlUrl="https://example.com/feed.xml" htmlUrl="https://example.com"/>
    <outline text="Tech News" title="Tech News" type="rss" xmlUrl="https://news.example.com/rss" htmlUrl="https://news.example.com"/>
  </body>

</opml>
```

## 5) Migration Steps

All examples assume single-user mode using `X-API-KEY`. Adjust `Authorization: Bearer` for JWT.

### 5A. Import sources (Bulk JSON) - Available Now

Endpoint: `POST /api/v1/watchlists/sources/bulk` (see `tldw_Server_API/app/api/v1/endpoints/watchlists.py:647`)

Request shape:
```
{
  "sources": [
    {"name":"Site A","url":"https://a.example.com/","source_type":"site","tags":["alpha"]},
    {"name":"RSS B","url":"https://b.example.com/feed","source_type":"rss","tags":["beta"]}
  ]
}
```

Response shape (per-entry status):
```
{
  "items": [
    {"name":"Site A","url":"https://a.example.com/","id":101,"status":"created","source_type":"site"},
    {"name":"RSS B","url":"https://b.example.com/feed","id":102,"status":"created","source_type":"rss"}
  ],
  "total": 2,
  "created": 2,
  "errors": 0
}
```

Notes:
- Invalid entries return `status:"error"` with `error` message; valid entries are created.
- YouTube-as-RSS: When `source_type="rss"`, non-feed YouTube URLs (e.g., `watch`, `shorts`, `@handle`) are rejected with
  `invalid_youtube_rss_url`. Accepted forms are canonical feeds, e.g. `https://www.youtube.com/feeds/videos.xml?channel_id=...`.
 - Tags: Each tag must be a non-empty, non-whitespace string. Invalid tags cause per-entry errors with `invalid_tag_names`.

Example:
```
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  --data @sources_bulk.json \
  http://127.0.0.1:8000/api/v1/watchlists/sources/bulk
```

Verify:
```
curl -sS -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  "http://127.0.0.1:8000/api/v1/watchlists/sources?q=ai"
```

Assign/replace tags on a source (PATCH):
```
curl -sS -X PATCH \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{"tags":["ai","research"]}' \
  http://127.0.0.1:8000/api/v1/watchlists/sources/123
```

### 5B. Import sources (OPML) - Available Now

Endpoints: `POST /api/v1/watchlists/sources/import`, `GET /api/v1/watchlists/sources/export`

```
curl -sS -X POST \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -F file=@sources.opml \
  -F active=true \
  -F tags='["ai","research"]' \
  http://127.0.0.1:8000/api/v1/watchlists/sources/import
```

### 5C. Create a Job (scope by tags or sources)

Endpoint: `POST /api/v1/watchlists/jobs` (`tldw_Server_API/app/api/v1/endpoints/watchlists.py:624`)

```
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{
    "name": "Daily AI Digest",
    "scope": {"tags":["ai","research"]},
    "schedule_expr": "0 8 * * *",
    "timezone": "UTC+8",
    "active": true,
    "max_concurrency": 4,
    "per_host_delay_ms": 750
  }' \
  http://127.0.0.1:8000/api/v1/watchlists/jobs
```

### 5D. Migrate Import Rules → Job Filters (Available Now)

Decision: carry forward as job-level filters using the job filters endpoints:
- `PATCH /api/v1/watchlists/jobs/{job_id}/filters` (replace entire filter set)
- `POST /api/v1/watchlists/jobs/{job_id}/filters:add` (append filters)

Example filter payload:
```
{
  "filters": [
    {"type":"keyword","value":{"keywords":["ai","ml"],"match":"any"},"action":"include","priority":100,"is_active":true},
    {"type":"date_range","value":{"max_age_days":30},"action":"include","priority":90,"is_active":true},
    {"type":"regex","value":{"field":"title","pattern":"(?i)breaking"},"action":"exclude","priority":110,"is_active":true}
  ]
}
```

Replace job filters:
```
curl -sS -X PATCH \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d @job_filters.json \
  http://127.0.0.1:8000/api/v1/watchlists/jobs/1/filters
```

Append filters:
```
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d @job_filters_delta.json \
  http://127.0.0.1:8000/api/v1/watchlists/jobs/1/filters:add
```

### 5E. Trigger First Run and Verify Items

Trigger run: `POST /api/v1/watchlists/jobs/{job_id}/run` (`watchlists.py:920`)
```
curl -sS -X POST -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  http://127.0.0.1:8000/api/v1/watchlists/jobs/1/run
```

List items: `GET /api/v1/watchlists/items` (`watchlists.py:1040`)
```
curl -sS -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  "http://127.0.0.1:8000/api/v1/watchlists/items?job_id=1&status=new"
```

### 5F. Outputs (Optional)

Create output: `POST /api/v1/watchlists/outputs` (`watchlists.py:1106`)
```
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{
    "run_id": 10,
    "title": "Daily AI Digest",
    "template_name": "briefing_md",
    "temporary": false,
    "deliveries": {"email": {"enabled": true, "recipients": ["me@example.com"], "attach_file": true}}
  }' \
  http://127.0.0.1:8000/api/v1/watchlists/outputs
```

Create output + enqueue audio briefing workflow:
```
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{
    "run_id": 10,
    "title": "Daily AI Digest Audio",
    "generate_audio": true,
    "target_audio_minutes": 8,
    "audio_model": "kokoro",
    "audio_voice": "af_heart",
    "audio_speed": 1.0
  }' \
  http://127.0.0.1:8000/api/v1/watchlists/outputs
```

Check run-level audio status/download metadata:
```
curl -sS -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  http://127.0.0.1:8000/api/v1/watchlists/runs/10/audio
```

Download: `GET /api/v1/watchlists/outputs/{id}/download` (`watchlists.py:1375`)

Templates: list/create under `/api/v1/watchlists/templates` (`watchlists.py:1403`, `watchlists.py:1440`).

## 6) Verification Checklist

- Sources imported and visible with correct tags/groups.
- Job created with expected scope; `next_run_at` computed; schedule registered.
- First run completes without errors; items present and dedupe is effective.
- Outputs generate and TTL semantics reflect `/watchlists/settings` values.

### UI Verification (Admin)

- Runs view: navigate to `/admin/watchlists-runs`.
  - Browse runs (Global or By Job), confirm counters (found/ingested and filters include/exclude/flag) and pagination.
  - Optionally enable “Include tallies” and set a filtered sample size to view per-run tallies and a small sample of filtered items.
  - For large result sets, prefer the “Server CSV” export links over client-side CSV.
  - Server CSV links include pagination parity header `X-Has-More` and honor the "Include tallies" toggle via `include_tallies=true`.

- Items view: from the Runs table, click “View items” or open `/admin/watchlists-items?run_id=<id>`.
  - Verify items list for the run, status filter (ingested/filtered/flagged), and pagination work as expected.

Tip: These views are intended for admin triage only and reflect the same data returned by the API endpoints under `/api/v1/watchlists/*`.
- Delivery (email/Chatbook) succeeds in integration/staging.

### CI Focused Suites (rate-limiter on)

- Ensure RG ingress is active (`RG_ENABLED=1`) and tests are not in TEST_MODE.
- Run focused Watchlists tests that assert headers and pagination metadata:
  - `python -m pytest -q tldw_Server_API/tests/Watchlists/test_rate_limit_headers_real.py`
  - `python -m pytest -q tldw_Server_API/tests/Watchlists/test_runs_csv_export.py tldw_Server_API/tests/Watchlists/test_runs_csv_has_more_header.py`
  - `python -m pytest -q tldw_Server_API/tests/Watchlists/test_youtube_normalization_more.py`
  - Perf (optional): `python -m pytest -q -m "perf or performance" tldw_Server_API/tests/Watchlists/test_opml_export_perf_more.py`

Known unrelated: `tests/sandbox/test_ws_heartbeat_seq.py` can hang in some local harnesses on teardown; track separately.

## 7) Rollback Plan

- Stop scheduled jobs (PATCH job `active=false`).
- Delete created sources/jobs if reverting (`DELETE /watchlists/sources/{id}`, `/watchlists/jobs/{id}`).
- Restore DB backups of affected user(s): `<USER_DB_BASE_DIR>/<user_id>/Media_DB_v2.db`.
- Re-run sanity checks.

## 8) Scripts (Current + Optional Additions)

Current helper scripts:

1) `Helper_Scripts/watchlists/watchlists_audio_smoke.py`
   - Purpose: end-to-end smoke flow (create source/job/run/output, enqueue audio, poll `/runs/{run_id}/audio`).
   - Typical usage:
   ```
   make watchlists-audio-smoke WATCHLISTS_API_KEY="$SINGLE_USER_API_KEY"
   ```

Optional additions (future ergonomics):

1) `opml_import.py` - Import OPML into Watchlists sources.
2) `bulk_sources_load.py` - Bulk import from CSV/JSON.
3) `subs_rules_to_job_filters.py` - Translate SUBS Import Rules to job filters.
4) `seed_job_and_run.py` - Create a job and trigger one run.

## 9) Notes

- YouTube-as-RSS: prefer canonical feed URLs. Where user pastes a channel/playlist URL, a helper may normalize to RSS feed in a future iteration.
- Filters: use `PATCH /jobs/{id}/filters` and `POST /jobs/{id}/filters:add` for operational migrations.
- Robots & politeness: abide by defaults; override with caution per job settings.
- PersonaPod transfer policy: copy high-level operator patterns only; do not transplant PersonaPod internals directly into `tldw_server2` services.

---
Coordinate with WebUI to surface OPML import and filter management UX.
