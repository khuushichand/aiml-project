# MediaWiki Vector Storage

## Overview
Implement MediaWiki dump vector storage by embedding per-page chunks and persisting them in the per-user ChromaDB collection. This fills the existing scaffold in `Media_Wiki.py` and aligns with the main embeddings pipeline.

## Goals
- Store MediaWiki page chunks in ChromaDB during `store_to_vector_db` ingestion.
- Use configuration defaults with optional overrides from `api_name_vector_db` / `api_key_vector_db`.
- Preserve section metadata for each chunk.

## Non-Goals
- Rework the MediaWiki chunker or migrate to the unified chunking module.
- Add async embedding calls inside the synchronous import generator.

## Approach
- Build a minimal embedding configuration for `create_embeddings_batch` using:
  - Provider/model from `Config_Files/mediawiki_import_config.yaml`.
  - Optional override via `api_name_vector_db` (provider:model or model-only).
  - Optional API key override via `api_key_vector_db` when supported by the provider.
- Use `ChromaDBManager.store_in_chroma` to persist embeddings with metadata:
  - `media_id`, `page_id`, `revision_id`, `wiki_name`, `title`, `chunk_index`, `section`.
- Use collection name `mediawiki_{wiki_name}` (prefix configurable via `mediawiki_import_config.yaml`).

## Error Handling
- If embeddings dependencies or config are missing, log a warning and skip vector storage for that page.
- Per-chunk failures are logged and added to the page message; ingestion continues.

## Tests
- Unit test that `process_single_item` invokes vector storage with mocked embeddings + Chroma manager.
