# MediaWiki Dump Ingestion Pipeline

## Overview

Processes MediaWiki XML dumps and yields structured events: total count, per-page results, and summary. Supports optional persistence to the primary DB and vector store (scaffolded). Includes checkpointing to resume after interruption.

## Primary Function

Module: `tldw_Server_API.app.core.Ingestion_Media_Processing.MediaWiki.Media_Wiki`

- `import_mediawiki_dump(file_path, wiki_name, namespaces=None, skip_redirects=False, chunk_options_override=None, progress_callback=None, store_to_db=True, store_to_vector_db=True, api_name_vector_db=None, api_key_vector_db=None) -> Iterator[Dict[str, Any]]`

### Parameters (selected)

- file_path: path to a `.xml`, `.xml.bz2`, or `.xml.gz` dump. Compressed files are supported transparently; the importer detects and streams decompression (gzip/bzip2) without loading the entire file in memory.
- wiki_name: name used in URLs/collection naming; sanitized to avoid path issues.
- namespaces: list of namespace IDs to include (e.g., `[0]` for main/articles).
- skip_redirects: ignore redirect pages.
- chunk_options_override: currently only `max_size` is honored by the module-local chunker; other keys (e.g., `method`, `overlap`) are ignored here.
- store_to_db: persist via a real DB instance - e.g., `db = create_media_database(client_id="mediawiki_import"); db.add_media_with_keywords(...)` - with `media_type="mediawiki_page"` and URL `mediawiki:{wiki_name}:{quoted_title}`.
- store_to_vector_db: scaffolded; code includes a placeholder for chunk vectorization.

### Event Stream

The iterator yields dicts with the following `type` fields:

- `progress_total`: `{ "type": "progress_total", "total_pages": int, "message": str }`
- `progress_item`: `{ "type": "progress_item", "status": str, "title": str, "page_id": int, "progress_percent": float }`
- `item_result`: `{ "type": "item_result", "data": { title, content, chunks, media_id?, message, status, ... } }`
- `summary`: `{ "type": "summary", "message": str }`
- `error`: `{ "type": "error", "message": str }`

Note: The ephemeral endpoint validates `item_result.data` against `ProcessedMediaWikiPage`. Validation failures are streamed as `{ "type": "validation_error", ... }` lines.

## Example (Ephemeral)

```python
from tldw_Server_API.app.core.Ingestion_Media_Processing.MediaWiki.Media_Wiki import import_mediawiki_dump

events = import_mediawiki_dump(
    file_path="/abs/path/to/enwiki-latest-pages-articles.xml",
    wiki_name="enwiki",
    namespaces=[0],
    skip_redirects=True,
    chunk_options_override={"max_size": 1500},  # only max_size is used here
    store_to_db=False,
    store_to_vector_db=False,
)
for ev in events:
    print(ev.get("type"), ev.get("message") or ev.get("data", {}).get("title"))
```

## Endpoint Integration

- `POST /api/v1/media/mediawiki/ingest-dump`: saves upload to temp, streams iterator with `store_to_db=True`, `store_to_vector_db=True` as NDJSON.
- `POST /api/v1/media/mediawiki/process-dump`: ephemeral processing; streams validated `ProcessedMediaWikiPage` items as NDJSON (plus `progress_*`, `summary`, `error`, `validation_error`).

Accepted form fields for both endpoints:
- `wiki_name` (str, required)
- `namespaces_str` (str, optional, e.g., `"0,1"`)
- `skip_redirects` (bool, default `true`)
- `chunk_max_size` (int, default from config; used as `max_size`)
- `api_name_vector_db` / `api_key_vector_db` (optional; used only by ingest when vector storage is enabled)

### curl Examples

Ingest and persist (streams NDJSON):

```bash
curl -N -s \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Accept: application/x-ndjson" \
  -F "wiki_name=enwiki" \
  -F "namespaces_str=0" \
  -F "skip_redirects=true" \
  -F "chunk_max_size=1500" \
  -F "dump_file=@/abs/path/enwiki-latest-pages-articles.xml.bz2;type=application/x-bzip2" \
  http://127.0.0.1:8000/api/v1/media/mediawiki/ingest-dump
```

