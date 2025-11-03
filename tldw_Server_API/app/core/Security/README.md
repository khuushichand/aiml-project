## 1. Descriptive of Current Feature Set

- Purpose: Central security controls for outbound network policy (SSRF guard), HTTP hardening headers, request ID propagation, CSP for the WebUI, URL validation for endpoints, and secret management.
- Capabilities:
  - Egress policy enforcement (allowlist/denylist, private IP blocking, port restrictions) with per-tenant helpers.
  - Hardened HTTP response headers (CSP, Permissions-Policy, HSTS opt-in, referrer policy, remove Server header).
  - Request ID middleware (sanitizes incoming X-Request-ID, generates UUID when invalid; propagates via response and request.state).
  - CSP nonce and relaxed policies for WebUI and API docs; WebUI remote access guard with IP allowlists.
  - Secret management: retrieval, validation, caching (e.g., single-user API key, JWT secret) via config sources.
- Related Endpoints/Middleware Wiring:
  - Middlewares added in `main.py`: RequestID, WebUI CSP, WebUI access guard, SecurityHeaders — see tldw_Server_API/app/main.py:2429, tldw_Server_API/app/main.py:2498, tldw_Server_API/app/main.py:2503, tldw_Server_API/app/main.py:2512.
  - URL validation helper used by endpoints (e.g., web scraping duplicate check): tldw_Server_API/app/api/v1/endpoints/web_scraping.py:320.
- Related Schemas: N/A (security uses middleware and utility functions rather than Pydantic models).

## 2. Technical Details of Features

- Egress/SSRF
  - Policy eval: `evaluate_url_policy(url)` returns `URLPolicyResult(allowed, reason)`: tldw_Server_API/app/core/Security/egress.py:146.
  - Helpers: `is_url_allowed`, `is_url_allowed_for_tenant`, `is_webhook_url_allowed_for_tenant` (env-based allow/deny, per-tenant overrides), scheme/port checks, DNS resolution with private IP guard (IPv4/IPv6).
  - Env knobs: `EGRESS_ALLOWLIST`, `EGRESS_DENYLIST`, `WORKFLOWS_EGRESS_ALLOWLIST`, `WORKFLOWS_EGRESS_DENYLIST`, `WORKFLOWS_EGRESS_BLOCK_PRIVATE`, `WORKFLOWS_EGRESS_ALLOWED_PORTS`, `WORKFLOWS_EGRESS_PROFILE`.
  - Endpoint-friendly wrapper: `assert_url_safe(url)` — tldw_Server_API/app/core/Security/url_validation.py:6.

- HTTP Hardening
  - `SecurityHeadersMiddleware` sets default CSP/permissions, removes `Server`, adds HSTS when `SECURITY_ENABLE_HSTS=true` and request is HTTPS (incl. `X-Forwarded-Proto: https`): tldw_Server_API/app/core/Security/middleware.py:86.
  - Path-scoped CSP:
    - WebUI (`/webui`, `/setup`): relaxed CSP; nonce-aware when `request.state.csp_nonce` present.
    - API docs (`/docs`, `/redoc`): relaxed CSP allowing inline/eval and optional HTTPS CDNs.
    - Else: strict default CSP.
  - `WebUICSPMiddleware` injects a per-request CSP nonce and tailored policy for WebUI: tldw_Server_API/app/core/Security/webui_csp.py:72.
  - `WebUIAccessGuardMiddleware` enforces WebUI remote access policy and IP allowlists: tldw_Server_API/app/core/Security/webui_access_guard.py:74.

- Request ID Propagation
  - `RequestIDMiddleware` validates/sanitizes `X-Request-ID`, stores value on `request.state.request_id`, and returns header in responses: tldw_Server_API/app/core/Security/request_id_middleware.py:34.

- Secret Management
  - `SecretManager` provides typed getters/validation for secrets (JWT, OAuth, single-user API key) with source precedence and caching: tldw_Server_API/app/core/Security/secret_manager.py:76.
  - Single-user mode requires explicit `SINGLE_USER_API_KEY` with strong length; no hard-coded defaults.

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure
  - `egress.py`: URL policy evaluation and env-driven allow/deny controls.
  - `middleware.py`: security headers + CSP strategies.
  - `webui_csp.py`: CSP nonce injection for WebUI.
  - `webui_access_guard.py`: remote access guard for WebUI.
  - `request_id_middleware.py`: request ID sanitization and echo.
  - `secret_manager.py`: secret sources, types, validation.
  - `url_validation.py`: endpoint helper to assert URL safety.
- Extension Points
  - When adding outbound integrations, call `evaluate_url_policy` or `assert_url_safe` before any HTTP call.
  - Prefer centralized `SecurityHeadersMiddleware`; if you need per-route CSP overrides, set `response.headers["Content-Security-Policy"]` explicitly for that route.
- Tests
  - Security headers: tldw_Server_API/tests/Security/test_security_headers_middleware.py:1
  - Request ID: tldw_Server_API/tests/Security/test_request_id_middleware.py:1
  - Egress policy (core + global env): tldw_Server_API/tests/Security/test_egress.py:1, tldw_Server_API/tests/Security/test_egress_global_env.py:1
  - Downstream enforcement examples: tldw_Server_API/tests/WebScraping/test_scraping_module.py:1
- Local Dev Tips
  - Set `SECURITY_ENABLE_HSTS=false` for local dev behind non-HTTPS proxies.
  - Use `WORKFLOWS_EGRESS_ALLOWLIST` to limit outbound access when testing integrations.
- Operational Notes
  - Keep security middlewares enabled in production; they’re added in `main.py` during normal runs.
  - When behind a proxy/ingress, ensure HSTS is emitted only once (proxy vs app). Middleware respects `X-Forwarded-Proto`.
  - Review and maintain egress allowlists as integrations evolve.
