# PDF Ingestion Pipeline

## Overview

Parses PDF files to Markdown/text using PyMuPDF or pymupdf4llm (optionally Docling), extracts metadata, optionally runs OCR on pages with low text, chunks content, and can run analysis/summarization. Returns a single structured result dict; DB-agnostic.

## Primary Functions

Module: `tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib`

- `process_pdf(file_input, filename, parser='pymupdf4llm', title_override=None, author_override=None, keywords=None, perform_chunking=True, chunk_options=None, perform_analysis=False, api_name=None, api_key=None, custom_prompt=None, system_prompt=None, summarize_recursively=False, enable_ocr=False, ocr_backend=None, ocr_lang='eng', ocr_dpi=300, ocr_mode='fallback', ocr_min_page_text_chars=40) -> Dict[str, Any]`
- `async process_pdf_task(file_bytes, filename, ...) -> Dict[str, Any]` (async wrapper for API)

### Parameters (selected)

- file_input: `str|bytes|Path` (bytes written to temp file internally when needed).
- parser: `pymupdf4llm` (default), `pymupdf`, or `docling` (if installed).
- enable_ocr/ocr_*: render pages and OCR text when needed; Tesseract CLI backend supported.
- perform_chunking: chunk extracted text; chunk options: `method`, `max_size`, `overlap`.
- perform_analysis: summarize per chunk and combine if `summarize_recursively=True`.

Notes on OCR backends:
- `ocr_backend`: supports `tesseract` (CLI), `dots` (dots.ocr), `points` (POINTS-Reader), `auto`/None (first available), and `auto_high_quality` (tries `points` → `dots` → `tesseract`).

### Return Structure

```
{
  "status": "Success"|"Warning"|"Error",
  "input_ref": str,                # filename
  "processing_source": str,        # temp path or original path used
  "media_type": "pdf",
  "parser_used": str,
  "content": Optional[str],
  "metadata": Optional[Dict],      # {title, author, page_count, creationDate, modDate, producer, creator, raw}
  "chunks": Optional[List[Dict]],
  "analysis": Optional[str],
  "keywords": List[str],
  "warnings": Optional[List[str]],
  "error": Optional[str],
  "analysis_details": Dict
}
```

## Example

```python
from pathlib import Path
from tldw_Server_API.app.core.Ingestion_Media_Processing.PDF.PDF_Processing_Lib import process_pdf

pdf_bytes = Path("/abs/report.pdf").read_bytes()
res = process_pdf(
    file_input=pdf_bytes,
    filename="report.pdf",
    parser="pymupdf4llm",
    perform_chunking=True,
    chunk_options={"method": "sentences", "max_size": 1500, "overlap": 200},
    perform_analysis=True,
    api_name="openai",
    custom_prompt="Summarize in 10 bullets",
    summarize_recursively=True,
    enable_ocr=False,
)
print(res["status"], len(res.get("chunks") or []))
```

## Endpoint Integration

- `POST /api/v1/media/process-pdfs` (media.py) uses the async wrapper `process_pdf_task`.

Notes:
- URL downloads are restricted to `.pdf` files. URLs without a `.pdf` suffix are still accepted if the final redirected response provides either a `Content-Disposition` filename ending in `.pdf` or `Content-Type: application/pdf`. Otherwise, the URL is rejected.
- The endpoint gates chunking behind analysis: `perform_chunking` is only applied when `perform_analysis=True`. Library usage does not enforce this.
- API key handling: the endpoint reads provider keys from server configuration; passing `api_key` in the request is not required. Library usage can pass `api_key` explicitly.

## Dependencies & Config

- `pymupdf`, `pymupdf4llm` (default), optional `docling`.
- OCR: Backends managed via `OCR/registry.py` with auto-detection; page rendering via PyMuPDF. Optional env/config: `OCR_PAGE_CONCURRENCY` and `OCR.backend_priority`.
- Config: size limits are defined as `media_processing.max_pdf_file_size_mb` and enforced at upload validation (`Upload_Sink`). `pdf_conversion_timeout_seconds` is loaded but not currently applied within the PDF processing function.

## Error Handling & Notes

- Missing optional parsers fallback to alternatives; errors are recorded in `warnings`/`error`.
- OCR is selective when `ocr_mode='fallback'` (pages with minimal text).
- Summarization runs only if `perform_analysis=True` and both `api_name` and an API key are available; results are attached per-chunk and optionally combined.
- `analysis_details` may include OCR metadata `{backend, mode, dpi, lang, total_pages, ocr_pages, page_concurrency, ...}` and summarization settings used.
- Metrics logged via `metrics_logger` (attempts, durations, errors).
