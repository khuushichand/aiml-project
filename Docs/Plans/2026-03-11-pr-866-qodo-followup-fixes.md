# PR 866 Qodo Follow-up Fixes

## Stage 1: Lock the regressions with tests
**Goal**: Add focused failing tests for the three remaining Qodo findings.
**Success Criteria**: Tests prove storage failures are reported, quiz history returns most recent first, and the text-selection popover hides while recalculating a new position.
**Tests**:
- `bunx vitest run apps/packages/ui/src/hooks/document-workspace/__tests__/useResizablePanel.test.tsx`
- `bunx vitest run apps/packages/ui/src/hooks/document-workspace/__tests__/offlineQueue.test.ts`
- `bunx vitest run apps/packages/ui/src/components/DocumentWorkspace/DocumentViewer/__tests__/TextSelectionPopover.test.tsx`
**Status**: Complete

## Stage 2: Apply the minimal fixes
**Goal**: Update the three implementation files without unrelated refactors.
**Success Criteria**: Local storage failures emit a warning, quiz history ordering is correct, and the popover readiness flag resets before applying a new position.
**Tests**:
- Targeted Vitest files from Stage 1
**Status**: Complete

## Stage 3: Verify and publish
**Goal**: Re-run the targeted UI tests and Bandit on the touched scope, then land the fixes on the PR branch.
**Success Criteria**: Targeted tests pass, Bandit reports no new findings in touched code, and the branch is pushed.
**Tests**:
- `bunx vitest run apps/packages/ui/src/hooks/document-workspace/__tests__/useResizablePanel.test.tsx apps/packages/ui/src/hooks/document-workspace/__tests__/offlineQueue.test.ts apps/packages/ui/src/components/DocumentWorkspace/DocumentViewer/__tests__/TextSelectionPopover.test.tsx`
- `source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/hooks/document-workspace apps/packages/ui/src/components/DocumentWorkspace/DocumentViewer -f json -o /tmp/bandit_pr866_qodo_followup.json`
**Status**: In Progress
