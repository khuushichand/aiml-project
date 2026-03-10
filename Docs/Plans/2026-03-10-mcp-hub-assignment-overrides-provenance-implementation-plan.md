# MCP Hub Assignment Overrides And Provenance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a single assignment-bound override record, nested override APIs, effective-policy provenance, and MCP Hub assignment UI that clearly separates base policy from override policy.

**Architecture:** Extend the existing MCP Hub assignment model with a 1:1 `mcp_policy_overrides` record keyed by `assignment_id`, expose it through nested assignment endpoints, and update the resolver to compute `profile -> assignment inline -> assignment override` with field-level provenance. Reuse the current `PolicyDocumentEditor` for both layers and keep assignment list responses lightweight by including override summary fields.

**Tech Stack:** FastAPI, existing AuthNZ repo/service stack, SQLite/Postgres migrations, React, Ant Design, Vitest, pytest, Bandit

---

### Task 1: Add the failing backend tests for override storage and nested APIs

**Files:**
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py`

**Step 1: Write the failing repo/service-facing tests**

Add tests for:

- creating one override for an assignment
- rejecting a second override for the same assignment
- deleting an assignment removes its override
- inactive overrides are ignored

**Step 2: Run the new override tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py -v
```

Expected: FAIL because override repo/service support does not exist yet.

**Step 3: Extend API tests for nested override routes**

Add failing tests for:

- `GET /api/v1/mcp/hub/policy-assignments/{assignment_id}/override`
- `PUT /api/v1/mcp/hub/policy-assignments/{assignment_id}/override`
- `DELETE /api/v1/mcp/hub/policy-assignments/{assignment_id}/override`

Also add assertions that assignment list rows include:

- `has_override`
- `override_active`

**Step 4: Run the focused API tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -k override -v
```

Expected: FAIL because the nested override routes and response fields do not exist yet.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py
git commit -m "test: add MCP Hub assignment override coverage"
```

### Task 2: Implement repo support and enforce the 1:1 override model

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Test: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py`

**Step 1: Add repo CRUD for policy overrides**

Implement methods to:

- get override by assignment id
- upsert override by assignment id
- delete override by assignment id

Normalize `override_policy_document_json` the same way other MCP Hub policy blobs are normalized.

**Step 2: Add or verify unique enforcement on `assignment_id`**

Ensure both SQLite and Postgres schema paths enforce a unique `assignment_id` for `mcp_policy_overrides`.

**Step 3: Add assignment summary enrichment in repo list/get paths**

When listing assignments, include:

- `has_override`
- `override_id`
- `override_active`
- `override_updated_at`

Prefer a compact join or follow-up fetch that does not change assignment semantics.

**Step 4: Run the override repo tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py tldw_Server_API/app/core/AuthNZ/migrations.py tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py
git commit -m "feat: add MCP Hub policy override storage"
```

### Task 3: Add service and nested API endpoints for assignment overrides

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`

**Step 1: Add service methods for assignment-bound overrides**

Implement:

- get assignment override
- upsert assignment override
- delete assignment override

On assignment delete, explicitly remove the override or ensure coordinated cleanup and audit emission.

**Step 2: Add nested override request and response schemas**

Add models for:

- override upsert request
- override response
- assignment override summary fields

**Step 3: Add nested routes under assignments**

Implement:

- `GET /api/v1/mcp/hub/policy-assignments/{assignment_id}/override`
- `PUT /api/v1/mcp/hub/policy-assignments/{assignment_id}/override`
- `DELETE /api/v1/mcp/hub/policy-assignments/{assignment_id}/override`

Apply the same mutation and grant-authority patterns already used in MCP Hub.

**Step 4: Run the focused API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -k override -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_service.py tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py
git commit -m "feat: add nested MCP Hub override APIs"
```

### Task 4: Extend the resolver with assignment override application and provenance

**Files:**
- Modify: `tldw_Server_API/app/services/mcp_hub_policy_resolver.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`

**Step 1: Add failing provenance assertions**

Write tests that expect:

- merge order `profile -> inline -> override`
- provenance entries for fields contributed by profile, inline policy, and override
- `effect = merged` for list fields
- `effect = replaced` for overwritten scalar fields

**Step 2: Run the resolver tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py -k provenance -v
```

Expected: FAIL because provenance is not emitted yet.

**Step 3: Implement provenance in the resolver**

Extend resolver output with a compact `provenance` array. Keep the existing `sources` array unchanged.

Do not build a per-item diff engine. Emit field-level provenance only.

**Step 4: Reuse current merge semantics**

Apply the override using the same merge logic as the rest of the resolver so behavior stays deterministic and unsurprising.

**Step 5: Run the override and API suites**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add tldw_Server_API/app/services/mcp_hub_policy_resolver.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py
git commit -m "feat: add MCP Hub policy provenance"
```

### Task 5: Enforce broadened-access checks for override writes

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_policy_resolver.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py`

**Step 1: Add the failing grant-authority tests**

Cover this case:

- base assignment is restrictive
- proposed override broadens effective access
- write is rejected without matching grant authority
- write succeeds when grant authority is present

**Step 2: Run the focused tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -k grant -v
```

