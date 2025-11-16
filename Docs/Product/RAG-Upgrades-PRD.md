# PRD: RAG Upgrades (Unified Pipeline)

- Owner: RAG/Backend
- Stakeholders: API, WebUI, Evaluations, Embeddings
- Status: Draft
- Last updated: 2025-11-15
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
- On internal benchmark suite, achieve: Recall@10 +8% and claim‑faithfulness +10% (target ranges above) with cost/latency within budgets.
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
- Performance: Soak tests with flags; record per‑phase TP95 and timeouts.

## 17) Open Questions

- Which corpora benefit most from precomputed spans vs on‑the‑fly?
- Minimum viable feature set for learned fusion before considering LTR?
- Where to store calibrator artifacts and how to roll versions across multi‑env deployments?

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
