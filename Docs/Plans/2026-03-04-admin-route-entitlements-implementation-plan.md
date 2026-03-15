# Admin Route Entitlements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement route-level entitlement enforcement across WebUI and extension so admins can allow/deny specific pages per scope with deny-wins and fail-closed behavior.

**Architecture:** Add a backend entitlement policy surface (`/api/v1/entitlements/me/routes` + scoped management CRUD), enforce scoped admin writes via shared admin scope services, add AuthNZ-backed policy tables for SQLite/Postgres, and extend frontend route metadata with canonical `route_id` for both options and sidepanel routes. Client route rendering combines server capability flags and entitlement decisions, while backend endpoint dependencies enforce sensitive route restrictions server-side for selected route/API bundles.

**Tech Stack:** FastAPI, Pydantic, AuthNZ scope services, SQLite/Postgres migrations, React Router, TypeScript, Vitest, Pytest.

---

### Task 0: Add Delegated-Admin-Capable Management Surface

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/admin_entitlements.py`
- Modify: `tldw_Server_API/app/main.py`
- Modify: `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py`
- Test: `tldw_Server_API/tests/Entitlements/test_entitlements_management_access_surface.py`

**Step 1: Write failing access tests**

```python
def test_org_admin_can_access_entitlement_policy_list(client, org_admin_headers):
    resp = client.get("/api/v1/admin/entitlements/policies", headers=org_admin_headers)
    assert resp.status_code == 200


def test_non_manager_cannot_access_entitlement_policy_list(client, member_headers):
    resp = client.get("/api/v1/admin/entitlements/policies", headers=member_headers)
    assert resp.status_code == 403
```

**Step 2: Run tests to verify failures**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_entitlements_management_access_surface.py`
Expected: FAIL (route/dependency not implemented).

**Step 3: Implement scoped manager dependency + router inclusion**

- Add an auth dependency that allows platform admins plus scoped org/team managers.
- Mount entitlements management router directly in `main.py` (not through the global admin router dependency that requires role `admin`).
- Keep path under `/api/v1/admin/entitlements/*` for contract consistency.

**Step 4: Run tests to verify pass**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_entitlements_management_access_surface.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/admin_entitlements.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/app/api/v1/API_Deps/auth_deps.py \
  tldw_Server_API/tests/Entitlements/test_entitlements_management_access_surface.py
git commit -m "feat(entitlements): add delegated-admin capable management surface"
```

### Task 1: Add Entitlement Schemas and Read Contract

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/entitlements_schemas.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/entitlements.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Entitlements/test_entitlements_contract.py`

**Step 1: Write failing contract tests**

```python
def test_get_entitlements_me_routes_contract(client, auth_headers):
    resp = client.get("/api/v1/entitlements/me/routes", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "version" in body
    assert "ttl_seconds" in body
    assert "routes" in body
    assert "ETag" in resp.headers
```

**Step 2: Run test to verify fail**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_entitlements_contract.py::test_get_entitlements_me_routes_contract`
Expected: FAIL (endpoint missing).

**Step 3: Implement minimal endpoint and schema**

- Add `GET /entitlements/me/routes` response model.
- Return deterministic placeholder payload with `version` and `ttl_seconds`.
- Add ETag support (reuse `generate_etag` + `is_not_modified` helpers).

**Step 4: Run test to verify pass**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_entitlements_contract.py::test_get_entitlements_me_routes_contract`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/entitlements_schemas.py \
  tldw_Server_API/app/api/v1/endpoints/entitlements.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/tests/Entitlements/test_entitlements_contract.py
git commit -m "feat(entitlements): add me routes contract endpoint"
```

### Task 2: Add AuthNZ Migrations for Policy Tables (SQLite + Postgres)

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/AuthNZ_SQLite/test_entitlements_migrations_sqlite.py`
- Test: `tldw_Server_API/tests/AuthNZ/test_entitlements_migrations_pg.py`

**Step 1: Write failing migration tests**

```python
def test_sqlite_entitlement_tables_created_after_authnz_migrations(...):
    assert "route_entitlement_policies" in table_names
    assert "route_entitlement_audit" in table_names
```

