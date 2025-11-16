# PRD: RAG Upgrades (Unified Pipeline)

- Owner: RAG/Backend
- Stakeholders: API, WebUI, Evaluations, Embeddings
- Status: In Progress
- Last updated: 2025-11-16
- Related docs: RAG core guide (tldw_Server_API/app/core/RAG/README.md), API ref (tldw_Server_API/app/core/RAG/API_DOCUMENTATION.md), Benchmarking (Docs/RAG/RAG_Benchmarks.md), Prior plans (Docs/Design/RAG_Plan.md, Docs/Design/RAG_Features_Evaluation_And_Plan.md, Docs/Design/RAG-Benchmarking.md)

## 1) Background & Problem Statement

The current unified RAG pipeline already supports hybrid retrieval (FTS5 + vector), query expansion (HYBRID), reranking (cross‑encoder, LLM, hybrid, two‑tier), MMR diversity, domain synonyms, post‑generation verification with adaptive rerun, hard citations, numeric fidelity, and on‑the‑fly multi‑vector span scoring.

Opportunities to improve:
- Improve retrieval precision for long documents without heavy latency costs.
- Boost recall and coverage on vague/compound queries.
- Reduce unsupported claims with stronger calibration and safer defaults.
- Make ranking/fusion more principled via lightweight learning and analytics.
- Add optional graph/multi‑hop capabilities for complex reasoning tasks.

Constraints: Maintain single‑endpoint control (`/api/v1/rag/search`), predictable latency/cost via feature flags and budgets, and backwards compatibility with existing clients.

## 2) Goals

- Increase retrieval Recall@10 by +8–12% and MRR by +5–8% on internal benchmarks.
- Improve groundedness/claim‑faithfulness by +10–15% with minimal latency increase.
- Keep TP95 end‑to‑end latency impact ≤ +20% in Precision mode; ≤ +30% in Recall mode.
- Provide clean flags + docs for per‑request control; safe production defaults.

## 3) Non‑Goals

- Building a full offline LTR training pipeline; we will use lightweight calibrators first.
- Replacing the storage backend (SQLite/ChromaDB remain default).
- Rewriting ingestion or chunking wholesale (incremental changes only).

## 4) Users & Key Use Cases

- Precision Q&A (numbers, citations, compliance) → safer defaults, hard citations, numeric fidelity.
- Exploratory research & synthesis → higher recall/diversity, multi‑query, PRF.
- Complex “why/how/compare/timeline” → guided decomposition, (optional) graph neighborhood retrieval.

## 5) Feature Summary (Phased)

### Phase 1 — Quick Wins (config‑level, low risk)
1. Multi‑vector spans into generation
   - Enable `mv_flatten_to_spans=true` to feed best spans (ColBERT‑style) into answer generation for longer docs.
2. Calibrated two‑tier reranking defaults
   - Defaults to cross‑encoder shortlist (e.g., `BAAI/bge-reranker-v2-m3`) → LLM reranker with higher `rerank_min_relevance_prob` and `rerank_sentinel_margin`.
3. Diversity enforcement
   - Ensure MMR gets weight in `hybrid` reranker to reduce redundancy.
4. Intent‑adaptive hybrid mixing
   - Enable `enable_intent_routing=true` to auto-adjust `hybrid_alpha` for lexical vs semantic queries.
5. Corpus‑aware synonyms
   - Encourage `index_namespace` in requests; wire synonyms registry usage by default when present.
6. Safer defaults
   - `require_hard_citations=true`, `enable_numeric_fidelity=true` in production; numeric fidelity behavior default to `ask`.
7. Adaptive rerun on low confidence
   - `adaptive_rerun_on_low_confidence=true` with strict doc/time budgets.

### Phase 2 — Retrieval Quality & Stability
8. Pseudo‑Relevance Feedback (PRF)
   - After initial retrieval, mine salient terms/entities/numbers from top‑n hits and rerun a second retrieval with boosted terms; fuse with RRF.
9. Precomputed late‑interaction index
   - Precompute and store paragraph/span embeddings at ingestion; query‑time uses cached vectors for fast “best‑span” scoring.
10. Numeric grounding boost
  - Unit‑normalization and token presence checks to lightly boost spans with matching normalized numerics.
11. Temporal heuristics, clearer knobs
  - Promote `auto_temporal_filters`; expose range in metadata and make behavior explicit.
12. Corpus‑learned synonyms
  - Batch miner to auto‑update `synonyms_registry` from co‑occurrence/PMI and headings; versioned per corpus.

