# Ingest-Plan-1

This document defines a standalone plan to deliver five improvements to the Retrieval-Augmented Generation (RAG) stack. It is self-contained and does not rely on other documents.

## Goals

- Improve grounding and explainability with precise structure indices and strict extractive options.
- Increase reliability and performance with persistent caches and stronger observability.
- Enhance the agentic planner’s effectiveness while preserving graceful fallback.
- Keep backwards compatibility and provide clear acceptance criteria and tests for each phase.

## Non-Goals

- Replacing existing databases or LLM providers.
- Introducing new external services by default (Redis, external tracing backends) - these are optional.

## Assumptions

- SQLite remains the default database; Postgres is optional and can follow similar patterns.
- Ingestion pipelines already produce plain text for documents (PDF/EPUB/HTML/Markdown/etc.).
- Feature flags and environment variables are acceptable for rollout control.

## Definitions

- Structure Index: A persisted index of document boundaries (sections, paragraphs, lists, tables) containing start/end character offsets and optional titles/levels.
- Hard Citations: Per-sentence mapping of generated content to supporting source spans (doc id + start/end).
- Agentic Cache: A cache of query-specific, synthetic “ephemeral” context assembled at query time.

---

## Rollout Roadmap (Five Phases)

### Phase 1 - Structure Index + Ingestion Population; Retrieval Surfaces Section Info

Objectives
- Persist document structure (headings/paragraphs/tables/lists) with character offsets.
- Populate the index during ingestion for supported content types.
- Make section and paragraph metadata available in retrieval results.

Scope & Work Items
- Database: Add `DocumentStructureIndex` table with columns: `id`, `media_id`, `parent_id`, `kind` (section|paragraph|list|table|header), `level`, `title`, `start_char`, `end_char`, `order_index`, `path` (optional), `created_at`, `last_modified`, `version`, `client_id`, `deleted`.
- Ingestion: For plaintext and PDF, compute sections/paragraphs with offsets and write to `DocumentStructureIndex`. Continue writing flat chunks to the existing chunks table to keep FTS working.
- Retrieval: When available, attach section/paragraph fields to metadata (e.g., `section_title`, `section_start`, `section_end`, `paragraph_start`, `paragraph_end`).

Deliverables
- New table and migration script (idempotent); write helpers for batched inserts.
- Ingestion routines updated for plaintext and PDF; toggled by env flag `RAG_ENABLE_STRUCTURE_INDEX` (default on).
- Retrieval surfaces `section_*` metadata when the index exists.

Acceptance Criteria
- Ingested documents have structure rows with correct parent/level/order and offsets.
- Retrieval returns section metadata for at least plaintext/PDF.
- No regression to existing FTS and embeddings flows.

Risks & Mitigations
- DB growth: keep rows compact, batch inserts; add indexes on `(media_id, kind)` and `(media_id, start_char)`.
- Incorrect offsets: property tests and sampling in CI; reject obviously invalid ranges.

Rollback Plan
- Table is additive; disable with `RAG_ENABLE_STRUCTURE_INDEX=0`. Existing flows continue.

### Phase 2 - Observability Parity (Tool/Budget Metrics; Compact Plan in Metadata)

Objectives
- Provide uniform metrics for tool usage and budgets across standard and agentic strategies.
- Always return a compact `plan` and key `metrics` in metadata for debugging.

Scope & Work Items
- Metrics: Add counters/gauges such as `agentic_tool_calls_total`, `agentic_budget_tokens_read`, `rag_hard_citation_coverage`, `rag_claims_unsupported_ratio`.
- Metadata: Include `metadata.plan` (bounded JSON with steps and rationale summary) and `metadata.agentic_metrics` (coverage, unique_docs, redundancy) for agentic; include similar core metrics for standard strategy.
- Tracing: Set span attributes for query difficulty, doc_count, tool steps; this is optional when OpenTelemetry is present.

Deliverables
- Metrics and metadata present by default (size-capped) without requiring debug flags.
- Documentation of metric semantics and labels.

Acceptance Criteria
- All requests export phase timings; plan/metrics present in `metadata` with size under 8KB.
- Tool and budget metrics increment as expected in unit/integration tests.

