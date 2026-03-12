# MCP Hub Audit Remediation Suggestions Implementation Plan

Date: 2026-03-11
Status: Ready

Linked design:
- `Docs/Plans/2026-03-11-mcp-hub-audit-remediation-suggestions-design.md`

## Goal

Add deterministic remediation suggestions to audit finding rows and include the
same guidance in current client-side audit exports.

## Task List

- Task 1: Not Started
- Task 2: Not Started
- Task 3: Not Started
- Task 4: Not Started
- Task 5: Not Started

## Task 1: Add Red Tests For Remediation Generation And Rendering

**Goal**: Capture the expected remediation UI and export behavior in failing
tests first.

**Success Criteria**:
- tests fail before implementation for:
  - remediation list rendering
  - advisory note rendering
  - export inclusion of remediation steps

**Tests**:
- `apps/packages/ui/src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx`
- add helper tests if a dedicated audit-helper test file is cleaner

**Status**: Not Started

## Task 2: Add Pure Remediation Helper Logic

**Goal**: Implement one shared pure remediation helper used by both UI and
export.

**Success Criteria**:
- helper exists, e.g. `buildAuditRemediationSteps(...)`
- rules prefer structured details before message fallbacks
- fallback suggestions are always available
- remediation output is deterministic

**Files**:
- `apps/packages/ui/src/components/Option/MCPHub/governanceAuditHelpers.ts`
- optional adjacent helper test file

**Status**: Not Started

## Task 3: Render Remediation In The Audit Tab And Exports

**Goal**: Show remediation inline in the audit UI and include it in export
payloads/reports.

**Success Criteria**:
- finding rows show `Suggested next steps` when available
- advisory note is shown for warning-style readiness findings
- JSON export includes `suggested_steps` and `suggestion_note`
- Markdown export includes remediation guidance

**Files**:
- `apps/packages/ui/src/components/Option/MCPHub/GovernanceAuditTab.tsx`
- `apps/packages/ui/src/components/Option/MCPHub/governanceAuditHelpers.ts`

**Status**: Not Started

## Task 4: Run Focused And Broader UI Verification

**Goal**: Verify remediation rendering and ensure the MCP Hub UI suite stays
green.

**Success Criteria**:
- focused governance audit tests pass
- broader MCP Hub UI suite passes

**Commands**:
- `bunx vitest run src/components/Option/MCPHub/__tests__/GovernanceAuditTab.test.tsx`
- `bunx vitest run src/components/Option/MCPHub/__tests__`

**Status**: Not Started

## Task 5: Mark Docs Implemented And Commit

**Goal**: Update the saved docs and checkpoint the slice.

**Success Criteria**:
- design doc status changed to `Implemented`
- all task statuses marked `Complete`
- commit created with a focused message

**Files**:
- `Docs/Plans/2026-03-11-mcp-hub-audit-remediation-suggestions-design.md`
- `Docs/Plans/2026-03-11-mcp-hub-audit-remediation-suggestions-implementation-plan.md`

**Status**: Not Started
