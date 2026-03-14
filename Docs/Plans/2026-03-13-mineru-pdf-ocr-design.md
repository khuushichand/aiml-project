# MinerU PDF OCR Design

**Date:** 2026-03-13

## Goal

Add MinerU as an OCR option for PDF ingestion while preserving MinerU's document-layout and table-extraction strengths, keeping the public API stable, and avoiding regressions in OCR discovery, evaluation, and persistence.

## Context

The current OCR path is centered on page-image backends registered in `tldw_Server_API/app/core/Ingestion_Media_Processing/OCR/registry.py` and invoked from `tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/PDF_Processing_Lib.py`.

Existing API inputs already cover the right user-facing controls:

- `enable_ocr`
- `ocr_backend`
- `ocr_mode`
- `ocr_output_format`
- `ocr_prompt_preset`

MinerU upstream is not primarily a page-image OCR backend. It is document-oriented and can emit Markdown plus structured artifacts such as `content_list.json` and `middle.json`, which makes it a better fit for whole-document PDF processing than for the existing `ocr_image(image_bytes)` contract.

Upstream references:

- https://github.com/opendatalab/MinerU
- https://opendatalab.github.io/MinerU/usage/quick_usage/
- https://opendatalab.github.io/MinerU/usage/cli_tools/
- https://opendatalab.github.io/MinerU/reference/output_files/

## Recommended Approach

Expose MinerU to users as `ocr_backend="mineru"`, but implement it internally as a PDF-only, document-level OCR adapter.

This keeps the HTTP API stable while avoiding the main failure mode of a naive integration: flattening MinerU into the existing per-page OCR contract and losing its layout and table advantages.

## Non-Goals

- No non-PDF image OCR support in v1.
- No `pdf_parsing_engine="mineru"` flag in v1.
- No inclusion in `auto` OCR selection in v1.
- No storage of full raw upstream artifact payloads by default.
- No remote MinerU service mode in v1.

## Key Design Decisions

### 1. Public API stays the same

MinerU is selected through the existing OCR surface:

- `enable_ocr=true`
- `ocr_backend=mineru`

No new request fields are required in v1.

### 2. MinerU is PDF-only in v1

MinerU support is valid only inside the PDF ingestion and PDF OCR evaluation flows. If a future feature needs image OCR, that should be designed separately.

### 3. MinerU is document-level, not page-image-first

When `ocr_backend == "mineru"` and OCR should run, the PDF pipeline will bypass `_ocr_pdf_pages(...)` and invoke a new MinerU document adapter on the prepared PDF path.

### 4. MinerU is discoverable, but opt-in only

MinerU should appear in OCR discovery and documentation, but:

- it must not participate in `auto`
- it must not participate in `auto_high_quality`
- it must not participate in `OCR.backend_priority` in v1

This avoids surprising users with a heavier whole-document backend becoming the default OCR path.

### 5. Structured output is normalized and versioned

The integration must not dump raw MinerU output files directly into `analysis_details`.

Instead, it should produce a stable normalized schema:

```json
{
  "schema_version": 1,
  "text": "...",
  "format": "markdown",
  "pages": [],
  "tables": [],
  "artifacts": {},
  "meta": {}
}
```

Raw artifacts may be included only as bounded summaries, excerpts, or explicit debug payloads.

## Architecture

### New internal components

#### `MinerUDocumentAdapter`

Purpose:

- accept a local PDF path
- execute MinerU once for the whole document
- collect output files
- return a normalized internal result

Recommended home:

- `tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/mineru_adapter.py`

Responsibilities:

- resolve MinerU executable configuration
- run MinerU via subprocess with argv-based invocation
- manage temp output directories
- apply timeout and cleanup
- parse MinerU output layout
- produce a provider-neutral result for the PDF pipeline

#### `MinerUResultNormalizer`

Purpose:

- map MinerU outputs into the repo's OCR result shape

Recommended home:

- same module as the adapter initially, unless it grows enough to justify a separate file

Responsibilities:

- determine canonical document text
- normalize output format to `text`, `markdown`, or `json`
- derive `pages[]` when upstream artifacts allow it
- extract `tables[]`
- emit bounded `artifacts`
- populate backend metadata

### PDF pipeline integration

Inside `tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/PDF_Processing_Lib.py`:

