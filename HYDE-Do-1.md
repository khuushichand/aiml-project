# HYDE-Do-1 — Add HYDE/doc2query question embeddings per chunk

Status: Draft v0.1 • Owner: Platform • Related: Embeddings pipeline, VectorStore adapters (Chroma/pgvector)

## Executive Summary

We will augment each chunk with a small set of “HYDE” (Hypothetical Document Embeddings) or doc2query-style questions that a user might ask and that the chunk can answer. We embed these questions using the same embedding model and store them alongside chunk vectors. Retrieval queries search across both kinds and merge results back to the parent chunk, improving recall on sparse or terse text without changing public APIs.

Goals
- Improve recall for short/sparse chunks via question reformulation.
- Keep the pipeline backward compatible and adapter-agnostic (Chroma/pgvector).
- Be safe-by-default: low priority, rate/budget guarded, and idempotent.

---

## Scope

In scope
- HYDE question generation per chunk (N questions, concise, user-style).
- Embedding + storage of questions with metadata linking to parent chunk.
- Retrieval: combined search across chunk and question vectors with merge + optional weighting.
- Config flags (HYDE_*), prompts, and operational safeguards (priority, backpressure, budgets).
- Tests (unit + integration against adapters), minimal WebUI hints.

Out of scope (v0)
- Offline/batch HYDE backfill for historical data (documented later in this file as a post‑v0 outline).
- Learned weighting or cross-encoder re-rankers (can follow in vNext).

---

## Current State

- Embeddings pipeline: chunking → embedding → storage workers with idempotency and priority queues.
- Storage uses adapter interface; Chroma and pgvector adapters exist and are tested.
- Retrieval supports vector-store adapter; metadata filters supported (JSONB in pgvector, where in Chroma).

Touchpoints
- `tldw_Server_API/app/core/Embeddings/workers/embedding_worker.py` (emit HYDE questions)
- `tldw_Server_API/app/core/Embeddings/workers/storage_worker.py` (metadata/idempotency already in place)
- `tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py` (merge results)
- `tldw_Server_API/app/core/RAG/rag_service/vector_stores/*` (filters/queries already supported)

---

## Data Model

Per generated question vector:
- id: `${chunk_id}:q:${qhash8}` (stable even if order changes)
- metadata:
  - `kind`: `hyde_q`
  - `parent_chunk_id`: original `chunk_id`
  - `hyde_rank`: 0..N-1 (rank within the generated set; informational)
  - `question_hash`: SHA256 (hex) of the normalized question text (we use the first 8 chars in the ID as `qhash8`)
  - `content_hash`: normalized hash of the parent chunk text (for dedupe)
  - `embedder_name`, `embedder_version` (existing enforcement)
- document: the question string (short, 1 line)

Question hash and normalization
- Normalize questions for hashing and dedupe similarly to chunk text normalization (NFC, lowercase, collapse whitespace, strip punctuation tails). This yields deterministic `question_hash` so IDs remain stable across retries/prompt tweaks that don’t change the question content.

Chunk vectors keep existing structure with `metadata.kind = 'chunk'` (we’ll start writing this field for new writes; old entries imply kind='chunk').

Optional pgvector indexes
- `(metadata->>'kind')`
- `(metadata->>'parent_chunk_id')`
- `(metadata->>'question_hash')` (optional, supports auditing and selective deletes)

---

## Configuration

Settings / env (added to config + Env_Vars.md):
- `HYDE_ENABLED` (default `false`)
- `HYDE_QUESTIONS_PER_CHUNK` (default `3`, range 1–5)
- `HYDE_PROVIDER`, `HYDE_MODEL` (reuse `analyze()` path; can be local or hosted)
- `HYDE_TEMPERATURE` (default `0.2`), `HYDE_MAX_TOKENS` (default `96`)
- `HYDE_PRIORITY` (default `low`, uses priority queues)
- `HYDE_BUDGET_PER_DOC` / `HYDE_BUDGET_PER_MINUTE` (optional guard)
- `HYDE_WEIGHT_QUESTION_MATCH` (retrieval rank bonus, e.g., `0.05`)
- `HYDE_K_FRACTION` (fraction of k to allocate to HYDE candidates, e.g., `0.5`)
- `HYDE_ONLY_IF_NEEDED` (bool; only run HYDE search when baseline is weak)
- `HYDE_SCORE_FLOOR` (float 0..1; baseline score threshold for early exit)
- `HYDE_MAX_VECTORS_PER_DOC` (hard cap per document, default derived from N and chunk count)
- `HYDE_MAX_COST_PER_MINUTE` (guardrail; ties into existing quota/backpressure)

