## Stage 1: Router Analytics Contract and Schema Baseline
**Goal**: Define backend-facing request/response schemas for router analytics status surfaces.
**Success Criteria**: Admin schemas include range query, status payload, breakdown payload, and metadata payload models used by backend + frontend.
**Tests**: `tldw_Server_API/tests/Admin/test_router_analytics_schemas.py`
**Status**: Complete

## Stage 2: Usage Log Schema Enrichment for Router Analytics Dimensions
**Goal**: Extend AuthNZ usage schema to persist status-tab breakdown dimensions.
**Success Criteria**: `llm_usage_log` supports `remote_ip`, `user_agent`, `token_name`, and `conversation_id`; migration is additive and backward compatible for SQLite/Postgres.
**Tests**:
- `tldw_Server_API/tests/AuthNZ_SQLite/test_authnz_llm_usage_log_router_columns_sqlite.py`
- `tldw_Server_API/tests/AuthNZ_Postgres/test_authnz_llm_usage_log_router_columns_pg.py`
**Status**: Complete

## Stage 3: Usage Write-Path Enrichment
**Goal**: Populate new router analytics dimensions at write time from request context.
**Success Criteria**: Usage logging includes resolved client IP, user agent, token name derivation, and optional conversation id in supported call paths.
**Tests**: `tldw_Server_API/tests/Usage/test_usage_tracker_sqlite.py`
**Status**: Complete

## Stage 4: Router Analytics Aggregate Service (Status + Breakdowns)
**Goal**: Implement backend aggregation service for status KPIs, timeseries, and status breakdown tables.
**Success Criteria**:
- New admin service returns `RouterAnalyticsStatusResponse`.
- New admin service returns `RouterAnalyticsBreakdownsResponse`.
- Aggregation respects range window and optional provider/model/token filters.
- Backend supports SQLite and Postgres paths.
**Tests**:
- `tldw_Server_API/tests/Admin/test_router_analytics_service.py`
**Status**: Complete

## Stage 5: Admin Router Analytics Endpoints (Status Delivery Slice)
**Goal**: Expose Stage 4 aggregates via additive `/api/v1/admin/router-analytics/*` endpoints.
**Success Criteria**:
- Endpoints: `status`, `status/breakdowns`, and `meta`.
- Existing `/admin/usage` and `/admin/llm-usage*` endpoints unchanged.
- Admin scope restrictions (`org_id`) are applied consistently with current admin services.
**Tests**:
- `tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`
**Status**: Complete

## Stage 6: Verification and Security Scan
**Goal**: Validate touched scope and ensure no new security findings are introduced.
**Success Criteria**:
- Targeted pytest suites pass for touched scope.
- Bandit scan run on touched files; any new findings resolved.
**Tests**:
- `python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_schemas.py tldw_Server_API/tests/Admin/test_router_analytics_service.py tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`
- `python -m bandit -r tldw_Server_API/app/services/admin_router_analytics_service.py tldw_Server_API/app/api/v1/endpoints/admin/admin_router_analytics.py tldw_Server_API/app/api/v1/endpoints/admin/__init__.py -f json -o /tmp/bandit_router_analytics_status_backend.json`
**Status**: Complete

## Stage 7: Admin-UI Status Tab Migration to Router Analytics API
**Goal**: Replace legacy `/usage` page data plumbing with new router analytics aggregate endpoints while keeping a thin frontend layer.
**Success Criteria**:
- `admin-ui/app/usage/page.tsx` renders a status-first shell (tabs, KPI cards, timeline, breakdown tables).
- Frontend calls `GET /admin/router-analytics/status`, `/status/breakdowns`, and `/meta` via `api-client` + thin router analytics client wrappers.
- Non-status tabs render placeholder content for staged rollout.
**Tests**:
- `admin-ui/app/usage/__tests__/page.test.tsx`
**Status**: Complete

