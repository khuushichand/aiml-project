# Agentic Chunking - Design Note (v0)

Goal: add a query-time, agentic evidence assembly path that avoids fixed pre-chunks. The agent first performs coarse retrieval (hybrid FTS5 + vector) to select top-K candidate documents, then assembles an ephemeral, query-specific chunk composed of quoted spans with provenance.

Why: fixed chunking can miss cross-boundary context and degrade faithfulness. Agentic chunking lets the system “skim then zoom” into relevant spans, improving precision while preserving provenance.

Scope (v0): deterministic, test-friendly baseline. No external tool-LLM loop; instead uses keyword-guided span extraction around hits and builds a synthetic chunk with offsets. Optional answer generation uses the existing `AnswerGenerator`.

API: POST `/api/v1/rag/search` with `strategy=agentic` plus optional knobs:
- `agentic_top_k_docs` (default 3)
- `agentic_window_chars` (default 1200)
- `agentic_max_tokens_read` (default 6000)
- `agentic_extractive_only` (default true)
- `agentic_quote_spans` (default true)

Implementation:
- Orchestrator: `tldw_Server_API/app/core/RAG/rag_service/agentic_chunker.py`
- Schema: fields added to `UnifiedRAGRequest`
- Endpoint: `rag_unified.py` branches to agentic pipeline when `strategy=agentic`

Future Work:
- Replace heuristic span selection with LLM-guided tool use (ReAct-style): search_within, open_section, expand_window, quote_spans.
- Budgeted read loops with early stopping based on coverage/confidence.
- Per-sentence hard citations and strict extractive guardrails.
- Caching of ephemeral chunks keyed by (query, doc_ids, versions).

Evaluation: compare correctness, faithfulness, latency, and cost against baseline RAG; add ablations (+rerank, +agentic, +agentic+strict).

## Ablation Endpoint

To make comparisons easy, a lightweight ablation helper is available.

- Route: `POST /api/v1/rag/ablate`
- Input (AblationRequest):
  - `query` (str), `top_k` (int), `search_mode` (fts|vector|hybrid), `with_answer` (bool), `reranking_strategy` (flashrank|cross_encoder|hybrid|llama_cpp|none)
- Behavior: runs four configurations and returns both a compact summary and full responses
  1. `baseline` (reranking off)
  2. `+rerank` (reranking on; strategy configurable)
  3. `agentic` (agentic pipeline; default budgets)
  4. `agentic_strict` (agentic with tighter budgets + tool loop enabled)
- Output shape:
  - `summary`: [{ label, total_time, cache_hit, doc_count, first_doc_id }]
  - `runs`: [{ label, result: UnifiedRAGResponse }]

Example request:

```
POST /api/v1/rag/ablate
{
  "query": "How do residual connections help?",
  "top_k": 8,
  "search_mode": "hybrid",
  "with_answer": false,
  "reranking_strategy": "none"
}
```

Notes:
- This endpoint is for experimentation and evaluation; it shares infrastructure with the unified pipeline and the agentic orchestrator.
- For reproducibility in CI, agentic tool-loop and LLM planner are disabled by default; the strict variant enables tools under a small budget.

## New Agentic Knobs (v0.2)

- Query decomposition:
  - `agentic_enable_query_decomposition` (bool, default false)
  - `agentic_subgoal_max` (int, default 3)
  - Effect: splits multi-hop queries into sub-goals and assembles spans per sub-goal.

- Intra-doc semantic search:
  - `agentic_enable_semantic_within` (bool, default true)
  - `agentic_use_provider_embeddings_within` (bool, default false)
  - `agentic_provider_embedding_model_id` (optional)
  - Effect: embeds paragraphs with hashed vectors (default) or configured provider; caches per document version.

- Structural anchors (headings/TOC):
  - `agentic_enable_section_index` (bool, default true)
  - `agentic_prefer_structural_anchors` (bool, default true)
  - Effect: precompute heading→offset map; `open_section` prefers anchors; provenance includes `section_title`.

- Tables/figures (heuristic):
  - `agentic_enable_table_support` (bool, default true)
  - Effect: for table-like queries, prioritize table-like paragraphs (pipes/tabs/numbers). Integrates with VLM late chunking when enabled.

- VLM late chunking (agentic path):
  - `agentic_enable_vlm_late_chunking` (bool, default false)
  - `agentic_vlm_backend` (optional, e.g., `hf_table_transformer`, `docling`)
  - `agentic_vlm_detect_tables_only` (bool, default true)
  - `agentic_vlm_max_pages` (optional int)
  - `agentic_vlm_late_chunk_top_k_docs` (int, default 2)
  - Effect: for top-k PDFs with local file paths, run table/figure detection and add VLM hints as extra spans.

- Adaptive budgets & metrics:
  - `agentic_adaptive_budgets` (bool, default true)
  - `agentic_coverage_target` (float, default 0.8)
  - `agentic_min_corroborating_docs` (int, default 2)
  - `agentic_max_redundancy` (float, default 0.9)
  - `agentic_enable_metrics` (bool, default true)
  - Effect: dynamically stops the tool loop when term coverage and cross-doc corroboration are sufficient; emits metrics for tool calls, durations, span lengths, and bytes read.

- Verification on agentic generation:
  - `require_hard_citations` (bool, default false)
  - `enable_numeric_fidelity` (bool, default false)
  - `numeric_fidelity_behavior` ("continue"|"ask"|"decline"|"retry", default "continue")
  - `enable_claims` (bool, default false), `claim_verifier` ("nli"|"llm"|"hybrid"), `claims_top_k`, `claims_conf_threshold`, `claims_max`, `nli_model`, `claims_concurrency`
  - Effect: verifies each sentence/claim and numeric values against assembled spans; attaches `hard_citations` and `numeric_fidelity` metadata.

## Multi-Hop Example

POST /api/v1/rag/search
{
  "query": "Explain residual connections and dropout",
  "strategy": "agentic",
  "enable_generation": false,
  "agentic_enable_tools": true,
  "agentic_enable_query_decomposition": true,
  "agentic_enable_semantic_within": true,
  "agentic_enable_section_index": true,
  "agentic_enable_table_support": true
}

When PDFs are present and tables matter (optional VLM integration):

{
  "query": "Compare accuracy tables for ResNet vs EfficientNet",
  "strategy": "agentic",
  "enable_generation": false,
  "agentic_enable_tools": true,
  "agentic_enable_vlm_late_chunking": true,
  "agentic_vlm_backend": "hf_table_transformer",
  "agentic_vlm_detect_tables_only": true,
  "agentic_vlm_late_chunk_top_k_docs": 2
}
