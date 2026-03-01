## Stage 1: Baseline Rendering Harness
**Goal**: Establish stable baseline test coverage for `WritingPlayground` empty-state rendering.
**Success Criteria**:
- A deterministic baseline test renders key empty-state landmarks without network calls.
- Targeted component tests run without worker OOM.
**Tests**:
- `bunx vitest run ../packages/ui/src/components/Option/WritingPlayground/__tests__/WritingPlayground.phase1-baseline.test.tsx --reporter=verbose`
- `bunx vitest run ../packages/ui/src/components/Option/WritingPlayground/__tests__/writing-token-utils.test.ts --reporter=verbose`
**Status**: Complete

## Stage 2: Render Loop Risk Remediation
**Goal**: Remove mount-time state-reset loop that can trigger unbounded rerenders when no active session detail exists.
**Success Criteria**:
- The `activeSessionDetail` reset path executes only on transition from loaded session to no session.
- No OOM when mounting `WritingPlayground` in baseline test harness.
**Tests**:
- `bunx vitest run ../packages/ui/src/components/Option/WritingPlayground/__tests__/WritingPlayground.phase1-baseline.test.tsx --reporter=verbose`
**Status**: Complete

## Stage 3: Extension UI Phase-1 Follow-ons
**Goal**: Continue planned Phase-1 implementation work after baseline stability and issue triage are complete.
**Success Criteria**:
- Remaining Phase-1 UI changes are implemented against stable test harness.
- Regression checks for updated interactions pass.
**Tests**:
- `bunx vitest run ../packages/ui/src/components/Option/WritingPlayground/__tests__/WritingPlayground.phase1-baseline.test.tsx ../packages/ui/src/components/Option/WritingPlayground/__tests__/WritingPlayground.inspector-tabs.test.tsx ../packages/ui/src/components/Option/WritingPlayground/__tests__/writing-diagnostics-utils.test.ts --reporter=verbose`
- `bunx vitest run ../packages/ui/src/components/Option/WritingPlayground/__tests__`
 - `bunx playwright test tests/e2e/writing-playground-themes-templates.spec.ts --grep "navigates inspector tabs and preserves editor content" --reporter=line` (may skip without real-server env vars)
**Status**: Complete

### Completed in this stage
- Extracted structural shell and panel components:
  - `WritingPlaygroundShell`
  - `WritingPlaygroundLibraryPanel`
  - `WritingPlaygroundEditorPanel`
- Added typed IA contracts in `WritingPlayground.types.ts`.
- Added tabbed inspector scaffold via `WritingPlaygroundInspectorPanel` with semantic tab roles and keyboard arrow navigation.
- Added diagnostics summary helper (`buildDiagnosticsSummary`) and unit coverage.
- Added responsive layout mode utility (`resolveWritingLayoutMode`) and shell mode detection attributes.
- Added an accessibility label for the session actions icon button.
- Added/expanded baseline coverage for shell + panel landmarks and inspector tab switching.
- Moved template/theme/chat-mode controls and context controls from `Generation` to `Planning`.
- Added tab-regression coverage asserting template/theme management actions are shown in `Planning` and not `Generation`.
- Replaced Diagnostics tab placeholder with live diagnostics sections (response inspector, token inspector, wordcloud) wired to existing state/actions.
- Added diagnostics-tab regression coverage to guard against placeholder regressions.
- Removed editor-side diagnostics panel injection from the prompt-chunks collapse so diagnostics workflows are surfaced from the Diagnostics tab only.
- Extracted diagnostics tab UI into `WritingPlaygroundDiagnosticsPanel.tsx` and wired typed props from `index.tsx`.
- Split diagnostics panel into focused subcomponents:
  - `WritingPlaygroundResponseInspectorCard.tsx`
  - `WritingPlaygroundTokenInspectorCard.tsx`
  - `WritingPlaygroundWordcloudCard.tsx`
  - shared diagnostics prop types in `WritingPlaygroundDiagnostics.types.ts`
- Reduced diagnostics prop fan-out by grouping panel inputs into typed objects (`response`, `token`, `wordcloud`) passed from `index.tsx`.
- Added compact/narrow layout behavior by tagging primary layout grids and applying shell compact-mode overrides for single-column stacking.
- Expanded inspector keyboard coverage with focus traversal behavior (Arrow/Home/End + wraparound) and resize-driven layout mode baseline tests.
- Added extension E2E coverage in `writing-playground-themes-templates.spec.ts` for inspector tab keyboard navigation and editor-content persistence across tab switches.

### Remaining follow-ons
- None for Phase-1 follow-ons.
