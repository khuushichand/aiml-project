# RAG Benchmarking — PRD

- Status: Draft (v0.1)
- Last Updated: 2025-11-13
- Authors: Codex (coding agent)
- Stakeholders: RAG, Evaluations, WebUI, Docs, Providers

---

## 1. Overview

### 1.1 Summary
Deliver end‑to‑end workflows that let users evaluate, compare, and select the best RAG configuration for their own datasets and questions. The feature composes the unified RAG pipeline with the unified Evaluations module to run hyperparameter sweeps (chunking, retrieval, reranking, generation), compute standardized metrics (retrieval and answer quality), and surface a leaderboard with aggregate scores, latency, and cost/time insights. Results persist in the Evaluations database and are queryable via API and viewable in the WebUI.

### 1.2 Motivation
- RAG performance depends heavily on many parameters (chunking strategy/size/overlap, retriever type and weights, reranker approach, prompting, LLM choice). Defaults are rarely optimal for a given corpus and query distribution.
- Teams need a repeatable, cost‑aware, and reproducible way to benchmark alternative settings against their own ground truth.
- Integrating with the unified Evaluations module provides consistent CRUD, runs, rate‑limiting, webhooks, and storage patterns already used elsewhere in the platform.

### 1.3 Goals
1. Run RAG pipeline sweeps over user‑provided datasets with configurable search/grid/random strategies.
2. Compute retrieval and answer quality metrics and produce a sortable leaderboard.
3. Persist evaluations, runs, metrics, and artifacts; enable idempotent re‑runs and reproducible results.
4. Provide simple APIs, CLI snippets, and WebUI affordances to manage datasets, runs, presets, and reports.
5. Keep costs and latency visible; support caching and ephemeral indexing for speed.

### 1.4 Non‑Goals
- Building a full AutoML/Hyperopt service. We support grid/random search; advanced Bayesian search is out of scope for this phase.
- Creating new vector DB engines. We leverage existing adapters and collections.
- Changing core RAG pipeline output shapes; we evaluate on top of the existing API.

---

## 2. Personas & Stories

| Story | Persona | Description |
| --- | --- | --- |
| US1 | ML/Platform Engineer | “Given my PDFs and known Q/A pairs, I want to sweep chunking and retrieval settings to find the best config.” |
| US2 | Researcher | “I want a leaderboard that ranks configurations by a weighted score I define (faithfulness > diversity > latency).” |
| US3 | Developer | “I want to store and re‑use pipeline presets and run them over new datasets.” |
| US4 | Maintainer | “I need runs to be rate‑limited, observable, and reproducible, with idempotency to avoid duplicate charges.” |

---

## 3. Success Metrics

- Functional
  - Run RAG sweeps on datasets up to 5k samples with concurrency controls and no crashes.
  - Produce leaderboard and per‑config aggregates: overall score, latency, retrieval coverage/diversity, MRR/nDCG (when ground truth IDs present).
  - Persist all runs and allow retrieval via API; export JSON/CSV summaries.
- Quality/Experience
  - Reproducible runs with stable config hashing, idempotency keys, and deterministic random seeds where applicable.
  - Cost/time visibility: per‑sample and per‑config elapsed time; token usage where available.
  - WebUI can list pipeline presets, kick off runs, and view top configurations with filters.

---

## 4. Scope

- In‑scope
  - RAG pipeline sweeps: chunking, retrieval, reranking, generation.
  - Dataset ingestion for evaluation (JSONL/JSON via API; linking to existing content by ID optional).
  - Metrics computation and aggregation; leaderboard with weighted composite score.
  - Preset CRUD and ephemeral collection cleanup.
  - API and minimal CLI flows; WebUI list/detail views integrated with existing Evaluations pages.
- Out‑of‑scope (Phase 1)
  - Advanced hyperparameter search (Bayesian/Optuna).
  - Automated dataset synthesis beyond a helper stub.
  - Full interactive per‑sample error analysis UI (basic JSON export and summary are included).

