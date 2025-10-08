# PDF Ingestion Pipeline

## Overview

Parses PDF files to Markdown/text using PyMuPDF or pymupdf4llm (optionally Docling), extracts metadata, optionally runs OCR on pages with low text, chunks content, and can run analysis/summarization. Returns a single structured result dict; DB‑agnostic.

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

### Return Structure

```
{
  "status": "Success"|"Warning"|"Error",
  "input_ref": str,                # filename
  "processing_source": str,        # temp path or original path used
  "media_type": "pdf",
  "parser_used": str,
  "content": Optional[str],
  "metadata": Optional[Dict],      # {title, author, raw}
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
    chunk_options={"method": "recursive", "max_size": 1500, "overlap": 200},
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

## Dependencies & Config

- `pymupdf`, `pymupdf4llm` (default), optional `docling`.
- OCR: Tesseract CLI (binary on PATH) via `OCR/registry.py`. Page rendering via PyMuPDF.
- Config: `media_processing.max_pdf_file_size_mb`, `pdf_conversion_timeout_seconds`.

## Error Handling & Notes

- Missing optional parsers fallback to alternatives; errors are recorded in `warnings`/`error`.
- OCR is selective when `ocr_mode='fallback'` (pages with minimal text).
- Metrics logged via `metrics_logger` (attempts, durations, errors).

