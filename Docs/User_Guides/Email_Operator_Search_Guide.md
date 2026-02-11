# Email Operator Search Guide

Last Updated: 2026-02-10

## Overview

Email operator search provides Gmail-style query syntax for message retrieval.

Use it when you need field-aware search such as sender, labels, date windows, and attachment presence.

## Where to Use It

You can query through either path:

1. Email-native endpoint:
   - `GET /api/v1/email/search?q=...`
2. Media compatibility endpoint:
   - `POST /api/v1/media/search` with:
     - `media_types=["email"]`
     - `email_query_mode="operators"` (explicit delegation), or
     - server cutover mode `EMAIL_MEDIA_SEARCH_DELEGATION_MODE=auto_email`

## Supported Operators (v1)

### Field Operators

1. `from:alice@example.com`
2. `to:bob@example.com`
3. `cc:team@example.com`
4. `bcc:legal@example.com`
5. `subject:invoice`
6. `label:inbox`

### Special Operators

1. `has:attachment`
2. `before:2026-01-01`
3. `after:2026-01-01`
4. `older_than:30d`
5. `newer_than:7d`

Relative windows support units:

1. `m` (minutes)
2. `h` (hours)
3. `d` (days)
4. `w` (weeks)
5. `y` (years)

Examples: `newer_than:12h`, `older_than:90d`.

## Query Semantics

1. Default operator is `AND`.
2. Explicit `OR` is supported.
3. Unary negation uses `-` (example: `-label:spam`).
4. Quoted phrases are supported (example: `"budget review"`).
5. Parentheses are not supported in v1.

### Valid Examples

1. `from:alice@example.com label:inbox`
2. `subject:incident has:attachment newer_than:7d`
3. `budget OR invoice`
4. `from:finance@example.com -label:archive`
5. `"quarterly review" after:2025-10-01`

## API Examples

### Email-native Search

```bash
curl -G "http://127.0.0.1:8000/api/v1/email/search" \
  --data-urlencode "q=from:alice@example.com has:attachment newer_than:30d" \
  --data-urlencode "limit=50" \
  --data-urlencode "offset=0" \
  -H "X-API-KEY: <your-api-key>"
```

### Media Endpoint with Explicit Operator Delegation

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/media/search?page=1&results_per_page=10" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <your-api-key>" \
  -d '{
    "query": "from:alice@example.com label:inbox",
    "media_types": ["email"],
    "email_query_mode": "operators"
  }'
```

## Troubleshooting

### 400 Bad Request

Likely causes:

1. Parentheses used in query (`(` or `)`).
2. Invalid date format for `before:` or `after:` (must be `YYYY-MM-DD`).
3. Invalid `older_than:` / `newer_than:` format (must look like `7d`, `12h`, `30m`).

### 422 Unprocessable Entity

Likely causes on `/api/v1/media/search`:

1. `email_query_mode="operators"` used without `media_types=["email"]`.
2. Operator mode disabled by configuration (`EMAIL_OPERATOR_SEARCH_ENABLED=false`).

### No Results

Check:

1. Tenant/user scope and API key.
2. Label value spelling (labels are normalized by key).
3. Date window strictness (`before:` and `after:` can exclude expected rows).
4. Whether results are hidden by soft-delete defaults.

## Behavior Notes

1. Result ordering is deterministic: `internal_date DESC`, then `email_message_id DESC`.
2. `limit` max is 500 for email-native endpoint.
3. `/api/v1/media/search` response shape stays media-compatible, even when delegated.

