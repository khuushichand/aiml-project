# Implementation Plan: Characters Gap 05 - Restore Retention Policy (2026-02-19)

## Issue Summary

UI messaging implies a fixed restore window, but backend enforcement and explicit policy behavior need stronger alignment.

## Stage 1: Specify Retention Policy and Error Semantics
**Goal**: Define enforceable restore eligibility policy for soft-deleted characters.
**Success Criteria**:
- Retention window and eligibility rules are documented.
- Policy source of truth is configurable and versioned.
- Error response format for out-of-window restores is explicit.
**Tests**:
- Unit tests for eligibility calculation around boundary timestamps.
- API schema tests for out-of-window error payload shape.
**Status**: Complete
**Update (2026-02-19)**:
- Defined the restore retention policy source of truth as `CHARACTERS_RESTORE_RETENTION_DAYS` (default `30`, minimum valid value `1`).
- Added endpoint-level retention config validation in `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`.
- Added explicit out-of-window error semantics using `RestoreWindowExpiredError` mapped to HTTP `409` with actionable restore-window detail.

## Stage 2: Implement Backend Enforcement
**Goal**: Enforce retention window in restore endpoint and related listing behavior.
**Success Criteria**:
- Restore endpoint rejects records outside retention window.
- Deleted-only lists indicate eligibility where needed.
- Logs/metrics capture restore denials with reason codes.
**Tests**:
- Integration tests for in-window restore success.
- Integration tests for out-of-window restore rejection.
**Status**: Complete
**Update (2026-02-19)**:
- Extended `CharactersRAGDB.restore_character_card` to enforce restore eligibility against soft-delete timestamp (`last_modified`) and configured retention window.
- Wired retention enforcement from API -> facade -> DB via `restore_character_from_db(..., retention_days=...)`.
- Added denial logging with explicit reason code `restore_window_expired` in the characters restore endpoint.
- Added backend integration coverage for out-of-window restore rejection in `tldw_Server_API/tests/Characters/test_characters_endpoint.py`.

## Stage 3: Align UI Messaging and Recovery UX
**Goal**: Make client messaging and actions accurately reflect backend policy.
**Success Criteria**:
- UI no longer overpromises restore availability.
- Out-of-window errors are rendered with actionable guidance.
- Docs and inline help reference actual retention behavior.
**Tests**:
- Frontend tests for out-of-window error rendering.
- Manual checklist for copy consistency across surfaces.
**Status**: Complete
**Update (2026-02-19)**:
- Updated deleted-list copy in `apps/packages/ui/src/components/Option/Characters/Manager.tsx` to avoid fixed-day promises and reference server-enforced restore window behavior.
- Added/updated manager test coverage for restore-window-expired error rendering in `apps/packages/ui/src/components/Option/Characters/__tests__/Manager.first-use.test.tsx`.
- Added user-facing documentation note in `Docs/User_Guides/User_Guide.md` describing restore window behavior and the default policy.
