# Implementation Plan: Characters - Missing Functionality Roadmap

## Scope

Components: `apps/packages/ui/src/components/Option/Characters/Manager.tsx`, world-book UI surfaces in `apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`, character APIs in `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py` and related character-chat modules
Finding IDs: `C-31` through `C-34`

## Finding Coverage

- No system-managed version history/diff UI: `C-31`
- No favorites/pinning/foldered organization model: `C-32`
- No world-book attachment controls in characters page: `C-33`
- No side-by-side character comparison workflow: `C-34`

## Stage 1: Character Version Timeline and Diff
**Goal**: Provide auditable character evolution and safe rollback.
**Success Criteria**:
- Character detail/edit flow exposes version timeline with timestamp and author metadata.
- Users can inspect field-level diffs between selected revisions.
- Restore/revert action creates a new version entry (no destructive overwrite).
**Tests**:
- Backend tests for version snapshot retrieval and diff payload integrity.
- Integration tests for revert flow and post-revert version lineage.
- UI tests for timeline selection and diff rendering.
**Status**: Not Started

## Stage 2: Favorites and Collection Baseline
**Goal**: Introduce lightweight organization primitives for large libraries.
**Success Criteria**:
- Characters support favorite/pinned flag with visible star toggle in table and gallery.
- Favorites filter is available in list controls.
- Data model extension is backward-compatible for users without favorites.
**Tests**:
- Backend tests for favorite flag persistence/query behavior.
- Component tests for toggle state and optimistic update behavior.
- Integration test for favorites-only filtering.
**Status**: Not Started

## Stage 3: World-Book Attachment in Character Editing
**Goal**: Expose existing world-book capability in character authoring flow.
**Success Criteria**:
- Advanced character form includes section for attach/detach world books.
- Attached world books are visible in character summary/preview context.
- Attachment operations validate access/scope permissions.
**Tests**:
- Integration tests for attach/detach workflow and persisted links.
- Backend tests for invalid world-book references and permission handling.
- UI tests for empty and populated attachment states.
**Status**: Not Started

## Stage 4: Character Comparison View
**Goal**: Enable side-by-side review for tuning and QA workflows.
**Success Criteria**:
- Bulk-select mode supports compare action for two selected characters.
- Comparison UI highlights differing fields with clear labels.
- Compare view supports copy/export of diff summary for collaboration.
**Tests**:
- Component tests for compare action availability constraints.
- Integration tests for side-by-side diff correctness across key fields.
- E2E test for select two characters -> compare -> close/back flow.
**Status**: Not Started

## Dependencies

- Stage 1 depends on backend version history availability and stable revision identifiers.
- Stage 3 depends on world-book endpoints and attachment semantics being exposed to the frontend API client.
- Stage 4 can reuse diff primitives introduced by Stage 1 to reduce duplicate logic.
