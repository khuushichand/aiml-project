# PRD: PDF → Extract → Chunk in Chunking Playground (reuse /media/process-pdfs)

## Summary
Add a PDF upload input to the existing Chunking Playground, reuse `/api/v1/media/process-pdfs` (no‑DB) to extract text and chunk in one call, require a PDF preview in the UI, introduce a split‑view inspector, and expose a chunking options schema so the form can be generated dynamically.

## Context / Existing Code
- Chunking Playground (shared UI for WebUI + Extension):
  - `apps/packages/ui/src/components/Option/ChunkingPlayground/index.tsx`
  - `apps/packages/ui/src/components/Option/ChunkingPlayground/CompareView.tsx`
  - `apps/packages/ui/src/components/Option/ChunkingPlayground/ChunkCardView.tsx`
  - `apps/packages/ui/src/components/Option/ChunkingPlayground/ChunkInlineView.tsx`
- Chunking API client:
  - `apps/packages/ui/src/services/chunking.ts`
- Chunking endpoints + schema:
  - `tldw_Server_API/app/api/v1/endpoints/chunking.py`
  - `tldw_Server_API/app/api/v1/schemas/chunking_schema.py`
- PDF processing (no‑DB):
  - `tldw_Server_API/app/api/v1/endpoints/media/process_pdfs.py`

## Problem
The Chunking Playground currently chunks text from paste/upload (txt/md), sample text, or existing media. It does not let users upload a PDF and immediately see extracted text + chunks, nor does it provide a split‑view inspector (PDF/text left, chunk list right). Chunking controls are hardcoded rather than schema‑driven.

## Goals
- Enable PDF upload → extract → chunk within the existing Chunking Playground (WebUI + Extension parity).
- Provide a split‑view inspector for PDF/text on the left and chunk list/detail on the right.
- Expose a schema endpoint for chunking options so the UI can render fields dynamically.

## Non‑Goals
- No new standalone page; must live inside Chunking Playground.
- No database persistence for PDF extraction.
- No new OCR/extraction engine additions.

## Target Surfaces
- WebUI and Extension via shared component: `apps/packages/ui/src/components/Option/ChunkingPlayground/`

## User Stories
1) As a user, I can upload a PDF and get extracted text + chunks in the playground.
2) As a user, I can view PDF pages side‑by‑side with chunk detail.
3) As a user, I can adjust chunk settings generated from a schema rather than a fixed UI.

## Functional Requirements

**Note:** Expose OCR endpoints/engines for PDF parsing so users can compare different backends and see their extraction quality/performance side‑by‑side (engine selection + comparison view).

### A) PDF Upload → Extract → Chunk (reuse `/api/v1/media/process-pdfs`)
- Add a new input source “PDF” in Chunking Playground input selector.
- Support drag‑and‑drop PDF upload (single file).
- On “Chunk Text”, call `/api/v1/media/process-pdfs` and pass chunking options.
- Response must include, per PDF result:
  - `conversion_text` (full extracted text used for chunking)
  - `chunks` (chunked output with metadata)
  - `metadata` (full extraction metadata; returned verbatim)

**Required response shape (per result)**
```json
{
  "status": "Success" | "Error",
  "processing_source": "...",
  "conversion_text": "...",
  "chunks": [ { "text": "...", "metadata": {...} } ],
  "metadata": { ... },
  "error": "..."
}
```

### B) Split‑View Inspector (PDF/Text Left, Chunks Right)
- Add a new view mode in Chunking Playground (e.g., “Split”).
- Left panel:
  - PDF preview (required) using object URL from uploaded file.
  - If preview fails to render, show blocking error (no fallback to text-only view).
- Right panel:
  - chunk list + chunk detail using existing chunk components.
- Keep inside shared `ChunkingPlayground` component for WebUI + Extension parity.

### C) Chunking Option Schema Endpoint
- Extend `/api/v1/chunking/capabilities` to include a schema definition:
  - types, defaults, descriptions, constraints derived from `ChunkingOptionsRequest`.
- Keep existing capability fields backward‑compatible.
- UI should use schema when present and fall back to hardcoded controls if schema fetch fails.

## UX / UI Requirements
- Must remain inside existing Chunking Playground tabs (Single/Compare/Templates/Capabilities).
- Add “PDF” input source alongside Paste/Upload/Sample/Media.
- Add view toggle “Split” alongside Cards/Inline.
- Require PDF preview; show an error if preview cannot render.
- Display full extraction metadata (collapsible panel).

## Error Handling
- If extraction fails: show `results[].error`.
- If chunking fails: show error and keep PDF preview visible.
- If schema endpoint fails: fall back to existing hardcoded fields.

## Telemetry / Logging
- Log usage of input source (pdf vs other).
- Log success/failure and latency for `/media/process-pdfs`.
- Track usage of “Split” view.

## Performance
- PDF conversion may be heavy; UI must show loading state.
- Chunking should reuse existing chunking code path to avoid duplication.

## Risks
- Response shape mismatches when reusing `/media/process-pdfs` without normalization.
- Schema-driven UI may not fully reflect method-specific logic without extra hints.

## Acceptance Criteria
- PDF upload → preview visible → chunk results shown in Split view.
- Extracted text + chunks come from `/api/v1/media/process-pdfs` without DB persistence.
- Full extraction metadata is surfaced in the UI.
- Chunking options UI is schema‑driven with fallback.

## Dependencies
- Backend changes in `process_pdfs.py` to return conversion text, chunks, and metadata.
- Schema extension in `/api/v1/chunking/capabilities`.
- Shared UI changes in `apps/packages/ui/src/components/Option/ChunkingPlayground/`.