Risks & Mitigations
- Payload bloat: cap plan/trace fields and redact internals.

Rollback Plan
- Feature flags to disable additional metadata fields and metrics emission.

### Phase 3 - Persistent Agentic Cache (SQLite Backend + Invalidation on Updates)

Objectives
- Introduce a shared, file-backed cache for agentic synthetic chunks to survive process restarts and support multi-worker setups.
- Ensure robust invalidation on document updates and deletes.

Scope & Work Items
- Cache abstraction with backends: `memory` (default), `sqlite` (new). Optional `redis` can follow later.
- Key format: `user:{user_id}:ver:{content_version_or_hash}:q:{sha256(query)}`; value stores minimal payload (checksum, content length, spans/provenance) under a TTL.
- Invalidation: On media update/delete, invalidate by prefix for the affected version/hash; expose a helper to receive invalidation events.
- Configuration: `RAG_AGENTIC_CACHE_BACKEND`, `RAG_AGENTIC_CACHE_TTL_SEC`.

Deliverables
- SQLite backend stored under per-user dir (e.g., `Databases/user_databases/<user_id>/Agentic_Cache/`).
- Invalidation hooks invoked from write paths and soft deletes.

Acceptance Criteria
- Cache hit after restart with `sqlite` backend; no stale hits after a document update.
- Load under contention passes basic concurrency tests (serialized while writing).

Risks & Mitigations
- File contention: use simple locking and append-only patterns; fall back to memory cache on error.

Rollback Plan
- Switch backend to `memory`; stale entries naturally expire.

### Phase 4 - Smarter Planner (Few-Shot/Tool-Aware; Fallback; Tracing)

Objectives
- Improve planner quality with curated few-shot examples and explicit tool guidance.
- Preserve deterministic heuristic fallback when LLM access is constrained.

Scope & Work Items
- Prompting: Curate few-shot prompts demonstrating when to use `open_section`, `search_within`, `expand_window`, and budget reasoning.
- Fallbacks: If planner errors, timing out, or disabled, use deterministic heuristics without breaking behavior.
- Tracing: Add compact tool trace (steps with cost/time) to `metadata.plan` (bounded and redacted where needed).

Deliverables
- Configurable planner with budget/time caps; conservative defaults.
- Unit tests covering fallback paths and plan size/shape.

Acceptance Criteria
- With LLM disabled, fallback path matches current heuristic behavior.
- With LLM enabled, steps reflect tool-aware reasoning and do not exceed budgets.

Risks & Mitigations
- Latency: apply strict time budgets and early exits; test prompts for brevity.

Rollback Plan
- Disable planner with a flag; keep heuristic path.

### Phase 5 - Strict Extractive Mode; Consistent Ask/Decline Using Hard-Citation/NLI Thresholds

Objectives
- Ensure the standard strategy can operate in a strict extractive mode.
- Make ask/decline behavior consistent across strategies when evidence is insufficient.

Scope & Work Items
- Add `strict_extractive` option: assemble answers only from retrieved spans; avoid hallucinated synthesis.
- Guardrails: If `require_hard_citations` and coverage < 1.0 or claims unsupported ratio > threshold, apply `low_confidence_behavior` (continue/ask/decline).
- Config: `RAG_STRICT_EXTRACTIVE`, `RAG_REQUIRE_HARD_CITATIONS`, `RAG_LOW_CONFIDENCE_BEHAVIOR`.

Deliverables
- Strict extractive generation path; consistent gate logic for hard-citations and NLI results.

Acceptance Criteria
- Coverage=1.0 yields an answer; coverage<1.0 yields ask/decline per setting.
- NLI unsupported ratio beyond threshold yields ask/decline per setting.

Risks & Mitigations
- Over-abstention: keep thresholds configurable; document sensible defaults.

Rollback Plan
- Disable strict extractive and require_hard_citations flags.

---

## Test Strategy