Prompts (Docs/Config prompts file)
- “Generate N concise, user-style questions a researcher would ask that can be answered by the following text. Avoid duplicates. Keep 8–16 words.”

Config snippets
```
# config.txt (INI-style)
[HYDE]
enabled = true
questions_per_chunk = 3
provider = openai
model = gpt-4o-mini
temperature = 0.2
max_tokens = 96
priority = low
weight_question_match = 0.05
k_fraction = 0.5
only_if_needed = true
score_floor = 0.30
max_vectors_per_doc = 200
max_cost_per_minute = 1.5
prompt_version = 1

# Language-aware example
# auto-detect language per chunk; fallback to English
language = auto
```

```
# Environment variables
HYDE_ENABLED=true
HYDE_QUESTIONS_PER_CHUNK=3
HYDE_PROVIDER=openai
HYDE_MODEL=gpt-4o-mini
HYDE_TEMPERATURE=0.2
HYDE_MAX_TOKENS=96
HYDE_PRIORITY=low
HYDE_WEIGHT_QUESTION_MATCH=0.05
HYDE_K_FRACTION=0.5
HYDE_ONLY_IF_NEEDED=true
HYDE_SCORE_FLOOR=0.30
HYDE_MAX_VECTORS_PER_DOC=200
HYDE_MAX_COST_PER_MINUTE=1.5
# Language-aware generation
HYDE_LANGUAGE=auto   # values: auto | en | es | fr | ...
HYDE_PROMPT_VERSION=1
```

---

## Metadata & Versioning

To avoid drift and enable controlled re-generation, add the following metadata and constants:

- Key constants (use shared constants to avoid typos):
  - `KIND = 'kind'`
  - `PARENT_CHUNK_ID = 'parent_chunk_id'`
  - `HYDE_RANK = 'hyde_rank'`
  - `QUESTION_HASH = 'question_hash'`
  - `CONTENT_HASH = 'content_hash'`
- Versioning & provenance:
  - `hyde_prompt_version` (integer/string) — bump when prompt template changes.
  - `hyde_generator` — `${provider}:${model}` used for generation.
  - `language` — ISO 639-1 (or 639-3) code inferred from chunk; used for language-aware generation.
  - Constant values for `kind`: use exactly `'chunk'` for original chunk vectors and `'hyde_q'` for generated question vectors throughout the system.
- Source of truth for versioning:
  - Read `HYDE_PROMPT_VERSION` from env/config; optionally override via prompts YAML metadata (e.g., `prompts.embeddings.hyde.version`).
  - When `hyde_prompt_version` changes, re-generation is allowed and idempotency keys must change accordingly.
- Idempotency/dedupe:
  - Compose HYDE IDs using `question_hash` to avoid instability when question order changes across runs: `${chunk_id}:q:${qhash8}`.
  - Fold `hyde_prompt_version` (and optionally `language`) into idempotency/dedupe keys so prompt/language changes force refresh (even if IDs don’t change), e.g., include them in the ledger keys and message keys.

Storage workers should pass these fields through; retrieval consumers may use them for diagnostics.

---

## Generation Policy & Quality

Language-aware generation
- Detect chunk language (fast heuristic or provider) and instruct HYDE to generate questions in that language; fall back to English if unknown.

Heuristics to reduce cost/noise
- Minimum content threshold: only generate when chunk length/entropy exceeds a small threshold.
- Adaptive N:
  - Short chunks → N=1
  - Medium → N=2–3
  - Long → N=3–4 (bounded by `HYDE_MAX_VECTORS_PER_DOC`)
- Skip boilerplate (headers/footers/TOCs) via simple regex/structure heuristics.

Safety & logging
- Redact PII-like patterns from logs; do not log generated question texts at info level.
- Emit summarized counts/latency only; use debug logging behind a feature flag for content in dev.
- Enforce bounds: limit generated question length to ~6–20 words (or ≤ 120 chars) and de-duplicate by normalized text.
- Determinism guardrails: prefer low temperature and a fixed seed (if provider supports) to increase stability of outputs; still treat IDs as content-hash based to remain robust under any variability.

