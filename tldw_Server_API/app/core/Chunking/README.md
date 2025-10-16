# Chunking Module – Developer README

This module provides robust, extensible text chunking for ingestion, RAG, embeddings, analytics, and downstream tasks. It includes a strategy registry, hierarchical chunking, and a template system that now supports learning rules from a “seed” document.

## Overview
- Entry point: `Chunker` in `chunker.py` (methods: `words`, `sentences`, `paragraphs`, `tokens`, `semantic`, `json`, `xml`, `ebook_chapters`, `rolling_summarize`, …).
- Entry point: `Chunker` in `chunker.py` (methods: `words`, `sentences`, `paragraphs`, `tokens`, `semantic`, `json`, `xml`, `ebook_chapters`, `rolling_summarize`, `code`, …).
- Template pipeline: `TemplateProcessor` and `TemplateManager` in `templates.py`.
- Built-in templates: JSON files under `template_library/`, seeded into DB by `template_initialization.py`.
- New: Seed-driven templates via learned “boundary” rules inferred from example (“seed/template”) documents.

## Layout
- `base.py` — core types and interfaces (`ChunkingMethod`, `ChunkResult`, `ChunkerConfig`, `BaseChunkingStrategy`)
- `chunker.py` — orchestrator, strategy registry, hierarchical helpers
- `strategies/` — implementation of strategies (words, sentences, tokens, structure-aware, semantic, etc.)
- `templates.py` — `TemplateProcessor`, `TemplateManager`, `TemplateClassifier`, `TemplateLearner`
- `template_initialization.py` — seeds built-in templates to DB
- `template_library/` — built-in template JSONs (auto-loaded/seeded)

## Using the Template System
Two supported template schemas:
1) Stage-based:
  {
    "name": "...",
    "base_method": "words",
    "stages": [
      { "name": "preprocess", "operations": [...] },
      { "name": "chunk", "operations": [{ "method": "sentences", "config": {...}}] },
      { "name": "postprocess", "operations": [...] }
    ],
    "default_options": { ... },
    "metadata": { ... }
  }
2) Simple (DB/file format) with explicit blocks:
  {
    "name": "...",
    "preprocessing": [ { "operation": "normalize_whitespace", "config": {...} } ],
    "chunking": { "method": "sentences", "config": { "max_size": 8, "overlap": 2 } },
    "postprocessing": [ { "operation": "filter_empty", "config": {...} } ]
  }

Both are supported by `TemplateManager.load_template(...)`.

## Hierarchical + Seed-Driven Templates
Hierarchical chunking segments a document into sections/blocks (headers, hrules, code fences, lists, etc.) and chunks the leaf blocks. You can steer segmentation with custom “boundary” rules:
- Enable hierarchical mode:
  "chunking": {
    "method": "sentences",
    "config": {
      "hierarchical": true,
      "hierarchical_template": {
        "boundaries": [
          { "kind": "header_atx", "pattern": "^\\s*#{1,6}\\s+.+$", "flags": "m" }
        ]
      }
    }
  }

### Learning from a seed (“template”) document
- Programmatic: `TemplateLearner.learn_boundaries(example_text)` returns:
  { "boundaries": [{ "kind": "...", "pattern": "...", "flags": "im" }, ...] }
- API: `POST /api/v1/chunking/templates/learn`
  Body:
  {
    "name": "my_seeded_template",
    "example_text": "Your sample content here...",
    "save": true,
    "classifier": { "media_types": ["document"], "title_regex": ".*MyCorpus.*" }
  }
  The API responds with a usable template config and optionally saves it.

Notes and limits:
- Keep boundary rules concise and safe. Validation caps boundaries to ≤ 20 and enforces pattern length.
- Prefer anchored, case-insensitive patterns for stable matching (e.g., `^\\s*Abstract\\b`, flags `im`).

## Classifying Templates (Optional)
Add a simple classifier (top-level or under `chunking.config`) for `/chunking/templates/match`:
  "classifier": {
    "media_types": ["document", "ebook"],
    "filename_regex": ".*\\.(pdf|epub)$",
    "title_regex": "(paper|thesis)",
    "min_score": 0.3,
    "priority": 1
  }

`TemplateClassifier` computes a simple score from media type + regex matches to help auto-select templates.

