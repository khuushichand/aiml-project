# Implementation Plan: Notes Page - Version Control & Conflict Handling

## Scope

Components/pages: note save/version metadata, conflict handling UX, delete/restore lifecycle surfaces, multi-tab edit signaling.
Finding IDs: `10.1` through `10.7`

## Finding Coverage

- Preserve robust conflict recovery baseline: `10.1`, `10.5`, `10.7`
- Add save/version visibility: `10.2`
- Add trash/recovery workflows: `10.4`
- Define revision/diff roadmap: `10.3`
- Improve early conflict awareness in concurrent editing: `10.6`

## Stage 1: Version and Save Metadata Visibility
**Goal**: Provide clear state confidence while editing.
**Success Criteria**:
- Show current version number and last-saved timestamp in editor footer/header.
- Update metadata after successful manual save and autosave.
- Ensure metadata survives note switches and reloads correctly.
**Tests**:
- Integration tests for metadata updates across save cycles.
- Formatting tests for locale-safe time rendering.
- Regression tests for selected-note transitions.
**Status**: Complete

## Stage 2: Trash and Restore UX
**Goal**: Expose backend soft-delete/restore in a recoverable workflow.
**Success Criteria**:
- Add `Trash` section/filter showing soft-deleted notes.
- Support restore action and post-restore navigation.
- Define permanent-delete policy and gated confirmation if exposed.
**Tests**:
- Integration tests for delete -> trash visibility -> restore roundtrip.
- Permission/edge tests for missing or already-restored notes.
- UX tests for empty trash and bulk restore affordances if enabled.
**Status**: Complete

## Stage 3: Revision History Decision and Incremental Delivery
**Goal**: Set clear path for note history and diff capabilities.
**Success Criteria**:
- Document architecture decision for revisions table and diff surface.
- If deferred, expose minimum viable history context (version + modified metadata).
- If advanced history is approved, define API and UI milestones separately.
**Tests**:
- Decision artifact captured and linked in docs.
- Contract tests for revision retrieval API if implemented.
- Snapshot tests for diff rendering if UI shipped.
**Status**: Complete

## Stage 4: Proactive Multi-Tab Conflict Awareness
**Goal**: Reduce surprise 409s by surfacing stale-state risk earlier.
**Success Criteria**:
- Add lightweight version freshness checks (polling or event-driven signal).
- Warn user before save when remote version has advanced.
- Preserve existing authoritative server-side `expected_version` check.
**Tests**:
- Integration tests simulating dual-tab edit race conditions.
- Warning UX tests for stale-state banners.
- Regression tests for save path conflict handling under stale detection.
**Status**: Complete

## Dependencies

- Autosave/version metadata should align with Plan 02 editor lifecycle.
- Delete/undo messaging standards should coordinate with Plan 13.

## Progress Notes (2026-02-18)

- Completed Stage 1 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added editor revision metadata summary showing current version and last-saved timestamp.
  - Updated save flows to refresh metadata after create/update/autosave and reload paths.
  - Preserved metadata across note switching and manual reload actions.
- Stage 1 verification exists in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage4.revision-attachments.test.tsx`:
  - Verifies version + last-saved metadata rendering and update behavior.
- Completed Stage 2 across backend and frontend:
  - Added trash listing support in backend:
    - `/tldw_Server_API/app/api/v1/endpoints/notes.py` (`GET /api/v1/notes/trash`)
    - `/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py` (`list_deleted_notes`, `count_deleted_notes`).
  - Added Notes sidebar mode toggle (`Notes` / `Trash`) and trash-specific list rendering in:
    - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - `/apps/packages/ui/src/components/Notes/NotesListPanel.tsx`
  - Added restore action wiring to `POST /api/v1/notes/{id}/restore?expected_version={version}` with post-restore return to active mode and note-open navigation.
- Added Stage 2 verification in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage8.trash-restore.test.tsx`:
  - Verifies trashed note restoration roundtrip and post-restore note opening.
  - Verifies trash empty-state behavior.
- Completed Stage 3 decision artifact:
  - Added `/Docs/Plans/DECISION_RECORD_notes_version_history_stage3_2026_02_18.md`.
  - Decision: defer full revisions/diff UI; keep version + last-saved metadata and staged conflict awareness as current MVP baseline.
- Completed Stage 4 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added periodic freshness polling for selected notes to detect newer remote versions.
  - Added in-editor stale-version warning banner with `Reload note` action.
  - Added pre-save warning confirmation when remote version is ahead, while preserving authoritative server `expected_version` checks.
- Added Stage 4 verification in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage9.stale-version-warning.test.tsx`:
  - Verifies stale-version warning display and save-cancel behavior.
  - Verifies reload action clears warning and loads latest note content/version.
