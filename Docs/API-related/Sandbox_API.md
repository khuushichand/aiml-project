# Sandbox API — Quick Guide (Spec 1.0/1.1)

This guide summarizes the Sandbox (code interpreter) API with concise examples. The API supports spec 1.0 and 1.1. Version 1.1 is backward‑compatible and adds optional interactivity and resume features.

Base URL: `/api/v1/sandbox`

Auth: Standard tldw AuthNZ
- Single user: `X-API-KEY: <key>`
- Multi user (JWT): `Authorization: Bearer <token>`

## Firecracker host prep

If you plan to use the Firecracker runtime, follow the host prerequisites and
smoke-test steps in `Docs/Deployment/Operations/Firecracker_Host_Checklist.md`.

## Feature discovery
GET `/api/v1/sandbox/runtimes`
Response (example):
```
{
  "runtimes": [
    {
      "name": "docker",
      "available": true,
      "default_images": ["python:3.11-slim", "node:20-alpine"],
      "max_cpu": 4.0,
      "max_mem_mb": 8192,
      "max_upload_mb": 64,
      "max_log_bytes": 10485760,
      "queue_max_length": 100,
      "queue_ttl_sec": 120,
      "workspace_cap_mb": 256,
      "artifact_ttl_hours": 24,
      "supported_spec_versions": ["1.0", "1.1"],
      "interactive_supported": false,
      "egress_allowlist_supported": false,
      "store_mode": "memory"
    }
  ]
}
```

## Create a session
POST `/api/v1/sandbox/sessions`
Headers: `Idempotency-Key: <uuid>` (recommended)
Body (1.0):
```
{
  "spec_version": "1.0",
  "runtime": "docker",
  "base_image": "python:3.11-slim",
  "timeout_sec": 300
}
```
Response:
```
{ "id": "<session_id>", "runtime": "docker", "base_image": "python:3.11-slim", "expires_at": null, "policy_hash": "<hash>" }
```

## Start a run (one‑shot or session)
POST `/api/v1/sandbox/runs`
Headers: `Idempotency-Key: <uuid>` (recommended)
Body (1.0):
```
{
  "spec_version": "1.0",
  "runtime": "docker",
  "base_image": "python:3.11-slim",
  "command": ["python", "-c", "print('hello')"],
  "timeout_sec": 60
}
```
Body (1.1 additions — optional):
```
{
  "spec_version": "1.1",
  "runtime": "docker",
  "base_image": "python:3.11-slim",
  "command": ["python", "-c", "input(); print('ok')"],
  "timeout_sec": 60,
  "interactive": true,
  "stdin_max_bytes": 16384,
  "stdin_max_frame_bytes": 2048,
  "stdin_bps": 4096,
  "stdin_idle_timeout_sec": 30,
  "resume_from_seq": 100
}
```
Response (scaffold example):
```
{
  "id": "<run_id>",
  "spec_version": "1.1",
  "runtime": "docker",
  "base_image": "python:3.11-slim",
  "phase": "completed",
  "exit_code": 0,
  "policy_hash": "<hash>",
  "log_stream_url": "ws://host/api/v1/sandbox/runs/<run_id>/stream?from_seq=100"
}
```

## Stream logs (WebSocket)
WS `/api/v1/sandbox/runs/{id}/stream`
- Optional query: `from_seq=<N>` (1.1 resume)
- When signed URLs are enabled, include `token` and `exp` query params.
Frames:
- `{ "type": "event", "event": "start" }`
- `{ "type": "stdout"|"stderr", "encoding": "utf8"|"base64", "data": "...", "seq": 123 }`
- `{ "type": "heartbeat", "seq": 124 }`
- `{ "type": "truncated", "reason": "log_cap", "seq": 125 }`
- `{ "type": "event", "event": "end", "data": {"exit_code": 0}, "seq": 126 }`
- Interactivity (1.1): client→server stdin frames `{ "type": "stdin", "encoding": "utf8"|"base64", "data": "..." }`