---

## Retrieval Merge Options

Weighting & quotas
- Make weighting explicit and per-tenant configurable:
  - `HYDE_WEIGHT_QUESTION_MATCH` — additive bonus to similarity of HYDE hits before merging.
  - `HYDE_K_FRACTION` — cap how many HYDE candidates are pulled (e.g., if k=10 and fraction=0.5 → at most 5 HYDE results).
 - Score normalization: ensure baseline and HYDE similarity scores are on a comparable scale; if adapters return heterogeneous scales, normalize to [0,1] per result set before weighting.

Merge strategies
- Max-score per parent (default):
  - Map HYDE hits to `parent_chunk_id`; score = max(baseline chunk score, hyde score + weight).
- Reciprocal Rank Fusion (RRF):
  - Fuse ranks from chunk and HYDE lists to improve robustness; keep as an optional mode.

Latency safeguard
- “Only-if-needed” mode: run HYDE search/merge only when baseline chunk search returns <K candidates or below a score floor (`HYDE_ONLY_IF_NEEDED`, `HYDE_SCORE_FLOOR`).

Pseudocode
```
def hyde_search(query, k):
    # 1) baseline on chunk vectors
    chunk_hits = vs.search(collection, query, k=k, filter={'kind': 'chunk'})

    # optional early exit
    if len(chunk_hits) >= k and max_score(chunk_hits) >= SCORE_FLOOR:
        return topk(chunk_hits, k)

    # 2) hyde_q search (bounded by HYDE_K_FRACTION)
    k_hyde = int(k * HYDE_K_FRACTION)
    hyde_hits = vs.search(collection, query, k=k_hyde, filter={'kind': 'hyde_q'})

    # 3) map hyde_q → parent_chunk_id and apply weight
    parent_scored = aggregate_by_parent(hyde_hits, weight=HYDE_WEIGHT_QUESTION_MATCH)

    # 4) fuse (choose one)
    fused = fuse_max_score(chunk_hits, parent_scored)
    # or: fused = rrf_fuse(chunk_hits, parent_scored)

    # 5) de-duplicate by parent_chunk_id and trim to k
    return dedupe_and_trim(fused, key='parent_chunk_id', k=k)
```
Notes: For pgvector, filters like `{'kind': {'$in': ['chunk','hyde_q']}}` or `{'parent_chunk_id': '<id>'}` map to JSONB predicates. For Chroma, simple equality works; complex operators may fallback client-side.

---

## Storage & Indexing Considerations

pgvector
- Optional helper indexes to accelerate filters:
  - `CREATE INDEX IF NOT EXISTS <tbl>_kind_idx ON <tbl> ((metadata->>'kind'));`
  - `CREATE INDEX IF NOT EXISTS <tbl>_parent_idx ON <tbl> ((metadata->>'parent_chunk_id'));`
 - Prefer pgvector ≥ 0.7 for HNSW; fallback to IVFFLAT otherwise. HNSW build can be memory-heavy — plan builds off-hours and set appropriate maintenance_work_mem.

Chroma
- Document that `where` filters are evaluated within Chroma’s API and may be less selective; keep `HYDE_QUESTIONS_PER_CHUNK` small to limit collection growth.

Filter syntax examples (adapters)
- pgvector (JSONB filter translated server-side):
  - `{'kind': {'$in': ['chunk','hyde_q']}}`
  - `{'parent_chunk_id': '<chunk_id>'}`
- Chroma (same dictionary shapes; complex operators may fall back to client-side filtering):
  - `{'kind': {'$in': ['chunk','hyde_q']}}`
  - `{'parent_chunk_id': '<chunk_id>'}`

---

## Budget & Backpressure

Tie HYDE into existing controls
- Respect tenant quotas and orchestrator backpressure (depth/age) — skip/defer HYDE when under pressure.
- Hard caps:
  - `HYDE_MAX_VECTORS_PER_DOC` — overall per-doc vector budget.
  - `HYDE_MAX_COST_PER_MINUTE` — generation budget guardrail; fail open (skip HYDE) when exceeded.

Schedule HYDE at low priority so core chunk vectors are unaffected under load.

---

## Failure Handling (no DLQ for HYDE)

