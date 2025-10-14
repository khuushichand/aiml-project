# RAG Module - Unified Pipeline Architecture

## Overview

The RAG (Retrieval-Augmented Generation) module provides intelligent search and question-answering capabilities for the tldw_server application. It uses a **unified pipeline architecture** where ALL features are accessible through a single function with explicit parameters - no configuration files, no presets, just direct parameter control.

✅ Current Status: Unified pipeline is the primary interface. The parameters and examples below match the request schema in `api/v1/schemas/rag_schemas_unified.py`.

## Available Features

### ✅ Fully Connected & Accessible
- **Unified Pipeline**: Single function with 50+ parameters for complete control
- **Multi-Database Search**: Query across media, notes, character cards, and chat history
- **Query Expansion**: Multiple strategies (acronyms, synonyms, domain terms, entities)
- **Hybrid Search**: Combines keyword (FTS5) and vector similarity search
- **Smart Caching**: Semantic cache with adaptive thresholds and LRU eviction
- **Document Reranking**: Multiple strategies (FlashRank, cross-encoder, hybrid)
- **Citations**: Academic citations (APA/MLA/Chicago/Harvard/IEEE); chunk‑level details in progress
- **Analytics Integration**: Privacy-preserving server analytics with SHA256 hashing
- **Batch Processing**: Concurrent processing of multiple queries
- **Security Features**: PII detection and content filtering
- **Performance Optimizations**: Connection pooling and embedding cache
- **Production Ready**: Circuit breakers, retries, fallbacks, health monitoring
- **Answer Generation**: LLM-powered response generation from retrieved context

### ⚠️ Limited Integration
- **Observability Tracing**: Partial implementation in analytics system
- **Advanced Query Features**: Some edge cases not fully tested
- **Document Processing Integration**: Basic implementation, could be enhanced

## Quick Start

```python
from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline

# Simple usage with unified pipeline
result = await unified_rag_pipeline(
    query="What is machine learning?",
    sources=["media_db", "notes"],
    enable_cache=True,
    expand_query=True,
    expansion_strategies=["acronym", "synonym"],
    top_k=10,
    enable_citations=True,
    citation_style="apa"
)

# Access comprehensive results
documents = result.documents
citations = result.citations  # Academic + chunk citations
timings = result.timings
feedback_id = result.feedback_id  # For analytics
generated_answer = result.generated_answer

## Claims & Factuality

Enable per‑claim extraction and verification, and get a factuality summary:

```python
result = await unified_rag_pipeline(
    query="What is CRISPR?",
    enable_generation=True,
    enable_claims=True,
    # Use APS-style (Abstractive Proposition Segmentation) for atomic claims
    claim_extractor="aps",  # or "auto" / "claimify"
    claim_verifier="hybrid",
    claims_top_k=5,
    claims_conf_threshold=0.7,
)

print(result.claims)       # per-claim label, confidence, evidence
print(result.factuality)   # supported/refuted/nei, precision, coverage, claim_faithfulness

### APS (Abstractive Proposition Segmentation)

What it is:
- APS decomposes text into minimal, self‑contained factual propositions that can be individually verified.
- We use an APS‑style prompt profile ("gemma_aps") with the proposition chunker to extract atomic claims with high precision.

How it’s implemented here:
- `claim_extractor="aps"` routes claim extraction through `PropositionChunkingStrategy` using the LLM engine with `proposition_prompt_profile="gemma_aps"`.
- The extractor windows long text (≈1200 chars), extracts atomic propositions, normalizes/merges short items, and returns one claim per proposition.
- Verification then runs per‑claim using a hybrid approach: local NLI if available (`RAG_NLI_MODEL`), otherwise an LLM judge.

Using APS elsewhere:
- Chunking API: use `method="propositions"`, `proposition_engine="llm"`, `proposition_prompt_profile="gemma_aps"` for APS‑style proposition chunking.

Recommended models (optional):
- `google/gemma-2b-aps-it`
- `google/gemma-7b-aps-it` (or community GGUF variants for CPU/quantized)

Model configuration notes:
- The APS extractor uses your default OpenAI‑compatible chat endpoint. To back it with a specific APS‑IT model:
  - Point your OpenAI‑compatible gateway (e.g., vLLM/TabbyAPI/OpenRouter/custom‑openai) at the APS model and set it as the default model, or
  - For ingestion‑time claim extraction (non‑APS path), set `CLAIMS_LLM_PROVIDER` and `CLAIMS_LLM_MODEL` in `Config_Files/config.txt`.