### Phase 3 — Ranking/Fusion Learning & Multi‑hop
13. Learned fusion + abstention calibration
  - Lightweight logistic calibrator on features (bm25 norm, vec sim, recency, CE score, MMR pos, source quality) to yield fused score and abstention threshold; train from feedback/eval logs.
14. Guided query decomposition orchestration
  - First‑class sub‑query workflow for “why/how/compare/timeline”; retrieve per sub‑goal, then synthesize + verify.

### Phase 4 — Graph‑Augmented Retrieval (Optional)
15. Graph neighborhoods retrieval
  - Build per‑corpus lightweight entity/section graph; retrieve by communities and blend with text retrieval for multi‑hop questions.

## 6) Functional Requirements

Common across features:
- All enhancements are opt‑in per request; safe defaults for production.
- Respect global budgets: time, docs, tokens; abort phases cleanly on budget breach and record metrics.
- Return detailed `metadata` for transparency (what was enabled, budgets used, reasons for abstention).

Phase‑specific FRs:
- Multi‑vector spans (already present):
  - When `enable_multi_vector_passages=true` and `mv_flatten_to_spans=true`, generation input uses top span per doc with `metadata.mv_best_span` preserved.
- PRF:
  - Flags: `enable_prf`, `prf_terms` (default 10), `prf_sources` (keywords|entities|numbers), `prf_alpha` (boost strength), `prf_top_n` (seeds).
  - Merge second‑pass hits via RRF; record `metadata.prf` with terms used and win rate.
- Precomputed late‑interaction:
  - Ingestion stores per‑paragraph/span vectors with offsets; query path loads vectors and does max‑sim per doc.
  - Flags: `enable_precomputed_spans`, `span_chars`, `span_stride` fall back to stored params.
- Learned fusion/calibration:
  - Flags: `enable_learned_fusion`, `calibrator_version`, `abstention_policy` (continue|ask|decline).
  - Response exposes `metadata.reranking_calibration` and `abstention_decision`.
- Decomposition:
  - Flags: `enable_query_decomposition`, `max_subqueries`, `subquery_time_budget_sec`, `subquery_doc_budget`.
  - Response returns `metadata.decomposition` with subqueries and partial results.
- Graph retrieval (optional):
  - Flags: `enable_graph_retrieval`, `graph_version`, `graph_neighbors_k`, `graph_alpha` (blend weight).

## 7) Non‑Functional Requirements

- Performance: TP50/TP95 latency budgets by phase; minimal memory growth under high‑QPS.
- Cost: LLM/reranker token budgets capped; LLM reranker kept on shortlist only.
- Observability: per‑phase timers, counters (success/timeout/abstain), calibration histograms; debug tracing gated by flag.
- Security: guardrails preserved (injection filter, numeric fidelity, hard citations); no leakage of secrets to logs.

## 8) API Changes (request/response)

Endpoint: `POST /api/v1/rag/search`

New/extended request fields (opt‑in):
- Retrieval: `enable_prf`, `prf_terms`, `prf_sources`, `prf_alpha`, `prf_top_n`
- Spans: `enable_precomputed_spans` (defaults to false), reuses existing `mv_*` knobs
- Learning: `enable_learned_fusion`, `calibrator_version`, `abstention_policy`
- Decomposition: `enable_query_decomposition`, `max_subqueries`, `subquery_time_budget_sec`, `subquery_doc_budget`
- Graph: `enable_graph_retrieval`, `graph_version`, `graph_neighbors_k`, `graph_alpha`

Response additions (under `metadata`):
- `prf`: { terms_used, second_pass, fusion_method, wins }
- `reranking_calibration`: { fused_score, threshold, decision }
- `decomposition`: { subqueries: [...], timings }
- `graph_retrieval`: { communities, neighbors_k, alpha }

Documentation to update: `tldw_Server_API/app/core/RAG/API_DOCUMENTATION.md` and WebUI helper texts.

## 9) Architecture & Code Touchpoints

