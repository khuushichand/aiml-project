# Chunking Module - Developer Guide

This document explains the architecture, extension points, and best practices for the v2 Chunking subsystem. It is aimed at project developers and maintainers.

## Purpose

The Chunking module turns raw text (or structured content) into smaller, semantically meaningful units (“chunks”) suitable for RAG, embedding, and downstream analytics. It offers:

- A pluggable registry of chunking strategies
- Consistent metadata on chunk boundaries and positions
- Streaming and hierarchical chunking helpers
- Metrics and tracing hooks for observability
- Compatibility helpers for legacy call sites

## Module Layout

- `tldw_Server_API/app/core/Chunking/`
  - `base.py` - Core types and interfaces
    - `ChunkingMethod` (Enum)
    - `ChunkMetadata`, `ChunkResult`
    - `ChunkingStrategy` protocol
    - `BaseChunkingStrategy` base class
    - `ChunkerConfig` (configuration object)
  - `chunker.py` - Main orchestrator and strategy registry
    - `Chunker` (public entry point)
    - Lazy registry of strategies and convenience APIs
    - LRU caching and metrics hooks
    - Hierarchical helpers and streaming utilities
    - `create_chunker()` factory
  - `strategies/` - Strategy implementations
    - `words.py`, `sentences.py`, `paragraphs.py`, `tokens.py`, `json_xml.py`, `structure_aware.py`, `propositions.py`, `rolling_summarize.py`, `ebook_chapters.py`, `semantic.py`, `code.py`, `code_ast.py`
  - `templates.py` - Template system (processor/manager/learner)
  - `template_initialization.py` - Built-in chunking template seeding and updates (DB-backed)
  - `__init__.py` - Public API surface, defaults, and legacy bridges

## Key Types

- `ChunkingMethod` - Canonical method names (e.g., `words`, `sentences`, `paragraphs`, `tokens`, `json`, `xml`, `ebook_chapters`, `propositions`, `rolling_summarize`, `semantic`).
- `ChunkMetadata` - Per-chunk metadata (character offsets, word counts, language, method, overlap, etc.).
- `ChunkResult` - Struct holding the `text` and its `ChunkMetadata`.
- `ChunkerConfig` - Defaults for method, max size, overlap, language, caching, max text size, and metrics toggle.

## The Strategy Registry

Strategies are discovered and instantiated through the `Chunker`’s internal registry of factory functions.

- Registration: `Chunker._register_strategy_factories()` populates a dict mapping method name → factory lambda.
- Lazy creation: `get_strategy(method)` creates the strategy on first use and caches the instance.
- Extensible: Add a new strategy by implementing `BaseChunkingStrategy` and registering it in `_register_strategy_factories()` with a unique method key (typically the `ChunkingMethod` enum value; a few legacy adapters such as `code_ast` still use string keys).

Example (excerpt):

- `words` → `WordChunkingStrategy`
- `sentences` → `SentenceChunkingStrategy`
- `tokens` → `TokenChunkingStrategy`
- `json` → `JSONChunkingStrategy`, `xml` → `XMLChunkingStrategy`
- `rolling_summarize` → `RollingSummarizeStrategy` (requires LLM hooks)

## Public Entry Points

- `Chunker` (preferred):
  - `chunk_text(text, method=..., max_size=..., overlap=..., language=..., **options) -> List[str]`
  - `chunk_text_with_metadata(...) -> List[ChunkResult]`
  - `chunk_text_generator(...) -> Generator[str, None, None]` (memory-efficient)
  - `chunk_file_stream(file_path, ...) -> Generator[str, None, None]` (very large files)
  - `process_text(text, options, tokenizer_name_or_path=None, llm_call_func=None, llm_config=None) -> List[Dict]` - end-to-end pipeline that: parses optional front-matter, handles basic header stripping, resolves defaults (incl. language heuristics), applies hierarchical or multi-level paragraph chunking when requested, and normalizes outputs to dicts.
  - Hierarchical helpers:
    - `chunk_text_hierarchical_tree(...) -> Dict[str, Any]` - build sections/blocks tree with chunk leaves
    - `chunk_text_hierarchical_flat(...) -> List[Dict]` - flattened leaves (with offsets and paragraph kinds)
  - Utilities:
    - `get_available_methods() -> List[str]`
    - `get_strategy(method)` - retrieve or instantiate a strategy
    - `clear_cache()`, `get_cache_stats()`

