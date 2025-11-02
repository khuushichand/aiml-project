# Chunking Templates

This document explains the JSON schema for chunking templates (DB-compatible), how the server applies templates, and provides examples.

## Overview

Chunking templates let you define document-type-specific chunking pipelines consisting of:

- preprocessing: optional operations that normalize or annotate the input text.
- chunking: the core method and its configuration (e.g., words, sentences, structure_aware).
- postprocessing: optional operations that filter, merge, or format the resulting chunks.

Templates are stored in the database as JSON and managed via the Chunking Templates API.

## JSON Schema (DB-Compatible)

Top-level fields used by the API and DB layer:

- name: string - template name (unique among non-deleted templates)
- description: string - human-readable description
- tags: list[string] - optional categorization
- preprocessing: list[Operation] - optional list of preprocessing steps
- chunking: ChunkingSpec - required; defines the chunking method and config
- postprocessing: list[Operation] - optional list of postprocessing steps

Where:

- Operation: { operation: string, config?: object }
- ChunkingSpec: { method: string, config?: object }

Notes:

- The system also supports an alternate internal stage-based schema (stages with {type, params}). The API transparently maps the DB schema to internal stages.
- The validate endpoint checks that chunking.method is one of the supported methods from the live Chunker.

## Supported Methods (examples)

- words, sentences, paragraphs, tokens, semantic, structure_aware, json, xml, ebook_chapters, rolling_summarize, propositions

Run GET /api/v1/chunking/templates/validate to verify a template, or check the chunker’s available methods at runtime.

## Built-in Operations

Preprocessing operations (operation value):

- normalize_whitespace: { max_line_breaks?: number }
- remove_headers: { patterns?: string[] }
- extract_sections: { pattern?: string } - writes section positions to internal metadata
- clean_markdown: { remove_links?: bool, remove_images?: bool, remove_formatting?: bool }
- detect_language: {} - writes detected_language to internal metadata

Postprocessing operations (operation value):

- add_overlap: { size?: number, marker?: string }
- filter_empty: { min_length?: number }
- merge_small: { min_size?: number, separator?: string }
- add_metadata: { prefix?: string, suffix?: string }
- format_chunks: { template: string } - e.g., "--- Section {index}/{total} ---\n{chunk}\n"

## Examples

Academic paper:

{
  "name": "academic_paper",
  "description": "Template for processing academic papers and research documents",
  "tags": ["academic", "research", "papers"],
  "preprocessing": [
    { "operation": "normalize_whitespace", "config": { "max_line_breaks": 2 } },
    { "operation": "extract_sections", "config": { "pattern": "^#+\\s+(.+)$" } }
  ],
  "chunking": {
    "method": "sentences",
    "config": { "max_size": 5, "overlap": 1 }
  },
  "postprocessing": [
    { "operation": "filter_empty", "config": { "min_length": 20 } },
    { "operation": "merge_small", "config": { "min_size": 200, "separator": "\n\n" } }
  ]
}

Code documentation:

{
  "name": "code_documentation",
  "description": "Template for processing code documentation",
  "preprocessing": [ { "operation": "clean_markdown", "config": { "remove_images": true } } ],
  "chunking": {
    "method": "structure_aware",
    "config": { "max_size": 500, "overlap": 50, "preserve_code_blocks": true, "preserve_headers": true }
  },
  "postprocessing": [ { "operation": "filter_empty", "config": { "min_length": 50 } } ]
}

## Using Templates via API

- List: GET /api/v1/chunking/templates
- Get one: GET /api/v1/chunking/templates/{template_name}
- Create: POST /api/v1/chunking/templates (body includes the JSON above under template)
- Update/Delete: PUT/DELETE /api/v1/chunking/templates/{template_name}
- Validate only: POST /api/v1/chunking/templates/validate
- Apply (full template pipeline): POST /api/v1/chunking/templates/apply

### Diagnostics (DB Capability Headers)

Templates endpoints include optional diagnostic headers to help verify that the correct database implementation is in use:

- `X-Template-DB-Class`: module.ClassName of the DB dependency instance.
- `X-Template-DB-Capability`: `native` (DB supports templates natively) or `fallback` (endpoints are using an in-memory fallback store for this process).
- `X-Template-DB-Missing`: Comma-separated list of required methods not found on the DB class.
- `X-Template-DB-Hint`: Suggests using `tldw_Server_API.app.core.DB_Management.Media_DB_v2.MediaDatabase`.

If you see `fallback`, templates will function but not persist across restarts. Update DI wiring to use Media_DB_v2.MediaDatabase to enable native persistence and full feature support.

### Chunking Endpoint Integration

When calling POST /api/v1/chunking/chunk_text with options.template_name set, the server now executes the full template pipeline (preprocess, chunk, postprocess). The response includes minimal metadata per chunk:

- chunk_index: number
- total_chunks: number
- chunk_method: string (template’s base method)
- max_size: number | null (from template config)
- overlap: number | null (from template config)
- language: string | null (from options if provided)
- relative_position: [0.0, 1.0]
- template_applied: string
- template_version: number

If you need detailed offsets or method-specific metadata, use the non-template path or extend your template to embed explicit metadata via postprocessing operations.

### LLM-Dependent Methods

For methods like rolling_summarize that require LLM access, the server uses its configured provider and model (from config.txt / env). Client-provided llm options can suggest temperature/system_prompt/max_tokens via options.llm_options_for_internal_steps, but provider/model are server-controlled for consistency and security.

## Notes

- The template processor is tolerant to both {operation, config} and {type, params} shapes.
- Built-in templates are shipped under tldw_Server_API/app/core/Chunking/template_library and seeded into the DB on startup.
