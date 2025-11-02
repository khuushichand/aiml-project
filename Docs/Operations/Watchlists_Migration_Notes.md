# Watchlists Migration Notes (Subscriptions → Watchlists)

Status: Informational - Subscriptions never shipped to prod; a dedicated migration CLI is not required for v1. Use OPML import and job filters instead.

## Summary

The legacy "Subscriptions" model maps directly to Watchlists. For teams who experimented with SUBS locally, you can migrate configurations using OPML and job filters:

- Subscription → Source
- ImportRules → Job Filters (job-scoped)
- SubscriptionChecks → Runs (job history)

Key points:
- No separate migration CLI is needed.
- Use OPML import to create sources in bulk.
- Create jobs targeting those sources and translate Import Rules to job-level filters.
- The API and WebUI already support these flows.

## Recommended Flow

1) Export your legacy feeds to OPML (from your previous tool or list). If not available, build a simple OPML file from your URLs.
2) Import via `POST /api/v1/watchlists/sources/import` with optional defaults:
   - `active` (defaults to true)
   - `tags` (tag names applied to each created source)
   - `group_id` (attach to an existing group)
3) Create a job targeting imported sources (scope can include `sources`, `tags`, or `groups`).
4) Add job filters if you had SUBS Import Rules. Use `PATCH /api/v1/watchlists/jobs/{id}/filters`.
5) Optionally test with the preview endpoint before ingestion: `POST /api/v1/watchlists/jobs/{id}/preview`.

## Include-Only Gating (Quick Reference)

- Job flag: `job_filters.require_include = true|false`
- Org default: `organizations.metadata.watchlists.require_include_default = true|false` (or flat `watchlists_require_include_default`)
- Env fallback: `WATCHLISTS_REQUIRE_INCLUDE_DEFAULT=1|true|yes|on`

Behavior:
- Gating applies only when include rules exist on the job.
- Effective policy = job flag if set, else org default if present, else env fallback.
- When active: only include-matched items ingest; others are marked `filtered`.

## OPML Examples

Import nested outlines with defaults (multipart):

```
file = (feeds.opml)
active = 1
tags = ["news","tech"]
group_id = 12
```

Export by group OR and tag AND:

```
GET /api/v1/watchlists/sources/export?group=10&group=11&tag=keep
```

Export all RSS sources tagged with "keep" (case-insensitive):

```
GET /api/v1/watchlists/sources/export?tag=keep&type=rss
```

## Preview (Dry-Run)

Use the preview endpoint to see candidate items and filter decisions without ingestion:

```
POST /api/v1/watchlists/jobs/{job_id}/preview?limit=20&per_source=10
```

Response includes per-item `decision` (ingest|filtered) and `matched_action` (include|exclude|flag|None). Honors include-only gating.

## Notes

- YouTube links must be canonical RSS feeds. The server normalizes common channel/user/playlist forms and rejects unsupported forms with `400 invalid_youtube_rss_url`.
- Per-run stats include filter counters and optional `filter_tallies`; see API docs for details.