Test Types
- Unit
  - Guardrails gating: hard-citation coverage gate; low_confidence_behavior logic; NLI threshold handling.
  - Structure index: insertion helpers validate parent/level/order; simple readback checks.
  - Cache adapters: memory and sqlite implementations (hit/miss/expiry/invalidations).
  - Planner fallback: deterministic path when planner is disabled/unavailable/timeout.
- Integration
  - Ingestion → Retrieval flow: structured offsets persisted and surfaced in retrieval metadata; FTS unchanged.
  - Hard-citations + NLI: verify metadata includes per-sentence citations and unsupported ratios lead to ask/decline as configured.
  - Observability: metrics present; plan/metrics included in response metadata (bounded size).
- Property
  - Offsets monotonicity for structure rows; non-overlapping ranges per paragraph.
  - `open_section` returns a valid [start,end) within document bounds.

Fixtures & Environments
- Minimal SQLite media DB with a few plaintext and small PDF cases; include headings and multi-paragraph bodies.
- Test config enabling each phase behind flags; CI runs with default (safe) flags.

Coverage Targets
- ≥80% lines for new helpers; 100% branch coverage for guardrails gating logic.

CI Gates
- Lint/typecheck pass; unit + integration suites green; property tests run on structure indices.

---

## Operational Readiness

Metrics & Alerting
- Phase timings: retrieval, reranking, citations, generation, post-verification.
- Tool/budget counters: tool calls, tokens read, time budget exhausted.
- Coverage gauges: hard-citation coverage, unsupported ratio.
- Add dashboards and basic alerts for persistent failures or budget exhaustions.

Performance & Limits
- Default TTLs for caches; conservative chunk sizes.
- Planner and post-verification time budgets; graceful degrade when exceeded.

Security & Privacy
- Never log secrets; redact long prompts/answers in plan metadata.
- Optional PII detection toggle for retrieved chunks pre-generation.

---

## Dependencies & Ownership

- Ownership: RAG module maintainers; DB migrations reviewed by DB owners.
- Dependencies: SQLite available; optional OTEL; optional Redis later.

## Timeline (Indicative)

- Phase 1: 1-2 weeks
- Phase 2: 1 week
- Phase 3: 1-2 weeks
- Phase 4: 1 week
- Phase 5: 3-5 days

---

## Change Management

- All new capabilities are guarded by feature flags.
- Migrations are additive and idempotent; safe to roll forward/back by flags.


---

## Implementation Steps & Code Touchpoints

This section turns the roadmap into concrete, code-level tasks and references. All items are additive and gated by flags.

### Feature Flags (env or config)
- `RAG_ENABLE_STRUCTURE_INDEX` (default: on) - enable structure index writes/lookups.
- `RAG_STRICT_EXTRACTIVE` (default: off) - strict extractive generation path in standard strategy.
- `RAG_REQUIRE_HARD_CITATIONS` (default: off) - enforce hard-citation coverage gate.
- `RAG_LOW_CONFIDENCE_BEHAVIOR` (default: continue) - one of continue|ask|decline.
- `RAG_AGENTIC_CACHE_BACKEND` (default: memory) - one of memory|sqlite.
- `RAG_AGENTIC_CACHE_TTL_SEC` (default: 600) - TTL for agentic cache entries.

