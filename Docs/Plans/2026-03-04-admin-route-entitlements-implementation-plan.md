# Admin Route Entitlements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement route-level entitlement enforcement across WebUI and extension so admins can allow/deny specific pages per scope with deny-wins and fail-closed behavior.

**Architecture:** Add a backend entitlement policy surface (`/api/v1/entitlements/me/routes` + admin CRUD), enforce scoped admin writes via shared admin scope services, and extend frontend route metadata with canonical `route_id`. Client route rendering combines server capability flags and entitlement decisions and enforces both nav hiding and direct route blocking.

**Tech Stack:** FastAPI, Pydantic, AuthNZ scope services, SQLite/Postgres migrations, React Router, TypeScript, Vitest, Pytest.

---

### Task 1: Add Entitlement Schemas and Router Skeleton

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/entitlements_schemas.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/entitlements.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Entitlements/test_entitlements_contract.py`

**Step 1: Write the failing test**

```python
def test_get_entitlements_me_routes_contract(client, auth_headers):
    resp = client.get("/api/v1/entitlements/me/routes", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "version" in body
    assert "routes" in body
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_entitlements_contract.py::test_get_entitlements_me_routes_contract`
Expected: FAIL (endpoint missing).

**Step 3: Write minimal implementation**

- Add Pydantic response models for route decisions.
- Add `GET /entitlements/me/routes` returning placeholder deterministic payload.
- Include router in `main.py` under `/api/v1`.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_entitlements_contract.py::test_get_entitlements_me_routes_contract`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/entitlements_schemas.py \
  tldw_Server_API/app/api/v1/endpoints/entitlements.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/tests/Entitlements/test_entitlements_contract.py
git commit -m "feat(entitlements): add me routes contract endpoint scaffold"
```

### Task 2: Add Policy Storage + Deterministic Resolver

**Files:**
- Create: `tldw_Server_API/app/services/entitlements_service.py`
- Create: `tldw_Server_API/app/core/AuthNZ/repos/entitlements_repo.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/entitlements.py`
- Test: `tldw_Server_API/tests/Entitlements/test_entitlements_resolver.py`

**Step 1: Write failing resolver tests**

```python
def test_deny_wins_over_allow():
    assert resolve_decision([allow_rule, deny_rule]) == "deny"


def test_deterministic_tiebreak_order():
    assert resolve_trace(rules) == expected_rule_ids
```

**Step 2: Run tests to verify failures**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_entitlements_resolver.py`
Expected: FAIL.

**Step 3: Implement minimal resolver + repo methods**

- Persist policy records with scope/effect/route_id.
- Implement precedence tuple and deny-wins logic.
- Wire `/entitlements/me/routes` to resolver.

**Step 4: Run tests to verify pass**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_entitlements_resolver.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/entitlements_service.py \
  tldw_Server_API/app/core/AuthNZ/repos/entitlements_repo.py \
  tldw_Server_API/app/api/v1/endpoints/entitlements.py \
  tldw_Server_API/tests/Entitlements/test_entitlements_resolver.py
git commit -m "feat(entitlements): add deterministic deny-wins policy resolver"
```

### Task 3: Add Admin CRUD + Scope Enforcement

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/admin/admin_entitlements.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/__init__.py`
- Modify: `tldw_Server_API/app/services/admin_scope_service.py`
- Test: `tldw_Server_API/tests/Entitlements/test_admin_entitlements_scope.py`

**Step 1: Write failing scope tests**

```python
def test_org_admin_cannot_write_platform_scope(client, org_admin_headers):
    resp = client.post("/api/v1/admin/entitlements/policies", json=platform_payload, headers=org_admin_headers)
    assert resp.status_code == 403
```

**Step 2: Run tests to verify failures**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_admin_entitlements_scope.py`
Expected: FAIL.

**Step 3: Implement admin endpoints with scope checks**

- Add list/create/update/delete endpoints.
- Reuse `admin_scope_service` checks for org/team boundaries.
- Require `reason` on write payloads.

**Step 4: Run tests to verify pass**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements/test_admin_entitlements_scope.py`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/admin/admin_entitlements.py \
  tldw_Server_API/app/api/v1/endpoints/admin/__init__.py \
  tldw_Server_API/app/services/admin_scope_service.py \
  tldw_Server_API/tests/Entitlements/test_admin_entitlements_scope.py
git commit -m "feat(admin): add scoped entitlements policy management"
```

### Task 4: Add Route ID Manifest to Frontend Routing

**Files:**
- Modify: `apps/packages/ui/src/routes/route-registry.tsx`
- Create: `apps/packages/ui/src/routes/route-entitlement-manifest.ts`
- Test: `apps/packages/ui/src/routes/__tests__/route-entitlement-manifest.test.ts`

**Step 1: Write failing contract test**

```ts
it("ensures every option route has a stable routeId", () => {
  expect(missingRouteIds).toEqual([])
})
```

**Step 2: Run test to verify fail**

Run: `bunx vitest run apps/packages/ui/src/routes/__tests__/route-entitlement-manifest.test.ts`
Expected: FAIL.

**Step 3: Implement route IDs + manifest export**

- Add `routeId` field to route definition type.
- Populate every route with stable `routeId`.
- Export manifest helper map keyed by `routeId`.

**Step 4: Run test to verify pass**

Run: `bunx vitest run apps/packages/ui/src/routes/__tests__/route-entitlement-manifest.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/route-registry.tsx \
  apps/packages/ui/src/routes/route-entitlement-manifest.ts \
  apps/packages/ui/src/routes/__tests__/route-entitlement-manifest.test.ts
git commit -m "feat(ui-routes): add stable route ids and entitlement manifest"
```

### Task 5: Add Client Entitlement Service + Combined Gating

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

**Step 3: Implement service and combined checks**

- Fetch `/api/v1/entitlements/me/routes` with TTL/version cache.
- In route shell, evaluate `capability && entitlement`.
- Fail closed on unknown entitlements except safe-route allowlist.

**Step 4: Run test to verify pass**

Run: `bunx vitest run apps/packages/ui/src/routes/__tests__/route-entitlement-gating.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/route-entitlements.ts \
  apps/packages/ui/src/routes/app-route.tsx \
  apps/packages/ui/src/components/Layouts/settings-nav.ts \
  apps/packages/ui/src/routes/__tests__/route-entitlement-gating.test.tsx
git commit -m "feat(ui-authz): enforce combined capability and entitlement gating"
```

### Task 6: Add Resilience Mode + Revocation Refresh

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/route-entitlements.ts`
- Modify: `apps/packages/ui/src/routes/app-route.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/route-entitlement-resilience.test.tsx`

**Step 1: Write failing resilience tests**

```ts
it("allows only safe routes when entitlement fetch fails and cache is stale", () => {
  expect(isRouteAccessible("/settings")).toBe(true)
  expect(isRouteAccessible("/settings/admin/server")).toBe(false)
})
```

**Step 2: Run test to verify fail**

Run: `bunx vitest run apps/packages/ui/src/routes/__tests__/route-entitlement-resilience.test.tsx`
Expected: FAIL.

**Step 3: Implement resilience and refresh policy**

- Safe-route allowlist in client gate.
- Stale-cache behavior + retry banner state.
- Version polling (30-60s) and invalidation on auth/scope changes.

**Step 4: Run test to verify pass**

Run: `bunx vitest run apps/packages/ui/src/routes/__tests__/route-entitlement-resilience.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/route-entitlements.ts \
  apps/packages/ui/src/routes/app-route.tsx \
  apps/packages/ui/src/routes/__tests__/route-entitlement-resilience.test.tsx
git commit -m "feat(ui-authz): add fail-closed resilience mode and revocation refresh"
```

### Task 7: Verification, Security Check, and Docs

**Files:**
- Modify: `Docs/AuthNZ/AUTHNZ_PERMISSION_MATRIX.md`
- Modify: `Docs/Plans/2026-03-04-admin-route-entitlements-design.md`
- Test outputs: `/tmp/bandit_admin_route_entitlements.json`

**Step 1: Run backend and frontend focused tests**

Run:
```bash
source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Entitlements
bunx vitest run apps/packages/ui/src/routes/__tests__/route-entitlement-manifest.test.ts apps/packages/ui/src/routes/__tests__/route-entitlement-gating.test.tsx apps/packages/ui/src/routes/__tests__/route-entitlement-resilience.test.tsx
```
Expected: PASS.

**Step 2: Run Bandit on touched backend scope**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/entitlements.py tldw_Server_API/app/api/v1/endpoints/admin/admin_entitlements.py tldw_Server_API/app/services/entitlements_service.py -f json -o /tmp/bandit_admin_route_entitlements.json`
Expected: No new high-severity findings in touched code.

**Step 3: Update docs**

- Document new APIs and scope matrix.
- Add revocation SLA and resilience behavior notes.

**Step 4: Commit**

```bash
git add Docs/AuthNZ/AUTHNZ_PERMISSION_MATRIX.md \
  Docs/Plans/2026-03-04-admin-route-entitlements-design.md
git commit -m "docs(authz): document route entitlement policy model and rollout"
```
