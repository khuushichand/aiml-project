# MCP Hub Audit Export And Correlation Summary Implementation Plan

Date: 2026-03-11
Status: Implemented

Linked design:
- `Docs/Plans/2026-03-11-mcp-hub-audit-export-correlation-design.md`

## Goal

Add client-side audit export/share actions and a related-object correlation
summary strip to the MCP Hub `Audit` tab, operating on the current filtered
view only.

## Task List

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete

## Task 1: Add Red Tests For Export And Correlation Behavior

**Goal**: Capture the desired export/share and summary-strip behavior in failing
UI tests first.

**Success Criteria**:
- tests fail before implementation for:
  - related-object summary strip rendering
  - related-object focus and clear behavior
  - copy report behavior
  - JSON export behavior
  - Markdown report contents

**Tests**:
- `apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx`

**Status**: Complete

## Task 2: Add Pure Audit Helper Utilities

**Goal**: Extract pure helpers for grouping, correlation summaries, and export
payload/report generation.

**Success Criteria**:
- helper layer exists for:
  - `groupAuditFindings(...)`
  - `summarizeRelatedObjects(...)`
  - `buildAuditMarkdownReport(...)`
  - `buildAuditJsonExport(...)`
- helper outputs are deterministic and easy to test

**Files**:
- `apps/packages/ui/src/components/Option/MCPHub/policyHelpers.ts`
- or a small adjacent audit helper file if cleaner

**Status**: Complete

## Task 3: Extend GovernanceAuditTab With Summary Strip And Export Actions

**Goal**: Wire the helper layer into the audit tab UI.

**Success Criteria**:
- top related-object summary strip renders from the current filtered findings
- clicking a summary chip applies exact related-object focus
- active related-object focus is visibly shown and clearable
- `Copy Report`, `Download JSON`, and `Download Markdown` operate on the final
  visible subset
- success/failure feedback is shown for copy/download flows

**Files**:
- `apps/packages/ui/src/components/Option/MCPHub/GovernanceAuditTab.tsx`

**Status**: Complete

## Task 4: Run Focused And Broader UI Verification

**Goal**: Verify the new audit interactions and ensure the MCP Hub UI suite
stays green.

**Success Criteria**:
- focused governance audit test file passes
- broader MCP Hub UI suite passes

**Commands**:
- `bunx vitest run src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx`
- `bunx vitest run src/components/Option/MCPHub/__tests__`

**Status**: Complete

## Task 5: Mark Docs Implemented And Commit

**Goal**: Update the saved docs and checkpoint the slice.

**Success Criteria**:
- design doc status changed to `Implemented`
- all task statuses marked `Complete`
- commit created with a focused message

**Files**:
- `Docs/Plans/2026-03-11-mcp-hub-audit-export-correlation-design.md`
- `Docs/Plans/2026-03-11-mcp-hub-audit-export-correlation-implementation-plan.md`

**Status**: Complete
