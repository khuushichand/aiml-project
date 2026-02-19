# Implementation Plan: Flashcards APKG Import + Round-Trip Validation (2026-02-18)

## Stage 1: Backend APKG Import Parser
**Goal**: Add a reusable APKG parser that extracts note/deck/model/scheduling data from Anki packages.
**Success Criteria**: Parser returns normalized flashcard import rows and structured row-level errors for unsupported/invalid notes.
**Tests**: Unit tests for basic, reverse, cloze, scheduling extraction, and invalid APKG handling.
**Status**: Complete

## Stage 2: Flashcards API Endpoint + Persistence
**Goal**: Add `/api/v1/flashcards/import/apkg` upload endpoint and persist parsed cards with scheduling metadata.
**Success Criteria**: Endpoint accepts `.apkg`, imports cards/decks/tags, returns `{ imported, items, errors }`, and enforces import caps.
**Tests**: API integration tests for happy path, scheduling preservation, and invalid upload errors.
**Status**: Complete

## Stage 3: Web UI APKG Import Mode
**Goal**: Add APKG as a first-class import mode in Flashcards Import/Export tab.
**Success Criteria**: UI supports selecting APKG file, calls API upload path, displays detailed results/errors, and keeps existing import modes intact.
**Tests**: Vitest coverage for APKG mode mutation routing and transfer summary compatibility.
**Status**: Complete

## Stage 4: End-to-End Round-Trip Verification
**Goal**: Validate APKG export -> APKG import round-trip behavior for core card models and scheduling fields.
**Success Criteria**: Automated tests verify model/deck/tag/scheduling fidelity at acceptable parity level.
**Tests**: Backend round-trip tests using exporter output as importer input.
**Status**: Complete

## Post-Completion Remediation (2026-02-19)

- Follow-up plan: `Docs/Plans/IMPLEMENTATION_PLAN_flashcards_findings_remediation_2026_02_19.md` (Stage 4).
- APKG import UX now includes large-import confirmation parity with other import modes:
  - APKG large-file/estimated-item preflight confirmation before mutation execution.
  - APKG-specific confirmation summary copy showing file name, file size, and estimated item count.
