# MediaWiki Dump Ingestion Pipeline

## Overview

Processes MediaWiki XML dumps and yields structured events: total count, per-page results, and summary. Supports optional persistence to the primary DB and vector store (scaffolded). Includes checkpointing to resume after interruption.

## Primary Function

Module: `tldw_Server_API.app.core.Ingestion_Media_Processing.MediaWiki.Media_Wiki`

- `import_mediawiki_dump(file_path, wiki_name, namespaces=None, skip_redirects=False, chunk_options_override=None, progress_callback=None, store_to_db=True, store_to_vector_db=True, api_name_vector_db=None, api_key_vector_db=None) -> Iterator[Dict[str, Any]]`

### Parameters (selected)

- file_path: path to `.xml`, `.xml.bz2`, or `.xml.gz` dump.
- wiki_name: name used in URLs/collection naming; sanitized to avoid path issues.
- namespaces: list of namespace IDs to include (e.g., `[0]` for main/articles).
- skip_redirects: ignore redirect pages.
- chunk_options_override: chunking config for page content (method/max_size/overlap).
- store_to_db: persist via `MediaDatabase.add_media_with_keywords`.
- store_to_vector_db: scaffolded; code shows placeholder for chunk vectorization.

### Event Stream

The iterator yields dicts with one of the following `type` fields:

- `progress_total`: `{ "type": "progress_total", "total_pages": int, "message": str }`
- `progress_item`: `{ "type": "progress_item", "status": str, "title": str, "page_id": int, "progress_percent": float }`
- `item_result`: `{ "type": "item_result", "data": { title, content, chunks, media_id?, message, status, ... } }`
- `summary`: `{ "type": "summary", "message": str }`
- `error`: `{ "type": "error", "message": str }`

## Example (Ephemeral)

```python
from tldw_Server_API.app.core.Ingestion_Media_Processing.MediaWiki.Media_Wiki import import_mediawiki_dump

events = import_mediawiki_dump(
    file_path="/abs/enwiki-latest-pages-articles.xml.bz2",
    wiki_name="enwiki",
    namespaces=[0],
    skip_redirects=True,
    chunk_options_override={"method": "recursive", "max_size": 1500, "overlap": 200},
    store_to_db=False,
    store_to_vector_db=False,
)
for ev in events:
    print(ev.get("type"), ev.get("message") or ev.get("data", {}).get("title"))
```

## Endpoint Integration

- `POST /api/v1/mediawiki/ingest-dump`: saves upload to temp, streams iterator with `store_to_db=True`, `store_to_vector_db=True`.
- `POST /api/v1/mediawiki/process-dump`: ephemeral processing; yields validated `item_result` models.

## Dependencies & Config

- Requires `mwxml` for dump parsing.
- Checkpoint files saved to `./checkpoints/` (atomic writes and safe cleanup).
- Filename/path validation and sanitization in utilities within the module.

## Error Handling & Notes

- Skips pages via checkpointing when resuming; removes checkpoint on success.
- Vector store integration is marked as TODO in current code.
- Errors are emitted as `error` events; endpoint passes them to clients line-by-line (NDJSON).

