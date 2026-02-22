# Implementation Plan: Notes Page Gap Remediation

## Scope

This plan addresses all issues identified in the 2026-02-19 plan-vs-implementation audit for Notes UX/HCI plans 01-15.

Impacted areas:
- Notes frontend (`apps/packages/ui/src/components/Notes/*`)
- Notes Dock frontend (`apps/packages/ui/src/components/Common/NotesDock/*`)
- Notes API and DB integration (`tldw_Server_API/app/api/v1/endpoints/notes.py`, `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`)
- Notes test suites (frontend Vitest + backend pytest)
- Plan/documentation consistency in `Docs/Plans/`

## Findings Coverage

- `R1` Notebook/collection model marked complete but currently frontend-local only.
- `R2` Attachments flow is placeholder-only; no upload endpoint/storage path.
- `R3` Search tips popover is static and not searchable.
- `R4` Delete undo restore lookup only checks first trash page (`limit=100`).
- `R5` Ctrl/Cmd+S save shortcut is global, not editor-aware.
- `R6` Plan documentation conflict on Notes Dock mobile behavior.
- `R7` Backend notes integration tests have fixture-reset leak for mock side effects.

## Stage 1: Correctness and Reliability Quick Fixes
**Goal**: Close lower-scope correctness gaps before adding net-new backend features.
**Success Criteria**:
- Fix undo-restore lookup to resolve deleted note versions beyond first trash page.
- Scope Ctrl/Cmd+S handling to editor-aware contexts while preserving existing save flow.
- Add searchable filtering to Search Tips popover content (keyword/phrase matching).
- Fix backend test fixture reset to clear `get_keyword_by_text.side_effect` and related state.
**Tests**:
- Frontend integration tests for undo after deletion when note is not in first trash page result.
- Frontend keyboard tests for save shortcut behavior in editor vs non-editor contexts.
- Frontend component tests for searchable tips filtering behavior and accessibility announcements.
- Backend pytest regression for `test_import_notes_json_creates_notes_and_keywords` plus full file run.
**Status**: Complete

## Stage 2: Notebook/Collection Backend Model and API
**Goal**: Replace frontend-only notebook presets with a real notes organization model.
**Success Criteria**:
- Define backend notebook/collection schema and API for create/list/update/delete membership.
- Persist note membership server-side; support filtering notes by notebook/collection.
- Preserve compatibility with existing keyword-based filtering and query semantics.
- Provide migration strategy from local notebook settings (`tldw:notesNotebooks`) to server entities.
**Tests**:
- DB unit tests for notebook CRUD and note membership integrity.
- API integration tests for notebook create/update/delete, membership move, and filtered note retrieval.
- Frontend integration tests validating notebook filters use server-backed state and survive reload/session changes.
- Search/filter regression tests for notebook + keyword + query combined semantics.
**Status**: Complete

## Stage 3: End-to-End Attachments Implementation
**Goal**: Replace placeholder attachment links with real upload/download lifecycle.
**Success Criteria**:
- Add attachment API contract (`POST/GET/DELETE /api/v1/notes/{id}/attachments...`) with validation and auth checks.
- Implement storage strategy (pathing, size/type constraints, metadata persistence).
- Update editor attachment flow to upload files and insert stable attachment URLs only after successful upload.
- Preserve behavior for unsaved notes (explicit guidance remains required before attachments).
**Tests**:
- API tests for upload/download/delete, invalid file types, size limits, and permission edge cases.
- Frontend integration tests for upload progress/success/failure states and markdown insertion behavior.
- Regression tests ensuring no "pending contract" placeholder messaging remains in normal flow.
- Security tests for path traversal and unauthorized attachment access attempts.
**Status**: Complete

## Stage 4: Plan and Documentation Alignment
**Goal**: Eliminate contradictory documentation and ensure plan status fidelity.
**Success Criteria**:
- Reconcile Plan 09 and Plan 11 mobile dock behavior narrative with actual intended behavior.
- Update affected plan progress notes where criteria changed from scaffold/deferred to fully shipped.
- Add explicit "partial vs complete" labeling rules for future plan updates.
**Tests**:
- Documentation review checklist for cross-plan consistency.
- Spot-check references in index and linked decision records for behavior parity.
**Status**: Complete

## Stage 5: Full Validation and Release Gate
**Goal**: Prove all remediations are stable and prevent recurrence.
**Success Criteria**:
- Frontend Notes + Dock test suites pass with new regression coverage.
- Backend Notes API integration/unit suites pass for updated notebook/attachment/import behaviors.
- Add CI-targeted test selection for newly fixed regressions (`R4`, `R5`, `R7`) and net-new features (`R1`, `R2`, `R3`).
- Produce remediation summary mapping each `R#` to merged code/tests/docs.
**Tests**:
- `bunx vitest run src/components/Notes/__tests__ src/components/Common/NotesDock/__tests__`
- `python -m pytest -q tldw_Server_API/tests/Notes tldw_Server_API/tests/Notes_NEW`
- Targeted CI subset job for remediation-critical tests.
**Status**: Complete

