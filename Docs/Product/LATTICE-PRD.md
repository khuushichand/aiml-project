# PRD: Hierarchical RAG With LLM-Orchestrated Traversal, Calibration, and Reranking

- Document Owner: [You]
- Status: Draft (v1)
- Target Release: Phase 1 (4 weeks), Phase 2-3 (8-12 weeks total)

## Background
- Existing RAG pipelines plateau on quality due to noisy reranking and limited iterative reasoning.
- This initiative integrates a hierarchical search paradigm with robust LLM orchestration and score calibration to raise retrieval quality while controlling cost and latency.

## Objectives
- Improve retrieval quality (nDCG@10, Recall@10) on reasoning-heavy queries.
- Keep latency predictable at production loads via concurrency and backoff.
- Provide explainability through reasoned ranking and audit logs.
- Modularize components to swap LLM providers and tree builders.

## Success Metrics
- +5-10 points nDCG@10 over current baseline on evaluation set.
- ≥95th percentile end-to-end latency ≤ 3× current baseline at same QPS.
- Structured result validity (JSON schema conformance) ≥ 99.5% of calls.
- Error-resilience: ≥ 99% batch completion despite transient API errors.

## Scope
- In-Scope:
  - Reasoned reranking with JSON-constrained prompts.
  - Async batching with concurrency control and categorized backoff.
  - Score calibration over slates (Plackett-Luce-style + MSE prior).
  - Optional hierarchical traversal/beam search over a semantic tree.
  - Evaluation metrics (nDCG, Recall), logging/metrics, and prompt budget control.
- Out-of-Scope:
  - Tree construction tooling for your corpus (covered later as separate effort).
  - UI/visualization beyond minimal metrics and logs.

## Personas
- ML Engineer: builds and operates retrieval stack; needs modular components and metrics.
- Applied Researcher: experiments with prompts, scoring, and trees to maximize quality.
- Platform Engineer: needs stable APIs, observability, and safe failure modes.

## Assumptions
- A working baseline RAG stack exists (embedder, retriever, LLM client).
- You can consume Python components and run async workloads.
- Access to LLM providers (e.g., OpenAI/Anthropic/Google) and secrets management.

## Constraints
- Cost and latency budgets must be tunable (concurrency, timeouts, retries).
- Provider-agnostic orchestration; no hard dependency on a single vendor.

## Functional Requirements
- Prompting
  - Provide two prompt families: traversal (tree/leaf) and reranking, each outputting JSON with specified schema.
  - Enforce response schema validation; recover from malformed JSON when possible.
  - Manage prompt size with iterative candidate truncation to stay under token budget.
- LLM Orchestration
  - Async batch execution with optional concurrency limits.
  - Categorized backoff for typical HTTP and provider errors (429/503/timeout).
  - Per-batch metrics: success counts, retry distribution, active requests, durations.
- Calibration
  - Accept slates of (doc_id, score in [0,1]) per query and learn θ vector.
  - Normalize and export calibrated scores; support blending with parent path relevance.
- Hierarchical Traversal (optional Phase 3)
  - Maintain a semantic tree registry; run beam search with LLM-scored expansions.
  - Combine local calibrated relevance with parent path via `relevance_chain_factor`.
- Evaluation
  - Compute nDCG@k and Recall@k per iteration and aggregate summary.
- Observability
  - Structured application logs, progress bars in experiments, and batch summary reports.
  - Track error breakdown, retries, throughput, and average attempts.

## Non-Functional Requirements
- Reliability: graceful degradation on provider errors; resilient batch completion.
- Performance: linear scaling with concurrency, bounded backoff delays.
- Maintainability: modular interfaces to swap LLM providers and calibration models.
- Security: strict handling of API keys via environment or secret stores; no logging of secrets.

## System Overview
- Components
  - LLM Client Orchestrator: async batch runner with retries and metrics.
  - Prompt Layer: traversal and reranking prompt generators with schema constraints.
  - Calibration Layer: PLLinearPrior + MSE alignment to stabilize scores across prompts.
  - Traversal Controller (optional): beam state manager, top-k candidate selection, path relevance chaining.
  - Metrics & Logging: batch summaries, structured logs, evaluation metrics.
- Data Flow
  - Candidate docs → Rerank Prompt → LLM JSON → Parse & Validate → Scores → Calibration → Final ranking.
  - Optional: Tree node candidates → Traversal Prompt → Expand children → Update beam → Repeat for N iterations.

## APIs & Interfaces
- LLM Orchestrator
  - `run(prompt, timeout, max_retries, response_schema) -> text`
  - `run_batch(prompts, max_concurrent_calls, response_schema, print_summary_report=True) -> List[text]`
