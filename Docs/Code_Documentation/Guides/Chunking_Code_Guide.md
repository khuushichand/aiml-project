# Chunking Module Code Guide (Developers)

This guide orients project developers to the Chunking module: what’s in it, how it works, and how to work with it across APIs, ingestion, RAG, and tests.

See also:
- tldw_Server_API/app/core/Chunking/README.md
- Docs/Code_Documentation/Chunking-Module.md
- Docs/Code_Documentation/Chunking_Templates_Developer_Guide.md

## Scope & Goals
- Turn raw text or structured inputs into smaller, useful “chunks” with stable metadata.
- Support multiple chunking methods (words/sentences/paragraphs/tokens/semantic/json/xml/ebook_chapters/propositions/rolling_summarize/structure_aware/fixed_size/code).
- Provide hierarchical splitting, streaming helpers, and a template pipeline.
- Integrate with unified Metrics, security logging, and AuthNZ patterns.

## Quick Code Map
- Core orchestrator and types
  - tldw_Server_API/app/core/Chunking/chunker.py → Chunker (primary entry), hierarchical + streaming, LRU cache, metrics
  - tldw_Server_API/app/core/Chunking/base.py → ChunkingMethod, ChunkResult, ChunkMetadata, BaseChunkingStrategy, ChunkerConfig
  - tldw_Server_API/app/core/Chunking/exceptions.py → exceptions (InvalidInputError, InvalidChunkingMethodError, ChunkingError, …)
  - tldw_Server_API/app/core/Chunking/constants.py → frontmatter sentinel helpers
  - tldw_Server_API/app/core/Chunking/async_chunker.py → AsyncChunker wrapper and streaming
