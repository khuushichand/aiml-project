# RAG Feature Additions - Evaluation and Plan (v0.1)

Author: tldw_server coding agent
Date: 2025-10-16

## Scope
Evaluate and plan six requested enhancements to the unified RAG module:

1) Sentence-level grounding (strict extractive mode; per-sentence citations; NLI verification; ask/decline on unsupported claims)
2) Document structure index (heading/paragraph offsets) to power precise open_section and page/section citations
3) Smarter planner (few-shot prompts; tool awareness; graceful fallback; exposed trace)
4) Persistent cache for agentic “ephemeral chunk” with user/version scoping and invalidation on updates
5) Observability (tool/budget metrics and traces; expose plan/spans/coverage in metadata)
6) Ingestion structure index (persist per-paragraph/heading offsets in MediaDB; expose in retrieval metadata)

This doc maps current capabilities, gaps, proposed changes, code touchpoints, testing, risks, and an incremental rollout plan.

---

## 1) Sentence-Level Grounding

### Current
- Per-sentence “hard citations” already exist, mapping generated sentences to doc offsets:
  - unified pipeline hard citations and handling for ask/decline when incomplete: tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py:1994
  - hard/quote citation builders: tldw_Server_API/app/core/RAG/rag_service/guardrails.py:280
- Claims (extraction + NLI/LLM hybrid verification) and post-verification/repair:
  - Claims/NLI in unified pipeline: tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py:2040
  - Post-generation verifier with threshold + optional repair pass: tldw_Server_API/app/core/RAG/rag_service/post_generation_verifier.py:52
- API schema exposes controls:
  - require_hard_citations, enable_claims, low_confidence_behavior: tldw_Server_API/app/api/v1/schemas/rag_schemas_unified.py:960, 1320

### Gaps
- “Strict extractive mode” for generation is not a first-class switch in the standard pipeline (agentic has extractive assembly but is separate).
- Default behavior to ask/decline on unsupported claims may need stronger, consistent enforcement across both standard and agentic strategies.

### Proposal
- Add a `strict_extractive` toggle (standard strategy) that instructs AnswerGenerator to assemble only quoted spans from retrieved documents (no novel synthesis). Minimal version uses hard citations coverage gating; advanced version uses sentence assembly by span stitching.
- When `require_hard_citations=True` and coverage < 1.0, honor `low_confidence_behavior` with ask/decline; ensure this is consistent in both standard and agentic paths.
- Ensure NLI guard (ClaimsEngine) integrates with the above gate: if unsupported ratio > threshold, prefer ask/decline.

### Touchpoints
- unified pipeline gating and answer path: tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py:1994
- guardrails hard/quote citations: tldw_Server_API/app/core/RAG/rag_service/guardrails.py:280
- post-verification controls: tldw_Server_API/app/core/RAG/rag_service/post_generation_verifier.py:52
- API schema (add strict_extractive if we make it public): tldw_Server_API/app/api/v1/schemas/rag_schemas_unified.py:720

### Tests
- Unit: coverage=1.0 returns answer; coverage<1.0 asks/declines per behavior.
- Integration: claim unsupported ratio above threshold triggers ask/decline; standard + agentic parity.

---

## 2) Document Structure Index (Headings/Paragraph Offsets)

### Current
- Hierarchical structure detection with exact offsets exists in Chunking:
  - chunk_text_hierarchical_tree and spans: tldw_Server_API/app/core/Chunking/chunker.py:280
- Agentic toolbox can open_section via heuristic and cached section map: tldw_Server_API/app/core/RAG/rag_service/agentic_chunker.py:410

### Gaps
- No persisted, queryable structure index to support exact section/page/paragraph lookup and fast open_section for large docs.

### Proposal
- Add a dedicated `DocumentStructureIndex` table to MediaDB (normalized):
  - columns: id, media_id, parent_id, kind (section|paragraph|table|header|list), level, title, start_char, end_char, order_index, path (optional), created_at, last_modified, version/client_id (align with v2 schema model), deleted flag.
- Populate on ingestion (PDF/Plaintext/Books). Keep ancestry titles/section path in a small JSON field or composite columns.
- Build SQLite indexes on (media_id, kind), and (media_id, start_char) for fast range queries.
- Provide helper queries to power precise open_section(page/section) and to return section-aware citation anchors.

