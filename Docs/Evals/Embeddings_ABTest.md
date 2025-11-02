# Embeddings A/B Testing - Evaluations Module

## Overview
A/B testing of embeddings compares two or more embedding models on the same corpus and queries. The module builds per-arm vector collections, runs queries (vector-only or hybrid), computes retrieval metrics, collects latency statistics, and optionally performs reranking and significance testing.

## Key Capabilities
- Multiple arms: each defined by `provider`, `model`, optional `dimensions`.
- Corpus selection: list of media IDs from the user’s Media DB.
- Chunking: method, size, overlap, optional language.
- Retrieval:
  - Vector-only (recommended for “pure embeddings” comparisons)
  - Hybrid via unified RAG pipeline (consistent `hybrid_alpha` across arms)
  - Optional reranking layer in vector mode (FlashRank by default)
- Metrics: Recall@k, MRR, nDCG, Hit@k; latency p50/p95/mean.
- Significance: pairwise sign-test p-values over per-query metrics.
- Exports: JSON/CSV including detailed per-query diagnostics.
- Background jobs: runs asynchronously with SSE progress stream.

## Data Model
- `embedding_abtests` - test config, status, aggregate stats, notes
- `embedding_abtest_arms` - arm config, hashes, per-arm collection name, stats, metadata
- `embedding_abtest_queries` - query text, optional ground truth IDs
- `embedding_abtest_results` - per-query/per-arm ranked IDs, metrics, latency
  - Diagnostics fields: `ranked_distances`, `ranked_metadatas`, `ranked_documents`, `rerank_scores`

## API
- `POST /api/v1/evaluations/embeddings/abtest`
  - Body: `EmbeddingsABTestCreateRequest { name, config, run_immediately? }`
  - Returns: `{ test_id, status: 'created' }`
- `POST /api/v1/evaluations/embeddings/abtest/{test_id}/run` (admin-only by default)

Idempotency:
- Supply `Idempotency-Key` to `POST /embeddings/abtest` to avoid creating duplicate tests when retrying.
- `POST /embeddings/abtest/{test_id}/run` also accepts `Idempotency-Key`; repeated calls with the same key return the current running status without enqueuing an additional job.
  - Launches background job; returns `{ test_id, status: 'running' }`
- `GET /api/v1/evaluations/embeddings/abtest/{test_id}`
  - Returns status + summary with per-arm metrics, latency, and doc/chunk counts.
- `GET /api/v1/evaluations/embeddings/abtest/{test_id}/results?page=&page_size=`
  - Returns summary + paginated result rows.
- `GET /api/v1/evaluations/embeddings/abtest/{test_id}/significance?metric=ndcg`
  - Returns pairwise p-values across arms.
- `GET /api/v1/evaluations/embeddings/abtest/{test_id}/export?format=json|csv` (admin-only)
  - Returns full results (CSV includes `metrics_json`).
- `GET /api/v1/evaluations/embeddings/abtest/{test_id}/events` (SSE)
  - Streams JSON updates `{ type: 'status', status, stats: { progress: { phase } , aggregates? } }`.

## Config Schema (simplified)
```json
{
  "arms": [
    { "provider": "openai", "model": "text-embedding-3-small" },
    { "provider": "huggingface", "model": "sentence-transformers/all-MiniLM-L6-v2" }
  ],
  "media_ids": [101, 102, 103],
  "chunking": { "method": "words", "size": 1000, "overlap": 200, "language": "en" },
  "retrieval": {
    "k": 10,
    "search_mode": "vector",
    "hybrid_alpha": 0.7,
    "re_ranker": { "provider": "flashrank", "model": "default" },
    "apply_reranker": false
  },
  "queries": [ { "text": "what is the title?", "expected_ids": [101] } ],
  "metric_level": "media",
  "reuse_existing": true,
  "cleanup_policy": { "on_complete": false }
}
```

## Reranking
- Vector-only path can apply an optional reranker:
  - Strategy mapping (simple heuristics):
    - `flashrank` → FLASHRANK (default)
    - Cross-encoder cues (provider or model contains one of): `cross_encoder`, `cross-encoder`, `crossencoder`, `mono`, `monot5`, `t5`, `ms-marco`, `msmarco`, `bge-reranker`, `gte-reranker`, `reranker`, `re-rank`, `rerank`, `cohere`, `voyage`, `nv-rerank` → CROSS_ENCODER
    - LLM cues (provider or model contains): `llm`, `gpt`, `claude`, `sonnet`, `haiku`, `mistral`, `mixtral`, `gemini`, `qwen`, `command` → LLM_SCORING
    - `diversity` or `mmr` → DIVERSITY
    - `hybrid` or `multi` → HYBRID
  - The config’s `re_ranker.model` is passed into `RerankingConfig.model_name`.

## Recommendations
- For “pure embeddings” comparisons set `search_mode="vector"` for all arms.
- For hybrid comparisons, keep `hybrid_alpha` identical across arms and runs.
- L2-normalize vectors when comparing across providers; Chroma should use cosine distance.

## SSE Client Examples
- JS EventSource: see `Docs/Examples/ABTest_SSE_Client.md`.
- Python: `Helper_Scripts/Examples/abtest_sse_client.py`.

## Admin/Heavy Runs
- Admin gating defaults to ON for heavy runs. Override with env `EVALS_HEAVY_ADMIN_ONLY=false` if needed.

## Storage & Audit
- Per-arm collections stored under user namespace: `user_{user_id}_abtest_{test_id}_arm_{i}`
- Collection metadata includes `embedding_model`, `embedding_provider`, `embedding_dim`, and when applicable, `hf_revision` or `onnx_sha`.

## Exports
- CSV export includes: `result_id, arm_id, query_id, ranked_ids, latency_ms, metrics_json`.
- JSON export returns the full rows, including diagnostics arrays.