---

## 5. Glossary

- Config grid: Cartesian product of parameter choices across Chunking, Retriever, Reranker, Generation.
- Sample: One question + expected answer (and optionally gold relevant doc IDs) used for scoring.
- Leaderboard: Ranked list of configuration aggregates per evaluation run.
- Ephemeral collection: Temporary vector index created for a run with TTL and automatic cleanup.

---

## 6. System Design

### 6.1 Components (existing modules leveraged)
- Unified RAG Pipeline: `tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py`
- Unified Evaluations Service and Runner: `tldw_Server_API/app/core/Evaluations/unified_evaluation_service.py`, `tldw_Server_API/app/core/Evaluations/eval_runner.py`
- RAG Pipeline Preset & Cleanup Endpoints: `tldw_Server_API/app/api/v1/endpoints/evaluations_rag_pipeline.py`
- Evaluations Unified Endpoints (CRUD/Datasets/Runs): `tldw_Server_API/app/api/v1/endpoints/evaluations_unified.py`, `.../evaluations_datasets.py`
- Evaluations DB: `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py` (tables: evaluations, evaluation_runs, datasets, pipeline_presets, ephemeral_collections)

### 6.2 Data Model (high‑level)
- Dataset
  - id, name, description, samples[]
  - Sample shape (convention for RAG):
    - input: { question: str, corpus?: ["media_db"|...], filters?: {...} }
    - expected: { answer?: str, relevant_doc_ids?: [str], citations?: [str] }
    - metadata: { category?: str, difficulty?: str, tags?: [str] }
- Evaluation (rag_pipeline)
  - eval_type = model_graded, sub_type = rag_pipeline
  - eval_spec.rag_pipeline: Chunking/Retrievers/Rerankers/Generation sweeps + execution settings
  - dataset_id or inline dataset
- Run
  - id, eval_id, status, progress, results (leaderboard, per‑config aggregates, per‑sample scores), usage
- Pipeline Preset
  - name, config (blocks), timestamps, user_id
- Ephemeral Collections
  - collection_name, namespace, run_id, ttl_seconds, created_at/deleted_at

### 6.3 Parameters (evaluation_schemas_unified)
- ChunkingSweepConfig
  - method: structure_aware | sentences | markdown | code | xml
  - chunk_size, overlap, structure_aware, parent_expansion, include_siblings, chunk_type_filters
- RetrieverSweepConfig
  - search_mode: fts | vector | hybrid; hybrid_alpha; top_k; min_score; keyword_filter
- RerankerSweepConfig
  - strategy: flashrank | cross_encoder | hybrid | llama_cpp | none; top_k; model
- GenerationSweepConfig
  - model; prompt_template; temperature; max_tokens
- Execution
  - search_strategy: grid | random; max_trials; concurrency; timeout_seconds; caching toggles; index_namespace; cleanup_collections; ephemeral_ttl_seconds
- Aggregation
  - aggregation_weights: e.g., { rag_overall: 1.0, retrieval_diversity: 0.2, retrieval_coverage: 0.2, chunk_cohesion: 0.1, mrr: 0.1, ndcg: 0.1 }

### 6.4 Metrics
- Retrieval (automatic when ground truth relevant IDs provided)
  - MRR, nDCG@k; coverage (custom metric), diversity (custom metric)
- Generation / Answer Quality
  - relevance, faithfulness, answer_similarity (embedding‑based)
  - optional: claim_faithfulness using extracted claims (costly; off by default)
- Efficiency
  - latency_ms per sample/config; aggregate mean latency per config
- Composite score
  - config_score = weighted sum across rag_overall, retrieval_diversity, retrieval_coverage, chunk metrics, MRR/nDCG as provided by weights

---

## 7. APIs & Workflows

### 7.1 Create a Dataset (API)
POST `/api/v1/evaluations/datasets`

