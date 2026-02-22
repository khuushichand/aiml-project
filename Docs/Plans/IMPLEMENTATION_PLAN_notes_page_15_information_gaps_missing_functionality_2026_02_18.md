# Implementation Plan: Notes Page - Information Gaps & Missing Functionality

## Scope

Components/pages: major net-new notes capabilities not covered by core reliability plans, including organization models and power-user extensions.
Finding IDs: `15.1` through `15.10`

## Finding Coverage

- High-impact near-term productivity additions: `15.1`, `15.3`, `15.4`, `15.6`
- Organizational model expansions: `15.2`, `15.9`
- Content-structure/authoring enhancements: `15.7`, `15.8`
- Offline and resilience extensions: `15.10`
- Trash functionality dependency tracked in Plan 10 for `15.5`

## Stage 1: Quick Productivity Extensions
**Goal**: Add low-complexity, high-frequency authoring improvements.
**Success Criteria**:
- Add note templates for common research workflows.
- Add pin/favorite toggle for top-of-list prioritization.
- Add duplicate-note action.
- Add keyboard shortcuts help overlay trigger (`?`).
**Tests**:
- Integration tests for template application and duplicate flow.
- Component tests for pinned ordering persistence.
- Keyboard tests for help overlay toggle and dismiss behavior.
**Status**: Complete

## Stage 2: Organization Model Enhancements
**Goal**: Improve large-collection navigability beyond flat keywording.
**Success Criteria**:
- Define and implement notebooks/collections grouping model.
- Add timeline/calendar view prototype for date-based browsing.
- Ensure grouping model interoperates with existing keywords and search.
**Tests**:
- API tests for notebook membership create/update/delete.
- Integration tests for moving notes across collections.
- Search regression tests across notebook-filtered scopes.
**Status**: Complete

## Stage 3: Advanced Editing Modes and Navigation Aids
**Goal**: Offer alternatives for different writing preferences and long notes.
**Success Criteria**:
- Evaluate and implement optional WYSIWYG mode alongside markdown source.
- Add generated table of contents for notes with heading thresholds.
- Preserve markdown fidelity when switching between editing modes.
**Tests**:
- Conversion fidelity tests between markdown and WYSIWYG representations.
- Component tests for TOC generation and anchor navigation.
- Regression tests for edit/preview parity with mixed markdown constructs.
**Status**: Complete

## Stage 4: Offline Drafting and Sync Strategy
**Goal**: Reduce dependence on constant connectivity for authoring continuity.
**Success Criteria**:
- Add local draft persistence when offline.
- Implement reconnect sync flow with conflict-safe merge rules.
- Provide explicit offline/queued-sync status indicators.
**Tests**:
- Integration tests for offline edit and reconnect sync lifecycle.
- Conflict tests for offline edits against newer server versions.
- Recovery tests for interrupted sync sessions.
**Status**: Complete

## Dependencies

- Trash/recovery UI for `15.5` is owned by Plan 10 and should be treated as prerequisite.
- WYSIWYG/editor mode decisions should align with Plan 02 editor architecture.
- Notebook/filter/search interactions should align with Plans 01 and 04.

## Progress Notes (2026-02-18)

### Stage 1 completion

- Added quick templates for new-note creation:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Added built-in templates: Meeting Notes, Research Brief, Literature Review, Experiment Log
    - Template selection now creates a prefilled draft and marks it dirty for explicit save
  - `/apps/packages/ui/src/components/Notes/NotesEditorHeader.tsx`
    - Added optional Template action dropdown in the editor toolbar
- Added duplicate-note workflow:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Added duplicate action that clones current title/content/keywords into a new unsaved draft (`(Copy)` suffix)
  - `/apps/packages/ui/src/components/Notes/NotesEditorHeader.tsx`
    - Added Duplicate action button in the editor toolbar
- Added pin/favorite toggle with top-of-list prioritization:
  - `/apps/packages/ui/src/services/settings/ui-settings.ts`
    - Added `NOTES_PINNED_IDS_SETTING` local persistence key (`tldw:notesPinnedIds`)
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Added pinned ID hydration/persistence and pinned-first ordering for active list mode
  - `/apps/packages/ui/src/components/Notes/NotesListPanel.tsx`
    - Added per-row pin toggle button and pinned badge indicator
- Shortcut help trigger (`?`) coverage remains active from existing implementation and tests:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage20.accessibility-shortcuts.test.tsx`
- Added Stage 1 tests:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage38.productivity-extensions.test.tsx`
    - template apply flow
    - duplicate draft flow
    - pin-to-top ordering with persistence