- Pipeline control: `tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py`
- Retrieval/fusion: `tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py`
- Multi‑vector spans: `tldw_Server_API/app/core/RAG/rag_service/advanced_retrieval.py`
- Rerankers & calibration: `tldw_Server_API/app/core/RAG/rag_service/advanced_reranking.py`
- Query expansion/PRF: `tldw_Server_API/app/core/RAG/rag_service/query_expansion.py` (new PRF helper) and a small `prf.py` helper (new)
- Synonyms registry: `tldw_Server_API/app/core/RAG/rag_service/synonyms_registry.py`
- Post‑verification: `tldw_Server_API/app/core/RAG/rag_service/post_generation_verifier.py`
- Ingestion for precomputed spans: `tldw_Server_API/app/core/Embeddings/ChromaDB_Library.py` (+ small store under `tldw_Server_API/app/core/RAG/rag_service/vector_stores/`)
- WebUI texts: `tldw_Server_API/WebUI/README.md` and RAG tab JSON builders

## 10) Rollout Plan

1. Phase 1 toggles defaulted on in staging; prod defaults remain conservative (safer defaults only).
2. Add PRF + toggles (off by default), ship behind env flag.
3. Precomputed spans ingestion (off by default); migrate a small corpus, measure.
4. Learned fusion calibrator (shadow mode → log only) → canary enable.
5. Decomposition orchestration (off by default) → enable per‑team.
6. Optional graph retrieval behind corpus‑level feature flag.

Rollback: All features are guarded by request flags and server env flags; revert defaults or disable flags without code changes.

## 11) Metrics & Evaluation

Primary KPIs
- Retrieval: Recall@{5,10,20}, MRR, Context Precision, Coverage, Diversity.
- Answer: Groundedness/Claim‑faithfulness, Citation coverage, Numeric fidelity.
- System: TP50/TP95 per‑phase, cost per request, cache hit‑rate.

Experiments & Ablations
- Baseline vs +PRF; baseline vs +precomputed spans; baseline vs +learned fusion.
- Decomposition on intents: why/how/compare/timeline.
- Safety: hard‑citation + numeric fidelity gates vs off.

Instrumentation
- Extend current metrics in pipeline; add `prf_*`, `calibration_*`, `mv_*`, and phase budget overrun counters.

## 12) Risks & Mitigations

- Latency bloat from PRF/multi‑vector: enforce strict per‑phase budgets and doc caps; prefer precomputed spans.
- Query drift (PRF/expansion): constrain boosts; intersection/union merge with guardrails.
- Calibrator overfitting: train/test split; shadow mode; versioning and rollback.
- Storage growth (spans): compress vectors; per‑corpus opt‑in; TTL and GC.

## 13) Dependencies

- Embedding service capacity for precomputed spans.
- Cross‑encoder model availability (e.g., `BAAI/bge-reranker-v2-m3`).
- Optional LLM reranker token budgets.
- Feedback/evals logs for calibrator.

## 14) Acceptance Criteria

- Phase 1 enabled in staging with doc updates; no regression in TP95 > +20% in Precision mode.
- On internal benchmark suite, achieve: Recall@10 +8% and claim-faithfulness +10% (target ranges above) with cost/latency within budgets.
- API docs and WebUI helpers updated; feature flags documented.

## 15) Timeline (tentative)

- Week 1–2: Phase 1 defaults + tests + docs.
- Week 2–3: PRF + toggles + ablations.
- Week 3–4: Precomputed spans ingestion + read‑path + ablations.
- Week 4–5: Calibrator shadow mode → gated enable; decomposition orchestration.
- Week 5–6: Optional graph retrieval PoC on one corpus.

## 16) Test Plan

- Unit: PRF term extraction; fusion correctness; calibrator decision boundaries; span metadata invariants.
- Integration: `/rag/search` with each flag; budgets honored; metadata fields present.
- E2E: Benchmark scripts (Docs/RAG/RAG_Benchmarks.md) plus new ablations; WebUI RAG tab flows.
- Performance: Soak tests with flags; record per-phase TP95 and timeouts.

## 17) Open Questions

- Which corpora benefit most from precomputed spans vs on‑the‑fly?
- Minimum viable feature set for learned fusion before considering LTR?
- Where to store calibrator artifacts and how to roll versions across multi-env deployments?

## 18) Presets (for Docs/WebUI)

- Precision mode
  - `enable_multi_vector_passages=true`, `mv_flatten_to_spans=true`
  - `enable_reranking=true`, `reranking_strategy="two_tier"`, `rerank_min_relevance_prob≈0.6–0.7`, `rerank_sentinel_margin≈0.2`
  - `require_hard_citations=true`, `enable_numeric_fidelity=true`, `numeric_fidelity_behavior="ask"`
  - `enable_numeric_table_boost=true`, `enable_intent_routing=true`

