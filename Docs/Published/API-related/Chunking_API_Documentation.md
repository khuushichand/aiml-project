# Chunking API Documentation

## Overview

The Chunking API exposes endpoints to split text or files into smaller, semantically useful chunks for downstream RAG and embeddings. It complements the Chunking Templates API and provides a simple way to invoke common strategies.

## Base URL

```
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
```
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
```
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

Example (template-based):
```
{
  "text_content": "# Title\n...",
  "file_name": "paper.md",
  "options": { "template_name": "academic_paper" }
}
```

### 2) POST /chunk_file

Upload a file via multipart form-data and return chunks.

Example request:
```
curl -X POST "http://localhost:8000/api/v1/chunking/chunk_file" \
  -H "Authorization: Bearer <JWT>" \
  -F file=@/path/to/large.txt \
  -F method=sentences \
  -F max_size=8 \
  -F overlap=2 \
  -F tokenizer_name_or_path=gpt2
```

Response shape matches `POST /chunk_text`.

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