- Validation runs:
  - `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Notes/__tests__/NotesManagerPage.stage38.productivity-extensions.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage31.single-note-export-copy.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage37.print-export.test.tsx`
  - `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Notes/__tests__/NotesManagerPage.stage20.accessibility-shortcuts.test.tsx`

### Stage 2 completion

- Implemented notebook/collection model as reusable keyword-backed notebooks:
  - `/apps/packages/ui/src/services/settings/ui-settings.ts`
    - Added persisted setting: `NOTES_NOTEBOOKS_SETTING` (`tldw:notesNotebooks`)
    - Added coercion/validation for notebook entries (`id`, `name`, `keywords`)
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Added notebook hydration/persistence and notebook selector controls
    - Added `Save` action to create notebook filters from current keyword tokens
    - Added `Remove` action with confirmation for selected notebook
    - Wired notebook filters into effective query scope (`effectiveKeywordTokens`)
    - Updated active filter summary and clear-filter behavior to include notebook scope
- Added timeline browsing prototype:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Added list/timeline view toggle for active notes
    - Added timeline grouping by month using note `updated_at`
    - Added timeline row selection and loading state support
- Verified notebook/search interoperability:
  - notebook keyword filters now feed:
    - paged note fetch query keys
    - search endpoint token params
    - export scope filtering
    - active-filter session metrics reset logic
- Added Stage 2 tests:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage39.organization-model.test.tsx`
    - notebook filter tokens applied to backend search calls
    - save notebook from keyword picker flow + persistence assertion
    - timeline grouped rendering + item navigation
- Validation runs:
  - `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Notes/__tests__/NotesManagerPage.stage39.organization-model.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage38.productivity-extensions.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage13.navigation-filter-summary.test.tsx`

### Stage 3 completion

- Added optional WYSIWYG input mode alongside markdown source editing:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Added input mode toggle: `Markdown` / `WYSIWYG`
    - Added markdown <-> WYSIWYG conversion helpers for headings, lists, links, bold/italic/code
    - Added fidelity-safe mode switching flow (no-edit round-trip preserves original markdown)
    - Added WYSIWYG editing surfaces for edit and split modes
- Added generated table of contents for long notes:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Added heading extraction and slugging logic
    - Added TOC panel rendered when note has 3+ headings
    - Added TOC jump behavior (cursor jump in markdown mode, heading scroll/focus in WYSIWYG mode)
- Preserved edit/preview parity and existing editor behaviors:
  - markdown preview pipeline remains source-of-truth from `content`
  - markdown toolbar actions continue in markdown mode and now operate in WYSIWYG mode
  - attachment placeholder insertion now works in WYSIWYG mode as markdown-backed updates
- Added Stage 3 tests:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage40.advanced-editing-navigation.test.tsx`
    - markdown <-> WYSIWYG no-edit fidelity
    - TOC generation and navigation jump behavior
    - WYSIWYG edit conversion back to markdown headings/inline formatting
- Stabilized Stage 2 notebook test runtime with explicit timeout:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage39.organization-model.test.tsx`
- Validation runs:
  - `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Notes/__tests__/NotesManagerPage.stage40.advanced-editing-navigation.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage2.editor-modes.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage3.toolbar-metrics.test.tsx`
  - `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Notes/__tests__/NotesManagerPage.stage39.organization-model.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage40.advanced-editing-navigation.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage38.productivity-extensions.test.tsx`

### Stage 4 completion

- Implemented offline draft persistence and reconnect sync strategy:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Added local offline draft queue persisted in `localStorage` (`tldw:notesOfflineDraftQueue:v1`)
    - Added explicit offline save behavior that stores drafts locally when disconnected
    - Added reconnect sync flow for queued drafts with conflict-safe guardrails
    - Added queue hydration on load to recover interrupted/offline sessions
- Implemented conflict-safe merge behavior for queued updates:
  - queued updates now fetch remote version before sync
  - if remote version is newer than queued base version, draft is retained as `conflict` and not overwritten
- Added explicit status indicators:
  - inline editor sync status text for offline, syncing, conflict, and queued states
  - footer metadata showing queued offline draft counts
- Added Stage 4 tests:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage41.offline-drafting-sync.test.tsx`
    - offline save queues locally without immediate server mutation
    - persisted queue recovers and syncs after reconnect
    - newer server version causes conflict retention instead of overwrite