- Local NLI for verification: set `RAG_NLI_MODEL` (e.g., `roberta-large-mnli`) to reduce LLM calls.
```

## Hierarchical Chunking (Optional)

The chunker supports hierarchical parsing of documents (sections, paragraphs, tables, lists) with exact offsets. You can enable hierarchical flattening at ingestion time so that leaf chunks include ancestry titles and paragraph kinds in metadata.

Example: enabling hierarchical chunking during ingestion/storage

```python
from tldw_Server_API.app.core.Embeddings.ChromaDB_Library import ChromaDBManager

mgr = ChromaDBManager(user_id="u1", db_path="Databases/Media_DB_v2.db")
mgr.process_and_store_content(
    content=my_text,
    media_id=42,
    file_name="notes.md",
    collection_name="default",
    create_embeddings=True,
    # New options:
    hierarchical_chunking=True,  # turns on hierarchical parsing + flattening
    hierarchical_template={      # optional custom boundaries
        'boundaries': [
            {'kind': 'my_section', 'pattern': r'^##\\s+Custom', 'flags': 'im'}
        ]
    },
    # You can still pass chunk_options as before; hierarchical wins if set here
    chunk_options={'max_size': 100, 'overlap': 10, 'method': 'sentences'}
)
```

## Adaptive Post-Verification (Optional)

After answer generation, you can enable a post-generation verifier that checks the draft answer against the retrieved evidence and optionally performs a bounded repair pass.

- Triggers when unsupported_ratio = (refuted + NEI) / total_claims exceeds a threshold.
- Runs a second‑chance retrieval + regeneration within time/attempt budgets.
- Exposes metrics for retries, unsupported counts, and duration.

Usage in unified pipeline:

```python
result = await unified_rag_pipeline(
    query="What is CRISPR?",
    enable_generation=True,
    # Enable post-verification and guardrails
    enable_post_verification=True,
    adaptive_max_retries=1,
    adaptive_unsupported_threshold=0.15,
    adaptive_max_claims=20,
    adaptive_time_budget_sec=10.0,
    low_confidence_behavior="ask",  # continue | ask | decline
)

print(result.metadata.get("post_verification"))
# { unsupported_ratio, total_claims, unsupported_count, fixed, reason }
```

Environment defaults (optional):
- RAG_ADAPTIVE_TIME_BUDGET_SEC: hard cap in seconds for post-check work

Metrics exported:
- rag_unsupported_claims_total (counter)
- rag_adaptive_retries_total (counter)
- rag_adaptive_fix_success_total (counter)
- rag_postcheck_duration_seconds (histogram, labels: outcome=[ok|fixed|unfixed|skipped])


Each flattened chunk contains:
- `metadata.ancestry_titles`: titles of enclosing sections
- `metadata.section_path`: joined titles (e.g., "Title > Subsection")
- `metadata.paragraph_kind`: block classifier (paragraph, list_unordered, header_line, table_md, ...)
- `metadata.start_offset` / `metadata.end_offset`: exact offsets in the original text

If you need a nested structure (tree) or a flattened list using the current v2 Chunker, use:

```python
from tldw_Server_API.app.core.Chunking.chunker import Chunker

ck = Chunker()

# Build a hierarchical tree (sections/blocks with offsets)
tree = ck.chunk_text_hierarchical_tree(my_text, method='sentences')

# Or directly produce a flattened list of chunks with offsets and ancestry metadata
flat_chunks = ck.chunk_text_hierarchical_flat(
    my_text,
    method='sentences',
)
```

## Streaming (NDJSON)

Stream the generated answer with incremental claim overlay events:

```
POST /api/v1/rag/search/stream
{
  "query": "What is CRISPR?",
  "enable_generation": true,
  "enable_claims": true,
  "claims_concurrency": 8
}
```

Events:
- `{ "type": "delta", "text": "..." }`
- `{ "type": "claims_overlay", ... }`
- `{ "type": "final_claims", ... }`

Notes:
- Control verification fan-out during streaming overlays with `claims_concurrency` (default 8, range 1–32).

## RAG Evaluation (claim_faithfulness)

The unified evaluations API can compute claim-level faithfulness by verifying extracted claims against your provided contexts.

- Metric name: `claim_faithfulness` (0–1). Internally uses APS-style extraction + hybrid verification (NLI if available, else LLM judge).

Example request:

```bash
curl -X POST "http://localhost:8000/api/v1/evaluations/rag" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-api-key" \
  -d '{
    "query": "What is CRISPR?",
    "retrieved_contexts": ["...context chunk 1...", "...context chunk 2..."],
    "generated_response": "...your model response...",
    "metrics": ["relevance", "faithfulness", "answer_similarity", "context_precision", "claim_faithfulness"]
  }'
