# Media → Embeddings → RAG → Evals: End-to-End Workflow

This practical guide walks you through a complete post-ingestion loop:

1) Ingest media into the Media DB
2) Generate per-user embeddings collections
3) Run RAG searches with useful toggles (hybrid, rerankers, agentic)
4) Wrap searches in an evaluation that grid-searches settings to find the best configuration for your dataset

The examples use the single-user API key header. For multi-user JWTs, replace `X-API-KEY` with `Authorization: Bearer <token>`.

## Prerequisites

- Server running: `uvicorn tldw_Server_API.app.main:app --reload`
- Auth: single-user API key printed at startup, or JWT login for multi-user
- FFmpeg installed (for A/V), and provider API keys in `.env`/`Config_Files/config.txt` if needed

## 1) Ingest Media into the Database

Use `POST /api/v1/media/add` to persist content and (optionally) chunk and analyze.

curl example (PDF upload):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/media/add \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -F "media_type=pdf" \
  -F "title=Attention Is All You Need" \
  -F "perform_chunking=true" \
  -F "hierarchical_chunking=true" \
  -F "files=@/path/to/paper.pdf"
```

Notes and tips:
- `media_type`: `audio|video|pdf|document|ebook|email|code`
- New: `json` - treat JSON files as plaintext content while preserving a distinct media type. Useful for storing config snippets alongside corpus items and tagging them via `keywords` for collection-level runs (e.g., `keywords: projectX, eval-config`).
- Hierarchical chunking: set `hierarchical_chunking=true` to prefer structure-aware splitting for long docs.
- You may also ingest by URL(s) via `urls=[...]` form fields.
- The response includes DB identifiers; you’ll need the `media_id` for embeddings.

## 2) Generate Embeddings (Per-User Collections)

Generate vector embeddings for a media record. The API writes to a per-user collection, e.g., `user_1_media_embeddings`.

Endpoint: `POST /api/v1/media/{media_id}/embeddings`

curl example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/media/123/embeddings \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "embedding_provider": "huggingface",
        "embedding_model": "Qwen/Qwen3-Embedding-4B-GGUF",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "force_regenerate": false
      }'
```

Batch mode:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/media/embeddings/batch \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "media_ids": [123,124,125],
        "provider": "huggingface",
        "model": "Qwen/Qwen3-Embedding-4B-GGUF",
        "chunk_size": 1000,
        "chunk_overlap": 200
      }'
```

## 3) RAG Search with Useful Toggles

Base endpoint: `POST /api/v1/rag/search`

Common toggles (subset of `UnifiedRAGRequest`):
- Retrieval: `search_mode` (`fts|vector|hybrid`), `hybrid_alpha`, `top_k`, `min_score`, `fts_level` (`media|chunk`)
- Reranking: `enable_reranking`, `reranking_strategy` (`flashrank|cross_encoder|hybrid|llama_cpp|llm_scoring|two_tier|none`), `rerank_top_k`
- Contextual expansion: `include_parent_expansion`, `include_sibling_chunks`, `parent_context_size`
- Agentic mode: set `strategy = "agentic"` and tune `agentic_*` parameters
- Answer generation: `enable_generation`, `generation_model`, `max_generation_tokens`, `require_hard_citations`

curl examples:

Hybrid + rerank (fast):
```bash
curl -X POST http://127.0.0.1:8000/api/v1/rag/search \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "query": "Key contributions of the Transformer paper",
        "sources": ["media_db"],
        "search_mode": "hybrid",
        "hybrid_alpha": 0.65,
        "top_k": 12,
        "enable_reranking": true,
        "reranking_strategy": "flashrank",
        "rerank_top_k": 10,
        "enable_generation": true,
        "max_generation_tokens": 300
      }'
```

Agentic retrieval (query-time synthetic chunking) with citations:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/rag/search \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "query": "Compare accuracy tables for ResNet vs EfficientNet",
        "strategy": "agentic",
        "search_mode": "hybrid",
        "top_k": 8,
        "agentic_enable_tools": true,
        "agentic_max_tool_calls": 6,
        "enable_generation": true,
        "require_hard_citations": true,
        "enable_chunk_citations": true
      }'
```

Tip: discover all supported features and defaults with `GET /api/v1/rag/capabilities`.

## 4) Wrap It in an Evaluation (Find Best Settings)

Two ways to evaluate:

- Simple scoring for a single example: `POST /api/v1/evaluations/rag`
- Grid/random search over RAG pipeline settings on a dataset: create a `model_graded` evaluation with `sub_type: rag_pipeline`, then run it.

### 4A. One-off RAG Scoring