## Stage 8: Frontend Verification
**Goal**: Validate touched admin-ui scope and ensure frontend quality gates pass for the delivery slice.
**Success Criteria**:
- Usage page tests pass against new router analytics shell.
- Touched frontend files pass targeted lint.
- Any verification constraints are documented when tooling prerequisites are absent.
**Tests**:
- `cd admin-ui && bunx vitest run app/usage/__tests__/page.test.tsx`
- `cd admin-ui && BROWSERSLIST_IGNORE_OLD_DATA=1 BASELINE_BROWSER_MAPPING_IGNORE_OLD_DATA=1 bunx eslint app/usage/page.tsx app/usage/__tests__/page.test.tsx lib/router-analytics-client.ts lib/router-analytics-types.ts lib/api-client.ts`
**Status**: Complete

## Stage 9: Router Analytics Quota Delivery Slice
**Goal**: Deliver Step 2 (`Quota`) with a backend aggregate endpoint and thin frontend tab rendering.
**Success Criteria**:
- Additive endpoint: `GET /api/v1/admin/router-analytics/quota`.
- Payload includes quota summary + key-level utilization against configured day/month token/USD budgets.
- `/usage` `Quota` tab uses router-analytics quota payload; non-quota follow-on tabs remain staged as coming soon.
**Tests**:
- `tldw_Server_API/tests/Admin/test_router_analytics_schemas.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_service.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `admin-ui/app/usage/__tests__/page.test.tsx`
**Status**: Complete

## Stage 10: Quota Slice Verification and Security Scan
**Goal**: Validate the quota delivery scope across backend/frontend and ensure no new security findings.
**Success Criteria**:
- Targeted backend admin tests and OpenAPI contract pass.
- Admin-ui usage tests and full vitest suite pass.
- Bandit scan on touched backend files is clean.
**Tests**:
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_schemas.py tldw_Server_API/tests/Admin/test_router_analytics_service.py tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`
- `cd admin-ui && bunx vitest run app/usage/__tests__/page.test.tsx`
- `cd admin-ui && bunx vitest run`
- `cd admin-ui && BROWSERSLIST_IGNORE_OLD_DATA=1 BASELINE_BROWSER_MAPPING_IGNORE_OLD_DATA=1 bunx eslint app/usage/page.tsx app/usage/__tests__/page.test.tsx lib/router-analytics-client.ts lib/router-analytics-types.ts lib/api-client.ts`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/admin_router_analytics_service.py tldw_Server_API/app/api/v1/endpoints/admin/admin_router_analytics.py tldw_Server_API/app/api/v1/schemas/admin_schemas.py -f json -o /tmp/bandit_router_analytics_quota.json`
**Status**: Complete

## Stage 11: Router Analytics Providers Delivery Slice
**Goal**: Deliver Step 3 (`Providers`) with a backend aggregate endpoint and thin frontend tab rendering.
**Success Criteria**:
- Additive endpoint: `GET /api/v1/admin/router-analytics/providers`.
- Payload includes provider summary counters and per-provider load/health rows.
- `/usage` `Providers` tab uses router-analytics providers payload; remaining follow-on tabs stay staged as coming soon.
**Tests**:
- `tldw_Server_API/tests/Admin/test_router_analytics_schemas.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_service.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `admin-ui/app/usage/__tests__/page.test.tsx`
**Status**: Complete

## Stage 12: Providers Slice Verification and Security Scan
**Goal**: Validate providers delivery scope across backend/frontend and ensure no new security findings.
**Success Criteria**:
- Targeted backend admin tests and OpenAPI contract pass.
- Admin-ui usage tests and full vitest suite pass.
- Bandit scan on touched backend files is clean.
**Tests**:
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_schemas.py tldw_Server_API/tests/Admin/test_router_analytics_service.py tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`
- `cd admin-ui && bunx vitest run app/usage/__tests__/page.test.tsx`
- `cd admin-ui && bunx vitest run`
- `cd admin-ui && bunx eslint app/usage/page.tsx lib/router-analytics-client.ts lib/router-analytics-types.ts`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/admin_router_analytics_service.py tldw_Server_API/app/api/v1/endpoints/admin/admin_router_analytics.py tldw_Server_API/app/api/v1/schemas/admin_schemas.py -f json -o /tmp/bandit_router_analytics_providers.json`
**Status**: Complete

