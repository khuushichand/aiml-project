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

### Latency SLOs (per provider/model)
- P50: ≤ baseline × 1.1; P90: ≤ baseline × 1.3; P95: ≤ baseline × 1.5.
- Tail guardrail: P99 ≤ 2.5× baseline, or fail closed to baseline ranking.
- Define baselines per provider/model family and re-evaluate on version changes.

### Evaluation Datasets & Baselines
- Datasets: HotpotQA (multi-hop, 1k eval subset), Natural Questions (NQ-open, 1k), and an internal domain set (500 curated Q/A with relevance judgments).
- Splits: fixed eval splits with run IDs; do not shuffle between runs.
- Baseline System: existing RAG “hybrid BM25 + vector + flashrank (if enabled)” as configured in unified RAG default preset.
- Target Deltas: +5–10 nDCG@10 overall; +3–5 on multi-hop (Hotpot subset); stat-sig at p<0.05 via paired bootstrap on queries.

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
  - Backoff Policy (with jitter):
    - 429: exponential backoff with full jitter; initial 250ms, factor 2.0, max 8 retries, cap 60s.
    - 5xx: decorrelated jitter, initial 500ms, max 5 retries, cap 30s; abort on repeated 502/503 after cap.
    - Timeouts/Connect errors: 3 retries with exponential backoff (250ms→2s); then trip circuit for provider for 30s.
    - Non-retryable (4xx except 429): no retry; return structured error and degrade to baseline.
  - Provider-aware concurrency & budgets:
    - Per-key `max_concurrent_calls` and `max_tokens_per_minute` enforced by token bucket.
    - Default caps: OpenAI-like 20 concurrent/60k TPM; Anthropic-like 10 concurrent/40k TPM; configurable via env.
    - Burst control: queue with backpressure; drop to baseline when queue wait > tail budget.
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

### Pydantic Schemas & OpenAPI
- RerankRequest (tldw_Server_API/app/api/v1/schemas/rag_rerank.py):
  - fields: `query: str`, `candidates: List[{id: str, text: str}]`, `topk: Optional[int]=None`, `provider: Optional[str]`, `model: Optional[str]`, `temperature: float=0.2`, `seed: Optional[int]`, `response_format: Optional[str]='json'`.
- RerankResponse: `ranking: List[str]`, `reasoning: Optional[str]`, `scores: Optional[List[{id: str, score_0_1: float}]]`, `meta: {provider, model, usage?: {input_tokens, output_tokens}}`.
- TraversalRequest/Response (tldw_Server_API/app/api/v1/schemas/rag_traversal.py) mirror above with `tree_id`, `beam`, `depth`.
- Add OpenAPI examples for happy-path and schema-failure fallback (baseline).

## Prompt & Schema Specs
- Traversal Prompts
  - Inputs: query, candidate passages with IDs, relevance definition text.
  - JSON Output: `reasoning: string`, `ranking: [int]`, `relevance_scores: [[node_id, score_0_100]]`.
- Reranking Prompt
  - Inputs: query, top-N passages; outputs `reasoning` and `ranking: [int]`.
- Constraints
  - Provider-agnostic JSON Schema; enforce validation before use.
  - Fallback: JSON repair and stricter parsing for robustness.

### Concrete JSON Schemas (Draft 2020-12)
- Rerank Output Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://tldw.ai/schemas/rerank_output.json",
  "type": "object",
  "required": ["ranking"],
  "properties": {
    "reasoning": {"type": "string"},
    "ranking": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 1
    },
    "scores": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "score_0_1"],
        "properties": {
          "id": {"type": "string"},
          "score_0_1": {"type": "number", "minimum": 0, "maximum": 1}
        }
      }
    }
  },
  "additionalProperties": false
}
```

- Traversal Output Schema
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://tldw.ai/schemas/traversal_output.json",
  "type": "object",
  "required": ["ranking", "relevance_scores"],
  "properties": {
    "reasoning": {"type": "string"},
    "ranking": {"type": "array", "items": {"type": "string"}},
    "relevance_scores": {
      "type": "array",
      "items": {
        "type": "array",
        "prefixItems": [
          {"type": "string"},
          {"type": "number", "minimum": 0, "maximum": 100}
        ],
        "minItems": 2,
        "maxItems": 2
      }
    }
  },
  "additionalProperties": false
}
```

### Example Outputs
- Rerank (example)
```json
{
  "reasoning": "Docs A and C directly answer the query; B is peripheral.",
  "ranking": ["doc_A", "doc_C", "doc_B"],
  "scores": [
    {"id": "doc_A", "score_0_1": 0.86},
    {"id": "doc_C", "score_0_1": 0.71},
    {"id": "doc_B", "score_0_1": 0.32}
  ]
}
```

- Traversal (example)
```json
{
  "reasoning": "Node N3 expands the relevant subtopic; N1 is less specific.",
  "ranking": ["N3", "N1", "N2"],
  "relevance_scores": [["N3", 92.1], ["N1", 71.4], ["N2", 40.0]]
}
```

### Provider JSON Modes and Fallback Order
1) Native JSON/tool/function-calling modes (OpenAI response_format, tool_calls; Anthropic tool_use; Google function calling).
2) If unavailable, force content-type: JSON via system prompt + strict schema examples.
3) If malformed: attempt `json_repair` once, then re-prompt with stricter constraints.
4) After N=2 failures: return baseline ranking with warning; log structured error.

## Calibration Model
- Model: θ per item with PL-style likelihood and MSE alignment to given human-like scores; temperature `tau` and weight `lambda_mse`.
- Training: short-run per query (small M), optimized with AdamW; output normalized θ in [0,1].
- Thresholding: optional bimodal GMM to pick a sampling threshold when selecting leaves.

