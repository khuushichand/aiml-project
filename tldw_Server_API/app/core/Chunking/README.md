# Chunking Module - Developer README

This module provides robust, extensible text chunking for ingestion, RAG, embeddings, analytics, and downstream tasks. It includes a strategy registry, hierarchical chunking, and a template system that now supports learning rules from a “seed” document.

## Overview
- Entry point: `Chunker` in `chunker.py` with unified APIs: `process_text`, `chunk_text`, `chunk_text_with_metadata`, `chunk_file_stream`, `chunk_text_hierarchical_tree`, `flatten_hierarchical`, `chunk_text_hierarchical_flat`. Built-in methods include: `words`, `sentences`, `paragraphs`, `tokens`, `semantic`, `json`, `xml`, `ebook_chapters`, `rolling_summarize`, `fixed_size`, `structure_aware`, `code` (Python AST or heuristic), and `code_ast` (explicit AST routing).
- Template pipeline: `TemplateProcessor` and `TemplateManager` in `templates.py`.
- Built-in templates: JSON files under `template_library/`, seeded into DB by `template_initialization.py`.
- Seed-driven templates: boundary rules learned from example (“seed/template”) documents via `TemplateLearner`.
- Where used: API endpoints (`api/v1/endpoints/chunking.py`, `api/v1/endpoints/chunking_templates.py`), media and scraping services (`app/services/document_processing_service.py`, `app/services/enhanced_web_scraping_service.py`, `app/services/xml_processing_service.py`), and RAG pipelines.

## Layout
- `base.py` - core types and interfaces (`ChunkingMethod`, `ChunkResult`, `ChunkerConfig`, `BaseChunkingStrategy`)
- `chunker.py` - orchestrator, strategy registry, hierarchical helpers
- `strategies/` - implementation of strategies (words, sentences, tokens, structure-aware, semantic, etc.)
- `templates.py` - `TemplateProcessor`, `TemplateManager`, `TemplateClassifier`, `TemplateLearner`
- `template_initialization.py` - seeds built-in templates to DB
- `template_library/` - built-in template JSONs (auto-loaded/seeded)

## Public API (Chunker)
- `process_text(text, options=None, *, tokenizer_name_or_path=None, llm_call_func=None, llm_config=None) -> List[Dict]`
  - End-to-end path. Returns list items `{"text": str, "metadata": dict}` with normalized fields such as `chunk_index`, `total_chunks`, `chunk_method`, `max_size`, `overlap`, `language`, `start_offset`, `end_offset`, `relative_position`, `paragraph_kind`, and optional `start_time`/`end_time` when `timecode_map` is supplied.
  - Supports `options` keys (see “Options” below). Handles adaptive sizing, hierarchical paragraph detection, timecode mapping, and content hashing.
- `chunk_text(text, method=None, max_size=None, overlap=None, language=None, **options) -> List[str]`
  - Thin wrapper around a single strategy. Returns plain strings.
  - Note: For some strategies (e.g., `words`), this path reconstructs output by joining tokens; spacing around punctuation may differ from the original source. When you require exact source fidelity and offsets, prefer `chunk_text_with_metadata` (or `process_text`) which returns spans and is normalized back to original slices.
- `chunk_text_with_metadata(...) -> List[ChunkResult]`
  - Strategy-level chunking with `ChunkResult` metadata (indices/offsets, counts).
- `chunk_text_hierarchical_tree(text, method=None, max_size=None, overlap=None, language=None, template=None) -> Dict`
  - Computes a section/block tree with paragraph kinds (`header_atx`, `code_fence`, `list_*`, `table_md`, `paragraph`, …) and attaches per-block chunks with offsets.
- `flatten_hierarchical(tree) -> List[Dict]`
  - Flattens a tree into `{text, metadata}` items, preserving ancestry (`ancestry_titles`, `section_path`).
- `chunk_text_hierarchical_flat(...) -> List[Dict]`
  - Convenience wrapper: `flatten_hierarchical(chunk_text_hierarchical_tree(...))`.
- `chunk_file_stream(file_path, method=None, max_size=None, overlap=None, language=None, buffer_size=8192, **options) -> Generator[str]`
  - Memory-efficient streaming for very large files.