## Stage 13: Router Analytics Access Delivery Slice
**Goal**: Deliver Step 4 (`Access`) with a backend aggregate endpoint and thin frontend tab rendering.
**Success Criteria**:
- Additive endpoint: `GET /api/v1/admin/router-analytics/access`.
- Payload includes access summary counters and token name / remote IP / user-agent breakdown tables.
- `/usage` `Access` tab uses router-analytics access payload; remaining follow-on tabs stay staged as coming soon.
**Tests**:
- `tldw_Server_API/tests/Admin/test_router_analytics_schemas.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_service.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `admin-ui/app/usage/__tests__/page.test.tsx`
**Status**: Complete

## Stage 14: Access Slice Verification and Security Scan
**Goal**: Validate access delivery scope across backend/frontend and ensure no new security findings.
**Success Criteria**:
- Targeted backend admin tests and OpenAPI contract pass.
- Admin-ui usage tests and full vitest suite pass.
- Bandit scan on touched backend files is clean.
**Tests**:
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_schemas.py tldw_Server_API/tests/Admin/test_router_analytics_service.py tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`
- `cd admin-ui && bunx vitest run app/usage/__tests__/page.test.tsx`
- `cd admin-ui && bunx vitest run`
- `cd admin-ui && bunx eslint app/usage/page.tsx app/usage/__tests__/page.test.tsx lib/router-analytics-client.ts lib/router-analytics-types.ts lib/api-client.ts`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/admin_router_analytics_service.py tldw_Server_API/app/api/v1/endpoints/admin/admin_router_analytics.py tldw_Server_API/app/api/v1/schemas/admin_schemas.py -f json -o /tmp/bandit_router_analytics_access.json`
**Status**: Complete

## Stage 15: Router Analytics Network Delivery Slice
**Goal**: Deliver Step 5 (`Network`) with a backend aggregate endpoint and thin frontend tab rendering.
**Success Criteria**:
- Additive endpoint: `GET /api/v1/admin/router-analytics/network`.
- Payload includes network summary counters and remote IP / endpoint / operation breakdown tables.
- `/usage` `Network` tab uses router-analytics network payload; remaining follow-on tabs stay staged as coming soon.
**Tests**:
- `tldw_Server_API/tests/Admin/test_router_analytics_schemas.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_service.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `admin-ui/app/usage/__tests__/page.test.tsx`
**Status**: Complete

## Stage 16: Network Slice Verification and Security Scan
**Goal**: Validate network delivery scope across backend/frontend and ensure no new security findings.
**Success Criteria**:
- Targeted backend admin tests and OpenAPI contract pass.
- Admin-ui usage tests and full vitest suite pass.
- Bandit scan on touched backend files is clean.
**Tests**:
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_schemas.py tldw_Server_API/tests/Admin/test_router_analytics_service.py tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`
- `cd admin-ui && bunx vitest run app/usage/__tests__/page.test.tsx`
- `cd admin-ui && bunx vitest run`
- `cd admin-ui && bunx eslint app/usage/page.tsx app/usage/__tests__/page.test.tsx lib/router-analytics-client.ts lib/router-analytics-types.ts lib/api-client.ts`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/admin_router_analytics_service.py tldw_Server_API/app/api/v1/endpoints/admin/admin_router_analytics.py tldw_Server_API/app/api/v1/schemas/admin_schemas.py -f json -o /tmp/bandit_router_analytics_network.json`
**Status**: Complete