- Calibration
  - `add(relevance_scores: Dict[int, float])`
  - `fit() -> None`
  - `theta -> np.ndarray` (normalized [0,1])
- Traversal Controller (optional)
  - `get_step_prompts() -> List[(prompt, slate_indices)]`
  - `update(beam_slates, beam_response_jsons) -> None`
  - `get_top_predictions(k, rel_fn) -> List[(node, score)]`

## Prompt & Schema Specs
- Traversal Prompts
  - Inputs: query, candidate passages with IDs, relevance definition text.
  - JSON Output: `reasoning: string`, `ranking: [int]`, `relevance_scores: [[node_id, score_0_100]]`.
- Reranking Prompt
  - Inputs: query, top-N passages; outputs `reasoning` and `ranking: [int]`.
- Constraints
  - Provider-agnostic JSON Schema; enforce validation before use.
  - Fallback: JSON repair and stricter parsing for robustness.

## Calibration Model
- Model: θ per item with PL-style likelihood and MSE alignment to given human-like scores; temperature `tau` and weight `lambda_mse`.
- Training: short-run per query (small M), optimized with AdamW; output normalized θ in [0,1].
- Thresholding: optional bimodal GMM to pick a sampling threshold when selecting leaves.

## Algorithms
- Reranking
  - Prompt → JSON ranking → Map back to original IDs → Final order.
- Calibration
  - Aggregate per-slate scores → optimize model → export θ → (optional) fuse with path relevance.
- Traversal (optional)
  - Beam search: maintain frontier; expand via traversal prompt; instantiate children with relevance scores; calibrate; update beam by rel_fn.

## Evaluation
- Metrics
  - `nDCG@k`, `Recall@k` with plug-in k; summary means per iteration.
- Reporting
  - Per-batch: throughput, success/failure counts, retry histograms.
  - Iteration logs: mean metrics and saved artifacts.

## Performance & Scaling
- Concurrency: `max_concurrent_calls` default 20; configurable per environment.
- Timeouts: default 60-120s per request; categorized backoff caps (e.g., 300s for 429s).
- Memory: JSON streaming where possible; avoid holding large results when not needed.

## Security & Privacy
- Secrets via env or secret store; never log API keys or request bodies with PII.
- Redact tokens and credentials in logs; enforce structured logging without secrets.

## Rollout Plan
- Phase 1: Reasoned Reranking
  - Integrate LLM orchestrator and reranking prompts with schema validation.
  - Acceptance: +5 points nDCG@10 on benchmark, ≤1.5× latency increase at current QPS.
- Phase 2: Calibration
  - Add calibration after reranking to stabilize scores; enable blending in final rank.
  - Acceptance: +1-2 additional points nDCG@10; improved stability across runs (≤5% variance).
- Phase 3: Hierarchical Traversal (optional)
  - Introduce semantic tree; replace flat rerank with iterative traversal for complex queries.
  - Acceptance: +3-5 points nDCG@10 on multi-hop benchmarks; latency within budget at constrained depth/beam.
- Phase 4: Observability & Hardening
  - Comprehensive batch reports, error dashboards, and guardrails on prompt size.
  - Acceptance: ≥99.5% valid JSON; complete error breakdown visible.

## Acceptance Criteria
- Schema conformance ≥ 99.5%; failures auto-retry and log structured context.
- Batch runner survives transient provider issues; final completion ratio ≥ 99%.
- Metrics: documented improvements vs. baseline; reproducible within ±5%.

## Risks & Mitigations
- Provider Variance: switchable client interface; keep prompts provider-neutral.
  - Mitigation: adapter pattern; schema validation; retries.
- Cost Growth: deeper traversal increases tokens.
  - Mitigation: beam/depth caps; prompt-size trimming; selective reranking.
- JSON Fragility: malformed outputs.
  - Mitigation: schema enforcement, JSON repair fallback, strict error categorization.

## Stack Tailoring: tldw_Server_API Integration

- Context
  - Framework: FastAPI app (`tldw_Server_API.app.main:app`).
  - Providers: unified LLM layer under `tldw_Server_API/app/core/LLM_Calls/` with 16+ backends.
  - Retrieval: SQLite FTS5 + Chroma under `tldw_Server_API/app/core/Embeddings/` and `tldw_Server_API/app/core/RAG/`.
  - AuthNZ: single-user API key and multi-user JWT; rate limiting via existing decorators.
  - Logging: Loguru with stdlib interception; Audit service present.