Process only (no persistence; streams validated page objects as NDJSON):

```bash
curl -N -s \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Accept: application/x-ndjson" \
  -F "wiki_name=enwiki" \
  -F "namespaces_str=0" \
  -F "skip_redirects=true" \
  -F "chunk_max_size=1500" \
  -F "dump_file=@/abs/path/enwiki-latest-pages-articles.xml.gz;type=application/gzip" \
  http://127.0.0.1:8000/api/v1/media/mediawiki/process-dump
```

## Chunking Behavior

- Uses a module-local, section-aware chunker (`optimized_chunking`) that splits on MediaWiki headings and respects `max_size`.
- This path does not yet use the unified v2 chunker; only `max_size` is effective in `chunk_options_override`.

## Dependencies & Config

- Requires `mwxml` (dump parsing) and `mwparserfromhell` (wikitext to plain text).
- Configuration: `tldw_Server_API/Config_Files/mediawiki_import_config.yaml` (e.g., `chunking.default_size` is used as the fallback for `max_size`).
- Checkpoint files saved to `./checkpoints/` (atomic writes and safe cleanup).
- Filename/path validation and sanitization are built into the module (see `validate_file_path`, `sanitize_wiki_name`, `get_safe_checkpoint_path`).

## Security & Validation

- Filenames: endpoints sanitize uploaded filenames using `sanitize_filename` before writing to a temporary directory managed by `TempDirManager`.
- Wiki name: sanitized by `sanitize_wiki_name` (alphanumeric, underscore, hyphen, spaces only; spaces converted to underscores; length-limited; path traversal patterns rejected).
- Path validation: `validate_file_path` resolves the provided path, ensures it exists, is a regular file, rejects symlinks escaping the allowed directory, and enforces directory containment. If `allowed_dir` is not provided, it defaults to the current working directory.
- Endpoint note: uploads are saved under an OS temporary directory. If you reuse `import_mediawiki_dump` in custom scripts or alternate servers where the temp path is outside your working directory, ensure your working directory permits access or pass a suitable `allowed_dir` when validating paths in your integration layer.

## Error Handling & Notes

- Skips pages via checkpointing when resuming; removes checkpoint on success.
- Vector store integration is currently scaffolded (placeholder calls only).
- Streaming responses use `application/x-ndjson` with one JSON object per line.
- Security hardening is covered by tests: see `tldw_Server_API/tests/test_mediawiki_security.py`.

## NDJSON Sample Output

Example lines you may see in the stream (truncated for brevity):

```ndjson
{"type":"progress_total","total_pages":1234,"message":"Found 1234 pages to process for 'enwiki'."}
{"type":"progress_item","status":"skipped_checkpoint","title":"Main Page","page_id":1,"progress_percent":0.001}
{"type":"item_result","data":{"title":"Alan Turing","content":"Alan Mathison Turing was...","namespace":0,"page_id":12345,"revision_id":67890,"timestamp":"2024-10-08T12:34:56+00:00","chunks":[{"text":"Alan Turing was..."}],"media_id":42,"message":"OK","status":"Success"},"progress_percent":0.42}
{"type":"validation_error","title":"Some Page","page_id":555,"detail":[{"loc":["content"],"msg":"field required","type":"value_error.missing"}]}
{"type":"summary","message":"Successfully processed MediaWiki dump: enwiki. Processed 1200/1234 pages."}
```

For the ephemeral endpoint (`/mediawiki/process-dump`), validated page objects are streamed without the wrapper `type=item_result`. Example line:

```ndjson
{"title":"Alan Turing","content":"Alan Mathison Turing was...","namespace":0,"page_id":12345,"revision_id":67890,"timestamp":"2024-10-08T12:34:56+00:00","chunks":[{"text":"Alan Turing was..."}],"media_id":null,"message":null,"status":"Success","error_message":null}
```