1. Existing parser extracts base PDF text.
2. Existing `ocr_mode` logic decides whether OCR should run.
3. If the requested backend is not MinerU, the current `_ocr_pdf_pages(...)` path remains unchanged.
4. If `ocr_backend == "mineru"`, call the new document adapter instead.
5. Persist normalized OCR metadata into `result["analysis_details"]["ocr"]`.
6. Set `result["content"]` using the same current rules:
   - replace content for `always`
   - replace content for `fallback` when parser text is below threshold
   - otherwise append only if the design explicitly chooses append behavior for MinerU

Recommended v1 rule:

- `always`: replace with MinerU text
- `fallback`: replace only when parser text is below threshold

Do not append parser text plus MinerU text by default. That is likely to duplicate content and reduce table/layout quality.

## Discovery And Backend Registry

The initial brainstormed design had a hidden special case in the PDF pipeline. That is not sufficient.

The reviewed design requires discovery alignment because OCR availability is surfaced via:

- `tldw_Server_API/app/core/Ingestion_Media_Processing/OCR/registry.py`
- `tldw_Server_API/app/api/v1/endpoints/ocr.py`

### Required behavior

MinerU must be visible through `/api/v1/ocr/backends`, even if it is not a normal page-image OCR backend.

Recommended discovery payload:

```json
{
  "mineru": {
    "available": true,
    "pdf_only": true,
    "document_level": true,
    "opt_in_only": true,
    "supports_per_page_metrics": true,
    "mode": "cli"
  }
}
```

This can be implemented either by:

- adding a MinerU capability entry to OCR discovery without forcing it into generic OCR backend selection
- or extending the registry to support non-generic backends with capability metadata

Recommended v1 choice:

- keep `get_backend(...)` behavior unchanged for page-image backends
- extend discovery separately for MinerU
- route MinerU explicitly in the PDF pipeline

This is less elegant than a generalized capability registry, but lower-risk for v1.

## Evaluation Integration

OCR evaluation is a critical seam.

`tldw_Server_API/app/core/Evaluations/ocr_evaluator.py` prefers direct per-page OCR for:

- `page_coverage`
- `per_page_metrics`

If MinerU is only document-level and we do not preserve page slices, evaluation quality will silently degrade.

### Required behavior

The MinerU normalizer must emit `pages[]` whenever MinerU artifacts support page-level reconstruction.

If page reconstruction is not possible:

- set `supports_per_page_metrics=false`
- return document-level OCR metrics only
- attach a warning in evaluator output rather than silently reporting incomplete page metrics

Recommended v1 target:

- preserve page text for metrics
- compute `total_pages` and `ocr_pages` from normalized MinerU output

## Normalized Structured Output Schema

The normalized payload persisted to `analysis_details.ocr.structured` should be:

```json
{
  "schema_version": 1,
  "text": "document markdown or text",
  "format": "markdown",
  "pages": [
    {
      "page": 1,
      "text": "...",
      "tables": [],
      "blocks": [],
      "meta": {}
    }
  ],
  "tables": [
    {
      "page": 1,
      "format": "html",
      "content": "<table>...</table>"
    }
  ],
  "artifacts": {
    "content_list_excerpt": [],
    "middle_json_excerpt": {}
  },
  "meta": {
    "backend": "mineru",
    "mode": "cli",
    "supports_per_page_metrics": true
  }
}
```

### Rules

- `schema_version` is mandatory.
- `text` is the canonical normalized OCR text.
- `format` should usually be `markdown` for MinerU.
- `pages` is required when page-level reconstruction is available.
- `tables` should be filled when MinerU yields table structure.
- `artifacts` must contain only bounded values.
- `meta` must include provider metadata and capability flags.

### Explicit size control

Do not persist full raw `content_list.json` or full raw `middle.json` by default.

Instead:

- store bounded excerpts
- store counts and summaries
- optionally store a debug payload only behind an explicit config flag

This matters because `analysis_details` is reused downstream for indexing and visual-document persistence, and unbounded payloads will increase API response size and storage costs.

## Parameter Mapping

Existing OCR parameters do not all map cleanly to MinerU.

### Supported in v1

- `ocr_backend=mineru`
- `ocr_mode=fallback|always`
- `ocr_output_format=text|markdown|json`

Recommended behavior:

- `text`: derive plain text from normalized Markdown
- `markdown`: return canonical MinerU Markdown
- `json`: same canonical text plus normalized structured payload

### Limited support in v1

- `ocr_prompt_preset`

Recommended preset support:

- `doc`
- `table`
- `json`

All other presets should either:

- map to a safe default, or
- emit a warning and fall back to `doc`