### Touchpoints
- Media DB schema and insert helpers: tldw_Server_API/app/core/DB_Management/Media_DB_v2.py:220
- Chunker structure and offsets: tldw_Server_API/app/core/Chunking/chunker.py:280
- Agentic tools open_section upgrade to DB-backed lookup.

### Tests
- Ingestion builds structure rows with correct parent/child and offsets.
- Retrieval returns section ranges for headings; open_section resolves in O(log N) with indexes.

---

## 3) Smarter Planner (Few-Shot + Tool Awareness)

### Current
- Agentic tool loop supports optional LLM planning and traces; few-shot not curated:
  - tool loop + optional planning: tldw_Server_API/app/core/RAG/rag_service/agentic_chunker.py:478
  - tool trace exposed when debug: tldw_Server_API/app/core/RAG/rag_service/agentic_chunker.py:1091
- Tools include search_within/open_section/expand/quote.

### Gaps
- Few-shot exemplars and tool-aware instructions not standardized; minimal, heuristic planner.
- Trace not uniformly exposed in standard pipeline or when not in debug.

### Proposal
- Add curated few-shot prompts demonstrating tool selection (open_section vs search_within), with budget hints.
- Persist planner params in config/prompt templates; ensure graceful fallback to deterministic heuristics on LLM errors/timeouts.
- Always expose a compact `metadata.plan` with steps taken and coverage metrics (even if debug_trace is off), bounded in size.

### Touchpoints
- agentic planner prompt + fallback: tldw_Server_API/app/core/RAG/rag_service/agentic_chunker.py:478
- prompts: tldw_Server_API/app/core/RAG/rag_service/prompt_templates.py:14262

### Tests
- Planner produces deterministic fallback when LLM disabled.
- Tool trace redaction/size caps; plan entries present in metadata.

---

## 4) Persistent Cache for Ephemeral Chunk (User/Version-Scoped)

### Current
- Ephemeral agentic cache in-process only: AdvancedAgenticCache (in-memory, TTL): tldw_Server_API/app/core/RAG/rag_service/advanced_cache.py:96
- Agentic ephemeral cache keys based on query + doc snapshot, no user/version scoping: tldw_Server_API/app/core/RAG/rag_service/agentic_chunker.py:883
- Intra-doc vectors cached in process + basic invalidation on media delete: tldw_Server_API/app/core/DB_Management/Media_DB_v2.py:3400

### Gaps
- No multi-process/shared backend; no robust invalidation on document updates; no user scoping; ephemeral cache not aware of document version/content_hash.

### Proposal
- Introduce a pluggable cache backend interface (Memory | SQLite | Redis). Default remains Memory; opt-in to SQLite file in `Databases/user_databases/<user_id>/Agentic_Cache/`.
- Cache key schema: `user:{user_id}:ver:{content_hash_or_version}:q:{sha(query)}` with TTL. Store small payload: chunk_text checksum, provenance spans.
- Invalidation: on media updates/soft deletes, call cache.invalidate_prefix for the affected `ver:{...}` or `media_id:` prefix; wire invalidation path in MediaDatabase on writes and in sync_log consumer.

### Touchpoints
- Cache adapter: extend advanced_cache.py with backend interface + SQLite adapter.
- Agentic key builder to include user_id and doc version/content_hash: tldw_Server_API/app/core/RAG/rag_service/agentic_chunker.py:883
- DB: hook invalidation for updates/deletes.

### Tests
- Cache hit/miss across processes (SQLite backend) with TTL.
- Invalidation on media updates removes stale entries.

---

## 5) Observability (Tools/Budgets/Traces/Metadata)

### Current
- Extensive timing and OTEL hooks in unified pipeline; per-phase histograms: tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py:540
- Agentic coverage/uniqueness/redundancy scores: tldw_Server_API/app/core/RAG/rag_service/agentic_chunker.py:920
- Tracing module + metrics available: tldw_Server_API/app/core/RAG/rag_service/observability.py:1

### Gaps
- Explicit “budget” metrics (token read/write, time budget exhaustion, tool call counts) not consistently recorded across strategies.
- Plan and spans not exposed consistently when not in debug.

### Proposal
- Add counters/gauges:
  - agentic_tool_calls_total, agentic_budget_tokens_read, agentic_time_budget_exhausted_total
  - rag_hard_citation_coverage_gauge, rag_claims_unsupported_ratio_gauge
