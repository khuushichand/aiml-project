# Chunking API Documentation

## Overview

The Chunking API exposes endpoints to split text or files into smaller, semantically useful chunks for downstream RAG and embeddings. It complements the Chunking Templates API and provides a simple way to invoke common strategies.

## Base URL

```bash
http://localhost:8000/api/v1/chunking
```

## Authentication

Authentication follows the server’s AuthNZ mode:
- Single-user mode: include `X-API-KEY: <your_key>` header
- Multi-user mode: include `Authorization: Bearer <JWT>` header

## Endpoints

### 1) POST /chunk_text

Chunk raw text and return normalized chunks with metadata.

Request body (JSON):
```json
{
  "text_content": "... your text ...",
  "file_name": "sample.txt",
  "options": {
    "method": "words",
    "max_size": 400,
    "overlap": 200,
    "language": "en"
  }
}
```

Notes
- Use `method='code'` with `code_mode` = `auto | ast | heuristic` for code-aware chunking.
- To use templates (including hierarchical rules), set `options.template_name` to a template managed via the Templates API.
- `applied_options` in the response shows effective options after defaults/overrides.

Example response (truncated):
```json
{
  "chunks": [
    {
      "text": "first chunk text ...",
      "metadata": {
        "chunk_index": 1,
        "total_chunks": 8,
        "chunk_method": "words",
        "max_size": 400,
        "overlap": 200,
        "language": "en",
        "start_offset": 0,
        "end_offset": 1234,
        "relative_position": 0.08
      }
    }
  ],
  "original_file_name": "sample.txt",
  "applied_options": {
    "method": "words",
    "max_size": 400,
    "overlap": 200,
    "language": "en",
    "tokenizer_name_or_path": "gpt2"
  }
}
```

OpenAPI schema (request/response)
```yaml
openapi: 3.0.3
info:
  title: Chunk Text
  version: 1.0.0
paths:
  /api/v1/chunking/chunk_text:
    post:
      summary: Chunk raw text and return normalized chunks
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                text_content:
                  type: string
                file_name:
                  type: string
                  nullable: true
                options:
                  type: object
                  description: Chunking parameters
                  properties:
                    template_name:
                      type: string
                    method:
                      type: string
                      description: words|sentences|paragraphs|tokens|semantic|json|xml|ebook_chapters|propositions|rolling_summarize|structure_aware|fixed_size|code
                    max_size:
                      type: integer
                      minimum: 1
                    overlap:
                      type: integer
                      minimum: 0
                    language:
                      type: string
                    tokenizer_name_or_path:
                      type: string
                    code_mode:
                      type: string
                      enum: [auto, ast, heuristic]
                  additionalProperties: true
              required: [text_content]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  chunks:
                    type: array
                    items:
                      type: object
                      properties:
                        text:
                          type: string
                        metadata:
                          type: object
                          additionalProperties: true
                  original_file_name:
                    type: string
                    nullable: true
                  applied_options:
                    type: object
                    additionalProperties: true
```

Example (template-based):
```json
{
  "text_content": "# Title\n...",
  "file_name": "paper.md",
  "options": { "template_name": "academic_paper" }
}
```

Hierarchical splitting examples

- Using a template (recommended): Define boundaries in a template once, then reference it via `options.template_name` as shown above. See the Templates API doc for create/update operations.

- Minimal template JSON with custom boundaries (for use with Templates Apply):
```json
{
  "name": "chapters_and_appendices",
  "description": "Chapters and appendices with headings",
  "base_method": "sentences",
  "default_options": {"language": "en"},
  "stages": [],
  "metadata": {},
  "chunking": {
    "method": "sentences",
    "config": {"max_size": 8, "overlap": 2, "hierarchical": true,
      "hierarchical_template": {
        "boundaries": [
          {"kind": "chapter",   "pattern": "^Chapter\\s+\\d+\\b",  "flags": "im"},
          {"kind": "appendix",  "pattern": "^Appendix\\s+[A-Z]\\b", "flags": "im"}
        ]
      }
    }
  }
}
```
Apply via Templates API:
```bash
POST /api/v1/chunking/templates/apply
{
  "template_name": "chapters_and_appendices",
  "text": "... document text ...",
  "override_options": {"max_size": 10}
}
```
Notes: Allowed flags are only `i` and `m`. Max 20 rules; max pattern length 256 chars.

### 2) POST /chunk_file

Upload a file via multipart form-data and return chunks.