Example:
```
from tldw_Server_API.app.core.Chunking import Chunker

ck = Chunker()
chunks = ck.process_text(
    text,
    options={
        "method": "sentences",
        "max_size": 8,
        "overlap": 2,
        "hierarchical": True,
        "hierarchical_template": {"boundaries": [{"kind": "header_atx", "pattern": "^\\s*#{1,6}\\s+.+$", "flags": "m"}]},
        "adaptive": True,
        "adaptive_overlap": True,
        "timecode_map": [{"start_offset": 0, "end_offset": 120, "start_time": 0.0, "end_time": 10.0}],
    },
)
```

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

## Integration Points
- HTTP APIs:
  - `tldw_Server_API/app/api/v1/endpoints/chunking.py` → chunk text (JSON/multipart); optional template path.
  - `tldw_Server_API/app/api/v1/endpoints/chunking_templates.py` → list/apply/match/learn templates.
- Services:
  - `tldw_Server_API/app/services/document_processing_service.py` → content ingestion + plaintext chunking helpers.
  - `tldw_Server_API/app/services/enhanced_web_scraping_service.py` and `web_scraping_service.py` → hierarchical flat chunking during scrape.
  - `tldw_Server_API/app/services/xml_processing_service.py` → XML chunking via improved process.

## Options (process_text)
- Core: `method`, `max_size`, `overlap`, `language` (defaults from `ChunkerConfig`: `words`, `400`, `200`, `en`).
- Sizing: `adaptive` (bool), `adaptive_overlap` (bool), `base_adaptive_chunk_size`, `min_adaptive_chunk_size`, `max_adaptive_chunk_size`, `base_overlap`, `max_adaptive_overlap`.
- Structure: `hierarchical` (bool), `hierarchical_template` (dict of `boundaries`), `multi_level` (paragraph-aware mode for words/sentences).
- Code: `code_mode` (`auto|ast|heuristic`), `language` (e.g., `python`, `typescript`).
- JSON/XML: method-specific knobs (see strategies files).
- Media: `timecode_map` → list of `{start_offset,end_offset,start_time,end_time}` to project times onto chunks.
- LLM: `tokenizer_name_or_path`, `llm_call_func`, `llm_config` (for strategies like `rolling_summarize`/`propositions`).
- Frontmatter: `enable_frontmatter_parsing` (defaults to `True`) and `frontmatter_sentinel_key` (defaults to `__tldw_frontmatter__`). JSON metadata is only stripped when the sentinel key is present with a truthy value; disable parsing to preserve all leading JSON.

## Return Shape and Metadata
- Each item: `{ "text": str, "metadata": { ... } }`
- Common metadata keys: `chunk_index`, `total_chunks`, `chunk_method`, `max_size`, `overlap`, `language`, `start_offset`, `end_offset`, `relative_position`, `paragraph_kind`, `ancestry_titles`, `section_path`, `adaptive_chunking_used`, `code_mode_used`, `chunk_content_hash`.
- Optional: `start_time`, `end_time` when `timecode_map` is provided; `initial_document_json_metadata` and `initial_document_header_text` when detected.

## Testing
- V2 unit suite: `tldw_Server_API/tests/Chunking/test_chunker_v2.py`
- Endpoint coverage: `tldw_Server_API/tests/Chunking/test_chunking_endpoint.py`
- Additional integration fixtures live alongside embeddings and ingestion tests

## Gotchas & Best Practices
- Do not exceed boundary/regex limits; prefer a few robust patterns over many fragile ones.
- Use `structure_aware` for code/docs when possible; otherwise seed headers/fences with `hierarchical_template`.
- Keep templates JSON-only; put operational notes in `metadata` (never secrets).