### Phase 1 - Structure Index + Retrieval Surfacing
Implementation steps
- Database schema and migration
  - Add `DocumentStructureIndex` table with columns: `id`, `media_id`, `parent_id`, `kind`, `level`, `title`, `start_char`, `end_char`, `order_index`, `path`, `created_at`, `last_modified`, `version`, `client_id`, `deleted`.
  - Add indices: `(media_id, kind)`, `(media_id, start_char)`.
  - Bump schema version to 7; add idempotent migration and helper CRUD.
  - File: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`.
- Ingestion writes
  - After plaintext/PDF conversion and chunking, compute heading/paragraph offsets and write rows to `DocumentStructureIndex` (preserve parent/level/order).
  - Start behind `RAG_ENABLE_STRUCTURE_INDEX` (default on).
  - File: `tldw_Server_API/app/services/document_processing_service.py`.
- Retrieval enrichment
  - When returning chunk-level results, enrich metadata via nearest range lookup: `section_title`, `section_start`, `section_end`, `paragraph_start`, `paragraph_end`.
  - Prefer DB lookups; fallback to existing heuristics when missing.
  - Files:
    - `tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py` (metadata enrichment).
    - `tldw_Server_API/app/core/RAG/rag_service/agentic_chunker.py` (`open_section` consults DB first).
- Tests
  - Unit: insert/read helpers; parent/level/order validations; range lookup returns expected section.
  - Property: offsets monotonicity/non-overlap; `open_section` returns valid `[start,end)`.
  - Integration: ingestion→retrieval surfaces section metadata; no FTS regressions.

### Phase 2 - Observability Parity
Implementation steps
- Metrics
  - Add/increment counters and gauges: `agentic_tool_calls_total`, `agentic_budget_tokens_read`, `rag_hard_citation_coverage`, `rag_claims_unsupported_ratio`; record phase timings.
  - Files: `tldw_Server_API/app/core/RAG/rag_service/agentic_chunker.py`, `tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py`.
- Metadata
  - Always attach a compact `metadata.plan` (bounded JSON) and `metadata.agentic_metrics` for both strategies; cap total metadata size (~8KB) and redact sensitive internals.
  - Files: same as above.
- Tracing (optional)
  - When OpenTelemetry enabled, set span attributes for tool steps, budgets, coverage scores.
- Tests
  - Verify presence/size bounds; counter increments; span attributes when telemetry is on.

### Phase 3 - Persistent Agentic Cache (SQLite)
Implementation steps
- Cache backend
  - Define a pluggable cache interface and add a `sqlite` backend stored under `Databases/user_databases/<user_id>/Agentic_Cache/`.
  - Extend cache key: `user:{user_id}:ver:{content_version_or_hash}:q:{sha256(query)}`.
  - Files: `tldw_Server_API/app/core/RAG/rag_service/advanced_cache.py`.
- Invalidation hooks
  - On media update/delete and post-chunk writes, call invalidation by media/version/prefix.
  - File: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py` (write paths) and any batch chunk upserts.
- Config
  - Support `RAG_AGENTIC_CACHE_BACKEND` and `RAG_AGENTIC_CACHE_TTL_SEC`.
- Tests
  - Restart persistence and hit; TTL expiry; invalidation on updates; basic single-writer/multi-reader concurrency.

### Phase 4 - Smarter Planner
Implementation steps
- Prompting
  - Add curated few-shot exemplars for tool-aware planning (`open_section`, `search_within`, `expand_window`, budgets) and a loader.
  - File: `tldw_Server_API/app/core/RAG/rag_service/prompt_templates.py`.
- Planner integration
  - In agentic path, add LLM planner option with time/token budgets and graceful deterministic fallback; emit compact tool trace in `metadata.plan`.
  - File: `tldw_Server_API/app/core/RAG/rag_service/agentic_chunker.py`.
- Tests
  - Fallback determinism without LLM; budget cutoffs respected; plan/trace size caps.

### Phase 5 - Strict Extractive Mode + Guardrails
Implementation steps
- API schema
  - Add `strict_extractive: bool` to standard pipeline request schema and document behavior.
  - File: `tldw_Server_API/app/api/v1/schemas/rag_schemas_unified.py`.
- Pipeline routing and gates
  - Route to extractive generation path when `strict_extractive=True` (assemble answer strictly from retrieved spans).
  - Enforce `require_hard_citations` coverage gate uniformly and honor `RAG_LOW_CONFIDENCE_BEHAVIOR`.
  - Integrate NLI `unsupported_ratio` gating with the same ask/decline behavior.
  - File: `tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py`.
- Tests
  - Coverage edge cases (0.99 vs 1.0); unsupported_ratio thresholds; consistent ask/decline across strategies.

### Notes & Guardrails
- Keep DB migration additive and idempotent; do not break existing fixtures.
- Prefer bounded DB lookups (use `(media_id, start_char)` index); batch inserts during ingestion.
- Cap metadata fields and redact secrets; never log API keys.
- All features are flag-gated; disable flags to roll back behavior without schema rollbacks.
