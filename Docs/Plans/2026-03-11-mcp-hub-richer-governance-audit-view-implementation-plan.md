# MCP Hub Richer Governance Audit View Implementation Plan

Date: 2026-03-11
Status: Ready

Linked design:
- `Docs/Plans/2026-03-11-mcp-hub-richer-governance-audit-view-design.md`

## Goal

Improve the MCP Hub `Audit` tab with grouped sections, richer client-side
filters, and clearer related-object labeling while preserving the current
read-only governance feed and drill-through behavior.

## Task List

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete

## Task 1: Add Red Tests For Grouping And Filters

**Goal**: Capture the richer audit-view behavior in failing UI tests before
implementation.

**Success Criteria**:
- tests fail before implementation for:
  - grouping by `finding_type`
  - fixed section ordering
  - client-side `has related object` filter
  - client-side object kind or scope filter
  - grouped-row `Open` behavior remaining intact

**Tests**:
- `apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx`

**Status**: Not Started

## Task 2: Refactor GovernanceAuditTab To Single-Fetch Client-Side Derivations

**Goal**: Move the audit tab from refetch-on-filter to one full fetch plus
client-side grouping/filtering.

**Success Criteria**:
- component fetches visible findings once on mount
- filter options are derived from returned rows
- filtered counts are derived from the currently visible subset
- no backend contract changes are required for this task

**Files**:
- `apps/packages/ui/src/components/Option/MCPHub/GovernanceAuditTab.tsx`

**Status**: Not Started

## Task 3: Add Grouped Section Rendering And Relationship Labels

**Goal**: Render findings grouped by finding type with stable ordering and
secondary relationship labels.

**Success Criteria**:
- sections render in fixed order
- empty sections are hidden
- rows show `Related to: ...` when related object metadata exists
- existing `Open` action still works from grouped rows

**Files**:
- `apps/packages/ui/src/components/Option/MCPHub/GovernanceAuditTab.tsx`

**Status**: Not Started

## Task 4: Run Focused UI Verification

**Goal**: Verify the richer audit-view behavior and ensure MCP Hub UI remains
green.

**Success Criteria**:
- focused governance-audit test file passes
- broader MCP Hub UI suite passes

**Commands**:
- `bunx vitest run src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx`
- `bunx vitest run src/components/Option/MCPHub/__tests__`

**Status**: Not Started

## Task 5: Mark Docs Implemented And Commit

**Goal**: Update doc status and checkpoint the slice.

**Success Criteria**:
- design doc status changed to `Implemented`
- all task statuses marked `Complete`
- commit created with a focused message

**Files**:
- `Docs/Plans/2026-03-11-mcp-hub-richer-governance-audit-view-design.md`
- `Docs/Plans/2026-03-11-mcp-hub-richer-governance-audit-view-implementation-plan.md`

**Status**: Not Started
