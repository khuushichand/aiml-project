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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Autosave/version metadata should align with Plan 02 editor lifecycle.
- Delete/undo messaging standards should coordinate with Plan 13.