```

Response includes `metrics.claim_faithfulness.score` along with the other metrics. To reduce cost, include this metric only when you need claim-level grounding.

## NLI Model Configuration

The verifier prefers a local MNLI model and falls back to an LLM judge if unavailable.

- Set environment variable `RAG_NLI_MODEL` or `RAG_NLI_MODEL_PATH` to a local model id or path (e.g., `roberta-large-mnli` or `/models/mnli`).
- Or pass `nli_model` to `unified_rag_pipeline` for per-request override.
```

## Production Guards

When running with `tldw_production=true`, the RAG retrievers disable all raw SQL fallbacks and require database adapters.

- Endpoints already pass adapters (MediaDatabase, ChaChaNotesDB) to the unified pipeline.
- If calling the pipeline directly in your own code, provide adapters explicitly:

```python
from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline

result = await unified_rag_pipeline(
    query="...",
    media_db_path="Databases/Media_DB_v2.db",
    character_db_path="Databases/user_databases/<uid>/ChaChaNotes.db",
    media_db=media_db_instance,       # required in production
    chacha_db=chacha_db_instance,     # required in production
)
```

If no adapter is supplied in production, retrievers raise `RuntimeError` instead of using raw sqlite.

## LLM Reranker Safety Defaults

LLM-based reranking (strategy `llm_scoring`) is powerful but expensive. Safety limits are enabled by default:

- Per-call timeout: `RAG_LLM_RERANK_TIMEOUT_SEC` (default `10`)
- Total time budget per query: `RAG_LLM_RERANK_TOTAL_BUDGET_SEC` (default `20`)
- Max documents to score: `RAG_LLM_RERANK_MAX_DOCS` (default `20`)

The reranker also respects the configured `top_k` and stops early if the total budget is reached. These controls prevent runaway costs and long-tail latencies in production.

## Comprehensive Unified RAG cURL Example

Use the unified RAG endpoint with all major options visible. Remove options you don’t need; unspecified fields use sensible defaults.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/rag/search" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -d '{
    "query": "Comprehensive unified RAG example",
    "sources": ["media_db", "notes", "characters", "chats"],
    "search_mode": "hybrid",
    "hybrid_alpha": 0.7,
    "top_k": 10,
    "min_score": 0.0,

    "expand_query": true,
    "expansion_strategies": ["acronym", "synonym", "domain", "entity", "semantic"],
    "spell_check": true,

    "enable_cache": true,
    "cache_threshold": 0.85,
    "adaptive_cache": true,

    "keyword_filter": ["neural", "training"],

    "enable_security_filter": true,
    "detect_pii": true,
    "redact_pii": true,
    "sensitivity_level": "internal",
    "content_filter": true,

    "enable_table_processing": true,
    "table_method": "markdown",

    "chunk_type_filter": ["text", "code", "table", "list"],
    "enable_parent_expansion": true,
    "parent_context_size": 800,
    "include_sibling_chunks": true,
    "sibling_window": 2,
    "include_parent_document": false,
    "parent_max_tokens": 1200,

    "enable_claims": true,
    "claim_extractor": "aps",
    "claim_verifier": "hybrid",
    "claims_top_k": 5,
    "claims_conf_threshold": 0.7,
    "claims_max": 25,
    "nli_model": "roberta-large-mnli",

    "enable_reranking": true,
    "reranking_strategy": "hybrid",
    "rerank_top_k": 20,

    "enable_citations": true,
    "citation_style": "apa",
    "include_page_numbers": true,
    "enable_chunk_citations": true,

    "enable_generation": true,
    "generation_model": "gpt-4o",
    "generation_prompt": "You are a helpful assistant. Provide a concise, grounded answer.",
    "max_generation_tokens": 500,

    "collect_feedback": true,
    "feedback_user_id": "user123",
    "apply_feedback_boost": true,

    "enable_monitoring": true,
    "enable_analytics": true,
    "use_connection_pool": true,
    "use_embedding_cache": true,
    "enable_observability": false,
    "trace_id": "trace-abc-123",

    "enable_performance_analysis": false,
    "timeout_seconds": 10.0,

    "highlight_results": true,
    "highlight_query_terms": true,
    "track_cost": false,
    "debug_mode": false,

    "enable_batch": false,
    "batch_queries": ["extra question 1", "extra question 2"],
    "batch_concurrent": 3,

    "enable_resilience": true,
    "retry_attempts": 3,
    "circuit_breaker": true,

    "user_id": "user123",
    "session_id": "session-456"
  }'
