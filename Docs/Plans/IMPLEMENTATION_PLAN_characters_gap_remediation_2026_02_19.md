# Implementation Plan: Characters - Gap Remediation (2026-02-19)

## Scope

Components:
- `apps/packages/ui/src/components/Option/Characters/Manager.tsx`
- `apps/packages/ui/src/components/Sidepanel/Chat/form.tsx`
- `apps/packages/ui/src/utils/default-character-preference.ts`
- `apps/packages/ui/src/components/Option/Characters/search-utils.ts`
- `apps/tldw-frontend/vitest.config.ts`
- `apps/tldw-frontend/vitest.setup.ts`
- `apps/packages/ui/vitest.setup.ts`
- `apps/packages/ui/src/components/Option/Characters/__tests__/Manager.first-use.test.tsx`
- `tldw_Server_API/app/api/v1/schemas/character_schemas.py`
- `tldw_Server_API/app/core/Character_Chat/modules/character_validation.py`
- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`
- `tldw_Server_API/tests/Characters/test_characters_endpoint.py`

## Gap Coverage

- Name-length contract mismatch between UI and API validators.
- Default-character preference is local-only instead of user-scoped server preference.
- Batch import lacks explicit drag-drop flow and granular per-file runtime status.
- Server-side query supports date-range/last-used dimensions not fully surfaced in UI.
- UI claims 30-day restore window without clear backend retention enforcement.
- Stage 10 C-32 organization scope resolved with shipped single-folder support (reserved token model, API filtering, UI assignment/filtering).
- Character test reliability differs between frontend and UI Vitest environments.

## Issue Plan Files

- `Docs/Plans/IMPLEMENTATION_PLAN_characters_gap_01_name_length_contract_2026_02_19.md`
- `Docs/Plans/IMPLEMENTATION_PLAN_characters_gap_02_default_preference_persistence_2026_02_19.md`
- `Docs/Plans/IMPLEMENTATION_PLAN_characters_gap_03_batch_import_ux_contract_2026_02_19.md`
- `Docs/Plans/IMPLEMENTATION_PLAN_characters_gap_04_query_dimensions_ui_surface_2026_02_19.md`
- `Docs/Plans/IMPLEMENTATION_PLAN_characters_gap_05_restore_retention_policy_2026_02_19.md`
- `Docs/Plans/IMPLEMENTATION_PLAN_characters_gap_06_scope_resolution_c32_2026_02_19.md`
- `Docs/Plans/IMPLEMENTATION_PLAN_characters_gap_07_test_harness_unification_2026_02_19.md`

## Stage 1: Align Name-Length Contract Across UI and API
**Goal**: Remove contradictory character name limits and enforce one contract end-to-end.
**Success Criteria**:
- One canonical max-name limit is selected and documented.
- UI form limits and backend schema validation use the same max value.
- API validation error messaging clearly communicates the same limit shown in UI.
- Existing over-limit stored records are handled by explicit migration or compatibility policy.
**Tests**:
- UI test for `maxLength` + counter messaging with canonical limit.
- API integration tests for accept/reject boundaries around the canonical limit.
- Regression test ensuring list/detail rendering remains stable for edge-length names.
**Status**: Complete
**Update (2026-02-19)**:
- Canonical max-name limit set to `500` characters to match backend schema validation.
- Updated characters create/edit UI validation/input max length to `500`.
- Preserved table readability by keeping display truncation separate from storage validation.
- Added backend integration coverage for name-length boundary acceptance and oversized-name rejection in `test_characters_endpoint.py`.
- Updated frontend character manager test coverage to assert the `500`-character limit.

## Stage 2: Move Default Character Preference to User-Scoped Persistence
**Goal**: Persist default character selection in user-scoped backend preferences.
**Success Criteria**:
- Add (or reuse) backend preference endpoint/field for default character ID.
- Characters page set/clear default actions write through backend, not local-only state.
- Chat bootstrap reads server preference and still respects explicit user overrides.
- Local storage remains only as fallback/cache during migration.
**Tests**:
- Backend API tests for set/get/clear default character preference.
- Frontend integration test for set default -> page reload -> chat preselect behavior.
- Regression test confirming explicit manual character selection overrides default.
**Status**: Complete
**Update (2026-02-19)**:
- Added profile catalog key `preferences.chat.default_character_id` to persist default character server-side.
- Added backend test coverage for set/get/clear and invalid-type rejection in `tldw_Server_API/tests/UserProfile/test_user_profile_updates.py`.
- Added `tldwClient` methods for user profile read/update and default-character preference get/set.
- Updated Characters Manager set/clear-default actions to perform backend write-through with local cache fallback.
- Updated Sidepanel chat bootstrap to prefer server default preference and use local storage only as fallback/cache.
- Added frontend manager tests that assert backend write-through calls for set/clear default actions.
- Added real integration coverage for default preselect + manual override on reload in `apps/extension/tests/e2e/playground-character-selection.spec.ts`.

## Stage 3: Complete Batch Import UX Contract (Drag-Drop + Per-File Status)
**Goal**: Match import UX behavior with planned batch workflow requirements.
**Success Criteria**:
- Characters import supports drag-and-drop in addition to file picker.
- Import UI shows per-file processing states (queued/processing/success/failure).
- Final summary still reports aggregate counts and per-file errors.
- Preview + confirm flow remains unchanged for safety.
**Tests**:
- Component test for drag-drop multi-file ingestion.
- Integration test for mixed-validity batch with per-file status transitions.
- E2E test for drag-drop batch import and summary correctness.
**Status**: Complete
**Update (2026-02-19)**:
- Completed Stage 1 of the dedicated batch-import gap plan by defining a shared import lifecycle state model (`queued`, `processing`, `success`, `failure`) and drag/drop callback semantics.
- Added reducer/state tests in `apps/packages/ui/src/components/Option/Characters/__tests__/import-state-model.test.ts`.
- Updated `Manager.tsx` upload callback dedupe logic to consume `shouldHandleImportUploadEvent` from the shared model.
- Implemented Stage 2 of the dedicated batch-import plan:
  - Added a drag-drop import zone in the characters manager toolbar.
  - Added per-file runtime status rendering and aggregate progress summary in import preview.
  - Kept picker-based upload and drop-based upload aligned through shared preview ingestion.
- Added manager coverage for drop-zone ingestion and per-file runtime status transitions.
- Added failure-recovery retry path (`Retry failed`) for preview items and integration coverage proving only failed files are retried.
- Verified targeted import preview/confirm/retry flows continue to pass.
- Added extension E2E coverage in `apps/extension/tests/e2e/characters-create-edit-import-export.spec.ts` for mixed-outcome batch import preview/confirm/summary flow and retry-failed path without duplicating successful imports.

## Stage 4: Surface Full Server Query Dimensions in UI
**Goal**: Expose date-range and last-used sorting/filtering already supported by API.
**Success Criteria**:
- UI adds created/updated date range controls mapped to server query params.
- Sort controls expose `last_used_at` where data is available.
- Query-state serialization includes all exposed filters/sort fields.
- Clear-filters action resets newly added controls consistently.
**Tests**:
- Frontend integration tests for query-state -> request param mapping.
- API contract tests for date-range + last-used sort interactions.
- UI tests for filter clear/reset behavior across new controls.
**Status**: Complete
**Update (2026-02-19)**:
- Added created/updated date range controls in `apps/packages/ui/src/components/Option/Characters/Manager.tsx` and mapped them to `created_from`, `created_to`, `updated_from`, and `updated_to`.
- Added `Last used` sort control in table columns and mapped UI sort key `lastUsedAt` to API `sort_by=last_used_at`.
- Updated query serialization and legacy page-query fallback request payloads to include the new dimensions.
- Updated clear-filters flows (toolbar + filtered-empty-state) to reset all new date controls.
- Added manager integration tests in `apps/packages/ui/src/components/Option/Characters/__tests__/Manager.first-use.test.tsx` for date-filter serialization/reset and last-used sort mapping.

## Stage 5: Enforce and Document Restore Retention Policy
**Goal**: Ensure “restore window” messaging is backed by deterministic backend behavior.
**Success Criteria**:
- Backend applies explicit retention-window policy for character restore eligibility.
- Restore endpoint returns clear, actionable error when item is outside window.
- UI messaging reflects actual enforced policy and does not overpromise.
- Policy documented for users and developers.
**Tests**:
- Backend tests for restore inside/outside retention window.
- Integration tests for deleted-only listing and restore eligibility transitions.
- UI test for out-of-window restore error messaging.
**Status**: Complete
**Update (2026-02-19)**:
- Added restore retention policy configuration `CHARACTERS_RESTORE_RETENTION_DAYS` (default `30`) in characters restore endpoint logic.
- Enforced retention window in DB restore path (`restore_character_card`) using deleted timestamp (`last_modified`) and explicit `RestoreWindowExpiredError`.
- Added API conflict mapping for out-of-window restores with actionable messaging and reason-coded logs (`restore_window_expired`).
- Added backend integration test coverage for out-of-window restore rejection in `tldw_Server_API/tests/Characters/test_characters_endpoint.py`.
- Updated UI restore error test to assert restore-window-expired messaging in `apps/packages/ui/src/components/Option/Characters/__tests__/Manager.first-use.test.tsx`.
- Added user guide note documenting server restore-window behavior in `Docs/User_Guides/User_Guide.md`.

## Stage 6: Resolve C-32 Scope (Favorites vs Collections/Folders)
**Goal**: Close the remaining organization-model gap with an explicit implementation path.
**Success Criteria**:
- Product/engineering decision is codified: implement collections/folders now or defer formally.
- If implemented: minimum viable collections/folders are available in model, API, and UI.
- If deferred: Stage 10 plan/docs are updated to mark favorites-only as partial and track follow-up scope.
- Avoid ambiguous “Complete” status when foldered organization is not shipped.
**Tests**:
- If implemented: backend + frontend tests for collection assignment/filtering.
- If deferred: documentation consistency checklist and status corrections.
**Status**: Complete
**Update (2026-02-19)**:
- Decision recorded: ship **single-folder** character organization in v1 (no multi-folder).
- Selected implementation path: reuse existing folder/keyword primitives and store one reserved folder token in character metadata/tags (no character schema migration in v1).
- Detailed execution contract documented in `Docs/Plans/IMPLEMENTATION_PLAN_characters_gap_06_scope_resolution_c32_2026_02_19.md`.
- Frontend implementation started in `apps/packages/ui/src/components/Option/Characters/Manager.tsx`:
  - Added folder assign/reassign controls in create/edit metadata.
  - Added folder filter mapped to reserved token query (`__tldw_folder_id:<collection_id>`).
  - Added token-hiding behavior across tag-centric UI surfaces.
- Added frontend integration coverage in `Manager.first-use.test.tsx` for folder filter/query mapping, token hiding, and single-folder reassignment semantics.
- Verified local UI suite pass: `bunx vitest run src/components/Option/Characters/__tests__/Manager.first-use.test.tsx` (78 passing).
- Enforced backend single-folder semantics in `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py` so create/update paths persist at most one reserved folder token.
- Added backend integration tests in `tldw_Server_API/tests/Characters/test_characters_endpoint.py` for reserved-folder query filtering and single-folder create/update normalization.
- Verified backend tests pass with startup privilege metadata validation disabled in test context:
  - `PRIVILEGE_METADATA_VALIDATE_ON_STARTUP=0 python -m pytest -q tldw_Server_API/tests/Characters/test_characters_endpoint.py -k "reserved_folder_tag_filters_integration or create_and_update_enforce_single_folder_token_integration"`
- Updated world-book lorebook debug handoff links from deprecated `/playground` to `/chat` in `apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`, with assertion updates in `WorldBooksManager.crossFeatureStage3.test.tsx`.
- Hardened Characters manager query error handling in `apps/packages/ui/src/components/Option/Characters/Manager.tsx` so unrecoverable list-query failures degrade to empty-state + notification instead of route-level crashes; added regression coverage in `Manager.first-use.test.tsx`.

## Stage 7: Unify Character Test Harness Across Frontend and UI Packages
**Goal**: Make character test results consistent regardless of where tests are executed from.
**Success Criteria**:
- Frontend Vitest setup includes required browser polyfills used by UI character tests.
- Character suites pass under both `apps/tldw-frontend` and `apps/packages/ui` test entry points.
- CI command path for character suites is standardized and documented.
**Tests**:
- Run `Manager.first-use`, `CharacterGalleryCard`, and `search-utils` suites from both package contexts.
- Add a lightweight smoke target to prevent future setup drift.
**Status**: Complete
**Update (2026-02-19)**:
- Frontend setup now imports shared baseline setup from `apps/packages/ui/vitest.setup.ts`.
- Added frontend jsdom compatibility polyfill for `Blob.text()` and `File.text()` to normalize import-preview behavior.
- Added `test:characters-harness` scripts in both `apps/tldw-frontend/package.json` and `apps/packages/ui/package.json`.
- Added drift guard test `apps/tldw-frontend/__tests__/vitest.setup-contract.test.ts` for setup contract and browser API parity.
- Verified target character suites pass in both contexts.
- Added CI workflow `.github/workflows/ui-characters-harness-tests.yml` to execute the canonical harness command path in both contexts.
- Added contributor guidance in `Docs/Development/Characters_Test_Harness.md` for where shared setup behavior belongs.

## Dependencies and Execution Order

1. Stage 1 first (shared contract baseline for UI/API validation behavior).
2. Stage 7 early (stabilize confidence in subsequent changes).
3. Stage 2 and Stage 5 next (cross-cutting behavior contracts).
4. Stage 4 and Stage 3 after query/persistence contract stabilization.
5. Stage 6 last (scope decision and roadmap closure).

## Completion Notes

- This plan is focused on closing plan-vs-implementation mismatches identified during the 2026-02-19 audit.
- Stage 1, Stage 2, Stage 3, Stage 4, Stage 5, Stage 6, and Stage 7 are complete.