Payload (example):
```
{
  "name": "my_corpus_eval_v1",
  "description": "Product docs Q/A",
  "samples": [
    {
      "input": {"question": "How do I reset the device?"},
      "expected": {"answer": "Press and hold power for 10s", "relevant_doc_ids": ["doc:manual#reset"]},
      "metadata": {"category": "support"}
    }
  ]
}
```

### 7.2 Define an Evaluation (rag_pipeline)
POST `/api/v1/evaluations`

Payload (example excerpt):
```
{
  "name": "rag-bench-my-corpus",
  "eval_type": "model_graded",
  "eval_spec": {
    "sub_type": "rag_pipeline",
    "metrics": ["relevance", "faithfulness", "answer_similarity"],
    "rag_pipeline": {
      "dataset_id": "<dataset_id>",
      "chunking": {"method": ["structure_aware", "sentences"], "chunk_size": [400, 800], "overlap": [40]},
      "retrievers": [{"search_mode": ["hybrid"], "hybrid_alpha": [0.5, 0.7], "top_k": [5, 10]}],
      "rerankers": [{"strategy": ["flashrank", "cross_encoder"], "top_k": [5, 10]}],
      "rag": {"model": ["gpt-4o-mini", "gpt-4o"], "temperature": [0.0, 0.2]},
      "search_strategy": "grid",
      "max_trials": 48,
      "aggregation_weights": {"rag_overall": 1.0, "retrieval_coverage": 0.2, "retrieval_diversity": 0.2, "mrr": 0.1},
      "caching": {"cache_embeddings": true, "cache_retrievals": true},
      "cleanup_collections": true,
      "ephemeral_ttl_seconds": 86400
    }
  }
}
```

### 7.3 Start a Run
POST `/api/v1/evaluations/{eval_id}/runs`

Payload:
```
{
  "target_model": "openai:gpt-4o-mini",
  "config": {"max_workers": 8, "batch_size": 8},
  "webhook_url": "https://example.tld/hooks/evals"
}
```

Track with:
- GET `/api/v1/evaluations/runs/{run_id}` — run status and summary
- GET `/api/v1/evaluations/{eval_id}/runs` — runs list
- POST `/api/v1/evaluations/runs/{run_id}/cancel` — cancel

### 7.4 Pipeline Presets
- POST `/api/v1/evaluations/rag/pipeline/presets` — create/update preset by name
- GET `/api/v1/evaluations/rag/pipeline/presets` — list
- GET `/api/v1/evaluations/rag/pipeline/presets/{name}` — get
- DELETE `/api/v1/evaluations/rag/pipeline/presets/{name}` — delete

### 7.5 Ephemeral Collections Cleanup
- POST `/api/v1/evaluations/rag/pipeline/cleanup` — deletes expired ephemeral collections registered to the TTL registry

### 7.6 CLI (tldw‑evals)
Examples (leveraging existing CLI):
- `tldw-evals run rag_bench --api openai`
- `tldw-evals compare run1.json run2.json`

---

## 8. Execution Model

### 8.1 Runner Behavior
- Build configuration grid from `eval_spec.rag_pipeline`.
- For each config and sample:
  - Call `unified_rag_pipeline(...)` with mapped args.
  - Collect retrieved documents and generated answer.
  - Compute metrics via `RAGEvaluator` and optional custom coverage/diversity metrics.
  - Record per‑sample latency and scores.
- Aggregate per‑config: mean overall score, mean latency, coverage/diversity, MRR/nDCG, chunk cohesion/separation.
- Rank configurations by `config_score` (fallback to overall) and produce leaderboard.
- Persist results and usage; emit webhook if provided.

### 8.2 Caching & Indexing
- Optional caching: chunksets, embeddings, retrievals.
- Ephemeral collections: when building temporary indexes, register collection name + TTL; cleanup endpoint deletes expired.

### 8.3 Rate Limiting & Quotas
- Enforced via evaluations config: `tldw_Server_API/Config_Files/evaluations_config.yaml` (tiers, burst protection, daily/monthly budgets).

---

## 9. Reporting & Exports

