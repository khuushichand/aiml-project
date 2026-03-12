# MCP Hub Broken Reference Audit Findings Implementation Plan

Date: 2026-03-11
Status: Not Started

Linked design:
- `Docs/Plans/2026-03-11-mcp-hub-broken-reference-audit-findings-design.md`

## Goal

Add a dedicated `broken_object_reference` audit finding family for direct stored
broken references on policy assignments and permission profiles.

## Task List

- Task 1: Not Started
- Task 2: Not Started
- Task 3: Not Started
- Task 4: Not Started
- Task 5: Not Started

## Task 1: Add Red Backend And UI Tests

**Goal**: Capture the new finding family and UI grouping behavior before
implementation.

**Success Criteria**:
- backend tests fail before implementation for:
  - broken assignment path-scope reference
  - broken assignment workspace-set reference
  - broken permission-profile path-scope reference
- UI tests fail before implementation for:
  - new finding type grouping/label
  - structured remediation rendering

**Tests**:
- `tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py`
- `apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx`
- `apps/packages/ui/src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts`

**Status**: Not Started

## Task 2: Add Non-Throwing Reference Inspection Helpers

**Goal**: Implement exact structured inspection helpers for path-scope and
workspace-set references.

**Success Criteria**:
- helper returns `None` for valid reference
- helper returns structured inspection payload for:
  - missing
  - inactive
  - scope-incompatible
- helpers inspect only direct stored references

**Files**:
- `tldw_Server_API/app/services/mcp_hub_service.py`

**Status**: Not Started

## Task 3: Emit Broken-Reference Findings In The Audit Feed

**Goal**: Add the new finding family to the backend audit feed and the frontend
type/grouping/remediation logic.

**Success Criteria**:
- audit feed returns `broken_object_reference` items with structured details
- frontend finding enum and grouping include the new family
- remediation suggestions use the structured detail fields

**Files**:
- `tldw_Server_API/app/services/mcp_hub_service.py`
- `tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py`
- `apps/packages/ui/src/services/tldw/mcp-hub.ts`
- `apps/packages/ui/src/components/Option/MCPHub/governanceAuditHelpers.ts`
- `apps/packages/ui/src/components/Option/MCPHub/GovernanceAuditTab.tsx`

**Status**: Not Started

## Task 4: Run Focused Verification

**Goal**: Verify both backend and UI behavior for the new finding family.

**Success Criteria**:
- focused backend audit suite passes
- focused governance audit UI suite passes

**Commands**:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/MCP_unified/test_mcp_hub_audit_findings.py -v`
- `bunx vitest run src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts`

**Status**: Not Started

## Task 5: Mark Docs Implemented, Run Bandit On Touched Backend Scope, And Commit

**Goal**: Close the slice with docs and a verified checkpoint.

**Success Criteria**:
- design doc status changed to `Implemented`
- all task statuses marked `Complete`
- Bandit run on touched backend files reports no new findings
- commit created with a focused message

**Commands**:
- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/mcp_hub_service.py tldw_Server_API/app/api/v1/schemas/mcp_hub_schemas.py -f json -o /tmp/bandit_mcp_hub_broken_refs.json`

**Files**:
- `Docs/Plans/2026-03-11-mcp-hub-broken-reference-audit-findings-design.md`
- `Docs/Plans/2026-03-11-mcp-hub-broken-reference-audit-findings-implementation-plan.md`

**Status**: Not Started
