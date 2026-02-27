## Stage 1: Moodboard Schema Contracts
**Goal**: Define API schema models for moodboards and validate baseline create behavior.
**Success Criteria**: `notes_moodboards.py` exists with create/update/response models and validators for empty names and smart-rule payloads; schema unit tests pass.
**Tests**: `python -m pytest tldw_Server_API/tests/Notes_NEW/unit/test_notes_moodboard_schemas.py -q`
**Status**: Complete

## Stage 2: DB Schema + Data Access
**Goal**: Add moodboard tables and CRUD/query methods in Notes DB layer.
**Success Criteria**: Migration creates `moodboards` and `moodboard_notes`; backend methods support create/list/get/update/delete plus pin/unpin/list-notes.
**Tests**: New DB unit tests covering table creation, board-note membership uniqueness, mixed/manual rule semantics.
**Status**: In Progress

## Stage 3: Notes API Endpoints
**Goal**: Expose moodboard endpoints under Notes API with auth and error handling.
**Success Criteria**: Router includes create/list/detail/update/delete and membership operations; response models align with schemas.
**Tests**: Endpoint integration tests for happy path, not-found, validation, and duplicate pin handling.
**Status**: Not Started

## Stage 4: Notes UI Moodboard View
**Goal**: Add third Notes view mode (Moodboard) with masonry wall and note-detail navigation.
**Success Criteria**: User can browse moodboards, view tile covers, open a note, and see compact related/backlinks/sources strip in detail panel.
**Tests**: Frontend unit/component tests for board rendering and note opening behavior.
**Status**: Not Started

## Stage 5: Verification + Documentation
**Goal**: Verify quality gates and document new user/developer behavior.
**Success Criteria**: Targeted tests pass, Bandit run on touched scope is clean for new findings, docs updated.
**Tests**: Relevant `pytest` subsets + `python -m bandit -r <touched_paths> -f json -o /tmp/bandit_notes_moodboard.json`
**Status**: Not Started