- Strategies (pluggable methods)
  - tldw_Server_API/app/core/Chunking/strategies/*.py → words, sentences, paragraphs, tokens, semantic, json_xml, ebook_chapters, propositions, rolling_summarize, structure_aware, code, code_ast
- Template pipeline
  - tldw_Server_API/app/core/Chunking/templates.py → TemplateProcessor/TemplateManager/TemplateClassifier/TemplateLearner
  - tldw_Server_API/app/core/Chunking/template_library/*.json → built‑ins
  - tldw_Server_API/app/core/Chunking/template_initialization.py → seeding/updates
- Safety & utilities
  - tldw_Server_API/app/core/Chunking/regex_safety.py → regex guards + RE2 fallback
  - tldw_Server_API/app/core/Chunking/security_logger.py → security event logging
  - tldw_Server_API/app/core/Chunking/utils/*.py → metrics glue, proposition helpers

API endpoints and schemas
- tldw_Server_API/app/api/v1/endpoints/chunking.py → /api/v1/chunking/*
- tldw_Server_API/app/api/v1/endpoints/chunking_templates.py → /api/v1/chunking/templates/*
- tldw_Server_API/app/api/v1/schemas/chunking_schema.py, chunking_templates_schemas.py

## Public APIs You’ll Use

Chunker (synchronous)
- process_text(text, options=None, *, tokenizer_name_or_path=None, llm_call_func=None, llm_config=None) → List[Dict]
  - End‑to‑end: optional frontmatter strip, option resolution, hierarchical mode, normalization to {text, metadata}.
- chunk_text(text, method=None, max_size=None, overlap=None, language=None, **options) → List[str]
  - Thin wrapper around a single strategy; for exact offsets prefer chunk_text_with_metadata or process_text.
- chunk_text_with_metadata(...) → List[ChunkResult]
  - Strategy outputs with precise offsets, counts, indices.
- chunk_text_generator(text, method=None, max_size=None, overlap=None, language=None, **options) → Generator[str]
  - Memory‑efficient generator for whole‑text inputs when you don’t need metadata.
- chunk_text_hierarchical_tree(...), flatten_hierarchical(...) → section/block tree and flattening with ancestry.
- chunk_text_hierarchical_flat(...) → convenience wrapper returning flat {text, metadata}.
- chunk_file_stream(file_path, method=None, max_size=None, overlap=None, language=None, buffer_size=8192, encoding='utf-8', **options) → Generator[str]
  - Streaming for very large files; see “Streaming” below.
  - Note: encoding is passed to file reads (defaults to 'utf-8') so callers can adjust text decoding if needed.

AsyncChunker (asynchronous)
- async methods mirror the above for I/O‑heavy paths and streaming text sources.

Template pipeline
- TemplateManager.process(text, template_name, **options) → List[Dict]
- TemplateProcessor.process_template(text, template, **options) → List[Dict]

## Typical Usage Patterns

Simple strategy call
```python
from tldw_Server_API.app.core.Chunking import Chunker

ck = Chunker()
chunks = ck.chunk_text_with_metadata(
    text, method="sentences", max_size=8, overlap=2, language="en"
)
for r in chunks:
    print(r.text, r.metadata.start_char, r.metadata.end_char)
```

Whole‑text generator vs. file streaming
- Prefer `chunk_text_generator` when you already have the full text in memory and only need strings (no metadata) in a streaming fashion.
- Prefer `chunk_file_stream` for very large files where you don’t want to load the entire file; it reads buffers from disk and carries overlap forward between buffers.

End‑to‑end normalized rows (recommended for app code)
```python
ck = Chunker()
rows = ck.process_text(
    text,
    options={
        "method": "words",
        "max_size": 400,
        "overlap": 200,
        # hierarchical mode optionally groups paragraphs/headers/code fences
        "hierarchical": True,
        # or provide a template of custom boundaries
        "hierarchical_template": {"boundaries": [{"kind": "chapter", "pattern": r"^Chapter\\s+\\d+\b", "flags": "im"}]},
    },
)
```

Streaming a very large file
```python
ck = Chunker()
for ch in ck.chunk_file_stream("/path/to/huge.txt", method="sentences", max_size=2048, overlap=128):
    process(ch)
```

Using templates (DB‑backed via endpoints or direct)
```python
from tldw_Server_API.app.core.Chunking.templates import TemplateManager

mgr = TemplateManager()
rows = mgr.process(text, template_name="academic_paper", max_size=6, overlap=1)
```

Timecode mapping for transcripts (best‑effort projection)
```python
segments = [
  {"start_offset": 0, "end_offset": 120, "start_time": 0.0, "end_time": 10.0},
  {"start_offset": 120, "end_offset": 300, "start_time": 10.0, "end_time": 25.0},
]
rows = Chunker().process_text(text, options={"method": "sentences", "timecode_map": segments})
```

## Choosing a Method (cheat‑sheet)
- words: token windows when you need stable sizes; good for classic embedding windows.
- sentences: keeps sentence boundaries; good for QA and semantic tasks.
- paragraphs: paragraph windows; strong for narrative/markdown/HTML‑ish content.
- tokens: use model/tokenizer semantics; enables exact token counts with offset_mapping.
- semantic: semantic segmentation + re‑packing; more compute but better boundaries.
- json / xml: structure‑aware chunking for documents/APIs; safety guards against XXE/regex issues.
- ebook_chapters: chapter/section detection; configurable patterns; regex safety enforced.
- propositions: clause/proposition chunks; can use LLM; tune via options in DEFAULT_CHUNK_OPTIONS.
- rolling_summarize: LLM‑assisted rolling chunks; requires llm_call_func + llm_config.
- structure_aware: paragraph‑kind grouping with max elements + overlap per section.
- code / code_ast: code structure segmentation; ‘code_mode’ routes auto/ast/heuristic.

Tip: for code
```python
rows = Chunker().process_text(code_text, options={"method": "code", "language": "python", "code_mode": "ast"})
```

## Hierarchical Splitting

- chunk_text_hierarchical_tree builds a light tree with sections and blocks. Markdown‑like features are recognized: ATX headers (`#`), hrules, lists, code fences, markdown tables, blank lines, plus optional custom “boundary” patterns from hierarchical_template.
- flatten_hierarchical emits flat items with ancestry_titles and section_path metadata.
- For structure_aware, flattening supports grouping “N elements per chunk” within each section, with optional overlap and per‑kind weighting.

When to use: long documents with headings/lists/code blocks where preserving structure aids retrieval, re‑ranking, or display.

## Streaming

- chunk_file_stream (sync) and AsyncChunker.chunk_stream (async) support large inputs.
- Overlap behavior is carry‑forward, not withholding:
  - For overlap > 0, the chunker computes an overlap buffer from the tail of the previous processed segment (method‑aware: words, sentences, paragraphs, tokens) and prefixes it to the next segment before chunking. Previously emitted chunks are not dropped; duplicates around buffer boundaries are expected by design when using overlap.
  - For overlap = 0, no carry is used. The next segment starts at a split point; the prior segment’s last chunk is not withheld.
- Streaming chooses split points near the flush threshold and avoids breaking tokens for words/sentences. Joining uses a space for words when needed.
- If you have the whole text but want low‑memory iteration, use chunk_text_generator.
- For exact offset fidelity, prefer chunk_text_with_metadata or process_text (streaming/generator yield strings).

## Options & Defaults

Global defaults come from ChunkerConfig and DEFAULT_CHUNK_OPTIONS. Common per‑call options include:
- method: str or ChunkingMethod
- max_size: int (>0)
- overlap: int (>=0 and < max_size)
- language: str ("auto"/"detect" supported in process_text)
- hierarchical: bool
- hierarchical_template: {"boundaries": [{"kind": str, "pattern": str, "flags": "im"}, ...]}
- tokenizer_name_or_path: for tokens strategy
- timecode_map: list of {start_offset, end_offset, start_time, end_time}
- adaptive, base_adaptive_chunk_size, min_adaptive_chunk_size, max_adaptive_chunk_size, adaptive_overlap, base_overlap, max_adaptive_overlap
- code_mode: for method="code" → "auto" | "ast" | "heuristic"

Metadata keys note
- process_text normalizes outgoing metadata and sets both max_size/overlap and max_size_setting/overlap_setting for compatibility. Consumers should prefer max_size and overlap but be tolerant of either set.

Defaults reference
- See defaults and proposition-related knobs in tldw_Server_API/app/core/Chunking/__init__.py: DEFAULT_CHUNK_OPTIONS (e.g., proposition_engine, proposition_aggressiveness, proposition_min_proposition_length, proposition_prompt_profile).

Config.txt overrides (optional) under [Chunking]
- max_streaming_flush_threshold_chars, regex_timeout_seconds, regex_disable_multiprocessing, regex_simple_only, strict_grapheme_end_expansion, json_single_metadata_reference, json_metadata_reference_key

## Error Handling & Security

- Input sanitization removes null bytes, suspicious control chars, and bidi overrides; Unicode normalization applied when safe (preserves length/offsets).
- Size limits enforced via ChunkerConfig.max_text_size.
- Regex safety for user patterns via regex_safety (length caps, nested quantifier checks, compile guard, optional RE2 path and timeouts from config).
- Security events are recorded via security_logger (e.g., oversized input, suspicious content).
- Exceptions to expect: InvalidInputError, InvalidChunkingMethodError, ChunkingError, TemplateError.

## Metrics, Caching, Performance

- Metrics: histograms/counters are no‑ops when Metrics isn’t available; otherwise frontmatter/header/normalization/overall timings and byte gauges are recorded.
- LRU cache: optional, thread‑safe; keyed by text + parameters; thresholds for min/max length to cache; copy‑on‑access configurable.
- For high‑throughput ingestion, prefer:
  - Using process_text with hierarchical=False unless structure matters.
  - Batching embeddings downstream and avoiding very large overlaps.
  - Limiting regex rules in templates; anchor patterns; avoid wide wildcards.

## Integrations in the Server

- REST endpoints: /api/v1/chunking
  - POST /chunk_text → chunk JSON body (tldw_Server_API/app/api/v1/endpoints/chunking.py)
  - POST /chunk_file → chunk uploaded file (same file)
  - GET /capabilities → runtime method list and defaults
- Template endpoints: /api/v1/chunking/templates/* (CRUD, apply, validate, match)
- Embeddings & RAG: chunking feeds embedding windows in tests and orchestrators; see Docs/Code_Documentation/Embeddings-Developer-Guide.md.

## Extending the Module

Add a strategy
1. Create strategies/<name>.py implementing BaseChunkingStrategy.chunk(...). Optionally override chunk_with_metadata for precise offsets.
2. Register in Chunker._register_strategy_factories with a stable method key. If it’s first‑class, add to ChunkingMethod.
3. Document options and defaults. Keep label/cardinality small if emitting metrics.
4. Add unit tests and update docs (this guide + Chunking-Module.md). If needed, add config keys.

Add template features
- Extend TemplateProcessor operations or TemplateManager seeding; follow regex_safety.
- Keep template JSON free of secrets; put notes under metadata.

## Testing Pointers

- Unit tests: strategy boundaries and offsets; overlap re‑clamp; grapheme boundary expansion.
- Integration: endpoints and embeddings flows that toggle perform_chunking.
- Property‑based: invariants around chunk stitching/reconstruction.
- Markers: unit, integration, external_api, local_llm_service

## Gotchas & Best Practices
- Overlap must be < max_size; strategies re‑clamp internally for forward progress.
- chunk_text returns strings and may not preserve exact source spacing in token‑reassembled methods; prefer chunk_text_with_metadata/process_text for exact spans.
- For long docs, use hierarchical or structure_aware to avoid breaking logical units.
- For JSON/XML, enable preserve_metadata and single‑metadata‑reference when large metadata repeats.
- Keep regex boundary rules short and anchored; avoid nested quantifiers.
- For code, set code_mode explicitly; ‘auto’ routes to AST for python when language hints start with "py".

## Minimal “How to Wire in an Endpoint”
```python
from fastapi import APIRouter, Body
from tldw_Server_API.app.core.Chunking import Chunker

router = APIRouter(prefix="/example")

@router.post("/chunk")
async def chunk_endpoint(body: dict = Body(...)):
    text = body.get("text", "")
    options = body.get("options", {})
    rows = Chunker().process_text(text, options=options)
    return {"chunks": rows}
```

## Where to Start
- Read chunker.py for orchestration and options.
- Pick a strategy under strategies/ and skim its chunk(...) implementation.
- Try process_text in a notebook with a few methods and hierarchical on/off.
- If your input has clear structure, design a small hierarchical_template and iterate.

---

Questions or proposals? Open a PR and attach a short design note under Docs/Design/; include tests and briefly update this guide.
