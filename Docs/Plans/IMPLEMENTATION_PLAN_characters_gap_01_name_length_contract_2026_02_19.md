# Implementation Plan: Characters Gap 01 - Name-Length Contract (2026-02-19)

## Issue Summary

Character name-length constraints were inconsistent between UI and backend behavior, causing contradictory validation outcomes and messaging.

## Stage 1: Confirm Canonical Contract
**Goal**: Set a single canonical character-name max length and align all validation messaging.
**Success Criteria**:
- Canonical max length is explicitly documented.
- UI and API reference the same limit in validation text.
- Contract decision is reflected in plan and tests.
**Tests**:
- Unit check for UI validator boundary values.
- API schema boundary checks for accepted/rejected lengths.
**Status**: Complete

## Stage 2: Enforce Contract in UI and API Paths
**Goal**: Ensure create/edit inputs and API requests enforce the same max length at runtime.
**Success Criteria**:
- UI input `maxLength` is aligned to canonical value.
- Backend accepts canonical boundary and rejects canonical+1.
- Display truncation remains separate from storage validation.
**Tests**:
- Frontend tests assert input `maxLength` and over-limit error message.
- Backend integration tests cover max-length accept and over-limit reject.
**Status**: Complete

## Stage 3: Backward-Compatibility and Documentation Cleanup
**Goal**: Prevent regressions from legacy over-limit records and document policy clearly.
**Success Criteria**:
- Explicit compatibility policy exists for any pre-existing invalid records.
- API/UI behavior for loading legacy records is deterministic and tested.
- Developer docs reference the canonical contract and rationale.
**Tests**:
- Integration test for listing/loading legacy boundary edge cases.
- Documentation checklist verification in review.
**Status**: Not Started