Classification and retries
- Classify generation errors into transient (429/5xx/provider timeouts) vs permanent (4xx prompt/content errors).
- Use existing delayed retry queues with exponential backoff and jitter for transient failures.
- On maximum retries or permanent failure, drop the HYDE attempt without DLQ. Record counters and minimal logs (with redaction) including `question_hash` and parent identifiers for operator debugging.

Requeue policy
- No DLQ requeue for HYDE. Operators do not requeue HYDE items; re-generation happens via backfill or normal re‑ingest flows if desired.

Fail-open defaults
- HYDE errors must not block baseline chunk embeddings or retrieval; generation failures simply omit HYDE for the affected chunk.

Metrics
- Increment `hyde_errors_total{type=...}` with reason classification; visualize HYDE error rates in existing embeddings dashboards. HYDE does not contribute to DLQ depth/rate.

---

## Observability & Metrics

Add new metrics
- Histograms: `hyde_generation_latency_seconds`, `hyde_questions_per_chunk` (labels: language, generator).
- Counters: `hyde_questions_generated_total`, `hyde_vectors_written_total`.
- Error-classification counters: `hyde_errors_total{type=prompt_cancelled|rate_limited|provider_error|decode_error}`.

Integrate into existing Prometheus endpoint and Grafana dashboards.

Canary KPIs & Guardrails
- Target cost overhead: ≤ 20% of baseline embeddings spend at N=2–3.
- Retrieval latency delta: ≤ 10–15% vs baseline (with HYDE_K_FRACTION cap).
- KPIs to monitor during canary:
  - % chunks with HYDE generated, vectors growth factor (≈ 1+N)
  - `hyde_generation_failures_total` rate and reasons
  - recall@k uplift on fixed eval set; precision@k stability
  - retrieval latency distribution (p50/p95) with HYDE on vs off

---

## Testing Enhancements

Property-based & multilingual
- Property-based tests for ID/dedupe stability (whitespace/Unicode; content_hash normalization).
- Multilingual tests to verify language-aware generation and retrieval uplift on non‑English text.

Retrieval contracts
- Ensure merge preserves baseline precision when HYDE is disabled or skipped (fail-open).
- Performance sanity tests: with HYDE enabled, retrieval remains within latency SLO; cap HYDE K via `HYDE_K_FRACTION`.

---

## Backfill & Lifecycle (post‑v0 outline)

Backfill CLI (optional)
- Add a helper script to iterate existing chunks and generate HYDE vectors respecting budgets and backpressure.
  - Path: `Helper_Scripts/hyde_backfill.py`
  - Flags:
    - `--tenant <id>` (repeatable), `--collection <name>`
    - `--n <int>` (override HYDE_QUESTIONS_PER_CHUNK), `--dry-run`
    - `--budget-per-minute <float>`, `--priority <low|normal>`
    - `--resume` (skip existing by content_hash + hyde_prompt_version)
    - `--language <auto|en|...>` (override)
  - Behavior:
    - Iterates in pages; respects backpressure; writes idempotently; emits progress + metrics summary.

Prune policy
- When chunks are soft-deleted or replaced (content_hash changes), delete associated HYDE vectors by `parent_chunk_id` and/or `content_hash`.

## Plan & Deliverables

### Phase 0 — Config & Prompts (0.5 day)
- Add HYDE_* flags to `core/config.py` and document in Env_Vars.md.
- Add default prompt entries (reusing prompt loader).

Acceptance
- Flags load from env/config; disabled by default.

### Phase 1 — Generator Helper (0.5 day)
- New module `tldw_Server_API/app/core/Embeddings/hyde.py`:
  - `generate_questions(text: str, n: int, provider: str, model: str, temperature: float, max_tokens: int) -> List[str]`
  - Uses `analyze()`; enforces short outputs, dedupes, trims to N.

Acceptance
- Unit: returns ≤N unique, non-empty lines for typical input; handles empty/short text.

### Phase 2 — Pipeline Wiring (1 day)
- In `embedding_worker.py` (behind `HYDE_ENABLED`):
  - For each chunk item: generate N questions.
  - Append them to the batch with ids `${chunk_id}:q:${i}`, `metadata.kind='hyde_q'`, `metadata.parent_chunk_id=chunk_id`, `hyde_rank=i`, `content_hash`.
  - Propagate idempotency/dedupe keys including the HYDE tuple `(chunk_id, content_hash, hyde_rank)`.
  - Assign `HYDE_PRIORITY` (low) when enqueuing to respect backpressure.