- API returns the full results JSON with:
  - `leaderboard`: [{ config_id, config, overall, latency_ms, config_score }]
  - `best_config`: full aggregate and per‑sample breakdown
  - `per_config`: detailed metrics per configuration
- Export helpers: CSV and JSON exports via CLI or WebUI actions (minimal implementation acceptable in Phase 1).
- Optional: Chatbook export for narrative reports (Phase 2).

---

## 10. Security, Privacy, and Compliance

- Sanitize user‑provided text in datasets (HTML/JS stripped in schemas).
- Respect AuthNZ modes and scopes (workflows/evals). Use per‑user DB roots.
- Never log secrets; redact prompts and answers when configured.
- Enforce request size and batch limits (see evaluations security config).

---

## 11. Testing Strategy

- Unit
  - Config grid builder: correct cartesian expansion, max_trials, random sampling.
  - Metric calculators: nDCG/MRR; coverage/diversity with tiny fixtures.
  - Preset CRUD DB ops.
- Integration
  - End‑to‑end small dataset (3–5 samples) with 2–3 configs; validate leaderboard ordering and aggregation.
  - Ephemeral collections registry and cleanup path.
  - Rate‑limit headers and idempotency behavior for runs and datasets.
- Mocking
  - Use `mock_openai_server` and local providers to avoid external calls.

---

## 12. Rollout Plan

- Phase 1 (MVP)
  - API + Runner + Presets + Cleanup + Docs + Minimal WebUI list view.
- Phase 2
  - WebUI compare view; CSV export; Chatbook report option; per‑sample error analysis.
- Phase 3
  - Advanced search strategies (Bayesian), adaptive early‑stopping, budget‑aware sweeps.

---

## 13. Open Questions

- Do we expose a dedicated endpoint for “leaderboard only” retrieval for a run, or reuse the run detail payload?
- Should claim‑level metrics be a first‑class toggle in rag_pipeline.metrics for larger datasets given cost?
- What default aggregation weights should we ship for general corpora vs. Q/A heavy corpora?

---

## 14. Acceptance Criteria

- Users can create a dataset, define a rag_pipeline evaluation, start a run, and retrieve a leaderboard via API.
- Pipeline presets can be created/retrieved and used to pre‑fill eval_spec blocks.
- Results include a best_config with per‑sample metrics and aggregated scores; ephemeral collections are cleaned up by TTL.
- Tests cover config grid expansion, metrics aggregation, basic end‑to‑end run with mocks.

---

## 15. Appendix

### 15.1 Minimal Example: Single‑file Run
```
POST /api/v1/evaluations/datasets
{ "name": "mini", "samples": [{"input": {"question": "What is CRISPR?"}, "expected": {"answer": "Gene editing method"}}] }

POST /api/v1/evaluations
{
  "name": "mini_rag",
  "eval_type": "model_graded",
  "eval_spec": {
    "sub_type": "rag_pipeline",
    "metrics": ["relevance", "faithfulness"],
    "rag_pipeline": {
      "dataset_id": "<dataset_id>",
      "retrievers": [{"search_mode": ["hybrid"], "top_k": [5]}],
      "rerankers": [{"strategy": ["flashrank"], "top_k": [5]}],
      "rag": {"model": ["gpt-4o-mini"], "temperature": [0.0]}
    }
  }
}

POST /api/v1/evaluations/{eval_id}/runs
{ "target_model": "openai:gpt-4o-mini", "config": {"max_workers": 4} }
```

### 15.2 Related Files
- Endpoints: `tldw_Server_API/app/api/v1/endpoints/evaluations_unified.py`, `.../evaluations_rag_pipeline.py`, `.../evaluations_datasets.py`
- Schemas: `tldw_Server_API/app/api/v1/schemas/evaluation_schemas_unified.py`
- Runner: `tldw_Server_API/app/core/Evaluations/eval_runner.py`
- DB: `tldw_Server_API/app/core/DB_Management/Evaluations_DB.py`