### Ignored or advisory in v1

- `ocr_lang`
- `ocr_dpi`

MinerU may not meaningfully honor the same semantics as page-render OCR backends.

Recommended behavior:

- record these inputs in metadata if supplied
- add warnings when they are ignored
- document that they are advisory/no-op for MinerU v1

## Deployment Mode

### Recommended v1 mode: CLI

Use a CLI subprocess adapter for v1.

Reasons:

- optional dependency boundary is cleaner
- fewer import and environment conflicts
- easier error isolation
- easier to support user-managed MinerU installs

### Not in v1

- direct Python library embedding
- remote service mode

These can be added later once the normalized contract is stable.

## Configuration

Recommended v1 environment variables:

- `MINERU_CMD`
- `MINERU_TIMEOUT_SEC`
- `MINERU_MAX_CONCURRENCY`
- `MINERU_TMP_ROOT`
- `MINERU_DEBUG_SAVE_RAW`

### Notes

- `MINERU_CMD` should be tokenized safely, not shell-interpolated.
- `MINERU_MAX_CONCURRENCY` should apply at the document level, not page level.
- `MINERU_TIMEOUT_SEC` should fail the MinerU run cleanly and preserve fallback behavior.
- `MINERU_DEBUG_SAVE_RAW` should be off by default.

## Failure Handling

MinerU must be optional and non-fatal.

### If MinerU is requested but unavailable

- do not crash the entire request
- return an OCR warning
- preserve parser text if available

### If MinerU fails in `fallback` mode

- preserve parser text
- attach warning in `result["warnings"]`

### If MinerU fails in `always` mode

Recommended v1 behavior:

- preserve parser text if any exists
- attach warning
- mark backend failure in `analysis_details.ocr`

This is more resilient than turning an OCR backend failure into a full document failure.

### Logging

Log:

- command mode
- duration
- timeout or exit code
- whether structured artifacts were found
- whether page reconstruction succeeded

Never log raw document content or secrets.

## Testing Strategy

### Unit tests

Add tests for:

- command construction
- timeout and cleanup behavior
- MinerU output normalization
- page reconstruction
- table extraction mapping
- schema version and bounded artifact behavior

### PDF pipeline tests

Add tests for:

- `ocr_backend=mineru` dispatch path
- `fallback` mode replacing only low-text parser output
- `always` mode replacing content
- ignored-parameter warnings
- failure fallback preserving parser text

### Evaluator tests

Add tests for:

- document-level MinerU OCR evaluation
- page-level metrics when `pages[]` is available
- explicit warning path when page metrics are unavailable

### API and discovery tests

Add tests for:

- `/api/v1/ocr/backends` includes MinerU capability metadata
- PDF endpoints accept `ocr_backend=mineru`
- structured OCR output shape remains stable

## Documentation Changes

Update:

- `Docs/OCR/OCR_Providers.md`
- `Docs/API-related/OCR_API_Documentation.md`
- environment variable docs

The docs must explicitly call out:

- PDF-only support
- document-level execution
- `auto` exclusion
- advisory/no-op handling for `ocr_lang` and `ocr_dpi`

## Rollout Plan

### Phase 1

- CLI-based PDF-only MinerU support
- normalized schema
- no `auto`
- no remote mode

### Phase 2

- optional remote service mode
- potential `pdf_parsing_engine="mineru"` alias
- richer artifact persistence if a bounded storage design exists

## Risks And Mitigations

### Risk: discovery/runtime mismatch

Mitigation:

- include MinerU in `/ocr/backends`
- mark it as `pdf_only` and `document_level`

### Risk: eval metrics degrade silently

Mitigation:

- require `pages[]` reconstruction when possible
- otherwise emit explicit evaluator warnings

### Risk: payload bloat

Mitigation:

- normalize and bound artifacts
- disable raw storage by default

### Risk: parameter confusion

Mitigation:

- document exact parameter mapping
- warn when inputs are ignored

### Risk: subprocess safety and cleanup

Mitigation:

- argv-only execution
- explicit timeout
- explicit temp directory cleanup

## Final Recommendation

Implement MinerU in v1 as a PDF-only, document-level OCR backend selected through `ocr_backend=mineru`, executed through a CLI adapter, surfaced in OCR discovery as an opt-in PDF capability, and normalized into a bounded, versioned structured schema under `analysis_details.ocr.structured`.

This preserves MinerU's strengths while keeping the current API stable and avoiding discovery, evaluation, and persistence regressions.