```

See also:
- RAG API docs: `tldw_Server_API/app/core/RAG/API_DOCUMENTATION.md`
- Examples: `tldw_Server_API/app/core/RAG/UNIFIED_PIPELINE_EXAMPLES.md`

## Anthropic Contextual RAG (example config)

To enable Contextual RAG using Anthropic for generating per‑chunk context headers and optional document outlines, set these in `tldw_Server_API/Config_Files/config.txt`:

```ini
# Use Anthropic as the default provider so contextualization routes correctly
default_api = anthropic

[Embeddings]
enable_contextual_chunking = true
contextual_llm_provider = anthropic
contextual_llm_model = claude-3-7-sonnet-20250219
contextual_llm_temperature = 0.1
context_strategy = outline_window   # options: auto | full | window | outline_window
context_window_size = 1200          # integer; or set to None to always use full document
context_token_budget = 6000         # used when strategy=auto

[API]
# Ensure your Anthropic API is configured; also set ANTHROPIC_API_KEY in your .env
anthropic_model = claude-3-7-sonnet-20250219
anthropic_temperature = 0.1
```

Notes:
- Customize the prompts for contextualization and outline under `tldw_Server_API/Config_Files/Prompts/embeddings.prompts.yaml|.md` using keys `situate_context_prompt` and `document_outline_prompt`.
- You can override the contextual LLM model per call using `llm_model_for_context` in `process_and_store_content`.

## Directory Structure

```
RAG/
├── README.md                    # This file
├── IMPLEMENTATION_STATUS.md     # Actual feature availability
├── DEPRECATION_NOTICE.md       # Migration information
├── __init__.py                 # Module exports
├── exceptions.py               # Custom exceptions
├── (uses unified audit service) # Audit logging via DI
├── rag_custom_metrics.py      # Metrics collection
├── rag_service/               # Core implementation
│   ├── unified_pipeline.py    # Unified pipeline entry point
│   ├── database_retrievers.py # Database retrieval
│   ├── query_expansion.py     # Query enhancement
│   ├── semantic_cache.py      # Caching layer
│   ├── advanced_cache.py      # Advanced caching strategies
│   ├── advanced_reranking.py  # Document reranking
│   ├── resilience.py          # Fault tolerance
│   ├── performance_monitor.py # Performance tracking
│   ├── metrics_collector.py   # Comprehensive metrics
│   ├── security_filters.py   # PII detection & content filtering
│   ├── batch_processing.py   # Batch query handling
│   ├── feedback_system.py    # User feedback collection
│   ├── citations.py          # Citation generation
│   ├── parent_retrieval.py   # Parent document retrieval
│   ├── generation.py         # Answer generation
│   ├── health_check.py      # Health monitoring
│   ├── config.py              # Configuration
│   ├── types.py               # Type definitions
│   └── ... (additional modules)
├── ARCHIVE/                    # Deprecated implementations
└── DEPRECATION_NOTICE.md      # Migration notes
```

## Unified Pipeline Architecture

### Single Function, All Features

Instead of pre-built pipelines, the unified architecture provides direct parameter control:

```python
    # All features accessible via parameters
    result = await unified_rag_pipeline(
        query="your query here",
    
    # Data sources
    sources=["media_db", "notes", "characters", "chats"],
    
    # Search configuration
    search_mode="hybrid",  # fts, vector, hybrid
    top_k=10,
    
    # Query expansion
    expand_query=True,
    expansion_strategies=["acronym", "synonym", "domain", "entity"],
    
    # Caching
    enable_cache=True,
    cache_threshold=0.85,
    
    # Reranking
    enable_reranking=True,
    reranking_strategy="hybrid",  # flashrank, cross_encoder, hybrid
    
    # Citations
    enable_citations=True,
    citation_style="apa",  # mla, apa, chicago, harvard, ieee
    enable_chunk_citations=True,
    
    # Generation
    enable_generation=True,
    generation_model="gpt-4o",
    
    # Security
    enable_security_filter=True,
    detect_pii=True,
    content_filter=True,
    
    # Monitoring
    enable_monitoring=True,
    
    # Feedback
    collect_feedback=True
    )
```

### Feature Combinations

Mix and match any features without restrictions:

```python
# Minimal setup (fast)
result = await unified_rag_pipeline(
    query="What is AI?",
    sources=["media_db"],
    search_mode="fts",
    top_k=5
)