### Operational Details
- Scope: θ is per-query, computed on the slate for that query; no cross-query reuse.
- Minimal slate: require M ≥ 5 items with ≥ 1 positive signal; otherwise skip calibration (no-op) and surface baseline scores.
- Early exit: stop after 50 steps or when Δloss < 1e-4 over 5 steps.
- Fallbacks: if optimizer diverges/NaNs, revert to normalized input scores.
- Alternatives: allow dependency-light calibration (`isotonic` or Platt-style logistic) via config flag if Torch is unavailable.

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
  - Significance testing: paired bootstrap over queries; report p-values for nDCG deltas.

## Performance & Scaling
- Concurrency: `max_concurrent_calls` default 20; configurable per environment.
- Timeouts: default 60-120s per request; categorized backoff caps (e.g., 300s for 429s).
- Memory: JSON streaming where possible; avoid holding large results when not needed.
 - Token/RPS budgets: enforce `max_tokens_per_minute` and `requests_per_minute` per provider key; queue with backpressure.

## Security & Privacy
- Secrets via env or secret store; never log API keys or request bodies with PII.
- Redact tokens and credentials in logs; enforce structured logging without secrets.

### Prompt Injection Hardening
- Sanitize candidate text (strip/control invisible characters; normalize Unicode; optionally escape HTML/Markdown when rendering).
- System prompts explicitly forbid following instructions in candidate text; require strictly structured JSON with no prose unless in `reasoning`.
- Use tool/function-calling where available to reduce injection risk; validate schema strictly before use.
- Do not log raw candidate text or full prompts; log hashed candidate IDs and aggregate statistics only.

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

## Reproducibility & Cost Budgets
- Phase 1 budget: ≤ 15k tokens/request avg; cap 50k/query end-to-end; ≤ 20 concurrent per key.
- Phase 2 budget: ≤ +10% tokens vs Phase 1 due to calibration metadata.
- Phase 3 budget: depth≤2, beam≤3 by default; hard cap 120k tokens/query.
- Determinism for evals: temperature ≤ 0.3; set `seed` where provider supports; record model version/family in `meta`.
- Log per-run `run_id`, dataset name, split, model/provider, and cost estimates.

## Acceptance Criteria
- Schema conformance ≥ 99.5%; failures auto-retry and log structured context.
- Batch runner survives transient provider issues; final completion ratio ≥ 99%.
- Metrics: documented improvements vs. baseline; reproducible within ±5%.
 - Degrade gracefully: after N=2 schema failures, return baseline ranking with warning and telemetry event.

## Risks & Mitigations
- Provider Variance: switchable client interface; keep prompts provider-neutral.
  - Mitigation: adapter pattern; schema validation; retries.
- Cost Growth: deeper traversal increases tokens.
  - Mitigation: beam/depth caps; prompt-size trimming; selective reranking.
- JSON Fragility: malformed outputs.
  - Mitigation: schema enforcement, JSON repair fallback, strict error categorization.

## Traversal Trees & Registry
- Format (JSON file):
  - `tree_id: str`, `version: int`, `created_at: iso8601`, `root_id: str`.
  - `nodes: [{ id: str, parent_id: Optional[str], title: str, summary: Optional[str], doc_ids: Optional[List[str]], metadata: Optional[dict] }]`.
- Validation rules: single root, acyclic graph, unique IDs, all `parent_id` reference valid nodes.
- Registry: `Databases/tree_registry.json` mapping `tree_id` → `{path, version}`; supports file path or external URI.
- Versioning: bump `version` on structural changes; store `last_built_with` (embedder + params) in metadata for provenance.
- Defaults: beam=3, depth=2 for medium corpora (<1M chunks); beam=2, depth=1 for small corpora; cost guardrails enforced.

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
  - Reuse existing RG policies/route_map for new endpoints (ingress rate limits are RG-owned).
  - Enforce AuthNZ dependency; redact PII in logs via existing middleware.

- Observability
  - Loguru structured logs; batch summary (success, retries, throughput) emitted at INFO.
  - Optionally persist evaluation artifacts via existing Evaluations module.
  - Metrics to emit (names/examples):
    - Counters: `rag_rerank_requests_total`, `rag_rerank_retries_total`, `rag_rerank_failures_total{code}`.
    - Histograms: `rag_rerank_latency_ms`, `provider_call_latency_ms`, `json_repair_attempts`.
    - Gauges: `inflight_requests`, `queue_depth`.
    - Token usage: `input_tokens_total`, `output_tokens_total`.

- Data & Storage
  - No schema migrations required; traversal trees stored as files (JSON/PKL) in `models/` or `Databases/` with registry mapping, or external URI.
  - Calibration state is per-request ephemeral; no persistence.

- Testing Plan
  - Unit: prompt builders, schema validation, calibration outputs shape/normalization.
  - Integration: rerank endpoint happy path, error/backoff paths, JSON conformance; traversal basic beam step (when enabled).
  - Property-based tests: randomized valid/invalid JSON against schemas to ensure robust parsing.
  - Golden tests: snapshot prompts/responses to detect regressions across prompt/template changes.
  - A/B harness: integrate with Evaluations module; every run has `run_id`, persists artifacts and metrics, and can compare baseline vs variant.

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

## Repo Process Alignment
- Add companion design: `Docs/Design/LATTICE-Design.md` detailing architecture, schemas, and flows.
- Add `IMPLEMENTATION_PLAN.md` with staged deliverables, success criteria, and status updates per project guidelines.
- Note schema code locations:
  - `tldw_Server_API/app/api/v1/schemas/rag_rerank.py`
  - `tldw_Server_API/app/api/v1/schemas/rag_traversal.py`

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
