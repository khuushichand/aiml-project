# Watchlists Job Filters - Schema and Examples (v0.1)

Status: In Progress
Owners: Watchlists Backend + WebUI
Updated: 2025-10-28

This document specifies the JSON schema for job-level filters in Watchlists, provides evaluation semantics, and shows common examples. Filters are attached to `scrape_jobs` and are evaluated when selecting items from runs before they are surfaced in outputs.

## Schema

Top-level payloads use a wrapper object with a `filters` array:

```
{
  "filters": [ Filter, ... ]
}
```

Each `Filter` has the following shape:

```
{
  "type": "keyword" | "author" | "regex" | "date_range" | "all",
  "action": "include" | "exclude" | "flag",
  "value": { ... },            // type-specific payload
  "priority": number,          // optional; higher runs earlier (default 0)
  "is_active": boolean         // optional; default true
}
```

Type-specific `value` objects:

- `keyword`
  - `{ "keywords": string[], "match": "any" | "all", "field?": "title" | "summary" | "content" }`
  - Default: `match="any"`, `field="title"`
- `author`
  - `{ "names": string[], "match": "any" | "all" }`
  - Default: `match="any"`
- `regex`
  - `{ "pattern": string, "flags?": string, "field": "title" | "summary" | "content" }`
  - Default: `flags="i"`, `field="title"`
- `date_range`
  - `{ "max_age_days"?: number, "since"?: string(ISO-8601), "until"?: string(ISO-8601) }`
  - At least one of `max_age_days`, `since`, `until` must be present
- `all`
  - `{}` (matches all items)

Unknown `type`/`action` values must be rejected by the API.

## Evaluation Semantics

- Filters are ordered by `priority` descending; equal priorities preserve submission order.
- An item is evaluated against filters and the first terminal decision wins:
  - `exclude` → item is dropped
  - `include` → item is selected
  - `flag` → item is selected and flagged (non-terminal unless configured terminal)
- If no filter matches, items are included by default (subject to global item limits).

Notes:
- The `flag` action can be surfaced in outputs (e.g., “⚑ flagged by: regex:breaking”).
- Future iterations may allow `flag` to be terminal via a job setting.

## Examples

Keyword include + regex exclude:

```
{
  "filters": [
    {"type": "keyword", "value": {"keywords": ["ai","ml"], "match": "any"}, "action": "include", "priority": 100},
    {"type": "regex", "value": {"field": "title", "pattern": "(?i)breaking"}, "action": "exclude", "priority": 110}
  ]
}
```

Author include + date window:

```
{
  "filters": [
    {"type": "author", "value": {"names": ["Alice","Bob"], "match": "any"}, "action": "include", "priority": 90},
    {"type": "date_range", "value": {"max_age_days": 7}, "action": "include", "priority": 80}
  ]
}
```

Flag suspicious terms:

```
{
  "filters": [
    {"type": "regex", "value": {"pattern": "(?i)rumor|leak", "field": "title", "flags": "i"}, "action": "flag", "priority": 120}
  ]
}
```

## API Endpoints (planned)

- `PATCH /api/v1/watchlists/jobs/{id}/filters` - replace full set
- `POST /api/v1/watchlists/jobs/{id}/filters:add` - append one or more

Refer to: `Docs/Product/Watchlists_Subscriptions_Bridge_PRD.md` for the full Watchlists bridge and feature scope.