# Maximum quality (thorough)
result = await unified_rag_pipeline(
    query="Explain neural networks",
    sources=["media_db", "notes"],
    search_mode="hybrid",
    expand_query=True,
    expansion_strategies=["acronym", "synonym", "domain", "entity"],
    enable_cache=True,
    enable_reranking=True,
    reranking_strategy="hybrid",
    enable_citations=True,
    citation_style="apa",
    enable_chunk_citations=True,
    enable_generation=True,
    enable_security_filter=True,
    top_k=20
)

# Batch processing
results = await unified_batch_pipeline(
    queries=["What is ML?", "Explain AI?", "Define neural networks?"],
    sources=["media_db"],
    max_concurrent=3,
    enable_citations=True
)
```

## Parameter Reference (selected)

### Core Parameters
- `query: str` - The search query (required)
- `sources: List[str]` - Databases to search (["media_db", "notes", "characters", "chats"])
- `search_mode: str` - Search type ("fts", "vector", "hybrid")
- `top_k: int` - Maximum results to return (default: 10)

### Query Enhancement
- `expand_query: bool` - Enable query expansion
- `expansion_strategies: List[str]` - Strategies (["acronym", "synonym", "domain", "entity"])
- `spell_check: bool` - Correct query spelling

### Caching
- `enable_cache: bool` - Enable semantic caching
- `cache_threshold: float` - Similarity threshold (0.0-1.0)

### Document Processing
- `enable_reranking: bool` - Enable document reranking
- `reranking_strategy: str` - Strategy ("flashrank", "cross_encoder", "hybrid")
- `enable_table_processing: bool` - Process table content
- `enable_parent_expansion: bool` - Include parent document context

#### VLM Late Chunking (Optional)

VLM (Vision-Language) late chunking augments retrieved results with compact, VLM-derived hints from PDFs at retrieval time. This is separate from OCR and can be turned on per request.

- `enable_vlm_late_chunking: bool` — enable/disable
- `vlm_backend: str | null` — `docling` for PDF-structural detection, or `hf_table_transformer` for per-page table detection
- `vlm_detect_tables_only: bool` — if true, only keep `table` detections; otherwise include images/figures as `vlm`
- `vlm_max_pages: int | null` — analyze up to this many pages per PDF
- `vlm_late_chunk_top_k_docs: int` — apply to top-k retrieved media_db documents (default: 3)

The created hints are appended as additional documents with `metadata.chunk_type` set to `table` (for tables) or `vlm` (for other labels). Combine with `chunk_type_filter` to include/exclude these:

```json
{
  "enable_vlm_late_chunking": true,
  "vlm_backend": "docling",
  "vlm_detect_tables_only": false,
  "chunk_type_filter": ["text", "table", "vlm"]
}
```

Backends are shared with ingestion; list available backends via `GET /api/v1/vlm/backends`.

### Citations
- `enable_citations: bool` - Generate citations
- `citation_style: str` - Format ("apa", "mla", "chicago", "harvard", "ieee")
- `enable_chunk_citations: bool` - Include chunk citations for verification

### Answer Generation
- `enable_generation: bool` - Generate LLM response
- `generation_model: str` - Model name (e.g., "gpt-4o")
- `generation_prompt: str` - Custom generation prompt

### Security & Privacy
- `enable_security_filter: bool` - Enable security/PII filter
- `detect_pii: bool` - Detect personally identifiable information
- `redact_pii: bool` - Redact detected PII
- `sensitivity_level: str` - Max sensitivity ("public", "internal", "confidential", "restricted")
- `content_filter: bool` - Enable content filtering

### Analytics & Feedback
- `enable_analytics: bool` - Record analytics (privacy-preserving)
- `enable_feedback_collection: bool` - Enable user feedback
- `user_id: str` - User identifier for feedback

### Performance Monitoring
- `enable_monitoring: bool` - Collect timing metrics
- `enable_debug_mode: bool` - Detailed debug information
- `enable_resilience: bool` - Circuit breakers and retries

## Dual Citation System

The RAG module provides two types of citations for different use cases:

### Academic Citations
Properly formatted citations for research and documentation:

```python
result = await unified_rag_pipeline(
    query="What is machine learning?",
    enable_citations=True,
    citation_style="apa"  # mla, apa, chicago, harvard, ieee
)

