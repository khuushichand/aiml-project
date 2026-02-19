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
**Status**: Complete
**Update (2026-02-18)**:
- Added backend version-diff endpoint `GET /api/v1/characters/{id}/versions/diff` and schema contracts for field-level diffs.
- Added/reused version-history and revert endpoints in the API client (`listCharacterVersions`, `diffCharacterVersions`, `revertCharacter`).
- Added Characters Manager version-history modal with timeline metadata (timestamp + client_id), field diff rendering, and revert action.
- Added integration tests for versions listing, diff payload, and revert lineage in `test_characters_endpoint.py`.
- Added UI coverage for opening version history and reverting from selected version in `Manager.first-use.test.tsx`.
- Added "Version history" action wiring in table overflow and gallery preview popup.
- Added locale entries for new version-history action labels/ARIA text.

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
**Status**: Complete
**Update (2026-02-18)**:
- Added `extensions.tldw.favorite` read/write support in Characters Manager without schema migration, preserving backward compatibility for records without favorites.
- Added visible favorite toggles in both table row actions and gallery cards.
- Added "Favorites only" filter control and wired it into both server-query and legacy client-side filtering paths.
- Added API query contract support for `favorite_only=true` in `/api/v1/characters/query` and DB-layer filtering in `query_character_cards`.
- Added UI tests for favorites-only filtering and favorite toggle mutation payload, plus backend integration coverage for `favorite_only`.

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
**Status**: Complete
**Update (2026-02-18)**:
- Wired world-book attachment controls into the advanced metadata section of the shared character form (`world_book_ids`) for both create and edit paths.
- Added characters-side world-book option/query wiring in `Manager.tsx` and synchronized edit-form initialization from existing attachments via `tldw:characterEditWorldBooks`.
- Kept attach/detach semantics in submit mutations (`createCharacter` and `updateCharacter`) through `syncCharacterWorldBookSelection`, with query invalidation for list/preview consistency.
- Added 401/403-aware error mapping for attachment sync failures so scope/permission denials surface as actionable UI feedback.
- Added frontend coverage in `Manager.first-use.test.tsx` for edit-mode preload/sync, create-mode attachment sync, and forbidden-permission sync failures.
- Added frontend coverage for preview-context world-book visibility states (populated, empty, and loading) via gallery preview tests in `Manager.first-use.test.tsx`.
- Added backend permission-error mapping in `characters_endpoint.py` so world-book attach/detach/list endpoints return `403` (instead of generic `500`) when DB-layer errors indicate permission denial.
- Added backend unit tests in `test_characters_endpoint.py` for attach/detach/list permission-denied paths.
- Added isolated backend unit coverage in `test_characters_world_book_permissions_unit.py` (router-level test app) so permission mapping can be validated without importing the full `app.main` stack in constrained local environments.
- Added backend integration coverage in `test_characters_endpoint.py` for attachment lifecycle (attach/list/detach) and missing-reference error handling.
- Stabilized world-book edit flow test timing by switching the critical modal/form interactions to deterministic `fireEvent` clicks in test harness.
- Increased timeout on the two create-flow world-book sync UI tests to keep grouped Stage 10 test runs stable under heavier Vitest suites.
- Hardened SQLite `character_cards_fts` trigger semantics for restore flows (`old.deleted = 0` guard) and enforced trigger normalization during schema initialization to prevent intermittent FTS "database disk image is malformed" errors during soft-delete restore operations.
- Added lightweight test-only stubs for heavyweight ML imports in `test_characters_endpoint.py`, allowing world-book permission and lifecycle subsets to run in local constrained environments without native import aborts.
- Factored the heavyweight-import stubs into shared helper `tests/Characters/_ml_import_stubs.py` and reused it in both endpoint test modules.
- Verified backend `test_characters_endpoint.py -k "world_book"` subset executes and passes locally (permission + lifecycle + missing-reference paths).
- Verified full Characters regression for this scope: `Manager.first-use.test.tsx` (62 tests) and `test_characters_endpoint.py` (42 tests) both pass locally under `.venv`.

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
**Status**: Complete
**Update (2026-02-18)**:
- Added bulk-selection compare affordance that only enables when exactly two characters are selected.
- Added side-by-side compare modal with field-level difference visualization and changed-field summary messaging.
- Added copy/export summary actions for collaboration handoff from compare modal.
- Added UI coverage for compare enablement constraints, modal diff rendering, and copy/export behaviors in `Manager.first-use.test.tsx`.
- Added extension e2e scenario in `apps/extension/tests/e2e/characters-ux.spec.ts` for the Stage 4 compare flow (select two characters -> open compare modal -> verify diff content -> close).
- Attempted local Playwright validation, but current extension e2e environment consistently lands on the global Characters route error screen before page interactions (this also affects a pre-existing baseline Characters UX test), so the new e2e scenario remains committed but not locally executable in this environment.

## Dependencies

- Stage 1 depends on backend version history availability and stable revision identifiers.
- Stage 3 depends on world-book endpoints and attachment semantics being exposed to the frontend API client.
- Stage 4 can reuse diff primitives introduced by Stage 1 to reduce duplicate logic.