Expected: FAIL for the new override-specific broadened-access cases.

**Step 3: Implement effective-base comparison**

Before accepting override writes:

1. resolve effective assignment state without override
2. simulate merge with the proposed override
3. compute broadened capability/tool reach
4. apply grant-authority checks to the broadened delta

Keep the implementation simple and deterministic. Do not attempt deep semantic analysis beyond current MCP Hub policy fields.

**Step 4: Run the focused API suite**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py tldw_Server_API/app/services/mcp_hub_policy_resolver.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py
git commit -m "feat: validate broadened MCP Hub overrides"
```

### Task 6: Add failing frontend tests for override editing and provenance preview

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx`
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`

**Step 1: Add failing assignment-tab tests**

Cover:

- assignment rows show override presence
- editor loads base policy and override separately
- effective preview renders provenance

**Step 2: Add failing persona-summary tests**

Cover:

- summary shows override-active state
- summary remains compact and does not attempt full provenance output

**Step 3: Run the focused frontend tests to verify they fail**

Run from `apps/packages/ui`:

```bash
./node_modules/.bin/vitest run src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx
```

Expected: FAIL because override DTOs and rendering do not exist yet.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx apps/packages/ui/src/services/tldw/mcp-hub.ts
git commit -m "test: add MCP Hub override UI coverage"
```

### Task 7: Implement assignment override UI and effective-policy explainability

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PolicyDocumentEditor.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx`

**Step 1: Add typed client support for overrides and provenance**

Extend client DTOs and request helpers for:

- assignment override CRUD
- assignment override summary fields
- effective-policy provenance

**Step 2: Update the assignments UI**

Add:

- override presence badges in list rows
- separate `Base Assignment Policy` and `Assignment Override` cards
- explicit helper text so users know which layer they are editing

**Step 3: Add effective-preview provenance rendering**

Show compact field-level provenance grouped under the effective preview.

Keep the display readable. Do not render a noisy diff table.

**Step 4: Update the persona summary**

Add a compact override-active indicator and keep the rest of the summary lightweight.

**Step 5: Run the focused UI suite**

Run:

```bash
cd apps/packages/ui && ./node_modules/.bin/vitest run src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx
```

Expected: PASS.

**Step 6: Commit**

```bash
git add apps/packages/ui/src/services/tldw/mcp-hub.ts apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx apps/packages/ui/src/components/Option/MCPHub/PolicyDocumentEditor.tsx apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx apps/packages/ui/src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx
git commit -m "feat: add MCP Hub override editing and provenance UI"
```

### Task 8: Run verification and security checks on the full touched scope

**Files:**
- Verify: `tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py`
- Verify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Verify: `tldw_Server_API/app/services/mcp_hub_policy_resolver.py`
- Verify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Verify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Verify: `apps/packages/ui/src/components/Option/MCPHub/PolicyAssignmentsTab.tsx`
- Verify: `apps/packages/ui/src/components/Option/MCPHub/PersonaPolicySummary.tsx`

**Step 1: Run backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_overrides.py tldw_Server_API/tests/MCP_unified/test_mcp_hub_policy_api.py -v
```

Expected: PASS.

**Step 2: Run frontend verification**

Run:

```bash
cd apps/packages/ui && ./node_modules/.bin/vitest run src/components/Option/MCPHub/__tests__/PolicyAssignmentsTab.test.tsx src/components/Option/MCPHub/__tests__/PersonaPolicySummary.test.tsx
```

Expected: PASS.

**Step 3: Run Bandit on touched backend files**

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/AuthNZ/repos/mcp_hub_repo.py tldw_Server_API/app/services/mcp_hub_service.py tldw_Server_API/app/services/mcp_hub_policy_resolver.py tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py -f json -o /tmp/bandit_mcp_hub_overrides.json
```

Expected: JSON written with no new findings in touched code.

**Step 4: Commit**

```bash
git add .
git commit -m "test: verify MCP Hub override and provenance slice"
```

### Task 9: Prepare the checkpoint for review

**Files:**
- Review: `Docs/Plans/2026-03-10-mcp-hub-assignment-overrides-provenance-design.md`
- Review: `Docs/Plans/2026-03-10-mcp-hub-assignment-overrides-provenance-implementation-plan.md`

**Step 1: Review the final diff**

Run:

```bash
git status --short
git diff --stat HEAD~1..HEAD
```

Expected: clean worktree and a focused override/provenance diff.

**Step 2: Summarize remaining follow-up work**

Document what is still out of scope:

- credential bindings
- path-scoped enforcement
- richer diff visualization

**Step 3: Commit any final doc adjustments**

```bash
git add Docs/Plans/2026-03-10-mcp-hub-assignment-overrides-provenance-design.md Docs/Plans/2026-03-10-mcp-hub-assignment-overrides-provenance-implementation-plan.md
git commit -m "docs: finalize MCP Hub override implementation plan"
```