## Adding/Updating Built-in Templates
1) Add a JSON template under `template_library/` (see examples in this folder).
2) Set method + config, and optionally:
   - `hierarchical: true` + `hierarchical_template.boundaries` (if you want seeded/learned rules)
   - `classifier` for auto-matching
   - `tags`, `metadata.seed_source`, etc. for traceability
3) On startup, `ensure_templates_initialized()` seeds or updates the DB-wide built-ins.

## Testing
- API tests: `tldw_Server_API/tests/Chunking/test_chunking_templates.py`
- Template apply/validate endpoints
- Strategy-level tests under `tests/Chunking_NEW/`

## Gotchas & Best Practices
- Do not exceed boundary/regex limits; prefer a few robust patterns over many fragile ones.
- Use `structure_aware` for code/docs when possible; otherwise seed headers/fences with `hierarchical_template`.
- Keep templates JSON-only; put operational notes in `metadata` (never secrets).

## Timecode Mapping for Media Transcripts

Attach approximate time bounds to chunks by supplying a `timecode_map` with character spans and times. The chunker projects `start_time`/`end_time` onto chunk metadata when spans overlap.

Example:

```
from tldw_Server_API.app.core.Chunking import Chunker

text = "[00:00] intro ... [00:10] content ..."
segments = [
    {"start_offset": 0, "end_offset": 120, "start_time": 0.0, "end_time": 10.0},
    {"start_offset": 120, "end_offset": 300, "start_time": 10.0, "end_time": 25.0},
]

ck = Chunker()
chunks = ck.process_text(
    text,
    method="sentences",
    max_size=3,
    overlap=1,
    timecode_map=segments,
    adaptive=True,
    adaptive_overlap=True,
)
for ch in chunks:
    md = ch["metadata"]
    print(md.get("start_time"), md.get("end_time"))
```

Notes:
- Mapping is best‑effort: if a chunk overlaps a segment, the mapped times cover the overlapped portion proportionally.
- If multiple segments overlap a chunk, the first overlap is used.

## Environment Toggles (Regex Safety)
These environment variables harden regex-based detection used by the eBook chapter strategy (`strategies/ebook_chapters.py`). They do not affect non‑regex strategies.

- `CHUNKING_REGEX_TIMEOUT`
  - Purpose: Cap regex execution time (seconds) for chapter/section detection.
  - Default: `2` (class default). Values `<= 0` are ignored.
  - Example: `export CHUNKING_REGEX_TIMEOUT=0.5`

- `CHUNKING_DISABLE_MP`
  - Purpose: Control optional process-based isolation fallback for regex execution.
  - Default: Multiprocessing is disabled when unset (safer cross‑platform default).
  - Values: `1`/`true`/`yes` keeps MP disabled; `0`/`false`/`no` enables MP fallback. Note some environments disallow process spawning.

- `CHUNKING_REGEX_SIMPLE_ONLY`
  - Purpose: Restrict custom chapter regex to a safe subset.
  - Effect: When set (`1`/`true`/`yes`), disallows grouping `()`, alternation `|`, wildcard `.`, `?`, `*`. Allows literals, anchors `^`/`$`, character classes `[A-Z]`, escapes `\d`/`\w`, and `+` after safe atoms. Unsafe patterns are rejected during validation.
## Code Chunking (Python + JavaScript)

- Method: `code` with optional `code_mode` for routing.
  - `code_mode=auto` (default): If `language` starts with `py`, uses AST-based Python chunking; otherwise uses heuristic chunking.
  - `code_mode=ast`: Force AST-based Python chunking (for `.py`).
  - `code_mode=heuristic`: Force heuristic chunking (works across JS/TS, C-like languages, etc.).

- Python (AST-based) produces chunks aligned to import block, top-level classes, and top-level functions with accurate character offsets.
- JavaScript/TypeScript (heuristic) recognizes:
  - `export default class Name`, `class Name`
  - `export function name(...)`, `function name(...)`
  - `export const name = (...) => { ... }`, `const name = function (...)`
  - `export default function name(...)`, `export default function (...)`
  - `export default (...) => { ... }`
  - `export interface Name { ... }`, `export type Name = ...`

Example:
  chunker.process_text(code, options={"method": "code", "language": "python", "code_mode": "ast", "max_size": 800})