## Stage 17: Router Analytics Models Delivery Slice
**Goal**: Deliver Step 6 (`Models`) with a backend aggregate endpoint and thin frontend tab rendering.
**Success Criteria**:
- Additive endpoint: `GET /api/v1/admin/router-analytics/models`.
- Payload includes model summary counters and model/provider health-load rows.
- `/usage` `Models` tab uses router-analytics models payload; remaining follow-on tabs stay staged as coming soon.
**Tests**:
- `tldw_Server_API/tests/Admin/test_router_analytics_schemas.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_service.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `admin-ui/app/usage/__tests__/page.test.tsx`
**Status**: Complete

## Stage 18: Models Slice Verification and Security Scan
**Goal**: Validate models delivery scope across backend/frontend and ensure no new security findings.
**Success Criteria**:
- Targeted backend admin tests and OpenAPI contract pass.
- Admin-ui usage tests and full vitest suite pass.
- Bandit scan on touched backend files is clean.
**Tests**:
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_schemas.py tldw_Server_API/tests/Admin/test_router_analytics_service.py tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`
- `cd admin-ui && bunx vitest run app/usage/__tests__/page.test.tsx`
- `cd admin-ui && bunx vitest run`
- `cd admin-ui && bunx eslint app/usage/page.tsx app/usage/__tests__/page.test.tsx lib/router-analytics-client.ts lib/router-analytics-types.ts lib/api-client.ts`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/admin_router_analytics_service.py tldw_Server_API/app/api/v1/endpoints/admin/admin_router_analytics.py tldw_Server_API/app/api/v1/schemas/admin_schemas.py -f json -o /tmp/bandit_router_analytics_models.json`
**Status**: Complete

## Stage 19: Router Analytics Conversations Delivery Slice
**Goal**: Deliver Step 7 (`Conversations`) with a backend aggregate endpoint and thin frontend tab rendering.
**Success Criteria**:
- Additive endpoint: `GET /api/v1/admin/router-analytics/conversations`.
- Payload includes conversation summary counters and per-conversation health-load rows.
- `/usage` `Conversations` tab uses router-analytics conversations payload; remaining follow-on tab (`Log`) stays staged as coming soon.
**Tests**:
- `tldw_Server_API/tests/Admin/test_router_analytics_schemas.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_service.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `admin-ui/app/usage/__tests__/page.test.tsx`
**Status**: Complete

## Stage 20: Conversations Slice Verification and Security Scan
**Goal**: Validate conversations delivery scope across backend/frontend and ensure no new security findings.
**Success Criteria**:
- Targeted backend admin tests and OpenAPI contract pass.
- Admin-ui usage tests and full vitest suite pass.
- Bandit scan on touched backend files is clean.
**Tests**:
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_schemas.py tldw_Server_API/tests/Admin/test_router_analytics_service.py tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`
- `cd admin-ui && bunx vitest run app/usage/__tests__/page.test.tsx`
- `cd admin-ui && bunx vitest run`
- `cd admin-ui && bunx eslint app/usage/page.tsx app/usage/__tests__/page.test.tsx lib/router-analytics-client.ts lib/router-analytics-types.ts lib/api-client.ts`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/admin_router_analytics_service.py tldw_Server_API/app/api/v1/endpoints/admin/admin_router_analytics.py tldw_Server_API/app/api/v1/schemas/admin_schemas.py -f json -o /tmp/bandit_router_analytics_conversations.json`
**Status**: Complete

## Stage 21: Router Analytics Log Delivery Slice
**Goal**: Deliver Step 8 (`Log`) with a backend aggregate endpoint and thin frontend tab rendering.
**Success Criteria**:
- Additive endpoint: `GET /api/v1/admin/router-analytics/log`.
- Payload includes log summary counters and recent request log rows with status, latency, tokens, and cost fields.
- `/usage` `Log` tab uses router-analytics log payload; all staged tabs are now fully implemented.
**Tests**:
- `tldw_Server_API/tests/Admin/test_router_analytics_schemas.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_service.py`
- `tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `admin-ui/app/usage/__tests__/page.test.tsx`
**Status**: Complete

## Stage 22: Log Slice Verification and Security Scan
**Goal**: Validate log delivery scope across backend/frontend and ensure no new security findings.
**Success Criteria**:
- Targeted backend admin tests and OpenAPI contract pass.
- Admin-ui usage tests and full vitest suite pass.
- Bandit scan on touched backend files is clean.
**Tests**:
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_router_analytics_schemas.py tldw_Server_API/tests/Admin/test_router_analytics_service.py tldw_Server_API/tests/Admin/test_router_analytics_endpoints.py`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`
- `cd admin-ui && bunx vitest run app/usage/__tests__/page.test.tsx`
- `cd admin-ui && bunx vitest run`
- `cd admin-ui && bunx eslint app/usage/page.tsx app/usage/__tests__/page.test.tsx lib/router-analytics-client.ts lib/router-analytics-types.ts lib/api-client.ts`
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/admin_router_analytics_service.py tldw_Server_API/app/api/v1/endpoints/admin/admin_router_analytics.py tldw_Server_API/app/api/v1/schemas/admin_schemas.py -f json -o /tmp/bandit_router_analytics_log.json`
**Status**: Complete