# Example output:
print(result.citations[0])  # "Smith, J. (2024). Introduction to Machine Learning. Tech Publications."
```

Both formats are exposed in the unified response:
- `academic_citations`: list of formatted strings (APA/MLA/Chicago/Harvard/IEEE)
- `chunk_citations`: per‑chunk evidence objects for verification
- `citations`: combined convenience list containing both types

### Combined Usage
Both citation types can be enabled simultaneously:

```python
result = await unified_rag_pipeline(
    query="Research question",
    enable_citations=True,
    citation_style="mla",
    enable_chunk_citations=True
)

# Academic citations for bibliography
academic_refs = result.citations

# Chunk citations for answer verification
verification_data = result.chunk_citations
```

## API Endpoints

The RAG module exposes a comprehensive unified API:

### Primary Endpoints
- `POST /api/v1/rag/search` - Unified pipeline with all features accessible
- `POST /api/v1/rag/search/stream` - Stream generated answer with optional claim overlay (NDJSON)
- `POST /api/v1/rag/batch` - Batch processing for multiple queries
- `GET /api/v1/rag/simple` - Simplified interface for basic use cases
- `GET /api/v1/rag/advanced` - Pre-configured advanced search
- `GET /api/v1/rag/features` - List all available features and parameters
- `GET /api/v1/rag/capabilities` - Feature defaults, supported options, and limits
- `GET /api/v1/rag/health` - Health check with detailed component status

### Example API Usage (unified search with all options)

```bash
# Required: query; choose sources and search_mode
# Optional groups:
# - Query Enhancement, Caching, Security, Table Processing
# - Context (parent/sibling), Claims/APS, Reranking, Citations, Generation
# - Feedback/Analytics/Monitoring, Observability/Performance, Quick Wins
# - Batch flags, Resilience, User Context
curl -X POST "http://localhost:8000/api/v1/rag/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Comprehensive unified RAG example",
    "sources": ["media_db", "notes", "characters", "chats"],
    "search_mode": "hybrid",
    "hybrid_alpha": 0.7,
    "top_k": 10,
    "min_score": 0.0,

    "expand_query": true,
    "expansion_strategies": ["acronym", "synonym", "domain", "entity", "semantic"],
    "spell_check": true,

    "enable_cache": true,
    "cache_threshold": 0.85,
    "adaptive_cache": true,

    "keyword_filter": ["neural", "training"],

    "enable_security_filter": true,
    "detect_pii": true,
    "redact_pii": true,
    "sensitivity_level": "internal",
    "content_filter": true,

    "enable_table_processing": true,
    "table_method": "markdown",

    "chunk_type_filter": ["text", "code", "table", "list"],
    "enable_parent_expansion": true,
    "parent_context_size": 800,
    "include_sibling_chunks": true,
    "sibling_window": 2,
    "include_parent_document": false,
    "parent_max_tokens": 1200,

    "enable_claims": true,
    "claim_extractor": "aps",
    "claim_verifier": "hybrid",
    "claims_top_k": 5,
    "claims_conf_threshold": 0.7,
    "claims_max": 25,
    "nli_model": "roberta-large-mnli",

    "enable_reranking": true,
    "reranking_strategy": "hybrid",
    "rerank_top_k": 20,

    "enable_citations": true,
    "citation_style": "apa",
    "include_page_numbers": true,
    "enable_chunk_citations": true,

    "enable_generation": true,
    "generation_model": "gpt-4o",
    "generation_prompt": "You are a helpful assistant. Provide a concise, grounded answer.",
    "max_generation_tokens": 500,

    "collect_feedback": true,
    "feedback_user_id": "user123",
    "apply_feedback_boost": true,

    "enable_monitoring": true,
    "enable_analytics": true,
    "use_connection_pool": true,
    "use_embedding_cache": true,
    "enable_observability": false,
    "trace_id": "trace-abc-123",

    "enable_performance_analysis": false,
    "timeout_seconds": 10.0,

    "highlight_results": true,
    "highlight_query_terms": true,
    "track_cost": false,
    "debug_mode": false,

    "enable_batch": false,
    "batch_queries": ["extra question 1", "extra question 2"],
    "batch_concurrent": 3,

    "enable_resilience": true,
    "retry_attempts": 3,
    "circuit_breaker": true,

    "user_id": "user123",
    "session_id": "session-456"
  }'
```
Remove optional blocks you don’t need; unspecified fields use sensible defaults.

## Testing

```bash
# Run unified RAG tests
python -m pytest tldw_Server_API/tests/RAG_NEW/ -v

# Run with coverage (module paths)
python -m pytest tldw_Server_API/tests/RAG_NEW/ \
  --cov=tldw_Server_API.app.core.RAG \
  --cov-report=html