### Capabilities Endpoint

`GET /api/v1/chunking/capabilities`

Returns the current chunking capabilities derived from the runtime registry and defaults.

Example response:

```
{
  "methods": ["words", "sentences", "paragraphs", "tokens", "semantic", "json", "xml", "ebook_chapters", "rolling_summarize", "structure_aware", "code", "code_ast"],
  "default_options": { ... },
  "llm_required_methods": ["rolling_summarize", "propositions"],
  "hierarchical_support": true,
  "notes": "Text chunking capabilities. For method='code', the option 'code_mode' controls routing: 'auto' (default), 'ast' (Python), or 'heuristic'. Ingestion-specific chunkers are configured via templates or step config.",
  "method_specific_options": {
    "code": {
      "code_mode": ["auto", "ast", "heuristic"],
      "language_hints": {"py": "python", "js": "javascript", "jsx": "javascript", "ts": "typescript", "tsx": "typescript"}
    }
  }
}
```

- Legacy bridges (back-compat):
  - `from ...Chunking import improved_chunking_process` - simplified wrapper around `Chunker`
  - `from ...Chunking import chunk_for_embedding` - standardized format for embedding pipelines
  - `from ...Chunking import flatten_hierarchical` - bridge to v1 flattener when available

## Strategy Interface

Each strategy implements `BaseChunkingStrategy` (or the `ChunkingStrategy` protocol):

- `chunk(text, max_size, overlap, **options) -> List[str]`
- Optional generator variant (for streaming): `chunk_generator(...) -> Generator[str, None, None]`
- Default `chunk_with_metadata(...)` is provided by `BaseChunkingStrategy` and wraps the raw chunks with computed offsets and metadata.

When writing a new strategy:
- Inherit from `BaseChunkingStrategy`, implement `chunk(...)` minimally.
- Keep the method deterministic and side-effect-free (pure functions where practical).
- Use `validate_parameters(...)` if you need to guard inputs.
- Avoid heavyweight operations inside tight loops; for tokenization-heavy methods prefer a cached tokenizer.

## Configuration

- Defaults are provided by `ChunkerConfig` and can be overridden via constructor or the `create_chunker(config_dict)` helper.
- `__init__.py` also sets legacy defaults `DEFAULT_CHUNK_OPTIONS` and reads system config (if available) for a few toggles (e.g., proposition engine defaults).
- Some `process_text` behaviors (e.g., adaptive sizing) respond to options like `adaptive`, `base_adaptive_chunk_size`, etc.

## Hierarchical & Templates

- Hierarchical chunking builds a simple tree of sections and blocks (headers, paragraphs, code fences, lists, hrules, tables, template matches), then chunks leaf blocks using a base method.
- Built-in templates can be stored/seeded in the media DB:
  - `template_initialization.py` loads JSON templates from `template_library/` and seeds them via `MediaDatabase.seed_builtin_templates()`.
  - Call `ensure_templates_initialized()` during app startup to guarantee availability.
  - Templates can define custom “boundary” regex rules used by the hierarchical splitter.

## Metrics & Tracing

- Chunking integrates with the unified metrics system (`app/core/Metrics`).
- High-level operations observe histograms (e.g., front-matter parsing, header stripping, overall processing) and increment counters.
- Legacy v1 registers Prometheus metric definitions (chunk counts, bytes, timing) for benchmarks and existing tests.
- Use labels consistently (e.g., `method`, `language`) for cardinality control.

## Caching

- `Chunker` optionally caches results with a simple thread-safe LRU (`LRUCache`) keyed on `(text_hash, method, max_size, overlap, language, options)`.
- Enable/size via `ChunkerConfig(enable_cache=True, cache_size=...)`.
- Use `clear_cache()` and `get_cache_stats()` for maintenance/inspection.