- Recall mode
  - `expand_query=true` with `["multi_query","synonym","domain"]`
  - `top_k=30`, `reranking_strategy="hybrid"`, `enable_query_decomposition=true`
  - Optional: `enable_prf=true`

## 19) Quick Usage Snippet (PRF + Multi-Vector)

Example of enabling PRF and multi-vector spans together via the unified pipeline:

```python
from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline

result = await unified_rag_pipeline(
    query="impact of Transformer models in 2024",
    sources=["media_db"],
    top_k=10,
    enable_prf=True,
    prf_terms=8,
    prf_top_n=5,
    enable_multi_vector_passages=True,
    mv_flatten_to_spans=True,
    enable_precomputed_spans=True,
    enable_reranking=False,
    enable_generation=False,
)

prf_meta = (result.metadata or {}).get("prf") or {}
mv_meta = (result.metadata or {}).get("multi_vector") or {}
```

- `prf_meta` highlights how PRF behaved for the request:
  - `enabled`, `base_query`, `expanded_query`, `terms_used`, `doc_seed_count`
  - `second_pass_performed`, `second_pass_added` (documents filled by the PRF second pass)
- `mv_meta` exposes how multi-vector spans were applied:
  - `enabled`, `span_chars`, `stride`, `max_spans_per_doc`, `flattened`, `precomputed_spans`

Clients (including the WebUI) can surface these fields in a debug/advanced pane to explain why particular documents were selected or why additional evidence was pulled in.

## 20) Implementation Status & Remaining Work (2025-11-16)

This section tracks which parts of the PRD are implemented vs remaining.

### Phase 1 — Quick Wins

Current:
- Multi-vector spans with `mv_flatten_to_spans` are implemented via `advanced_retrieval.apply_multi_vector_passages` and integrated into `unified_rag_pipeline`; metadata is exposed under `metadata.multi_vector`.
- Two-tier reranking (`reranking_strategy="two_tier"`) with calibrated probability, sentinel, and generation gating is implemented. Calibration is surfaced in `metadata.reranking_calibration`, and gating drives `metadata.generation_gate`.
- Diversity-aware reranking exists via `DiversityReranker` and as part of `HybridReranker`.
- Intent-adaptive hybrid mixing and query routing are implemented with `QueryAnalyzer` / `QueryRouter`, influencing `hybrid_alpha` and top-k when enabled.
- Corpus-aware synonyms are supported via `index_namespace` and the `synonyms_registry` + query expansion helpers.
- Safer defaults for hard citations and numeric fidelity are wired through env-driven guards in `unified_rag_pipeline`.
- Adaptive rerun on low confidence is implemented as part of `enable_post_verification` + `adaptive_rerun_on_low_confidence`, with `metadata.post_verification` and `metadata.adaptive_rerun`.

Remaining:
- Tune and document “Precision” vs “Recall” presets more explicitly in docs/WebUI, including recommended combinations of reranking strategy, hybrid weights, and guardrail defaults.
- Run and bake in benchmark-driven thresholds (MMR, intent routing, numeric fidelity defaults) instead of current heuristic values.

### Phase 2 — Retrieval Quality & Stability

Current:
- PRF:
  - `enable_prf`, `prf_terms`, `prf_sources`, `prf_alpha`, `prf_top_n` are exposed in API schemas and docs.
  - `prf.apply_prf` mines terms/entities/numbers from top documents and returns `expanded_query` plus `metadata.prf`.
  - `unified_rag_pipeline` runs an optional PRF second pass to fill up to `top_k` with deduped docs and records `second_pass_performed` / `second_pass_added`.
- Precomputed spans:
  - A no-op `apply_precomputed_spans` helper and `enable_precomputed_spans` flag are wired in; metadata `metadata.multi_vector.precomputed_spans` is emitted.
- Numeric grounding:
  - A numeric/table-aware boost is implemented via `enable_numeric_table_boost`, slightly boosting number-dense/table-like chunks and recording `metadata.numeric_table_boost`.
- Temporal heuristics:
  - `auto_temporal_filters` is implemented (relative dates, quarters, month/year) and records `metadata.temporal_filter`.
- Synonyms:
  - Static per-corpus synonyms are supported via config files and query expansion.

Remaining:
- PRF fusion:
  - Implement explicit rank-fusion (e.g., RRF) between first-pass and PRF second-pass hits instead of only “fill remaining slots”.
  - Extend `metadata.prf` with `fusion_method` and simple win-rate stats as sketched in the PRD.