## Strategy Requirements
- Overlap re-clamp: Each strategy must re-clamp `overlap < max_size` to guarantee forward progress. The base `validate_parameters` helper does not mutate caller state; strategies should set `overlap = max(0, min(overlap, max_size - 1))` before windowing.
- Offsets: When returning `ChunkResult`, prefer exact `start_char`/`end_char` spans taken from the source text; avoid naïve `.find()` when feasible.
  - Paragraphs strategy uses paragraph separators to compute per-paragraph spans directly from the source; chunk windows union these spans to produce precise `start_char`/`end_char` values.
  - In hierarchical mode, the `tokens` method uses strategy metadata to map local spans to global offsets; if metadata is unavailable, a bounded fallback is used.
  - Grapheme safety: All strategies clamp `end_char` to a grapheme boundary. In non-strict mode, only non-visible trailing marks/selectors are absorbed. In strict mode (`strict_grapheme_end_expansion = true`), ZWJ sequences and emoji modifiers are also absorbed to preserve visual stability at chunk boundaries.

## Tokens Strategy Notes
- `TokenChunkingStrategy.chunk_with_metadata(...)` now emits precise character offsets when possible:
  - Transformers fast tokenizers: uses `offset_mapping` for exact spans.
  - tiktoken: decodes each token and maps via a monotonic, rolling pointer.
  - Fallback tokenizer: approximates tokens via word windows, with precise char spans and approximate `token_count`.

## Streaming Overlap Semantics

The streaming helpers emit chunks incrementally and carry context across read buffers:

- `chunk_file_stream(file_path, method=None, max_size=None, overlap=None, ...) -> Generator[str]`
- `AsyncChunker.chunk_stream(text_stream, method=None, max_size=None, overlap=None, ...) -> AsyncGenerator[str]`

Behavior by method and overlap:
- words
  - overlap > 0: emits all chunks for each buffer, then carries the trailing `overlap` tokens from the last chunk forward. The first chunk of the next buffer may repeat those tokens. When reconstructing, drop a matching prefix (up to `overlap` tokens) from the first chunk after each boundary.
  - overlap == 0: emits all chunks except the last during a buffer read and carries the full last chunk into the next buffer.
- sentences and other methods
  - overlap > 0: emits all but the last chunk for each buffer and carries that last chunk forward so the overlap happens at the buffer boundary (deduplicate by removing a matching prefix on boundary).
  - overlap == 0: same withholding of the final chunk per buffer as above.

In both cases, the boundary join uses a method-aware separator to avoid token fragmentation (a space for `words`, newlines for structure-heavy kinds). If you need exact source fidelity, prefer `chunk_text_with_metadata` or `process_text`, which normalize returned text to original spans by `start_offset`/`end_offset`.

## Language Autodetection

`process_text(..., options={"language": "auto"})` triggers lightweight script-based detection when the language is not supplied (also the default). Detected codes include:
- zh (CJK), ja (Hiragana/Katakana), th (Thai), hi (Devanagari/Hindi), ru (Cyrillic/Russian), ko (Hangul/Korean), ar (Arabic).

These hints choose sensible tokenizers/splitters for strategies. You can always set `language` explicitly per call.

## Configuration (config.txt)
Add these optional keys under a new `[Chunking]` section. Environment variables with the same names in UPPERCASE override file values.

- max_streaming_flush_threshold_chars: Cap for streaming buffer size when chunking very large files.
  - Default: no cap beyond internal heuristic; minimum enforced is 2048 chars.
  - Env: `CHUNKING_MAX_STREAMING_FLUSH_CHARS`
  - Example: `max_streaming_flush_threshold_chars = 1000000`

- json_single_metadata_reference: Emit a single metadata chunk and reference it from subsequent JSON chunks (avoids repeating metadata).
  - Default: `false`
  - Env: `JSON_SINGLE_METADATA_REFERENCE`

- json_metadata_reference_key: Key name used for the metadata reference in JSON chunks.
  - Default: `__meta_ref__`
  - Env: `JSON_METADATA_REFERENCE_KEY`

- strict_grapheme_end_expansion: Expand `end_char` to the next grapheme boundary, including ZWJ sequences and emoji skin-tone modifiers.
  - Default: `false` (non-strict mode only expands trailing combining marks, variation selectors, and zero-width non-joiners except ZWJ).
  - Env: `STRICT_GRAPHEME_END_EXPANSION`
  - Per-call override: pass `strict_grapheme_end_expansion=True` in strategy `**options`.

