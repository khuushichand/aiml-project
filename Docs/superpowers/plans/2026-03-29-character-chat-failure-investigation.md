# Character Chat Failure Investigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the five remaining character-chat and character-db regressions by reproducing them in isolation, identifying the root causes, and applying the smallest compatible fixes.

**Architecture:** Treat these as a few bounded regression clusters rather than unrelated failures. First reproduce and classify each failing test, then patch the shared production paths in the character chat endpoints, ChaCha DB initialization/postgres schema handling, and conversation validation logic, followed by focused regression verification.

**Tech Stack:** FastAPI, pytest, sqlite/postgres adapters, CharactersRAGDB, character chat endpoint modules

---

## Stage 1: Reproduce And Classify
**Goal:** Reproduce each failure in isolation and capture the exact traceback.
**Success Criteria:** Each of the five failing tests is reproduced directly with a concrete error path.
**Tests:** The five pytest node IDs from the failure summary.
**Status:** Complete

- [x] Run `test_legacy_complete_deprecation_headers`
- [x] Run `test_sync_log_entity_column_adapts_to_entity_uuid_on_postgres` (skipped locally because PostgreSQL fixture was unavailable; root cause confirmed by code-path inspection)
- [x] Run `test_create_chat_with_alternate_random_greeting`
- [x] Run `test_full_chat_session_flow_integration`
- [x] Run `test_add_conversation_missing_char_id_fails`

## Stage 2: Patch Shared Regressions
**Goal:** Fix the smallest production code paths responsible for the failures.
**Success Criteria:** The isolated failures pass after minimal targeted edits.
**Tests:** Re-run the failing tests immediately after each change.
**Status:** Complete

- [x] Add or restore any endpoint/module compatibility seams required by legacy tests
- [x] Fix postgres-specific schema/bootstrap behavior for the sync-log entity-column test
- [x] Fix character chat greeting randomness hook and session-flow behavior
- [x] Fix conversation validation/error handling for missing character IDs

## Stage 3: Verify And Close
**Goal:** Prove the fixes hold together and do not introduce obvious regressions.
**Success Criteria:** Focused pytest verification is green and Bandit is clean on touched files.
**Tests:** Five original failing tests, any interacting character-chat subset, and Bandit on touched scope.
**Status:** Complete

- [x] Re-run all five original failing tests together
- [x] Re-run any interacting character-chat/character-db tests identified during debugging
- [x] Run `python -m bandit` on touched files from the project venv
