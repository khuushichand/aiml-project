# Implementation Plan: Workspace Playground - Quick Notes

## Scope

Components: `QuickNotesSection`, note load/search modal, note store integration
Finding IDs: `4.1` through `4.8`

## Finding Coverage

- Capture and workspace note navigation: `4.2`, `4.4`, `4.5`
- Authoring quality and resilience: `4.3`, `4.6`, `4.7`
- Layout prominence and portability: `4.1`, `4.8`

## Stage 1: Capture-to-Note Workflow
**Goal**: Eliminate manual copy/paste between chat and notes.
**Success Criteria**:
- Chat messages expose `Save to notes` action.
- Artifact text also supports `Save to notes` entry point.
- Action pre-fills note body and proposes title from source context.
**Tests**:
- Component tests for save button visibility on assistant/user messages.
- Integration test for save action populating note draft.
- Integration test for artifact-to-note append/replace behavior.
**Status**: Complete

## Stage 2: Workspace-Scoped Note Navigation
**Goal**: Make switching and finding notes fast within current workspace.
**Success Criteria**:
- Workspace note list (tabs/list) appears in Quick Notes panel.
- Load/search modal prioritizes workspace-tagged notes.
- API search requests include workspace filter where available.
**Tests**:
- Component test for workspace note list state transitions.
- Integration test for workspace-biased search ordering.
- API contract test for workspace filter parameter handling.
**Status**: Complete

## Stage 3: Better Authoring and Conflict Recovery
**Goal**: Upgrade note authoring from plain text to markdown-capable workflow.
**Success Criteria**:
- Notes support markdown edit + preview mode.
- Keyword input includes autocomplete from existing keywords.
- Conflict toast includes one-click `Reload latest` action and preserves unsaved draft for merge.
**Tests**:
- Component tests for markdown preview toggle.
- Unit test for keyword suggestion dedupe/ranking.
- Integration test for conflict reload flow retaining local draft.
**Status**: Complete

## Stage 4: Layout and Export
**Goal**: Increase note discoverability and enable external portability.
**Success Criteria**:
- Notes section gets equal visual weight/default expansion policy.
- Individual note export as `.md` available from toolbar.
**Tests**:
- Responsive component tests for notes visibility in constrained heights.
- Integration test for markdown export filename/content.
**Status**: Complete

## Dependencies

- Save-to-notes actions depend on shared cross-pane action model in Category 6.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Added workspace note-capture action in workspace store with explicit `append`/`replace` modes.
  - Wired chat messages to save directly into workspace Quick Notes draft with contextual title proposals.
  - Added Studio artifact `Save to notes` action with `Append to notes` and `Replace note draft` options.
  - Extended shared Playground message action bar to expose workspace-note save action for both user and assistant messages in Workspace Chat.
- Files updated:
  - `apps/packages/ui/src/store/workspace.ts`
  - `apps/packages/ui/src/components/Common/Playground/Message.tsx`
  - `apps/packages/ui/src/components/Common/Playground/MessageActionsBar.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
  - `apps/packages/ui/src/store/__tests__/workspace.test.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/store/__tests__/workspace.test.ts src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__ src/store/__tests__/workspace.test.ts`

- Stage 2 completed:
  - Added a workspace-scoped note strip in Quick Notes for rapid note switching inside the current workspace context.
  - Upgraded note search/list loading to prioritize workspace-tagged notes while preserving global results.
  - Added workspace token filtering (`tokens=<workspaceTag>`) to search requests where supported, with safe fallback behavior.
  - Normalized note keyword parsing (object/string payloads), persisted workspace tags in save payload keywords, and hid workspace system tag from editable keyword chips.
- Files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/QuickNotesSection.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage2.test.tsx`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage2.test.tsx`
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx src/store/__tests__/workspace.test.ts`

- Stage 3 completed:
  - Added markdown edit/preview mode toggle in Quick Notes using shared markdown renderer.
  - Added keyword autocomplete backed by existing Notes keyword API, including ranked prefix/contains matching and deduplication.
  - Implemented conflict recovery flow with toast action (`Reload latest`) that loads server state and preserves local unsaved draft content/keywords for merge.
- Files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/QuickNotesSection.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage3.test.tsx`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage3.test.tsx`

- Stage 4 completed:
  - Added `.md` export action in Quick Notes toolbar with sanitized filename and markdown payload (title + tags + content).
  - Increased Studio pane notes area baseline visual weight via a minimum height so notes remain visible in tighter layouts.
  - Added constrained-height visibility and export integration coverage.
- Files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/QuickNotesSection.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage4.test.tsx`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage4.test.tsx`
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage4.test.tsx src/store/__tests__/workspace.test.ts`
