# Implementation Plan: Characters Gap 02 - Default Preference Persistence (2026-02-19)

## Issue Summary

Default character preference is primarily local-state/local-storage driven and not reliably persisted in user-scoped backend state.

## Stage 1: Define Preference Persistence Contract
**Goal**: Define backend-owned contract for get/set/clear of default character preference.
**Success Criteria**:
- Endpoint or preference field for default character is defined.
- Ownership rules are explicit (per user, nullable, soft-delete behavior).
- Error cases are specified (missing character, forbidden, deleted default).
**Tests**:
- API contract tests for set/get/clear with ownership checks.
- Schema validation tests for invalid payloads.
**Status**: Complete
**Update (2026-02-19)**:
- Reused the existing `/api/v1/users/me/profile` preferences contract instead of adding a new endpoint.
- Added canonical key `preferences.chat.default_character_id` to the profile catalog.
- Defined clear semantics via `null` value update on the same key.

## Stage 2: Implement Backend Persistence and Retrieval
**Goal**: Add backend storage and retrieval paths for default character preference.
**Success Criteria**:
- Preference writes are persisted server-side per user.
- Chat bootstrap/read paths can resolve stored default.
- Clear action removes preference deterministically.
**Tests**:
- Integration tests for persistence across requests/sessions.
- Integration tests for deleted/default-invalid scenarios.
**Status**: Complete
**Update (2026-02-19)**:
- Catalog now accepts and validates `preferences.chat.default_character_id` as a user-editable preference.
- Added backend tests for set/get/clear lifecycle and invalid-type rejection in `tldw_Server_API/tests/UserProfile/test_user_profile_updates.py`.
- Added `tldwClient` profile APIs for get/update profile plus default-character preference helpers.

## Stage 3: Wire UI to Backend with Local Fallback
**Goal**: Move UI set/clear/read flow to backend-first behavior with graceful local fallback.
**Success Criteria**:
- Characters manager set-default action calls backend.
- Chat preselect loads backend default unless explicit user override exists.
- Local storage is fallback/cache only during migration period.
**Tests**:
- Frontend integration test for set default, reload, and preselect behavior.
- Regression test proving explicit manual selection overrides default.
**Status**: Complete
**Update (2026-02-19)**:
- `CharactersManager` now writes default selection through backend preference first, then updates local cache.
- `Sidepanel` chat bootstrap now reads server default preference first and falls back to local cache when server value is unavailable.
- Existing explicit-selection override guard remains active in bootstrap logic.
- Added frontend assertions that set/clear default row actions call backend write-through (`setDefaultCharacterPreference`).
- Added extension integration coverage in `apps/extension/tests/e2e/playground-character-selection.spec.ts` for server-default preselect on fresh load plus manual override persistence across reload.
- The new integration case follows existing real-server preflight/skip guards used by the character e2e suite.
