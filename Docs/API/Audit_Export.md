# API: Audit Export

Endpoint for exporting audit events in JSON, JSONL (NDJSON), or CSV.

- Method: GET
- Path: `/api/v1/audit/export`
- Auth: Requires admin privileges (X-API-KEY in single-user mode, or Bearer JWT in multi-user mode)
- Produces: `application/json`, `application/x-ndjson` (for JSONL), or `text/csv`

## Query Parameters

- `format` (string, optional)
  - `json` (default), `jsonl` (NDJSON), or `csv`
- `start_time` (string, optional)
  - ISO8601 timestamp; accepts trailing `Z`
- `end_time` (string, optional)
  - ISO8601 timestamp; accepts trailing `Z`
- `event_type` (string, optional)
  - Comma-separated list of enum names (e.g., `AUTH_LOGIN_SUCCESS`) or values (e.g., `auth.login.success`)
- `category` (string, optional)
  - Comma-separated list of enum names or values (e.g., `SECURITY` or `security`)
- `min_risk_score` (integer, optional)
- `user_id` (string, optional)
- `request_id` (string, optional)
- `correlation_id` (string, optional)
- `ip_address` (string, optional)
  - Filters by `context_ip_address`
- `session_id` (string, optional)
  - Filters by `context_session_id`
- `endpoint` (string, optional)
  - Filters by `context_endpoint`
- `method` (string, optional)
  - Filters by `context_method`
- `filename` (string, optional)
  - Suggested download filename; sanitized and normalized to match `format`
- `stream` (boolean, optional)
  - JSON/JSONL only. When `true`, response is streamed incrementally.
  - If `format=csv` and `stream=true`, endpoint returns 400.
- `max_rows` (integer, optional)
  - Hard cap on number of rows to export (applies to JSON, JSONL, and CSV paths; for streaming it truncates output once limit is reached)

### Count Endpoint

- Method: GET
- Path: `/api/v1/audit/count`
- Auth: Requires admin privileges
- Returns: `{ "count": <int> }`

Accepts the same filter parameters as the export endpoint (excluding `format`, `stream`, and `filename`).

## Responses

- 200 OK
  - JSON: body is a JSON array of events
  - JSONL: body is newline-delimited JSON (one JSON object per line)
  - CSV: body is CSV text with a fixed header schema
  - Content-Disposition `attachment; filename=...` (filename normalized to `.json`, `.jsonl`, or `.csv`)
- 400 Bad Request
  - Invalid `format` or `stream` used with CSV
- 403 Forbidden
  - Caller is not an admin

## Notes

- CSV exports use a fixed header schema for consistent column order.
- JSON streaming keeps memory usage low for large result sets; CSV streaming is not exposed via this endpoint.
- Timestamps are stored and filtered as ISO8601 strings.

## Examples

JSON (non-streaming)

```bash
curl -H "X-API-KEY: $KEY" \
  "http://127.0.0.1:8000/api/v1/audit/export?format=json&user_id=42" -OJ
```

JSON (streaming)

```bash
curl -H "X-API-KEY: $KEY" \
  "http://127.0.0.1:8000/api/v1/audit/export?format=json&stream=true&min_risk_score=70" -OJ
```

CSV

```bash
curl -H "X-API-KEY: $KEY" \
  "http://127.0.0.1:8000/api/v1/audit/export?format=csv&user_id=42&filename=audit.csv" -OJ
```

JSONL (NDJSON)

```bash
curl -H "X-API-KEY: $KEY" \
  "http://127.0.0.1:8000/api/v1/audit/export?format=jsonl&stream=true&user_id=42&max_rows=10000" -OJ
```

---

See also: Docs/Audit/README.md for the unified audit service design and usage details.
