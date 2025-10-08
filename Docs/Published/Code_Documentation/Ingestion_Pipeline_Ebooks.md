# EPUB / Books Ingestion Pipeline

## Overview

Extracts content and metadata from EPUB files using different strategies, optionally chunks and summarizes. Returns a structured result; DB‑agnostic.

## Primary Function

Module: `tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib`

- `process_epub(file_path, title_override=None, author_override=None, keywords=None, custom_prompt=None, system_prompt=None, perform_chunking=True, chunk_options=None, perform_analysis=False, api_name=None, api_key=None, summarize_recursively=False, extraction_method='filtered') -> Dict[str, Any]`

### Parameters (selected)

- file_path: path to `.epub`.
- extraction_method: `'filtered'` (spine-based, skip front matter), `'markdown'` (EPUB→Markdown), `'basic'` fallback.
- perform_chunking: chunk content with provided `chunk_options`.
- perform_analysis: per-chunk analysis via `analyze`, with optional recursive summary.

### Return Structure

```
{
  "status": "Success"|"Warning"|"Error",
  "input_ref": str,
  "processing_source": str,
  "media_type": "ebook",
  "content": Optional[str],
  "metadata": {
    "title": Optional[str],
    "author": Optional[str],
    "raw": Optional[Dict],
    "source_filename": str
  },
  "chunks": Optional[List[Dict]],
  "analysis": Optional[str],
  "keywords": List[str],
  "warnings": Optional[List[str]],
  "error": Optional[str],
  "analysis_details": Dict,
  "parser_used": Optional[str]
}
```

## Example

```python
from tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib import process_epub

book = process_epub(
    file_path="/abs/book.epub",
    perform_chunking=True,
    chunk_options={"method": "ebook_chapters", "max_size": 1500, "overlap": 200},
    perform_analysis=True,
    api_name="openai",
    summarize_recursively=True,
    extraction_method="filtered",
)
print(book["status"], book.get("metadata", {}).get("title"))
```

## Endpoint Integration

- `POST /api/v1/media/process-ebooks` (media.py) prepares URLs/uploads and invokes `process_epub` per file.

## Dependencies & Config

- Requires `ebooklib` for EPUB parsing (implied by code usage), and text cleaning utilities.
- Chunking via `tldw_Server_API.app.core.Chunking`.
- Summarization provider chosen by `api_name`; keys from server config.

## Error Handling & Notes

- If an extraction method fails, code may fallback to simpler modes; issues are recorded in `warnings`.
- Content may be `None` if parsing fails; `status` becomes `Error` and `error` contains details.