## Error Handling & Security

- Common errors:
  - `InvalidInputError` - bad input or missing file during streaming
  - `InvalidChunkingMethodError` - unknown method key or factory failure
  - `ChunkingError` - general operational failures
- Strategies should fail fast with clear messages and avoid swallowing exceptions.
- Security logging hooks (`security_logger`) exist for higher-risk operations; extend carefully if handling untrusted inputs.

## Adding a New Strategy - Checklist

1. Create `strategies/<your_method>.py` with a `BaseChunkingStrategy` subclass implementing `chunk(...)`.
2. Add a new key to `ChunkingMethod` (optional but recommended for consistency).
3. Register the strategy in `Chunker._register_strategy_factories()`:
   - `self._strategy_factories[ChunkingMethod.YOUR_METHOD.value] = lambda: YourStrategy(language=lang)`
4. (Optional) Add template support and defaults if needed.
5. Add unit tests under `tldw_Server_API/tests/Chunking/` and/or integration/bench tests.
6. If collecting metrics, use the unified metrics API and add label docs as needed.

## Testing & Benchmarks

- Unit coverage should target:
  - Strategy chunk boundaries and metadata
  - Method dispatch and validation
  - Hierarchical splitting on common markdown patterns
- Performance tests can reuse the fixtures in `tests/Chunking/` (e.g., mark with `@pytest.mark.benchmark`) to avoid diverging harnesses.
- The chunking metrics test expects Prometheus metric names like:
  - `chunk_time_seconds`, `chunk_output_bytes`, `chunk_input_bytes`, `chunk_count`, `chunk_avg_chunk_size_bytes`

## Practical Usage Patterns

- Simplest:
  - `chunker = Chunker()`
  - `chunks = chunker.chunk_text_with_metadata(text, method="sentences", max_size=512, overlap=50)`
- Hierarchical (flat):
  - `chunks = chunker.chunk_text_hierarchical_flat(text, method="words", max_size=400, overlap=50, template=template_dict)`
- End-to-end normalization:
  - `rows = chunker.process_text(text, options={...})` - returns a list of dicts with consistent metadata fields. JSON frontmatter is stripped only when the leading object carries the sentinel key (`__tldw_frontmatter__` by default); override with `frontmatter_sentinel_key` or disable via `enable_frontmatter_parsing=False`.
- Streaming a large file:
  - `for ch in chunker.chunk_file_stream(path, method="sentences", max_size=2048): ...`

## Code Chunking (Python and JavaScript/TypeScript)

- Method: `code`
- Routing option: `code_mode` in options controls backend:
  - `auto` (default): if `language` starts with `py`, routes to AST-based Python strategy; otherwise uses heuristic strategy.
  - `ast`: force AST-based Python strategy (`strategies/code_ast.py`).
  - `heuristic`: force heuristic strategy (`strategies/code.py`).

- Python (AST): segments into import block, top-level classes, and functions with precise char offsets and greedy packing/overlap.
- JavaScript/TypeScript (heuristic): recognizes `export default class Name`, `class Name`, `export function name(...)`, `function name(...)`,
  `export const name = (...) => {}`, `const name = function (...)`, `export default function name(...)`, `export default function (...)`,
  `export default (...) => {}`, `export interface Name {}`, and `export type Name = ...` and packs blocks accordingly.

Example usage:

```
rows = chunker.process_text(
    code_text,
    options={
        'method': 'code',
        'language': 'python',
        'code_mode': 'ast',
        'max_size': 800,
        'overlap': 50,
    },
)
```

## Maintenance Notes

- Keep the registry small and lazy: avoid importing heavy dependencies at module import time-prefer factory functions that import on demand.
- Preserve backward compatibility via `__init__.py` helpers as tests evolve; call out deprecations explicitly in docs/comments.
- Avoid breaking metric names/labels without a deprecation plan; benchmarks depend on them.
- When changing hierarchical split rules, run the bench tests and spot-check offsets on a few real documents.

---

For questions or proposals, open a PR with a short design note under `Docs/Design/` and link to relevant strategies/tests.