**Step 2: Run tests to verify fail**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/AuthNZ_SQLite/test_entitlements_migrations_sqlite.py`
Expected: FAIL (tables missing).

**Step 3: Implement migrations**

- Add next SQLite migration version in `migrations.py` for entitlement policy + audit tables and indexes.
- Add PostgreSQL ensure helper in `pg_migrations_extra.py` for equivalent tables/indexes.
- Invoke PG ensure helper from startup where other AuthNZ PG ensure calls occur.

**Step 4: Run tests to verify pass**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/AuthNZ_SQLite/test_entitlements_migrations_sqlite.py
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/AuthNZ/test_entitlements_migrations_pg.py
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/tests/AuthNZ_SQLite/test_entitlements_migrations_sqlite.py \
  tldw_Server_API/tests/AuthNZ/test_entitlements_migrations_pg.py
git commit -m "feat(authnz): add route entitlement tables for sqlite and postgres"
```

### Task 3: Add Repository + Deterministic Resolver

**Files:**
- Create: `tldw_Server_API/app/core/AuthNZ/repos/entitlements_repo.py`
- Create: `tldw_Server_API/app/services/entitlements_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/entitlements.py`
- Test: `tldw_Server_API/tests/Entitlements/test_entitlements_resolver.py`

**Step 1: Write failing resolver tests**

```python
def test_deny_wins_over_allow():
    assert resolve_decision([allow_rule, deny_rule]) == "deny"


def test_deterministic_tiebreak_order():
    assert resolve_trace(rules) == expected_rule_ids
```

**Step 2: Run tests to verify fail**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_entitlements_resolver.py`
Expected: FAIL.

**Step 3: Implement repo and resolver**

- Implement policy fetch/query helpers by scope and subject.
- Implement deterministic precedence tuple and deny-wins merge.
- Wire endpoint to resolved payload + stable version hash.

**Step 4: Run tests to verify pass**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_entitlements_resolver.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/repos/entitlements_repo.py \
  tldw_Server_API/app/services/entitlements_service.py \
  tldw_Server_API/app/api/v1/endpoints/entitlements.py \
  tldw_Server_API/tests/Entitlements/test_entitlements_resolver.py
git commit -m "feat(entitlements): add deterministic resolver and repository"
```

### Task 4: Add Admin Policy CRUD + Simulate + Audit Requirements

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin_entitlements.py`
- Modify: `tldw_Server_API/app/services/admin_scope_service.py`
- Modify: `tldw_Server_API/app/services/entitlements_service.py`
- Test: `tldw_Server_API/tests/Entitlements/test_admin_entitlements_scope.py`
- Test: `tldw_Server_API/tests/Entitlements/test_admin_entitlements_simulate.py`

**Step 1: Write failing scope and simulation tests**

```python
def test_org_admin_cannot_write_platform_scope(client, org_admin_headers):
    resp = client.post("/api/v1/admin/entitlements/policies", json=platform_payload, headers=org_admin_headers)
    assert resp.status_code == 403


def test_simulate_returns_impact_preview(client, admin_headers):
    resp = client.post("/api/v1/admin/entitlements/simulate", json=payload, headers=admin_headers)
    assert resp.status_code == 200
    assert "affected_users_count" in resp.json()
```

**Step 2: Run tests to verify fail**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_admin_entitlements_scope.py
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_admin_entitlements_simulate.py
```
Expected: FAIL.

**Step 3: Implement CRUD + simulate + audit fields**

- Add list/create/update/delete policy endpoints.
- Add `POST /admin/entitlements/simulate` impact preview.
- Enforce required `reason` field; persist audit metadata (`actor`, before/after, scope, route_id).
- Enforce scope boundaries via `admin_scope_service` for platform/org/team/user operations.

**Step 4: Run tests to verify pass**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_admin_entitlements_scope.py
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_admin_entitlements_simulate.py
```
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/admin_entitlements.py \
  tldw_Server_API/app/services/admin_scope_service.py \
  tldw_Server_API/app/services/entitlements_service.py \
  tldw_Server_API/tests/Entitlements/test_admin_entitlements_scope.py \
  tldw_Server_API/tests/Entitlements/test_admin_entitlements_simulate.py
git commit -m "feat(entitlements-admin): add scoped CRUD, simulation, and audit fields"
```

### Task 5: Add Backend Enforcement Dependency for Sensitive Route/API Bundles

**Files:**
- Create: `tldw_Server_API/app/core/AuthNZ/route_entitlement_catalog.py`
- Modify: `tldw_Server_API/app/api/v1/API_Deps/auth_deps.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/admin_system.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/admin_user.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mlx.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/llamacpp.py`
- Test: `tldw_Server_API/tests/Entitlements/test_route_entitlement_enforcement.py`

