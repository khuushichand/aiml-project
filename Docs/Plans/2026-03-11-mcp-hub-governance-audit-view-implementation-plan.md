# MCP Hub Governance Audit View Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a read-only MCP Hub `Audit` tab that aggregates concrete governance findings across all visible MCP Hub objects and lets users drill into the existing editors.

**Architecture:** Build one backend-composed audit findings endpoint backed by a normalized `GovernanceAuditFinding` DTO. Reuse existing readiness summaries, external server status, effective external access inspection, and a new non-throwing assignment inspection helper, then render the results in a new MCP Hub audit tab with shared MCP Hub-local navigation state.

**Tech Stack:** FastAPI, MCP Hub service layer, Pydantic schemas, React, Ant Design, Vitest, pytest, Bandit

---

## Status

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete

### Task 1: Add failing backend and UI tests for governance audit findings

**Files:**
- Create: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx`
- Create or Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx`

**Step 1: Write failing backend tests**

Cover:

- audit feed returns normalized findings for workspace-set readiness warnings
- audit feed returns normalized findings for shared-workspace overlap warnings
- audit feed returns assignment blocker findings without raising
- audit feed returns external server configuration findings

**Step 2: Write failing UI tests**

Cover:

- MCP Hub includes an `Audit` tab
- audit tab renders counts and findings
- clicking `Open` switches the active MCP Hub tab/context

**Step 3: Run focused tests to confirm failure**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py -v

cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx
```

Expected: FAIL.

### Task 2: Add normalized audit DTOs and backend service composition

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- Modify: `tldw_Server_API/app/services/mcp_hub_service.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py`

**Step 1: Add shared audit finding schemas**

Add:

- `GovernanceAuditFindingResponse`
- `GovernanceAuditNavigateTargetResponse`
- `GovernanceAuditFindingListResponse`

Include fields for:

- severity
- finding_type
- object_kind/object_id/object_label
- scope_type/scope_id
- message/details
- related object metadata
- navigate target metadata

**Step 2: Add non-throwing assignment inspection helper**

In `mcp_hub_service.py`, add a helper that mirrors
`validate_multi_root_assignment_readiness(...)` but returns blocker summaries
instead of raising.

**Step 3: Add service composition helper**

Implement:

- `list_governance_audit_findings(...)`

Compose findings from:

- assignment blocker inspection
- workspace-set readiness summaries
- shared-workspace readiness summaries
- external server list state
- assignment-effective external access inspection

**Step 4: Run focused backend tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py -v
```

Expected: PASS.

### Task 3: Expose the audit findings endpoint

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py`
- Modify: `tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py`

**Step 1: Add route**

Add:

- `GET /api/v1/mcp/hub/audit/findings`

Response model:

- `GovernanceAuditFindingListResponse`

**Step 2: Support basic filters**

Pass through optional query params:

- `severity`
- `finding_type`
- `object_kind`
- `scope_type`

**Step 3: Run focused API tests**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py -k "audit" -v
```

Expected: PASS.

### Task 4: Add MCP Hub audit tab and local drill-through state

**Files:**
- Modify: `apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx`
- Create: `apps/packages/ui/src/components/Option/MCPHub/GovernanceAuditTab.tsx`
- Modify: `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- Modify: `apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx`
- Modify or Create: `apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx`

**Step 1: Mirror audit DTOs in the client**

Add types and one client helper:

- `listGovernanceAuditFindings(...)`

**Step 2: Add MCP Hub-local navigation state**

Extend `McpHubPage.tsx` to hold:

- `activeTab`
- `selectedObjectKind`
- `selectedObjectId`

Pass setters down to the new audit tab and any destination tabs that need them.

**Step 3: Build the read-only audit tab**

Render:

- counts
- filters
- finding rows
- `Open` button

Use:

- scope badges
- severity badges
- clear `multi-root readiness` wording for workspace-source advisories

**Step 4: Wire `Open` actions**

Implement first-pass destination switching:

- assignment findings -> `Assignments`
- workspace-set findings -> `Workspace Sets`
- shared workspace findings -> `Shared Workspaces`
- external server findings -> `Credentials`

**Step 5: Run focused UI tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx
```

Expected: PASS.

### Task 5: Final verification, docs update, and commit

**Files:**
- Modify: `Docs/Plans/2026-03-11-mcp-hub-governance-audit-view-design.md`
- Modify: `Docs/Plans/2026-03-11-mcp-hub-governance-audit-view-implementation-plan.md`

**Step 1: Run focused backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py -v
```

Expected: PASS.

**Step 2: Run focused UI verification**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx
```

Expected: PASS.

**Step 3: Run Bandit on touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  -f json -o /tmp/bandit_mcp_hub_governance_audit.json
```

Expected: no new findings in touched code.

**Step 4: Update docs status**

Set:

- design doc status to `Implemented`
- all task statuses in this plan to `Complete`

**Step 5: Commit**

```bash
git add \
  Docs/Plans/2026-03-11-mcp-hub-governance-audit-view-design.md \
  Docs/Plans/2026-03-11-mcp-hub-governance-audit-view-implementation-plan.md \
  tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py \
  tldw_Server_API/app/services/mcp_hub_service.py \
  tldw_Server_API/app/api/v1/endpoints/mcp_hub_management.py \
  tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py \
  apps/packages/ui/src/components/Option/MCPHub/McpHubPage.tsx \
  apps/packages/ui/src/components/Option/MCPHub/GovernanceAuditTab.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/McpHubPage.test.tsx \
  apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx \
  apps/packages/ui/src/services/tldw/mcp-hub.ts
git commit -m "feat: add MCP Hub governance audit view"
```
