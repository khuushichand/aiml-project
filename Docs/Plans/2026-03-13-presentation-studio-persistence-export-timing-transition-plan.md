## Stage 1: Lock Down The Contract
**Goal**: Add regression coverage for Presentation Studio timing/transition metadata across create, patch, export, and version flows.
**Success Criteria**: Tests prove slide `metadata.studio.transition`, `timing_mode`, and `manual_duration_ms` survive persistence and JSON export in canonical form.
**Tests**: `python -m pytest tldw_Server_API/tests/Slides/test_slides_api.py -k studio`
**Status**: Complete

## Stage 2: Normalize At The API Boundary
**Goal**: Canonicalize Presentation Studio slide metadata in the Slides API before saving or returning presentations.
**Success Criteria**: Missing/invalid timing-transition fields are normalized consistently with the editor and renderer contract; images validation still works.
**Tests**: `python -m pytest tldw_Server_API/tests/Slides/test_slides_api.py -k studio`
**Status**: Complete

## Stage 3: Align WebUI Create Paths
**Goal**: Ensure new WebUI and extension-created projects send explicit studio defaults so first-save/export behavior matches the UI.
**Success Criteria**: Newly created decks persist explicit transition/timing defaults without waiting for a later autosave.
**Tests**: `bunx vitest run src/components/Option/PresentationStudio/__tests__/PresentationStudioPage.test.tsx`
**Status**: Complete

## Stage 4: Verify And Close
**Goal**: Run the smallest relevant backend/frontend regressions plus Bandit on touched production backend code.
**Success Criteria**: Targeted tests pass and Bandit reports zero findings for touched backend production files.
**Tests**: `python -m pytest tldw_Server_API/tests/Slides/test_slides_api.py tldw_Server_API/tests/Slides/test_presentation_rendering.py -q`, `bunx vitest run ...`, `python -m bandit -r tldw_Server_API/app/api/v1/endpoints/slides.py`
**Status**: Complete
