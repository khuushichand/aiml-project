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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Stage 4: Layout and Export
**Goal**: Increase note discoverability and enable external portability.
**Success Criteria**:
- Notes section gets equal visual weight/default expansion policy.
- Individual note export as `.md` available from toolbar.
**Tests**:
- Responsive component tests for notes visibility in constrained heights.
- Integration test for markdown export filename/content.
**Status**: Not Started

## Dependencies

- Save-to-notes actions depend on shared cross-pane action model in Category 6.