## Dependencies

- Stage 2 (notebook backend) should land before deprecating local notebook persistence behavior in UI.
- Stage 3 (attachments) depends on backend API/storage decisions and security review.
- Stage 4 should be executed after Stage 1-3 implementation details are finalized to avoid doc churn.

## Progress Notes (2026-02-19)

### Stage 1 completion

- Implemented paginated undo version lookup in:
  - `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - Replaced single-page trash lookup with bounded pagination (`limit=100`, incremental offsets) so Undo can resolve versions beyond the first trash page.
- Implemented editor-aware save shortcut scope in:
  - `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - `Ctrl/Cmd+S` now executes only when focus context is within the notes editor region.
- Implemented searchable Search Tips popover in:
  - `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - Added in-popover filter input and dynamic tip filtering with empty-state handling.
- Fixed backend notes test fixture side-effect leakage in:
  - `tldw_Server_API/tests/Notes/test_notes_api_integration.py`
  - Reset now clears `get_keyword_by_text.side_effect`/`return_value` and `get_keyword_by_id.return_value`.
- Added/updated Stage 1 verification in:
  - `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage1.editor-reliability.test.tsx`
    - Added non-editor shortcut guard assertion.
  - `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage11.search-filtering.test.tsx`
    - Added searchable tips filtering assertion.
  - `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage32.delete-undo.test.tsx`
    - Added multi-page trash lookup undo regression test.
- Validation runs:
  - `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Notes/__tests__/NotesManagerPage.stage1.editor-reliability.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage11.search-filtering.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage32.delete-undo.test.tsx`
  - `source .venv/bin/activate && python -m pytest -q -x tldw_Server_API/tests/Notes/test_notes_api_integration.py`

### Stage 2 completion

- Implemented notebook/collection API contracts in:
  - `tldw_Server_API/app/api/v1/endpoints/notes.py`
  - Added `/api/v1/notes/collections` CRUD, collection-keyword links, and conversation-keyword link listing/link/unlink routes.
  - Added collection keyword sync helpers to persist server-side notebook membership.
- Added collection schemas in:
  - `tldw_Server_API/app/api/v1/schemas/notes_schemas.py`
  - Added request/response models for keyword collections and collection/conversation keyword link payloads.
- Added Stage 2 backend integration coverage in:
  - `tldw_Server_API/tests/Notes/test_notes_api_integration.py`
  - Added tests for collection list/create/update/delete and fixture resets for new mock methods.
- Migrated Notes page notebooks to server-backed persistence in:
  - `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - Added server collection hydration, best-effort local-to-server migration, and create/delete server sync while preserving keyword-based notebook filtering semantics.
- Updated frontend Stage 2 notebook tests in:
  - `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage39.organization-model.test.tsx`
  - Updated test fixtures to exercise `/api/v1/notes/collections` server calls.
- Validation runs:
  - `source .venv/bin/activate && python -m pytest -q -x tldw_Server_API/tests/Notes/test_notes_api_integration.py`
  - `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Notes/__tests__/NotesManagerPage.stage39.organization-model.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage1.editor-reliability.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage11.search-filtering.test.tsx src/components/Notes/__tests__/NotesManagerPage.stage32.delete-undo.test.tsx`
  - `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Notes/__tests__ src/components/Common/NotesDock/__tests__`

### Stage 3 completion

- Implemented attachment API contracts in:
  - `tldw_Server_API/app/api/v1/endpoints/notes.py`
  - Added:
    - `POST /api/v1/notes/{note_id}/attachments`
    - `GET /api/v1/notes/{note_id}/attachments`
    - `GET /api/v1/notes/{note_id}/attachments/{file_name}`
    - `DELETE /api/v1/notes/{note_id}/attachments/{file_name}`
  - Enforced per-user storage isolation under `DatabasePaths.get_user_base_directory(user_id)/notes_attachments/<note_id>/`.
  - Added attachment validation guardrails:
    - safe filename normalization + strict filename checks for read/delete routes
    - extension allowlist
    - max-size enforcement (`NOTES_ATTACHMENT_MAX_BYTES`, default 25MB)
    - path-containment checks and metadata sidecar persistence.
- Added attachment response schemas in:
  - `tldw_Server_API/app/api/v1/schemas/notes_schemas.py`
  - New models: `NoteAttachmentResponse`, `NoteAttachmentsListResponse`.