**Step 1: Write failing enforcement tests**

```python
def test_denied_route_entitlement_blocks_admin_system_endpoint(client, denied_admin_headers):
    resp = client.get("/api/v1/admin/system/stats", headers=denied_admin_headers)
    assert resp.status_code == 403
```

**Step 2: Run tests to verify fail**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_route_entitlement_enforcement.py`
Expected: FAIL.

**Step 3: Implement enforcement dependency and mappings**

- Add `require_route_entitlement(route_id)` dependency helper.
- Add route-to-endpoint catalog mappings for v1 sensitive bundles:
  - `settings.admin.server`
  - `settings.admin.mlx`
  - `settings.admin.llamacpp`
- Attach dependency to corresponding endpoint handlers.

**Step 4: Run tests to verify pass**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_route_entitlement_enforcement.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/route_entitlement_catalog.py \
  tldw_Server_API/app/api/v1/API_Deps/auth_deps.py \
  tldw_Server_API/app/api/v1/endpoints/admin/admin_system.py \
  tldw_Server_API/app/api/v1/endpoints/admin/admin_user.py \
  tldw_Server_API/app/api/v1/endpoints/mlx.py \
  tldw_Server_API/app/api/v1/endpoints/llamacpp.py \
  tldw_Server_API/tests/Entitlements/test_route_entitlement_enforcement.py
git commit -m "feat(entitlements): enforce sensitive admin endpoint bundles by route entitlement"
```

### Task 6: Add Route ID Manifest for Options + Sidepanel

**Files:**
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Create: `apps/packages/ui/src/routes/route-entitlement-manifest.ts`
- Test: `apps/packages/ui/src/routes/__tests__/route-entitlement-manifest.test.ts`

**Step 1: Write failing route-ID contract tests**

```ts
it("ensures every option route has a stable routeId", () => {
  expect(missingOptionRouteIds).toEqual([])
})

it("ensures every sidepanel route has a stable routeId", () => {
  expect(missingSidepanelRouteIds).toEqual([])
})
```

**Step 2: Run test to verify fail**

Run: `bunx vitest run apps/packages/ui/src/routes/__tests__/route-entitlement-manifest.test.ts`
Expected: FAIL.

**Step 3: Implement route IDs + manifest export**

- Add `routeId` field to shared route definition type.
- Populate route IDs for all option and sidepanel routes.
- Export typed manifest keyed by `routeId`.

**Step 4: Run test to verify pass**

Run: `bunx vitest run apps/packages/ui/src/routes/__tests__/route-entitlement-manifest.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/route-registry.tsx \
  apps/packages/ui/src/routes/route-entitlement-manifest.ts \
  apps/packages/ui/src/routes/__tests__/route-entitlement-manifest.test.ts
git commit -m "feat(ui-routes): add stable route ids for options and sidepanel"
```

### Task 7: Add Client Entitlement Service + Combined Gating

**Files:**
- Create: `apps/packages/ui/src/services/tldw/route-entitlements.ts`
- Modify: `apps/packages/ui/src/routes/app-route.tsx`
- Modify: `apps/packages/ui/src/components/Layouts/settings-nav.ts`
- Test: `apps/packages/ui/src/routes/__tests__/route-entitlement-gating.test.tsx`

**Step 1: Write failing UI gating tests**

```ts
it("hides denied routes from settings nav", async () => {
  expect(screen.queryByText(/Server Admin/i)).not.toBeInTheDocument()
})

it("redirects when user deep-links to denied route", async () => {
  expect(mockNavigate).toHaveBeenCalledWith("/settings")
})
```

**Step 2: Run test to verify fail**

Run: `bunx vitest run apps/packages/ui/src/routes/__tests__/route-entitlement-gating.test.tsx`
Expected: FAIL.

**Step 3: Implement client service + gating composition**

- Fetch `/api/v1/entitlements/me/routes` with local TTL cache.
- Compose route visibility as `capability && entitlement`.
- Apply checks in nav construction and route element resolution.

**Step 4: Run test to verify pass**

