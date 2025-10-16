# Agentic Chunking – Design Note (v0)

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