- Replaced placeholder-only UI flow with real uploads in:
  - `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - Attachment insertions now occur only after successful upload responses, using returned attachment URLs and success/partial-failure messaging.
- Updated frontend Stage 4 attachment test in:
  - `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage4.revision-attachments.test.tsx`
  - Verifies upload request call + `FormData` payload and removes reliance on pending-contract placeholder messaging.
- Added backend attachment integration coverage in:
  - `tldw_Server_API/tests/Notes/test_notes_api_integration.py`
  - Includes upload/list/download/delete lifecycle plus unsupported extension, oversized file rejection, and invalid filename checks.
- Validation runs:
  - `source .venv/bin/activate && python -m pytest -q -x tldw_Server_API/tests/Notes/test_notes_api_integration.py`
  - `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Notes/__tests__/NotesManagerPage.stage4.revision-attachments.test.tsx`

### Stage 4 completion

- Reconciled the mobile dock behavior narrative conflict between Plan 09 and Plan 11:
  - Updated `Docs/Plans/IMPLEMENTATION_PLAN_notes_page_11_responsive_mobile_experience_2026_02_18.md`
  - Stage 3 now explicitly states mobile dock panel suppression preserves open/unsaved dock state for desktop return (no forced close), matching Plan 09 Stage 3 completion notes.
- Confirmed plan index ordering/dependencies remain valid after wording alignment.

### Stage 5 completion

- Full frontend Notes + Dock validation passed:
  - `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Notes/__tests__ src/components/Common/NotesDock/__tests__`
  - Result: `60 files`, `146 tests` passed.
- Full backend Notes + Notes_NEW validation passed in test-mode runtime:
  - `source .venv/bin/activate && TLDW_TEST_MODE=1 python -m pytest -q tldw_Server_API/tests/Notes tldw_Server_API/tests/Notes_NEW`
  - Result: `155` tests passed.
  - Note: plain run without `TLDW_TEST_MODE=1` can abort during torch import in TTS shutdown on this local environment; `TLDW_TEST_MODE=1` is the stable test profile and aligns with existing minimal-test startup patterns.
- Added CI-targeted remediation gate workflow:
  - `.github/workflows/notes-remediation-targeted.yml`
  - Includes:
    - remediation-critical Notes UI Vitest subset (`R1`, `R2`, `R3`, `R4`, `R5`)
    - remediation-critical backend pytest subset (`R1`, `R2`, `R7`)

### Remediation Mapping (`R1`-`R7`)

- `R1` Notebook backend model:
  - Code: `tldw_Server_API/app/api/v1/endpoints/notes.py`, `tldw_Server_API/app/api/v1/schemas/notes_schemas.py`, `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - Tests: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage39.organization-model.test.tsx`, `tldw_Server_API/tests/Notes/test_notes_api_integration.py`
  - Docs: this plan Stage 2 + Stage 5 sections.
- `R2` Attachments placeholder gap:
  - Code: `tldw_Server_API/app/api/v1/endpoints/notes.py`, `tldw_Server_API/app/api/v1/schemas/notes_schemas.py`, `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - Tests: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage4.revision-attachments.test.tsx`, `tldw_Server_API/tests/Notes/test_notes_api_integration.py`
  - Docs: this plan Stage 3 + Stage 5 sections.
- `R3` Search tips discoverability:
  - Code: `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - Tests: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage11.search-filtering.test.tsx`
  - Docs: this plan Stage 1 + Stage 5 sections.
- `R4` Undo restore pagination gap:
  - Code: `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - Tests: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage32.delete-undo.test.tsx`
  - Docs: this plan Stage 1 + Stage 5 sections.
- `R5` Global save shortcut scope:
  - Code: `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - Tests: `apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage1.editor-reliability.test.tsx`
  - Docs: this plan Stage 1 + Stage 5 sections.
- `R6` Dock mobile docs conflict:
  - Code/Docs alignment: `Docs/Plans/IMPLEMENTATION_PLAN_notes_page_11_responsive_mobile_experience_2026_02_18.md`
  - Verification: cross-plan review and Stage 4 notes in this plan.
- `R7` Backend fixture reset leak:
  - Code: `tldw_Server_API/tests/Notes/test_notes_api_integration.py` fixture reset path
  - Tests: `tldw_Server_API/tests/Notes/test_notes_api_integration.py` (import regression and full file run)
  - Docs: this plan Stage 1 + Stage 5 sections.

## Risk Notes

- Notebook backend introduction may affect query performance and filtering semantics if indexing is not added early.
- Attachment support introduces storage lifecycle and security surface area; strict validation is required.
- Shortcut behavior changes can regress keyboard power-user flow if editor-context detection is too restrictive.

## Definition of Done

- All `R1`-`R7` findings are resolved with code and tests.
- No placeholder-only claims remain for shipped functionality.
- Plan docs reflect actual implementation state and behavior without contradictions.
- Remediation validation passes in both frontend and backend suites.