- New Modules (proposed locations)
  - `tldw_Server_API/app/core/RAG/ReasonedReranker.py`
    - Builds prompts (cluster/leaf), enforces JSON schema, parses/repairs responses, returns ranking and scores.
  - `tldw_Server_API/app/core/RAG/Calibration/pl_calibration.py`
    - Ports PLLinearPriorModel + CalibModel; Torch-backed; no persistent state.
  - `tldw_Server_API/app/core/RAG/Traversal/hierarchical_search.py` (Phase 3)
    - Beam controller over a semantic tree; uses reranker + calibration per step.
  - `tldw_Server_API/app/api/v1/endpoints/rag_rerank.py`
    - REST endpoint: `POST /api/v1/rag/rerank` (query, candidates, provider/model, options) → ranked list with reasoning.
  - `tldw_Server_API/app/api/v1/endpoints/rag_traversal.py` (Phase 3)
    - REST endpoint: `POST /api/v1/rag/traversal/search` (query, tree_id or handle, depth/beam) → ranked leaves with traces.
  - Tests: `tldw_Server_API/tests/RAG/test_reasoned_rerank.py`, `test_pl_calibration.py`, `test_traversal_controller.py`.

- Provider Integration
  - Use existing chat provider manager (`LLM_Calls`) to request JSON-constrained outputs.
  - Strategy: prefer provider-native JSON modes (OpenAI `response_format`, etc.); fallback to strict system prompt + `json_repair` and schema validation.
  - Concurrency/backoff implemented in a reusable async helper akin to `LanguageModelAPI.run_batch`.

- Endpoints & Contracts
  - `POST /api/v1/rag/rerank`
    - Request: `{ query: str, candidates: [{id: str, text: str}], topk?: int, provider?: str, model?: str, temperature?: float, max_output_tokens?: int }`
    - Response: `{ ranking: [id], reasoning?: string, scores?: [{id, score_0_1}], meta: {provider, model, usage?} }`
  - `POST /api/v1/rag/traversal/search` (Phase 3)
    - Request: `{ query: str, tree_id: str, beam?: int, depth?: int, provider?: str, model?: str }`
    - Response: `{ results: [{id, path, score}], traces: [...], meta: {...} }`

- Config Flags (Config_Files/config.txt or .env)
  - `RAG_REASONED_RERANK_ENABLED=true|false`
  - `RAG_TRAVERSAL_ENABLED=true|false`
  - `RAG_RERANK_MODEL`, `RAG_TRAVERSAL_MODEL`
  - `RAG_LLM_MAX_CONCURRENT_CALLS` (default 20), `RAG_LLM_TIMEOUT_SEC` (default 60-120)

- Rate Limiting & Security
  - Reuse existing rate-limit decorators (slowapi/module limiters) for new endpoints.
  - Enforce AuthNZ dependency; redact PII in logs via existing middleware.

- Observability
  - Loguru structured logs; batch summary (success, retries, throughput) emitted at INFO.
  - Optionally persist evaluation artifacts via existing Evaluations module.

- Data & Storage
  - No schema migrations required; traversal trees stored as files (JSON/PKL) in `models/` or `Databases/` with registry mapping, or external URI.
  - Calibration state is per-request ephemeral; no persistence.

- Testing Plan
  - Unit: prompt builders, schema validation, calibration outputs shape/normalization.
  - Integration: rerank endpoint happy path, error/backoff paths, JSON conformance; traversal basic beam step (when enabled).

- Rollout Targets (tldw_server)
  - Phase 1 adds `rag_rerank.py`, ReasonedReranker module, tests, and docs; feature flag default ON in dev, OFF in prod.
  - Phase 2 adds calibration module and integrates into rerank responses (`scores` field) and optional fusion into search endpoint.
  - Phase 3 adds traversal controller + endpoint guarded by feature flag; depth/beam defaults conservative.

- Example Usage
  - Rerank
    - Request: `POST /api/v1/rag/rerank` with 20 candidates from existing `rag/search`.
    - Response returns `ranking` IDs to reorder results and optional reasoning for audit.
  - Fusion
    - Blend calibrated scores with existing BM25/embedding pipeline as a rerank stage; weight controlled in config (`RAG_RERANK_WEIGHT`).

## Open Questions
- Which provider(s) first? Need priority order for adapters.
- Target corpora for initial tree construction? Available embeddings, clustering strategy, and branching factor?
- Budget: max average tokens per request and max RPS?

## Milestone Deliverables
- Phase 1
  - Reranking service module, prompt builders, schema validator, batch metrics.
- Phase 2
  - Calibration module, θ export, fusion with ranker, A/B results.
- Phase 3
  - Traversal controller, beam search integration, perf tunings for depth/beam.
- Phase 4
  - Observability dashboards, alerting for retries/latency, run books.