```

## Advanced Features

## Security & Privacy Features

The RAG module includes comprehensive security features that are fully integrated:

### PII Detection
Automatically detect and handle personally identifiable information:

```python
result = await unified_rag_pipeline(
    query="Show me user emails",
    detect_pii=True,
    sources=["media_db"]
)

# Check security report
if result.security_report:
    pii_detected = result.security_report.get('pii_detected', [])
    if pii_detected:
        print(f"Detected PII types: {pii_detected}")
```

### Content Filtering
Filter content based on sensitivity levels:

```python
result = await unified_rag_pipeline(
    query="Research sensitive topics",
    content_filter=True,
    sensitivity_level="internal",
    sources=["media_db"]
)
```

### Privacy-Preserving Analytics
The Analytics.db system ensures user privacy:
- Query content is SHA256 hashed (16-char prefix)
- No raw query text stored
- User IDs are hashed
- Aggregate metrics only

```python
result = await unified_rag_pipeline(
    query="Private query",
    enable_analytics=True,  # Records performance metrics only
    user_id="user123"  # Stored as hash
)
```

## Batch Processing

Process multiple queries concurrently with full feature support:

### Basic Batch Processing
```python
results = await unified_batch_pipeline(
    queries=["What is AI?", "Explain ML?", "Define neural networks?"],
    sources=["media_db", "notes"],
    max_concurrent=3  # Process 3 queries simultaneously
)

# Access individual results
for i, result in enumerate(results):
    print(f"Query {i+1}: {result.documents[0].content[:100]}...")
```

### Advanced Batch Processing
```python
results = await unified_batch_pipeline(
    queries=["Complex query 1", "Complex query 2"],
    sources=["media_db"],
    max_concurrent=2,
    # All unified pipeline features available
    enable_citations=True,
    citation_style="apa",
    enable_generation=True,
    enable_analytics=True,
    search_mode="hybrid",
    top_k=15
)
```

### Resource Management
- Automatic concurrency limiting
- Memory usage monitoring
- Graceful failure handling
- Progress tracking
- Partial result recovery

## Analytics & Feedback System

Integrated dual-database feedback system for both server QA and user experience:

### Automatic Analytics Collection
```python
result = await unified_rag_pipeline(
    query="Research question",
    enable_analytics=True,  # Records to Analytics.db
    enable_feedback_collection=True
)

# Feedback ID for user rating
feedback_id = result.feedback_id
print(f"Rate this result: /feedback/{feedback_id}")
```

### Analytics Database (Server-Side QA)
- Privacy-preserving with SHA256 hashing
- Performance metrics and timing data
- Search pattern analysis
- Error tracking and debugging
- No PII or sensitive data stored

### User Feedback (ChaChaNotes_DB)
- User ratings and comments
- Relevance scoring
- Feature usage feedback
- Personalized recommendations
- Full user context preserved

## Performance Optimizations

The unified pipeline includes several performance enhancements:

### Connection Pooling
Connection pooling is handled internally by the service; no explicit flag is required.

### Embedding Cache
LRU cache for embeddings with 90%+ hit rates:

```python
result = await unified_rag_pipeline(
    query="Repeated query",
    use_embedding_cache=True,
    search_mode="vector"
)
```

### Module-Level Imports
Pre-loaded modules reduce cold start time by 500ms:
- All modules imported at startup
- Graceful fallbacks for missing dependencies
- Lazy loading for optional features

### Performance Monitoring
```python
result = await unified_rag_pipeline(
    query="Monitor this query",
    enable_monitoring=True
)

# Access detailed timings
print(result.timings)
# {
#   "total_time": 0.245,
#   "retrieval_time": 0.120,
#   "reranking_time": 0.085,
#   "citation_time": 0.040
# }
```

## Performance Benchmarks

Typical unified pipeline execution times (on standard hardware):

### Single Query Performance
- **Basic search** (FTS only): ~30-50ms
- **Hybrid search** (FTS + vector): ~80-150ms
- **With caching** (cache hit): ~10-25ms
- **Full features** (expansion + reranking + citations): ~200-400ms
- **With answer generation**: ~2000-5000ms (depends on LLM)

### Batch Processing Performance
- **3 concurrent queries**: ~100-200ms total (vs 300-600ms sequential)
- **10 concurrent queries**: ~400-800ms total
- **Memory overhead**: <100MB per concurrent query

### Cache Performance
- **Embedding cache hit rate**: 85-95% for repeated queries
- **Semantic cache hit rate**: 60-80% for similar queries
- **Connection pool efficiency**: 70% reduction in connection overhead

### Optimization Impact
- **Module-level imports**: 500ms faster cold starts
- **Connection pooling**: 30-70% faster database operations
- **LRU embedding cache**: 90%+ faster vector similarity when cached

## Migration Guide

### From Functional Pipeline (v3.0) to Unified Pipeline (v4.0)

```python
# Unified pipeline way
from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline
result = await unified_rag_pipeline(
    query="same query",
    enable_cache=True,
    top_k=10
)
```

### From Object-Oriented (v2.0) to Unified Pipeline

```python
# Old object-oriented way (deprecated)
from app.core.RAG.rag_service.integration import RAGService
service = RAGService(config)
result = await service.search(query)