```bash
curl -X POST http://127.0.0.1:8000/api/v1/evaluations/rag \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "query": "What are the benefits of exercise?",
        "retrieved_contexts": ["Exercise improves cardiovascular health..."],
        "generated_response": "Exercise provides numerous benefits including...",
        "ground_truth": "Expected answer for comparison",
        "metrics": ["relevance", "faithfulness", "answer_similarity"]
      }'
```

### 4B. Dataset + Grid Search via `rag_pipeline`

1) Create a dataset (`POST /api/v1/evaluations/datasets`):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/evaluations/datasets \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "getting_started_rag_ds",
        "description": "Small RAG QS dataset",
        "samples": [
          {"input": {"question": "What is the point of residual connections?"},
           "expected": {"answer": "They ease gradient flow and enable very deep networks."}},
          {"input": {"question": "List the datasets evaluated in the paper."},
           "expected": {"answer": "ImageNet, CIFAR-10/100, and others"}}
        ]
      }'
```

2) Create an evaluation (`POST /api/v1/evaluations/`) with `sub_type = rag_pipeline` and a sweep grid:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/evaluations/ \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "rag_cfg_search",
        "eval_type": "model_graded",
        "eval_spec": {
          "sub_type": "rag_pipeline",
          "rag_pipeline": {
            "dataset_id": "<DATASET_ID_FROM_STEP_1>",
            "search_strategy": "grid",
            "chunking": {
              "include_siblings": [false, true]
            },
            "retrievers": [
              {"search_mode": ["hybrid"], "hybrid_alpha": [0.5, 0.7], "top_k": [8, 12]}
            ],
            "rerankers": [
              {"strategy": ["flashrank", "cross_encoder"], "top_k": [10]}
            ],
            "rag": {
              "model": ["gpt-4o-mini"],
              "max_tokens": [300]
            },
            "aggregation_weights": {"rag_overall": 1.0, "retrieval_diversity": 0.1}
          }
        }
      }'
```

3) Start a run (`POST /api/v1/evaluations/{eval_id}/runs`):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/evaluations/<EVAL_ID>/runs \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"target_model": "openai"}'
```

4) Poll status / read results:

```bash
curl -s http://127.0.0.1:8000/api/v1/evaluations/runs/<RUN_ID> \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" | jq
```

The results include a leaderboard with aggregated metrics such as overall RAG score, retrieval coverage/diversity, MRR/nDCG if relevant IDs were provided, and latency. Use this to select the best config for your dataset.

5) Save the winning pipeline as a preset:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/evaluations/rag/pipeline/presets \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "baseline_hybrid_xenc",
        "config": {
          "chunking": {"include_siblings": true},
          "retriever": {"search_mode": "hybrid", "hybrid_alpha": 0.7, "top_k": 12},
          "reranker": {"strategy": "cross_encoder", "top_k": 10},
          "rag": {"model": "gpt-4o-mini", "max_tokens": 300}
        }
      }'
```

Optional: clean up expired ephemeral collections created during pipeline runs:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/evaluations/rag/pipeline/cleanup \
  -H "X-API-KEY: $SINGLE_USER_API_KEY"
```

## Practical Presets and Tips

- Speed first: vector-only (`search_mode=vector`) without reranking; add `flashrank` later.
- Quality first: hybrid with `hybrid_alpha≈0.6-0.75`, rerank to `rerank_top_k≈10-20`.
- Long PDFs: try `fts_level=chunk`, `include_parent_expansion=true`, `include_sibling_chunks=true`.
- Tables: set `enable_vlm_late_chunking=true` and consider agentic mode with VLM options.
- Agentic quick-win: `strategy=agentic`, `agentic_enable_tools=true`, `agentic_max_tool_calls=4-6`.
- Reproducibility: store chosen configs with Presets; include `index_namespace` in evals to isolate corpus.

## Python Snippet (RAG Search)

```python
import requests

API = "http://127.0.0.1:8000"
HEADERS = {"X-API-KEY": "<YOUR_API_KEY>", "Content-Type": "application/json"}

body = {
    "query": "What is the purpose of residual connections?",
    "search_mode": "hybrid",
    "hybrid_alpha": 0.65,
    "top_k": 12,
    "enable_reranking": True,
    "reranking_strategy": "flashrank",
    "enable_generation": True,
    "max_generation_tokens": 300
}

r = requests.post(f"{API}/api/v1/rag/search", headers=HEADERS, json=body, timeout=30)
r.raise_for_status()
print(r.json())
```

---

See also:
- RAG API Guide: `API-related/RAG-API-Guide.md`
- Evaluations API (Unified): `API-related/Evaluations_API_Unified_Reference.md`
- RAG Deployment/Production guides under User Guides