Acceptance
- Unit: embedding worker submits extra N items with correct IDs/metadata when enabled; none when disabled.
- E2E (fake LLM/embeddings): chunk → HYDE → embed → store paths complete without duplicates on re-run.
 - No duplicate `hyde_q` IDs across re-ingests (idempotency proven by ledger and content_hash/prompt_version).



### Phase 3 — Storage (0.25 day)
- Ensure storage worker passes metadata through and idempotent upsert works (already implemented with upsert/update fallback).

Acceptance
- Unit: Upsert invoked with question IDs and metadata; dimension checks preserved.

### Phase 4 — Retrieval Merge (0.5–1 day)
- In `database_retrievers.py` vector-store branch:
  - Query across both kinds (no filter) or explicitly `{'kind': {'$in': ['chunk','hyde_q']}}` when supported.
  - Merge results by `parent_chunk_id` (for hyde_q) or by `id` for chunk hits; compute score = max(score, score + weight_for_hyde).
  - Return deduped chunk-level hits.

Acceptance
- Unit/integration: queries that match HYDE questions surface the correct parent chunk; baseline queries unchanged when HYDE disabled.

### Phase 5 — Observability & Safeguards (0.5 day)
- Metrics: `hyde_questions_generated_total`, `hyde_generation_failures_total`, `hyde_vectors_written_total`.
- Respect existing backpressure; keep HYDE at low priority; optional per-doc budget guard.

Acceptance
- Counters visible in `/metrics`; backpressure blocks only HYDE when load is high.

### Phase 6 — Tests (1 day)
- Unit: generator, worker wiring, idempotent IDs, metadata correctness.
- Adapter integration: upsert + query for both Chroma and pgvector (using existing adapter tests as patterns).
- Retrieval merge logic tests.

Acceptance
- All new tests pass locally; CI picks unit suite by default; live pg tests optional via `PG_TEST_DSN`.
 - Retrieval latency delta within ≤ 15% of baseline under test load; recall@k uplift observed on eval set.

### Phase 7 — Docs & WebUI (0.5 day)
- Docs: Deployment Guide (HYDE section), Design doc updates, Env vars.
- WebUI: small badge/toggle note in Embeddings Admin indicating HYDE is enabled and N.

Acceptance
- Docs compiled; WebUI hint appears for admins when HYDE enabled.

---

## Rollout

- Default off; enable per environment.
- Canary on a subset of media types or tenants; validate retrieval uplift on known queries.
- Monitor: HYDE error rate, added storage volume, and retrieval latency delta.
- Rollback: toggle `HYDE_ENABLED=false`; no data loss; vectors remain but retrieval can filter to `kind='chunk'`.

---

## Risks & Mitigations

- Cost/latency of generation: Keep N small (2–3), concise outputs, low temperature; use cheaper/local provider.
- Index bloat: Adds ~N vectors per chunk; monitor table growth; prune HYDE for soft-deleted content.
- Duplicate or low-quality questions: Dedup and length bounds; allow prompt tuning per domain.
- Retrieval skew: Start with small weight; make configurable; add AB test if needed.

---

## Acceptance Checklist

- [ ] HYDE flags load; disabled by default
- [ ] Generator helper returns deduped, concise questions
- [ ] Embedding worker emits and embeds HYDE items with stable IDs/metadata
- [ ] HYDE IDs use `question_hash` (qhash8) and remain stable across retries/order changes
- [ ] Storage writes via adapter; idempotent upserts verified
- [ ] Retrieval merges results and improves recall in tests
- [ ] Metrics exported; HYDE respects priority/backpressure
- [ ] HYDE failures drop without DLQ; error counters incremented
- [ ] Docs + Env vars updated; WebUI hint present
- [ ] Observed recall uplift on a small, fixed eval set with HYDE enabled vs disabled (e.g., improved recall@k on a 50–200 query set)

---

## Follow-ups (post‑v0)

- Offline backfill tool for existing collections.
- Adapter helper `delete_by_filter` to quickly purge HYDE by parent_chunk_id.
- Learned weighting or re-ranker fusion for HYDE vs chunk signals.
- Budget-aware HYDE (per-tenant quotas integrated with existing guard).
- Prompt variants / multi‑prompt ensemble for robustness.