- Precomputed late-interaction:
  - Add ingestion-time span/paragraph embedding storage in the embeddings layer (e.g., ChromaDB adapter).
  - Implement `apply_precomputed_spans` to query span collections, compute best-span scores, and feed them into the multi-vector path.
  - Return meaningful `metadata.multi_vector.precomputed_spans=True` (with parameters) instead of a placeholder.
- Numeric grounding:
  - Add unit-normalization and explicit numeric-token presence checks (beyond the current coarse boost) and attach granular metadata for those signals.
- Corpus-learned synonyms:
  - Implement a batch miner to update synonyms files from co-occurrence/PMI/headings per corpus, with simple versioning and operational controls.

### Phase 3 — Ranking/Fusion Learning & Multi-hop

Current:
- Learned fusion + abstention:
  - Two-Tier:
    - Logistic calibrator over original score, CE score, LLM score + sentinel is implemented in `TwoTierReranker`.
    - Calibration metadata is exposed via `metadata.reranking_calibration` (top_doc_prob, sentinel scores, thresholds, prob_margin, gated), and used to gate generation.
  - Cross-encoder / hybrid:
    - When `enable_learned_fusion=true` and `reranking_strategy` is `cross_encoder` or `hybrid`, `unified_rag_pipeline` computes a simple fused probability from the top rerank score using the same env-controlled logistic weights.
    - `metadata.reranking_calibration` includes `fused_score`, `threshold`, `gated`, plus optional `enabled`, `version`, and `decision`.
  - Abstention:
    - When calibration gates generation, `abstention_policy` (for learned fusion) or `abstention_behavior` (for generic abstention) decides whether to continue, ask a clarifying question, or decline. The chosen `decision` is recorded in `metadata.reranking_calibration`, and `metadata.generation_gate` logs the gate.
- Guided decomposition:
  - Agentic path: `agentic_rag_pipeline` already supports multi-hop-style reading with subgoals and coverage/redundancy metrics.
  - Unified pipeline:
    - `enable_query_decomposition`, `max_subqueries`, `subquery_time_budget_sec`, `subquery_doc_budget` are implemented.
    - The pipeline decomposes the query into subqueries (using QueryAnalyzer + agentic `_decompose_query` when available; otherwise a heuristic splitter), runs additional retrievals for secondary subqueries, and merges extra docs under strict time/doc budgets.
    - `metadata.decomposition` includes `enabled`, optional `intent` / `complexity`, `subqueries` with `added_doc_ids`, `total_added`, and timing/budget info.

Remaining:
- Learned fusion:
  - Add a real training loop for calibrator weights (per `calibrator_version`) using feedback/eval logs instead of static env defaults.
  - Consider additional features (BM25 normalization, recency, source quality, MMR position) beyond the current score-only inputs.
  - Add calibration-focused metrics/histograms (e.g., reliability diagrams, calibration error) per PRD.
- Decomposition orchestration:
  - Promote decomposition to a first-class multi-hop mode: per-subquery retrieval + optional per-subquery synthesis, followed by a final synthesis/verification step.
  - Extend `metadata.decomposition` to optionally include per-subquery partial answers or evidence groupings, not just extra document IDs.

### Phase 4 — Graph-Augmented Retrieval (Optional)

Current:
- Flags and schema entries exist (`enable_graph_retrieval`, `graph_version`, `graph_neighbors_k`, `graph_alpha`), but there is no graph-storage or retrieval implementation yet.

Remaining:
- Define and build graph indices per corpus (entities/sections/links).
- Implement a graph retrieval path that, when enabled, retrieves graph neighbors and blends them with standard retrieval using `graph_alpha`.
- Expose `metadata.graph_retrieval` (communities, neighbors_k, alpha, basic stats) and add minimal graph-related metrics.

### Cross-Cutting: WebUI, Benchmarks, & Ops

Current:
- Core flags and metadata are documented in the RAG README and API docs; the server exposes the necessary toggles via `/api/v1/rag/search`.

Remaining:
- WebUI:
  - Add checkboxes/controls for PRF, multi-vector/precomputed spans, learned fusion + abstention, and decomposition in the RAG tab.
  - Surface `metadata.prf`, `metadata.multi_vector`, `metadata.reranking_calibration`, and `metadata.decomposition` in an advanced/debug view.
- Benchmarking:
  - Implement the ablation matrix described in this PRD (baseline vs +PRF, +precomputed spans, +learned fusion, +decomposition) using the existing RAG benchmarking scripts.
  - Use results to finalize defaults for presets and environment knobs.
