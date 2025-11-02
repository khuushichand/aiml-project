# EPUB / Books Ingestion Pipeline

## Overview

Extracts content and metadata from EPUB files using different strategies, optionally chunks and summarizes. Returns a structured result; DB-agnostic.

## Primary Function

Module: `tldw_Server_API.app.core.Ingestion_Media_Processing.Books.Book_Processing_Lib`

- `process_epub(file_path, title_override=None, author_override=None, keywords=None, custom_prompt=None, system_prompt=None, perform_chunking=True, chunk_options=None, perform_analysis=False, api_name=None, api_key=None, summarize_recursively=False, extraction_method='filtered') -> Dict[str, Any]`

### Parameters (selected)

- file_path: path to `.epub`.
- extraction_method: `'filtered'` (spine-based, skip front matter), `'markdown'` (EPUB→Markdown), `'basic'` fallback.
- perform_chunking: chunk content with provided `chunk_options`.
- perform_analysis: per-chunk analysis via `analyze`, with optional recursive summary.
- api_key: present for compatibility but typically not required; providers resolve keys from server config. Do not send API keys from clients.

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
  "analysis_details": Dict,            # e.g., {analysis_model, custom_prompt_used, system_prompt_used, summarized_recursively}
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

Supported files: `.epub` (uploads and URLs). This endpoint forces chunking method `ebook_chapters` for ebooks.

### Endpoint Examples

- Auth headers
  - Single-user: `X-API-KEY: <your_key>`
  - Multi-user: `Authorization: Bearer <jwt>`

- URLs only (multipart form):

```
curl -X POST "http://127.0.0.1:8000/api/v1/media/process-ebooks" \
  -H "X-API-KEY: $API_KEY" \
  -F "urls=https://example.com/book.epub" \
  -F "extraction_method=filtered" \
  -F "perform_chunking=true" \
  -F "perform_analysis=true" \
  -F "api_name=openai" \
  -F "summarize_recursively=true"
```

- File uploads (multipart form):

```
curl -X POST "http://127.0.0.1:8000/api/v1/media/process-ebooks" \
  -H "Authorization: Bearer $JWT" \
  -F "files=@/abs/path/book.epub" \
  -F "perform_chunking=true" \
  -F "chunk_size=1500" \
  -F "chunk_overlap=200" \
  -F "extraction_method=filtered"
```

- Python (requests):

```python
import requests

url = "http://127.0.0.1:8000/api/v1/media/process-ebooks"
headers = {"X-API-KEY": "<api-key>"}
data = {
    "urls": ["https://example.com/book.epub"],
    "perform_chunking": True,
    "perform_analysis": True,
    "api_name": "openai",
    "extraction_method": "filtered",
}
resp = requests.post(url, headers=headers, data=data)
print(resp.status_code)
print(resp.json())
```

Notes:
- Returns 200 when all items succeed, 207 for mixed outcomes, or 400 if nothing was processed.
- For ebooks, the endpoint always uses `ebook_chapters` chunking under the hood.
- URL downloads are restricted to `.epub` files; non-EPUB URLs are rejected with an error.

Redirect behavior:
- URLs that do not end with `.epub` may still be accepted if the final redirected response provides either a `Content-Disposition` filename ending in `.epub` or `Content-Type: application/epub+zip`. Otherwise, the URL is rejected.

## Dependencies & Config

- Requires `ebooklib` for EPUB parsing; uses `BeautifulSoup` and `html2text` for content extraction/cleanup.
- Chunking via `tldw_Server_API.app.core.Chunking`.
- Summarization provider chosen by `api_name`; keys resolved from server config (no keys from clients).

### OpenAPI (minimal)

```yaml
openapi: 3.0.3
paths:
  /api/v1/media/process-ebooks:
    post:
      summary: Extract, chunk, analyse EPUBs (NO DB Persistence)
      tags: ["Media Processing (No DB)"]
      requestBody:
        required: false
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                urls:
                  type: array
                  items: { type: string, format: uri }
                files:
                  type: array
                  items: { type: string, format: binary }
                extraction_method: { type: string, enum: [filtered, markdown, basic] }
                perform_chunking: { type: boolean }
                perform_analysis: { type: boolean }
                api_name: { type: string }
                summarize_recursively: { type: boolean }
      responses:
        "200": { description: OK }
        "207": { description: Multi-Status (mixed outcomes) }
        "400": { description: Bad Request }
        "422": { description: Validation Error }
```

### Response Example

```json
{
  "processed_count": 1,
  "errors_count": 0,
  "errors": [],
  "results": [
    {
      "status": "Success",
      "input_ref": "book.epub",
      "processing_source": "/tmp/process_ebook_abcd123/book.epub",
      "media_type": "ebook",
      "content": "# Chapter 1\n...",
      "metadata": {
        "title": "Sample Book",
        "author": "Jane Doe",
        "raw": {"dc:title": ["Sample Book"]},
        "source_filename": "book.epub"
      },
      "chunks": [
        {"index": 0, "text": "Chapter 1 content ...", "metadata": {"chapter": 1}}
      ],
      "analysis": "This book introduces...",
      "keywords": ["ebook", "epub"],
      "warnings": null,
      "error": null,
      "analysis_details": {"analysis_model": "openai", "summarized_recursively": true},
      "parser_used": "read_epub_filtered"
    }
  ]
}
```

### Error Examples

- 422 Unprocessable Entity (invalid enum value):

```
curl -X POST "http://127.0.0.1:8000/api/v1/media/process-ebooks" \
  -H "X-API-KEY: $API_KEY" \
  -F "urls=https://example.com/book.epub" \
  -F "extraction_method=advanced"   # invalid
```

Response (422):

```json
{
  "detail": [
    {
      "type": "literal_error",
      "loc": ["body", "extraction_method"],
      "msg": "Input should be 'filtered', 'markdown' or 'basic'",
      "input": "advanced"
    }
  ]
}
```

- 400 Bad Request (no inputs provided):

```
curl -X POST "http://127.0.0.1:8000/api/v1/media/process-ebooks" -H "X-API-KEY: $API_KEY"
```

Response (400):

```json
{
  "detail": "No valid media sources supplied. At least one 'url' in the 'urls' list or one 'file' in the 'files' list must be provided."
}
```

## Error Handling & Notes

- If an extraction method fails, code may fallback to simpler modes; issues are recorded in `warnings`.
- Content may be `None` if parsing fails; `status` becomes `Error` and `error` contains details.
