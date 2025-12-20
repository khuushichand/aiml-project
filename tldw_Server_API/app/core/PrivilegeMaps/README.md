 # PrivilegeMaps

## 1. Descriptive of Current Feature Set

- Purpose: Introspect FastAPI route dependencies to map scopes, RBAC, and rate-limit resources; aggregate into org/team/user summaries.
- Capabilities:
  - Route registry extraction and serialization
  - Role-scope mapping using catalog; admin roles and feature flags
  - Cached summaries with time-series trend store
- Inputs/Outputs:
  - Input: FastAPI app instance + privilege catalog
  - Output: per-scope route maps, summaries, trends, and cached snapshots
- Related Usage:
  - Used by admin/reporting endpoints and docs tooling

## 2. Technical Details of Features

- Architecture & Data Flow:
  - `collect_privilege_route_registry(app, catalog)` extracts dependencies and scope matches; `PrivilegeMapService` builds summaries with cache + trends
- Key Classes/Functions:
  - Service: `PrivilegeMaps/service.py:1`; Introspection: `PrivilegeMaps/introspection.py:1`; Startup hooks: `PrivilegeMaps/startup.py:1`; Caching/Trends helpers
- Dependencies:
  - Internal: AuthNZ settings, privilege catalog loader, caching store
- Data Models & DB:
  - In-memory caches by default; optional stores pluggable
- Configuration:
  - Cache TTL: `PRIVILEGE_MAP_CACHE_TTL_SECONDS` (default 120s)
- Concurrency & Performance:
  - Deterministic route signature to invalidate caches on changes
- Error Handling:
  - Unknown scope refs logged; strict mode raises on collection
- Security:
  - Admin roles set maintained; summaries respect RBAC design

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure:
  - `PrivilegeMaps/` with `service.py`, `introspection.py`, `startup.py`, `cache.py`, `trends.py`
- Extension Points:
  - Add derived views (team/org rollups); plug in persistent caches
- Coding Patterns:
  - Keep extraction deterministic; avoid side effects during introspection
- Tests:
  - `tldw_Server_API/tests/Privileges/test_privilege_service_sqlite.py:1`
  - `tldw_Server_API/tests/Privileges/test_privilege_endpoints.py:1`
- Local Dev Tips:
  - Run against the app instance after adding endpoints to validate scope wiring
- Pitfalls & Gotchas:
  - High-cardinality dependencies inflate summaries; ensure TTLs are sane
- Roadmap/TODOs:
  - Persisted trend backends; live dashboards