- Always include compact `metadata.agentic_metrics` and `metadata.plan` with step summaries + budgets; ensure size cap + redact internals.
- Attach OTEL attributes for query difficulty, doc_count (already partially in place) and tool steps.

### Touchpoints
- unified pipeline phase metrics: tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py:1490
- agentic metrics/trace: tldw_Server_API/app/core/RAG/rag_service/agentic_chunker.py:920, 1091
- telemetry manager: tldw_Server_API/app/core/Metrics/telemetry.py (if present), observability.py

### Tests
- Metric increments and span attributes present under both strategies.
- Metadata includes coverage and compact plan even without debug.

---

## 6) Ingestion Structure Index (Persisted Paragraph/Heading Offsets)

### Current
- Placeholder service outlines chunking to UnvectorizedMediaChunks with start/end + kind and small ancestry metadata: tldw_Server_API/app/services/document_processing_service.py:120
- MediaDB already has UnvectorizedMediaChunks with start_char/end_char and chunk_type; chunk FTS and retrieval return these offsets in metadata: tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py:388

### Gaps
- Not all ingestion paths populate `UnvectorizedMediaChunks` consistently; no dedicated structure table for hierarchical relationships; page mapping for PDFs is limited.

### Proposal
- Standardize ingestion to generate both:
  - Flat chunks in `UnvectorizedMediaChunks` with start/end/ctype (already supported)
  - Hierarchical entries in new `DocumentStructureIndex` (sections/paragraphs) with parent/level/order and optional page mapping
- Expose section/paragraph offsets in retrieval metadata when `fts_level='chunk'` or upon request flag `include_structure=true`.

### Touchpoints
- Ingestion modules (PDF/Books/Plaintext): tldw_Server_API/app/core/Ingestion_Media_Processing/
- MediaDB new table and insert helpers.
- Retrieval: augment metadata from structure index when available.

### Tests
- End-to-end ingestion for PDFs and plaintext produces consistent offsets and lookups via retriever.

---

## Rollout Plan

1) Structure index (DB) groundwork
   - Add `DocumentStructureIndex` schema + helpers in Media_DB_v2.
   - Wire Flat chunk + structure index population in ingestion (plaintext first; PDF second).
2) Observability + API parity
   - Add minimal budget/tool metrics and ensure metadata.plan/agentic_metrics present.
   - Ensure require_hard_citations + low_confidence_behavior works uniformly.
3) Persistent agentic cache
   - Introduce pluggable cache backend; add user/version scoping and invalidation.
4) Smarter planner (few-shot)
   - Curate prompts and integrate graceful fallback; expose compact plan always.
5) Strict extractive mode (standard strategy)
   - Add `strict_extractive` to unify with agentic path; implement sentence-stitcher with spans.

Each step ships behind feature flags/environment toggles. Migrations for DB changes are idempotent.

---

## Risks & Mitigations
- DB bloat from structure index: keep entries compact; index critical columns; batch ingestion writes.
- Cache invalidation complexity: drive from existing sync_log; prefer prefix invalidation by media/version.
- Planner latency: graceful fallback to heuristics; enforce small time/token budgets.
- Consistency between strategies: centralize guardrails (hard citations + NLI thresholds) into single utility calls.

---

## Testing Strategy
- Unit: guardrails (coverage gating), structure index inserts/queries, cache adapters, planner fallback.
- Integration: ingestion → retrieval (chunk + structure), hard citations + claim verification paths, observability metrics.
- Property tests: offsets monotonicity; open_section returns valid [start,end) ranges.

---

## Configuration (Suggested)
- RAG_STRICT_EXTRACTIVE=true|false
- RAG_AGENTIC_CACHE_BACKEND=memory|sqlite|redis
- RAG_AGENTIC_CACHE_TTL_SEC=600
- RAG_REQUIRE_HARD_CITATIONS=true|false
- RAG_LOW_CONFIDENCE_BEHAVIOR=continue|ask|decline
- RAG_ENABLE_STRUCTURE_INDEX=true|false

---

## Summary
Most of the requested capabilities are partially present today (hard citations per sentence, claims/NLI, OTEL/metrics, hierarchical offsets in chunker, chunk-level FTS). The plan above focuses on making them first-class, persistent, and consistent across both standard and agentic strategies with minimal disruption and clear rollout guards.
