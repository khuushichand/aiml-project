# Documents / Markup Ingestion Pipeline

## Overview

Converts various document formats to text (or Markdown), extracts simple metadata, optionally chunks and summarizes. Supports `.txt`, `.md`, `.html`, `.htm`, `.xml`, `.docx`, `.rtf` (Pandoc required for RTF).

## Primary Functions

Module: `tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files`

- `convert_document_to_text(file_path: Path) -> Tuple[str, str, Dict[str, Any]]`
- `process_document_content(doc_path: Path, perform_chunking, chunk_options, perform_analysis, summarize_recursively, api_name, api_key, custom_prompt, system_prompt, title_override=None, author_override=None, keywords=None) -> Dict[str, Any]`

### Parameters (selected)

- doc_path: input file path.
- perform_chunking: chunk text with method/max_size/overlap.
- perform_analysis: summarize per chunk and combine if configured.

### Return Structure

```
{
  "status": "Success"|"Warning"|"Error",
  "input_ref": str,
  "processing_source": str,
  "media_type": "document",
  "source_format": str,      # e.g., txt, md, html, xml, docx, rtf
  "content": Optional[str],
  "metadata": Dict,          # extracted_title, author, etc.
  "segments": Optional[List],
  "chunks": Optional[List[Dict]],
  "analysis": Optional[str],
  "analysis_details": Dict,
  "keywords": List[str],
  "error": Optional[str],
  "warnings": Optional[List[str]],
  "db_id": None,
  "db_message": Optional[str]
}
```

## Example

```python
from pathlib import Path
from tldw_Server_API.app.core.Ingestion_Media_Processing.Plaintext.Plaintext_Files import process_document_content

doc_res = process_document_content(
    doc_path=Path("/abs/article.docx"),
    perform_chunking=True,
    chunk_options={"method": "sentences", "max_size": 1200, "overlap": 200},
    perform_analysis=True,
    summarize_recursively=False,
    api_name="openai",
    api_key=None,
    custom_prompt="Summarize in bullet points",
)
print(doc_res["status"], doc_res["source_format"])
```

## Endpoint Integration

- `POST /api/v1/media/process-documents` (media.py) invokes this pipeline per uploaded/URL-provided document.

Notes:
- URL downloads are restricted to document extensions: `.txt`, `.md`, `.docx`, `.rtf`, `.html`, `.htm`, `.xml`.
- URLs without these suffixes may still be accepted if the final redirected response provides an appropriate `Content-Disposition` filename, or a supported `Content-Type` that maps to an allowed extension, for example:
  - `text/plain` → `.txt`
  - `text/markdown` or `text/x-markdown` → `.md`
  - `text/html` or `application/xhtml+xml` → `.html`
  - `application/xml` or `text/xml` → `.xml`
  - `application/rtf` or `text/rtf` → `.rtf`
  - `application/vnd.openxmlformats-officedocument.wordprocessingml.document` → `.docx`
- `application/msword` (`.doc`) is not accepted by this endpoint.

## Dependencies & Config

- `docx2txt` for DOCX, `pypandoc` for RTF, `BeautifulSoup`/`html2text` for HTML.
- Pandoc binary must be present for RTF conversion; otherwise raises `PandocMissing`.

## Error Handling & Notes

- Graceful decoding fallback from UTF-8 to latin-1; errors recorded.
- Unsupported file types raise `ValueError` with details.