## Artifacts
- List: GET `/api/v1/sandbox/runs/{id}/artifacts`
- Download: GET `/api/v1/sandbox/runs/{id}/artifacts/{path}`
  - Supports single HTTP Range only. Use `Range: bytes=start-end` or suffix `bytes=-N`.
  - Multiple ranges are not supported; the server returns `416 Range Not Satisfiable` with `Content-Range: bytes */<size>`.
  - Responses include `Accept-Ranges: bytes`. A valid partial response includes `206 Partial Content` and `Content-Range: bytes <start>-<end>/<size>`.

Example:
```
# First 5 bytes
GET /api/v1/sandbox/runs/<id>/artifacts/out.txt
Range: bytes=0-4

HTTP/1.1 206 Partial Content
Accept-Ranges: bytes
Content-Range: bytes 0-4/10
Content-Length: 5

01234

# Unsupported multi-range
GET /api/v1/sandbox/runs/<id>/artifacts/out.txt
Range: bytes=0-1,3-4

HTTP/1.1 416 Range Not Satisfiable
Content-Range: bytes */10
```

## Idempotency conflicts
409, example:
```
{
  "error": {
    "code": "idempotency_conflict",
    "message": "Idempotency-Key replay with different body",
    "details": { "prior_id": "<id>", "key": "<Idempotency-Key>", "prior_created_at": "<ISO8601>" }
  }
}
```

## Health
- Authenticated: GET `/api/v1/sandbox/health` (includes store timings and Redis ping)
- Public: GET `/api/v1/sandbox/health/public` (no auth)

## Egress Policy and DNS Pinning

Some deployments enforce an egress allowlist for sandboxed runs. The Docker runner supports a deny‑all baseline (network=none) and, when enabled, a granular host‑level allowlist using iptables on the DOCKER-USER chain.

Utilities exposed in `tldw_Server_API.app.core.Sandbox.network_policy` help you prepare and manage rules:

- `expand_allowlist_to_targets(raw_allowlist, resolver=..., wildcard_subdomains=("", "www", "api"))`
  - Accepts a mix of CIDR (e.g., `10.0.0.0/8`), literal IPs (`8.8.8.8`), hostnames (`example.com`), wildcard prefixes (`*.example.com`), and suffix tokens (`.example.com`).
  - Resolves hostnames to A records and promotes to `/32`; returns a de‑duplicated list like `['1.2.3.4/32', '10.0.0.0/8']`.

- `pin_dns_map(raw_allowlist, resolver=...)`
  - Returns a mapping `{ host -> [IPs] }` after resolution for observability/debugging.

- `refresh_egress_rules(container_ip, raw_allowlist, label, resolver=..., wildcard_subdomains=...)`
  - Best‑effort revocation + re‑apply: deletes all rules in DOCKER‑USER containing `label` and applies an updated set of `ACCEPT` rules for resolved targets, followed by a final `DROP` for the container IP.

Examples:
```
from tldw_Server_API.app.core.Sandbox.network_policy import (
    expand_allowlist_to_targets, pin_dns_map, refresh_egress_rules
)

# Allowlist with CIDR, IP, wildcard and suffix tokens
raw = ["10.0.0.0/8", "8.8.8.8", "*.example.com", ".example.org"]
targets = expand_allowlist_to_targets(raw)
# e.g., ['10.0.0.0/8', '8.8.8.8/32', '93.184.216.34/32', ...]

# Inspect pinned DNS map (for logs/metrics)
pins = pin_dns_map(raw)
# e.g., {'example.com': ['93.184.216.34', ...], 'example.org': ['203.0.113.10', ...]}

# Apply (or refresh) rules for a given container
apply_specs = refresh_egress_rules(
    container_ip="172.18.0.2",
    raw_allowlist=raw,
    label="tldw-run-<short-id>",
)
```

Notes:
- Suffix tokens (like `.example.com`) behave like wildcards for a few common subdomains plus the apex (configurable).
- If `iptables-restore` is unavailable, the code falls back to iterative `iptables` commands.
- To revoke rules for a finished container, the runner labels and deletes rules by that label.

## Notes
- Spec versions are validated against server config. Default: `["1.0","1.1"]`.
- Interactivity requires runtime and policy support; fields are ignored otherwise.
- `log_stream_url` may be unsigned; prefer Authorization headers if signed URLs are disabled.
