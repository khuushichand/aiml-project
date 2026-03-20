# Governance Pack Upgrade And Rebase Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add transactional, same-scope governance-pack upgrades that preserve immutable imported base objects, rebind explicit dependents safely, and keep runtime resolution limited to the active installed pack version.

**Architecture:** Extend the existing governance-pack import model with explicit active/superseded install state, an upgrade planner keyed by stable `source_object_id`, and a transaction-backed executor that materializes a new immutable base set and atomically cuts over. Reuse the existing MCP Hub repo/service/resolver boundaries instead of inventing a second policy plane.

**Tech Stack:** FastAPI, Pydantic, SQLite/PostgreSQL AuthNZ repo layer, MCP Hub services, React/TypeScript MCP Hub UI, pytest, vitest

---

### Task 1: Add Governance-Pack Install State And Upgrade Lineage Schema

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_repo.py`

**Step 1: Write the failing test**

Add repo tests that expect:
- governance-pack rows to expose `is_active_install`
- governance-pack rows to expose `superseded_by_governance_pack_id`
- upgrade-lineage rows to be persisted and listable

Example assertions:

```python
created = await repo.create_governance_pack(...)
assert created["is_active_install"] is True
assert created["superseded_by_governance_pack_id"] is None

upgrade = await repo.create_governance_pack_upgrade(...)
assert upgrade["from_pack_version"] == "1.0.0"
assert upgrade["to_pack_version"] == "1.1.0"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_repo.py -q
```

Expected: FAIL because the repo and schema do not expose the new install-state and lineage fields yet.

**Step 3: Write minimal implementation**

Implement:
- migration updates for `mcp_governance_packs`
  - `is_active_install`
  - `superseded_by_governance_pack_id`
  - optional `installed_from_upgrade_id`
- new `mcp_governance_pack_upgrades` table
- repo create/get/list helpers for install-state and upgrade-lineage rows
- row normalizers for the new fields

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_repo.py
git commit -m "feat: add governance pack install state schema"
```

