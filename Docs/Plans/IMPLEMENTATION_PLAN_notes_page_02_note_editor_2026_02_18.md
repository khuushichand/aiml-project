# Implementation Plan: Notes Page - Note Editor

## Scope

Components/pages: editor body, editor header actions, preview modes, save lifecycle in `NotesManagerPage.tsx` and `NotesEditorHeader.tsx`.
Finding IDs: `2.1` through `2.12`

## Finding Coverage

- Save reliability and safety: `2.6`, `2.11`
- Editing ergonomics and mode flexibility: `2.2`, `2.3`, `2.4`
- Authoring productivity tooling: `2.7`, `2.8`, `2.9`
- Extended editing capabilities: `2.10`, `2.12`
- Preserve strengths: `2.1`, `2.5`

## Stage 1: Keyboard Save and Save-State Reliability
**Goal**: Remove core data-loss anxiety in the editor.
**Success Criteria**:
- Add global editor-aware Ctrl/Cmd+S shortcut that triggers `saveNote()`.
- Add debounced autosave (target: 5s idle) with explicit `Saving...` and failure fallback indicators.
- Keep existing dirty-state and beforeunload warnings coherent with autosave outcomes.
**Tests**:
- Unit tests for keydown handler platform variants (`ctrlKey`, `metaKey`).
- Integration tests for autosave debounce timing, success transition, and retry on failure.
- Regression tests for unsaved-change prompts during route switches.
**Status**: Complete

## Stage 2: Editor Surface and Preview Modes
**Goal**: Improve writing flow for short and long-form notes.
**Success Criteria**:
- Replace raw fixed textarea behavior with auto-resize or richer editor integration.
- Introduce three-state mode switch: `Edit`, `Split`, `Preview`.
- Add visible Markdown+LaTeX support hint in edit mode.
**Tests**:
- Component tests for mode transitions and split-pane rendering.
- Layout tests for resize behavior across short/long notes.
- Snapshot tests confirming preview parity between split and preview-only modes.
**Status**: Complete

## Stage 3: Authoring Toolbar and Productivity Metrics
**Goal**: Reduce markdown syntax overhead and improve action discoverability.
**Success Criteria**:
- Add lightweight markdown toolbar actions (bold/italic/heading/link/code/list).
- Reorder header actions to prioritize `Save` and isolate destructive `Delete` action.
- Add footer metrics for words, characters, and estimated reading time.
**Tests**:
- Unit tests for cursor-aware markdown insertion behavior.
- Component tests for toolbar ordering and destructive action grouping.
- Metric calculation tests for representative multilingual and markdown-heavy content.
**Status**: Complete

## Stage 4: Advanced Editing Features and Attachments
**Goal**: Define extensibility path for revision-safe rich content.
**Success Criteria**:
- Document short-term decision on revision history vs native undo-only behavior.
- Implement baseline image/attachment insertion flow or stage-gated placeholder with API contract.
- Surface `last saved at` and version metadata if full revisions are deferred.
**Tests**:
- Integration tests for attachment insertion and markdown link generation when enabled.
- Regression tests for undo behavior after toolbar actions/autosave.
- Decision record with acceptance criteria for revision history phase.
**Status**: Not Started

## Dependencies

- Autosave conflict semantics should align with Plan 10 (versioning/conflict handling).
- Toolbar shortcuts/help should be aligned with Plan 15 keyboard cheat-sheet scope.

## Progress Notes (2026-02-18)

- Implemented Stage 1 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added global Ctrl/Cmd+S keyboard handling to trigger note saves.
  - Added 5-second idle autosave debounce (`NOTE_AUTOSAVE_DELAY_MS`) with cleanup on dependency changes/unmount.
  - Added explicit save-state feedback text (`Saving...`, saved state, autosave failure fallback) without success-toast spam on autosave.
  - Kept existing `beforeunload` unsaved-change warning behavior intact.
- Added Stage 1 test coverage in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage1.editor-reliability.test.tsx`:
  - Verifies Ctrl+S triggers save create path.
  - Verifies idle autosave triggers after debounce and suppresses manual success toast copy.
- Implemented Stage 2 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx` and `/apps/packages/ui/src/components/Notes/NotesEditorHeader.tsx`:
  - Replaced binary preview toggle with explicit `Edit`, `Split`, `Preview` editor modes.
  - Added split mode layout with side-by-side editor and markdown preview surfaces.
  - Added textarea auto-resize with bounded max height and resize recalculation on content/mode/window-size changes.
  - Added explicit edit-mode support hint text: `Markdown + LaTeX supported`.
- Added Stage 2 test coverage in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage2.editor-modes.test.tsx`:
  - Verifies mode transitions (`Edit` <-> `Split` <-> `Preview`) and preview content parity.
  - Verifies textarea auto-resize behavior with bounded height in both standard and split modes.
- Implemented Stage 3 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx` and `/apps/packages/ui/src/components/Notes/NotesEditorHeader.tsx`:
  - Added markdown formatting toolbar actions (bold, italic, heading, list, link, code) with cursor-aware insertion behavior.
  - Reordered editor header actions to lead with `Save`, and grouped destructive `Delete` behind a visual divider.
  - Added editor metrics footer with word count, character count, and estimated reading time.
- Added Stage 3 test coverage in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage3.toolbar-metrics.test.tsx`:
  - Verifies toolbar markdown insertion against selected ranges.
  - Verifies metrics footer updates as content changes.
  - Verifies save/delete action ordering and destructive action grouping affordance.
