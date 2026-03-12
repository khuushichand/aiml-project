# MCP Hub Inline Remediation Actions Implementation Plan

Date: 2026-03-11
Status: Implemented

Linked design:
- `Docs/Plans/2026-03-11-mcp-hub-inline-remediation-actions-design.md`

## Goal

Add the first safe inline remediation action to the MCP Hub `Audit` tab:

- `Deactivate server` for eligible managed
  `external_server_configuration_issue` findings

## Task List

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete

## Task 1: Add Red Tests For Action Eligibility And Row Rendering

**Goal**: Capture the action eligibility rules and audit-row behavior in tests
before implementation.

**Success Criteria**:
- tests fail before implementation for:
  - eligible managed external server finding renders an inline action
  - non-eligible findings do not render an inline action
  - confirmation and error/success states are represented in the UI

**Tests**:
- `apps/packages/ui/src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts`
- `apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx`

**Status**: Complete

## Task 2: Add A Pure Inline-Action Helper

**Goal**: Implement one deterministic helper that maps audit findings to safe
inline actions.

**Success Criteria**:
- helper returns an action only for:
  - `external_server_configuration_issue`
  - `external_server`
  - deterministic managed-server target
- helper returns `null` for all other finding families
- helper uses structured fields only, not message heuristics

**Files**:
- `apps/packages/ui/src/components/Option/MCPHub/governanceAuditHelpers.ts`
- helper tests alongside existing audit helper tests

**Status**: Complete

## Task 3: Wire The Audit Tab To Existing Managed-Server Mutation

**Goal**: Execute the safe action from the audit row using the existing MCP Hub
external-server update call.

**Success Criteria**:
- clicking `Deactivate server` opens a lightweight confirmation
- confirming calls the existing update mutation with `enabled: false`
- success refreshes the audit feed
- failure renders inline feedback
- `Open` continues to work unchanged

**Files**:
- `apps/packages/ui/src/components/Option/MCPHub/GovernanceAuditTab.tsx`
- `apps/packages/ui/src/services/tldw/mcp-hub.ts` only if a helper export is needed

**Status**: Complete

## Task 4: Run Focused And Broader UI Verification

**Goal**: Verify the new action path without changing backend behavior.

**Success Criteria**:
- focused governance audit tests pass
- broader MCP Hub UI suite stays green

**Commands**:
- `bunx vitest run src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx src/components/Option/MCPHub/__tests__/governanceAuditHelpers.test.ts`
- `bunx vitest run src/components/Option/MCPHub/__tests__`

**Status**: Complete

## Task 5: Mark Docs Implemented And Commit

**Goal**: Update the saved docs and checkpoint the slice once verification is
green.

**Success Criteria**:
- design doc status changed to `Implemented`
- all task statuses marked `Complete`
- commit created with a focused message

**Files**:
- `Docs/Plans/2026-03-11-mcp-hub-inline-remediation-actions-design.md`
- `Docs/Plans/2026-03-11-mcp-hub-inline-remediation-actions-implementation-plan.md`

**Status**: Complete
