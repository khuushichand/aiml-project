## Stage 1: Bundle Reveal Assets
**Goal**: Provide a local Reveal.js-compatible asset bundle so exports work without env overrides.
**Success Criteria**: `tldw_Server_API/app/core/Slides/revealjs` exists with required files and export no longer errors by default.
**Tests**: `python -m pytest tldw_Server_API/tests/Slides/test_slides_export.py -q`
**Status**: Complete

## Stage 2: Marp Theme Override
**Goal**: Add `marp_theme` support across schemas, storage, validation, and export.
**Success Criteria**: Requests accept `marp_theme`, stored in DB, and Markdown export uses the override.
**Tests**: `python -m pytest tldw_Server_API/tests/Slides/test_slides_db.py -q`, `python -m pytest tldw_Server_API/tests/Slides/test_slides_export.py -q`
**Status**: Complete

## Stage 3: Docs + Metrics
**Goal**: Document Slides API and add basic generation/export metrics.
**Success Criteria**: New API doc in `Docs/` and metrics recorded for generation/export success/error paths.
**Tests**: `python -m pytest tldw_Server_API/tests/Slides/test_slides_api.py -q` (smoke for changes)
**Status**: Complete

## Stage 4: Streaming Generation (Future, Optional)
**Goal**: Stream slide generation output while still persisting the final presentation (deferred to a future phase).
**Success Criteria**: Streaming endpoint available with clear protocol and unit/integration coverage.
**Tests**: TBD (streaming test)
**Status**: Not Started
