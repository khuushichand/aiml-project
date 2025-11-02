# Security Module

This document summarises the server-side security controls implemented in
`tldw_Server_API/app/core/Security` and adjacent modules. The focus is on
hardening outbound network access, HTTP responses, identity propagation, and
secret handling.

## Module Layout

```
tldw_Server_API/app/core/Security/
├── egress.py              # Outbound URL policy (SSRF protection)
├── middleware.py          # Hardened security headers
├── request_id_middleware.py  # Sanitised X-Request-ID propagation
├── secret_manager.py      # Centralised secret retrieval and validation
└── url_validation.py      # FastAPI-facing URL validator (wraps egress policy)
```

## HTTP Hardening

- **SecurityHeadersMiddleware** applies a conservative header set:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Content-Security-Policy` (self-only resources, form-action restrictions,
    `upgrade-insecure-requests`)
  - `Permissions-Policy` (disables high-risk browser capabilities)
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `X-Permitted-Cross-Domain-Policies: none`
  - Removes the `Server` header to avoid fingerprinting
  - HSTS is opt-in; set `SECURITY_ENABLE_HSTS=true` to emit the header when the
    request is served over HTTPS (including `X-Forwarded-Proto: https` deployments)

  The middleware is the canonical implementation; legacy imports in
  `app/core/AuthNZ/security_headers.py` now re-export this version. Optional
  development mode loosens HSTS and framing requirements for local debugging.

- **RequestIDMiddleware** now sanitises incoming `X-Request-ID` values. Any
  value longer than 128 characters, or containing characters outside
  `[A-Za-z0-9._:-]`, is replaced with a freshly generated UUIDv4. The cleaned ID
  is stored on `request.state.request_id` and echoed back in the response.

## Egress Controls

- `egress.is_url_allowed` enforces outbound allowlisting and IP hygiene:
  - Schemes limited to HTTP/HTTPS
  - Optimised allowlist matching (exact match or subdomain) sourced from
    `WORKFLOWS_EGRESS_ALLOWLIST`
  - Private/reserved address blocking covers IPv4, IPv6, and IPv4-mapped IPv6
    addresses (configurable through `WORKFLOWS_EGRESS_BLOCK_PRIVATE`)
  - Unresolvable hosts are rejected when private blocking is active

- `url_validation.assert_url_safe` simply calls the shared evaluator and raises
  a 400 error with the reason string, keeping FastAPI endpoints aligned with the
  core egress policy.

## Secret Management

- `secret_manager.SecretManager` owns retrieval, validation, and caching for all
  runtime secrets. The single-user API key configuration was hardened:
  - `single_user_api_key` is now marked as required with a 24-character minimum
  - No baked-in defaults; the server refuses to start in single-user mode until
    `SINGLE_USER_API_KEY` (or legacy `API_KEY`) is explicitly configured
  - Production health checks surface missing or weak secrets via
    `/api/v1/health` and the audit pipeline

- For local development, run the AuthNZ bootstrap helper to generate fresh
  secrets:

  ```bash
  python -m tldw_Server_API.app.core.AuthNZ.initialize  # choose "Generate secure keys"
  ```

## Configuration Reference

| Setting | Purpose |
| --- | --- |
| `SINGLE_USER_API_KEY` | Required for single-user mode authentication |
| `WORKFLOWS_EGRESS_ALLOWLIST` | Optional comma-separated domain allowlist |
| `WORKFLOWS_EGRESS_BLOCK_PRIVATE` | Controls private/reserved address blocking (default `true`) |
| `SINGLE_USER_TEST_API_KEY` | Optional deterministic key for automated tests |
| `SECURITY_ENABLE_HSTS` | Enable HSTS response header generation (default `false`) |

## Testing Coverage

- `tests/Security/test_egress.py` exercises allowlist matching and IPv4-mapped
  IPv6 blocking.
- `tests/Security/test_request_id_middleware.py` verifies sanitisation and
  header propagation.
- `tests/Security/test_security_headers_middleware.py` validates the presence
  (and conditional omission) of the hardened header set.

## Operational Notes

- Keep the security middleware enabled in production. Disable only for specific
  debug scenarios.
- When deploying behind a reverse proxy/ingress controller, ensure HSTS is
  emitted exactly once-either by the proxy or by the application. The middleware
  respects `X-Forwarded-Proto` to avoid false positives.
- Review egress allowlists whenever adding outbound integrations. The default
  behaviour is intentionally conservative.