Run: `bunx vitest run apps/packages/ui/src/routes/__tests__/route-entitlement-gating.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/route-entitlements.ts \
  apps/packages/ui/src/routes/app-route.tsx \
  apps/packages/ui/src/components/Layouts/settings-nav.ts \
  apps/packages/ui/src/routes/__tests__/route-entitlement-gating.test.tsx
git commit -m "feat(ui-authz): combine capability and entitlement route gating"
```

### Task 8: Add Resilience Mode + Revocation Freshness Mechanics

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/route-entitlements.ts`
- Modify: `apps/packages/ui/src/routes/app-route.tsx`
- Modify: `tldw_Server_API/app/api/v1/endpoints/entitlements.py`
- Test: `apps/packages/ui/src/routes/__tests__/route-entitlement-resilience.test.tsx`
- Test: `tldw_Server_API/tests/Entitlements/test_entitlements_etag_versioning.py`

**Step 1: Write failing resilience/versioning tests**

```ts
it("allows only safe routes when entitlement fetch fails and cache is stale", () => {
  expect(isRouteAccessible("/settings")).toBe(true)
  expect(isRouteAccessible("/settings/admin/server")).toBe(false)
})
```

```python
def test_entitlements_endpoint_returns_304_on_if_none_match(client, auth_headers):
    first = client.get("/api/v1/entitlements/me/routes", headers=auth_headers)
    etag = first.headers["ETag"]
    second = client.get("/api/v1/entitlements/me/routes", headers={**auth_headers, "If-None-Match": etag})
    assert second.status_code == 304
```

**Step 2: Run tests to verify fail**

Run:
```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/route-entitlement-resilience.test.tsx
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_entitlements_etag_versioning.py
```
Expected: FAIL.

**Step 3: Implement resilience + revocation freshness**

- Safe-route allowlist for fail-closed fallback.
- Stale-cache handling + retry banner state.
- Backend `version` + ETag consistency for polling.
- Client refresh strategy: periodic revalidation + invalidation on auth/org/team context changes.

**Step 4: Run tests to verify pass**

Run:
```bash
bunx vitest run apps/packages/ui/src/routes/__tests__/route-entitlement-resilience.test.tsx
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_entitlements_etag_versioning.py
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/route-entitlements.ts \
  apps/packages/ui/src/routes/app-route.tsx \
  tldw_Server_API/app/api/v1/endpoints/entitlements.py \
  apps/packages/ui/src/routes/__tests__/route-entitlement-resilience.test.tsx \
  tldw_Server_API/tests/Entitlements/test_entitlements_etag_versioning.py
git commit -m "feat(entitlements): add resilience mode and etag-based revocation refresh"
```

### Task 9: Verification, Security Check, and Documentation

**Files:**
- Modify: `Docs/AuthNZ/AUTHNZ_PERMISSION_MATRIX.md`
- Modify: `Docs/Plans/2026-03-04-admin-route-entitlements-design.md`
- Test outputs: `/tmp/bandit_admin_route_entitlements.json`

**Step 1: Run focused backend and frontend suites**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements tldw_Server_API/tests/AuthNZ_SQLite/test_entitlements_migrations_sqlite.py tldw_Server_API/tests/AuthNZ/test_entitlements_migrations_pg.py
bunx vitest run apps/packages/ui/src/routes/__tests__/route-entitlement-manifest.test.ts apps/packages/ui/src/routes/__tests__/route-entitlement-gating.test.tsx apps/packages/ui/src/routes/__tests__/route-entitlement-resilience.test.tsx
```
Expected: PASS.

**Step 2: Run Bandit on touched backend scope**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/entitlements.py tldw_Server_API/app/api/v1/endpoints/admin_entitlements.py tldw_Server_API/app/services/entitlements_service.py tldw_Server_API/app/core/AuthNZ/repos/entitlements_repo.py tldw_Server_API/app/core/AuthNZ/route_entitlement_catalog.py -f json -o /tmp/bandit_admin_route_entitlements.json`
Expected: No new high-severity findings in touched code.

**Step 3: Update docs**

- Document new API contracts, scope matrix details, enforcement caveats, and revocation behavior.
- Keep design doc and AuthNZ matrix consistent with implemented endpoint paths/dependencies.

**Step 4: Commit**

```bash
git add Docs/AuthNZ/AUTHNZ_PERMISSION_MATRIX.md \
  Docs/Plans/2026-03-04-admin-route-entitlements-design.md
git commit -m "docs(authz): finalize route entitlement contracts and operations notes"
```
