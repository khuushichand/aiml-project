# Implementation Plan: Media Pages - Content Versioning and History

## Scope

Pages/components: `VersionHistoryPanel.tsx`, `DiffViewModal.tsx`, version actions in media detail view
Finding IDs: `5.1` through `5.6`

## Finding Coverage

- Preserve strong existing versioning behavior: `5.1`, `5.2`, `5.3`, `5.5`
- Add explicit manual version creation: `5.4`
- Surface per-version safe metadata and comparison context: `5.6`

## Stage 1: Regression Baseline for Existing Version Workflows
**Goal**: Lock in current high-quality version history and diff behavior before extending features.
**Success Criteria**:
- Paginated list, compare, rollback, delete, and analysis-only filters remain intact.
- Prompt extraction and preview rendering paths remain stable.
- Diff modes (unified and side-by-side) preserve keyboard shortcuts.
**Tests**:
- Integration tests for version panel core actions.
- Component tests for prompt/analysis preview extraction paths.
- Keyboard interaction regression tests for diff modal navigation.
**Status**: Complete

## Stage 2: Manual "Save as Version" Action
**Goal**: Let users explicitly checkpoint content without requiring analysis generation/edit side effects.
**Success Criteria**:
- "Save as version" control added in media detail action area.
- Action calls `POST /{id}/versions` with clear success/failure feedback.
- Duplicate-click and in-flight state handling prevents accidental multiple submissions.
**Tests**:
- Integration tests for manual version creation success and error paths.
- Component tests for loading/disabled states.
- Regression tests ensuring existing create-on-edit flows still work.
**Status**: Complete

## Stage 3: Version Metadata Visibility and Diff Context
**Goal**: Expose meaningful metadata differences between versions.
**Success Criteria**:
- Version list shows key safe metadata fields where available.
- Compare flow can render metadata diff summary alongside text diff.
- Metadata rendering remains optional and non-blocking for versions without metadata.
**Tests**:
- Component tests for metadata row rendering and fallback behavior.
- Integration tests for metadata diff generation between two versions.
- Snapshot tests covering dense version histories with mixed metadata presence.
**Status**: Complete

## Dependencies

- Stage 3 should align metadata field naming with Category 4 display conventions.