Example request:
```bash
curl -X POST "http://localhost:8000/api/v1/chunking/chunk_file" \
  -H "Authorization: Bearer <JWT>" \
  -F file=@/path/to/large.txt \
  -F method=sentences \
  -F max_size=8 \
  -F overlap=2 \
  -F tokenizer_name_or_path=gpt2
```

Response shape matches `POST /chunk_text`.

OpenAPI schema (multipart request)
```yaml
openapi: 3.0.3
info:
  title: Chunk File
  version: 1.0.0
paths:
  /api/v1/chunking/chunk_file:
    post:
      summary: Upload a file and return normalized chunks
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                file:
                  type: string
                  format: binary
                method:
                  type: string
                max_size:
                  type: integer
                  minimum: 1
                overlap:
                  type: integer
                  minimum: 0
                language:
                  type: string
                  nullable: true
                tokenizer_name_or_path:
                  type: string
                  nullable: true
                code_mode:
                  type: string
                  enum: [auto, ast, heuristic]
              required: [file]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  chunks:
                    type: array
                    items:
                      type: object
                      properties:
                        text: {type: string}
                        metadata: {type: object, additionalProperties: true}
                  original_file_name: {type: string}
                  applied_options: {type: object, additionalProperties: true}
```

### 3) GET /capabilities

Discover runtime methods and defaults.

Example response (trimmed):
```
{
  "methods": ["words", "sentences", "paragraphs", "tokens", "semantic", "json", "xml", "ebook_chapters", "rolling_summarize", "structure_aware", "code", "code_ast"],
  "default_options": {
    "method": "words",
    "max_size": 400,
    "overlap": 200,
    "language": "en",
    "tokenizer_name_or_path": "gpt2"
  },
  "llm_required_methods": ["rolling_summarize", "propositions"],
  "hierarchical_support": true,
  "notes": "Text chunking capabilities. For method='code', 'code_mode' controls routing.",
  "method_specific_options": {
    "code": {
      "code_mode": ["auto", "ast", "heuristic"],
      "language_hints": {"py": "python", "js": "javascript", "jsx": "javascript", "ts": "typescript", "tsx": "typescript"}
    },
    "tokens": {
      "tokenizer_name_or_path": "gpt2",
      "add_special_tokens": [true, false]
    },
    "json": {
      "preserve_metadata": [true, false],
      "single_metadata_reference": [true, false],
      "metadata_reference_key": "__meta_ref__",
      "json_chunkable_data_key": "data"
    },
    "xml": {
      "preserve_metadata": [true, false]
    },
    "structure_aware": {
      "preserve_tables": [true, false],
      "preserve_code_blocks": [true, false],
      "preserve_headers": [true, false],
      "preserve_lists": [true, false],
      "table_serialization": ["markdown", "entity", "narrative"],
      "contextual_header_mode": ["none", "simple", "contextual"],
      "max_breadcrumb_levels": 6
    },
    "propositions": {
      "engine": ["heuristic", "spacy", "llm", "auto"],
      "aggressiveness": [0, 1, 2],
      "min_proposition_length": 15,
      "prompt_profile": ["generic", "claimify", "gemma_aps"]
    }
  }
}
```

Minimal OpenAPI schema (response) for stubbing
```
openapi: 3.0.3
info:
  title: Chunking Capabilities
  version: 1.0.0
paths:
  /api/v1/chunking/capabilities:
    get:
      summary: List chunking methods and defaults
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                type: object
                properties:
                  methods:
                    type: array
                    items:
                      type: string
                  default_options:
                    type: object
                    additionalProperties: true
                  llm_required_methods:
                    type: array
                    items:
                      type: string
                  hierarchical_support:
                    type: boolean
                  notes:
                    type: string
                  method_specific_options:
                    type: object
                    additionalProperties: true
```

Notes
- Methods include the union of enum values and runtime-registered strategies, so clients may see `structure_aware` and `code_ast` when available.
- Additional method-specific options may be added over time.
- `hierarchical_support` indicates that hierarchical splitting is supported via templates and/or server-side configuration; use a template to enable boundary rules.

## Tips

- Prefer `words` with `max_size≈400`, `overlap≈200` for general text.
- Use `structure_aware` or a template for long/structured docs.
- Use `tokens` with `tokenizer_name_or_path` to align to model token windows.
- For code, set `code_mode` (`auto|ast|heuristic`); `auto` routes to AST for Python when language hints start with `py`.