Behavior (JSON):
- With `json_single_metadata_reference = true` and `preserve_metadata = true`, JSON output begins with a metadata-only chunk:
  - `{ "__meta_ref__": "<id>", "metadata": { ... } }`
  - Subsequent chunks include `{ "data": [...], "__meta_ref__": "<id>" }` (for a list) or the analogous dict form.
  - When `output_format = 'text'`, these objects are rendered via `_json_to_text`.

## Strategies (Built-in)
- `words`, `sentences`, `paragraphs`, `fixed_size`, `tokens`, `semantic`, `json`, `xml`, `ebook_chapters`, `propositions`, `rolling_summarize`, `structure_aware`, `code` (Python AST / heuristic based on `code_mode`), `code_ast` (force AST).
  - See `strategies/` submodules for implementation and method-specific options.

## Caching and Metrics
- Config: `ChunkerConfig(enable_cache=True, cache_size=100, min_text_length_to_cache=0, max_text_length_to_cache=2_000_000)`.
- LRU cache keyed by text + parameters. Cache skips extremely short or very large texts based on thresholds.
- Metrics hooks are no-ops when Metrics module is unavailable; otherwise counters/histograms are emitted around processing and caching paths.

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
    options={
        "method": "sentences",
        "max_size": 3,
        "overlap": 1,
        "timecode_map": segments,
        "adaptive": True,
        "adaptive_overlap": True,
    },
)
for ch in chunks:
    md = ch["metadata"]
    print(md.get("start_time"), md.get("end_time"))
```

Notes:
- Mapping is best-effort: if a chunk overlaps a segment, the mapped times cover the overlapped portion proportionally.
- If multiple segments overlap a chunk, the first overlap is used.

## Config Settings (Regex Safety)
Configure regex safety for `ebook_chapters` via `Config_Files/config.txt` under `[Chunking]`:

- `regex_timeout_seconds`
  - Cap regex execution time (seconds) for chapter/section detection. `0` disables.
  - Default: `0` (disabled). Example: `regex_timeout_seconds = 0.5`.

- `regex_disable_multiprocessing`
  - When `true`, disables process-based isolation fallback and uses thread-guarded execution only.
  - Default: `true` (safer cross-platform default).

- `regex_simple_only`
  - When `true`, restricts custom chapter regex to a safe subset.
  - Disallows grouping `()`, alternation `|`, wildcard `.`, `?`, `*`; allows literals, anchors `^`/`$`, character classes `[A-Z]`, escapes `\d`/`\w`, and `+` after safe atoms.
  - Default: `false`.

## Security Hardening (General)
- Input sanitization removes null bytes, suspicious control characters, and bidi overrides; Unicode is normalized.
- Hierarchical detection and template boundaries run under safety limits (pattern length, count, optional timeouts); dangerous patterns are rejected.
- Keep custom regex minimal; prefer boundary anchors and case-insensitive flags.
## Code Chunking (Python + JavaScript)

- Method: `code` with optional `code_mode` for routing.
  - `code_mode=auto` (default): If `language` starts with `py`, uses AST-based Python chunking; otherwise uses heuristic chunking.
  - `code_mode=ast`: Force AST-based Python chunking (for `.py`).
  - `code_mode=heuristic`: Force heuristic chunking (works across JS/TS, C-like languages, etc.).
  - Note: You can also specify `method='code_ast'` directly to route to the AST strategy regardless of `language` or `code_mode`.

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

## Extending the Module
- New strategy:
  - Implement `BaseChunkingStrategy` in `strategies/<name>.py` with `chunk()` (and optionally `chunk_with_metadata()`).
  - Add an entry in `Chunker._register_strategy_factories()` to wire it by method name.
  - If it’s a first-class method, extend `ChunkingMethod` enum in `base.py`.
  - Add unit tests and brief docs here with method-specific options.
- New template features:
  - Extend `templates.py` processors or learners conservatively and update validators/safety in `regex_safety.py` as needed.
- Performance:
  - Avoid expensive regex or O(n^2) scans inside hot paths; prefer precomputed spans and streaming.
  - Keep cache-friendly behavior (stable options, deterministic output).

## Backwards Compatibility
- `Chunking.improved_chunking_process(...)` shims to `Chunker.process_text(...)`. Prefer direct `Chunker` usage and migrate call sites over time.