# New unified way
result = await unified_rag_pipeline(
    query=query,
    sources=["media_db"],
    enable_cache=True
)
```

### Configuration Mapping

| Old Config | New Parameter | Example |
|------------|---------------|----------|
| `config["enable_cache"]` | `enable_cache` | `enable_cache=True` |
| `config["sources"]` | `sources` | `sources=["media_db"]` |
| `config["top_k"]` | `top_k` | `top_k=10` |
| `config["expansion_strategies"]` | `expansion_strategies` | `expansion_strategies=["acronym"]` |
| Pipeline presets | Direct parameters | All features as parameters |

## Contributing

When extending the RAG module:

1. Extend unified behavior under `rag_service/` modules (e.g., retrieval, reranking)
2. Prefer adding explicit parameters in unified_rag_pipeline rather than hidden config
3. Keep features optional and guarded (graceful fallbacks)
4. Write tests under `tldw_Server_API/tests/RAG_NEW/`
5. Update this README

## Related Documentation

- [Implementation Status](IMPLEMENTATION_STATUS.md) - Current feature availability
- [API Documentation](API_DOCUMENTATION.md) - Comprehensive parameter reference
- [RAG Service Implementation](rag_service/README.md) - Internal architecture
- [Deprecation Notice](DEPRECATION_NOTICE.md) - Deprecated features and timelines

## License

Same as tldw_server (GPLv2)
## Reranking Backends (Details)

You can rerank retrieved documents using either Transformers cross-encoders or llama.cpp GGUF embedding models.

- Strategies (pipeline param `reranking_strategy`)
  - `flashrank`: Fast heuristic neural reranker
  - `cross_encoder`: Transformers (sentence-transformers CrossEncoder or raw Transformers)
  - `llama_cpp`: Embedding-based cosine using `llama-embedding`
  - `hybrid`: Combine multiple strategies

- Transformers Cross-Encoder
  - Use HF models like `BAAI/bge-reranker-v2-m3` or Jina rerankers
  - Set per-request via `reranking_model` or globally via `RAG_TRANSFORMERS_RERANKER_MODEL`
  - GPU recommended for performance; falls back gracefully

- llama.cpp (GGUF)
  - Use local GGUF embedding models (Qwen3, BGE, Jina)
  - Auto-formatting: if model name contains `bge`, the reranker prefixes the query/documents with `query: ` / `passage: `
  - Pooling defaults by family: BGE/Jina → `mean`; Qwen → `last` (overrideable)
  - Global defaults via `[RAG]` in `Config_Files/config.txt` (`llama_reranker_*` keys)

- Public HTTP reranking
  - `POST /v1/reranking` accepts `{ backend, model, query, documents, top_n }`
  - `backend: auto|llamacpp|transformers`. Auto rules: `.gguf`→llama.cpp; `model` containing `/`→transformers.

### Config Keys Snapshot

- Transformers: `transformers_reranker_model` (config) / `RAG_TRANSFORMERS_RERANKER_MODEL` (env)
- llama.cpp: `llama_reranker_model`, `llama_reranker_binary`, `llama_reranker_ngl`, `llama_reranker_separator`, `llama_reranker_output`, `llama_reranker_pooling`, `llama_reranker_normalize`, `llama_reranker_max_doc_chars`, `llama_reranker_template_mode`, `llama_reranker_query_prefix`, `llama_reranker_doc_prefix`

### Examples

Transformers (BGE):
```python
res = await unified_rag_pipeline(
    query="What is panda?",
    enable_reranking=True,
    reranking_strategy="cross_encoder",
    reranking_model="BAAI/bge-reranker-v2-m3",
)
```

llama.cpp (Qwen3 GGUF):
```python
res = await unified_rag_pipeline(
    query="What is panda?",
    enable_reranking=True,
    reranking_strategy="llama_cpp",
    reranking_model="/models/Qwen3-Embedding-0.6B_f16.gguf",
)
```
