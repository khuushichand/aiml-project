## Stage 1: Backend PDF Extraction + Chunking Response Shape
**Goal**: Extend `/api/v1/media/process-pdfs` to return `{ conversion_text, chunks, metadata }` per result and support OCR engine selection/comparison hooks.
**Success Criteria**:
- `/api/v1/media/process-pdfs` returns `conversion_text`, `chunks`, and `metadata` for each successful PDF result.
- Request accepts optional OCR engine selection (single engine or list for comparison).
- Errors are normalized without breaking existing callers.
**Tests**:
- New integration tests for `/api/v1/media/process-pdfs` response shape (success + error cases).
- If OCR engine selection is added, test single engine selection and invalid engine handling.
**Status**: Complete

**File-by-file tasks**:
- `tldw_Server_API/app/api/v1/endpoints/media/process_pdfs.py`
  - Add optional OCR engine selection params (e.g., `ocr_backend`, `ocr_backends[]`).
  - Ensure extracted text used for chunking is surfaced as `conversion_text`.
  - Attach `chunks` and full extraction `metadata` to each result.
- `tldw_Server_API/app/core/Ingestion_Media_Processing/pipeline.py`
  - If needed, expose extraction text + metadata from PDF processing results.
- `tldw_Server_API/app/core/Ingestion_Media_Processing/result_normalization.py`
  - Extend `normalise_pdf_result` to include `conversion_text`, `chunks`, `metadata`.
- `tldw_Server_API/app/api/v1/schemas/media_request_models.py`
  - Add request fields for OCR engine selection (if not already present).
- `tldw_Server_API/app/api/v1/endpoints/ocr.py`
  - Expose OCR engine list endpoint (if not already available) to drive UI dropdown.
- `tldw_Server_API/tests/...`
  - Add tests for response shape and engine selection.

## Stage 2: Chunking Schema Exposure
**Goal**: Extend `/api/v1/chunking/capabilities` to include schema definitions for chunking options.
**Success Criteria**:
- Capabilities response includes a schema object with types/defaults/descriptions/constraints.
- Existing clients continue to work without changes.
**Tests**:
- Unit/integration test validating schema shape and presence of required fields.
**Status**: Complete

**File-by-file tasks**:
- `tldw_Server_API/app/api/v1/endpoints/chunking.py`
  - Add schema generation and include in capabilities response.
- `tldw_Server_API/app/api/v1/schemas/chunking_schema.py`
  - Add helper to derive schema from `ChunkingOptionsRequest` field metadata.
- `tldw_Server_API/tests/...`
  - Validate schema output in capabilities response.

## Stage 3: Playground PDF Input + Split View + Schema-Driven Form
**Goal**: Add PDF input source, split-view inspector, and schema-driven chunking controls in the shared Chunking Playground component.
**Success Criteria**:
- User can upload a PDF and see PDF preview + chunk results in Split view.
- UI is generated from schema when available; fallback to existing controls if not.
- WebUI and Extension remain in parity (single shared component).
**Tests**:
- Component tests for PDF input flow and split view rendering.
- Smoke test for `/chunking-playground` page.
**Status**: Complete

**File-by-file tasks**:
- `apps/packages/ui/src/components/Option/ChunkingPlayground/index.tsx`
  - Add “PDF” input source and upload handling.
  - Add “Split” view toggle and wire to new view component.
  - Call `/api/v1/media/process-pdfs` via new service helper; map response to `inputText`, `chunks`, `metadata`.
  - Render full extraction metadata in a collapsible panel.
- `apps/packages/ui/src/components/Option/ChunkingPlayground/SplitView.tsx` (new)
  - Left: PDF preview (required).
  - Right: chunk list/detail using existing chunk components.
- `apps/packages/ui/src/services/chunking.ts`
  - Add `chunkPdfViaProcessPdfs()` helper.
  - Add schema-aware types for the capabilities response.
- `apps/packages/ui/src/components/Option/ChunkingPlayground/*`
  - Refactor existing settings UI to render from schema when present.

## Stage 4: OCR Engine Comparison UX (Optional but noted in PRD)
**Goal**: Allow users to select OCR backend(s) for PDF parsing and compare outputs.
**Success Criteria**:
- OCR engine list is visible in UI and sourced from server.
- Users can pick an engine or run comparison (if multi-engine supported).
**Tests**:
- UI test for OCR engine selection control.
- Integration test for multi-engine request behavior (if implemented).
**Status**: Not Started (Optional)

**File-by-file tasks**:
- `apps/packages/ui/src/components/Option/ChunkingPlayground/index.tsx`
  - Add OCR engine selector (single + multi-select if comparison supported).
- `apps/packages/ui/src/services/chunking.ts`
  - Add helper for OCR engine list endpoint.
- `tldw_Server_API/app/api/v1/endpoints/ocr.py`
  - Add/confirm engine list endpoint.
- `tldw_Server_API/app/api/v1/endpoints/media/process_pdfs.py`
  - Support passing selected engine(s) through to pipeline.