### Task 2: Make Governance-Pack Import And Runtime Resolution Respect Active Installs

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_service.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_policy_resolver.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_service.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py`

**Step 1: Write the failing test**

Add tests that prove:
- newly imported governance packs default to `is_active_install=True`
- superseded governance-pack objects are excluded from effective-policy resolution
- list/detail APIs can still show inactive pack history without making inactive objects live

Example assertions:

```python
effective = await resolver.get_effective_policy(...)
assert active_profile_name in effective["sources"]
assert superseded_profile_name not in effective["sources"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py -q
```

Expected: FAIL because runtime filtering by active governance-pack install does not exist yet.

**Step 3: Write minimal implementation**

Implement:
- import path sets `is_active_install=True` on first install
- repo list helpers for active governance packs and active governance-pack objects
- resolver-side filtering so superseded governance-pack-owned profiles/approvals/assignments do not contribute to live effective policy
- detail/list methods preserve history visibility without using inactive rows in live policy

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/app/services/mcp_hub_policy_resolver.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py
git commit -m "feat: filter governance policy to active installs"
```

### Task 3: Build The Upgrade Planner And Plan Fingerprints

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_service.py`

**Step 1: Write the failing test**

Add dry-run upgrade planner tests for:
- same-pack newer-version acceptance
- older/equal version rejection
- cross-scope rejection
- removed imported object with direct dependent conflict
- modified imported object with dependent semantic conflict
- adapter-state fingerprint and planner-input fingerprint in the plan response

Example assertions:

```python
plan = await service.dry_run_upgrade(...)
assert plan["upgradeable"] is False
assert "structural_conflicts" in plan
assert plan["adapter_state_fingerprint"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_service.py -q
```

Expected: FAIL because upgrade dry-run and plan objects do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- Pydantic schemas for dry-run upgrade request/response
- semantic-version comparison helper
- upgrade-plan builder keyed by stable `source_object_id`
- dependency-impact collector for imported approval/profile/assignment runtime objects
- planner-input fingerprint and adapter-state fingerprint generation

Keep v1 conflict logic explicit:
- structural conflicts
- behavioral conflicts on explicit dependents
- warnings

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_service.py
git commit -m "feat: add governance pack upgrade planner"
```

### Task 4: Add Transaction-Backed Upgrade Execution And Dependent Rebinding

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_service.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_service.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_repo.py`

**Step 1: Write the failing test**

Add executor tests that prove:
- execute-upgrade fails on stale fingerprints
- successful upgrade creates a new immutable base set
- direct dependents are rebound to the new imported object ids
- old pack is marked superseded and new pack is marked active
- transaction failure leaves the old version active

Example assertions:

```python
result = await service.execute_upgrade(...)
assert result["from_pack_version"] == "1.0.0"
assert result["to_pack_version"] == "1.1.0"
assert rebound_assignment["profile_id"] == new_profile_id
assert old_pack["superseded_by_governance_pack_id"] == new_pack["id"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_repo.py -q
```

Expected: FAIL because execute-upgrade, rebinding, and transaction semantics do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- repo transaction helper if missing on the governance-pack path
- execute-upgrade service method
- deterministic old-id -> new-id rebinding map from `source_object_id`
- lineage row creation in `mcp_governance_pack_upgrades`
- active/superseded state transition
- materialization strategy that avoids imported-name uniqueness collisions

Keep cutover atomic. Do not rely on best-effort rollback.

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_repo.py
git commit -m "feat: execute governance pack upgrades transactionally"
```

### Task 5: Expose Upgrade Dry-Run, Execute, And History APIs

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_governance_pack_service.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management.py`

**Step 1: Write the failing test**

Add endpoint tests for:
- `POST /governance-packs/dry-run-upgrade`
- `POST /governance-packs/execute-upgrade`
- `GET /governance-packs/{id}/upgrade-history`
- correct 400/409 behavior for structural conflicts and stale plans
- grant-authority and scope checks matching existing governance-pack mutation rules

Example assertions:

```python
response = client.post("/api/v1/mcp-hub/governance-packs/dry-run-upgrade", json=payload)
assert response.status_code == 200
assert response.json()["upgradeable"] is False
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management.py -q
```

Expected: FAIL because the upgrade endpoints and schemas do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- request/response schemas for dry-run, execute, and history
- endpoint wiring to governance-pack service
- conflict/status-code mapping
- scope and grant-authority checks consistent with existing pack import endpoints

**Step 4: Run test to verify it passes**

Run the same pytest command and confirm PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management.py
git commit -m "feat: add governance pack upgrade APIs"
```

### Task 6: Add MCP Hub Upgrade UI And History Visibility

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/GovernancePacksTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx`

**Step 1: Write the failing test**

Add UI tests for:
- rendering active/inactive install state
- opening a dry-run upgrade modal
- showing added/removed/modified object summaries
- blocking execute when conflicts exist
- showing upgrade history entries

Example assertions:

```tsx
expect(screen.getByText("Upgrade history")).toBeInTheDocument()
expect(screen.getByRole("button", { name: /execute upgrade/i })).toBeDisabled()
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx
```

Expected: FAIL because upgrade UI elements and client methods do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- client methods/types for upgrade dry-run, execute, and history
- Governance Packs tab updates for:
  - active/inactive install labels
  - dry-run upgrade workflow
  - conflict/warning rendering
  - history display

Keep v1 manual-only: show the blocking objects and actions required, but do not add auto-repair controls.

**Step 4: Run test to verify it passes**

Run the same vitest command and confirm PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/mcp-hub.ts \
  apps/packages/ui/src/components/Option/MCPHub/GovernancePacksTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx
git commit -m "feat: add governance pack upgrade UI"
```

### Task 7: Run Focused Regression, Security, And Final Review

**Files:**
- Verify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_repo.py`
- Verify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_service.py`
- Verify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py`
- Verify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_management.py`
- Verify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx`
- Verify: touched backend governance-pack files with Bandit

**Step 1: Run focused backend regression**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_repo.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_governance_pack_service.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_resolver.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_management.py -q
```

Expected: PASS.

**Step 2: Run focused UI regression**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernancePacksTab.test.tsx
```

Expected: PASS.

**Step 3: Run Bandit on touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/services/mcp_hub_governance_pack_service.py \
  tldw_Server_API/app/services/mcp_hub_policy_resolver.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py \
  -f json -o /tmp/bandit_governance_pack_upgrade.json
```

Expected: `0 issues` in changed code.

**Step 4: Run diff hygiene**

Run:

```bash
git diff --check
```

Expected: no output.

**Step 5: Request code review and commit any final fixups**

Use `superpowers:requesting-code-review`, address findings, then commit:

```bash
git add <touched files>
git commit -m "fix: finalize governance pack upgrade workflow"
```
