# Prompt Studio — Improvement Plan (Phase 1)

Here’s a concise, high‑ROI improvement plan for Prompt Studio. Grouped so you can pick what to tackle first.

## Current Status Snapshot
- Completed: Core idempotency flow (projects/prompts/optimizations) with metrics; CI matrix for sqlite/postgres; expanded strategy validation + coverage; concurrency harness + PG advisory lock plumbing; metrics instrumentation and docs refresh; job leasing with worker-owned leases + renewals.
- In Progress: Job leasing extras (optional PG advisory heartbeat/listen-notify polish); SQLite hardening polish; documentation of full DX scenarios.
- Not Started: Reproducibility snapshots; prompt version lineage auto-creation; FTS-backed search; cancellation hooks; tracing spans; CLI tooling; fine-grained rate limits; max budget enforcement.

## Architecture
- [Done] Single backend per run: Heavy Prompt Studio test suites pin `TLDW_PS_BACKEND` and reuse module-scope clients to avoid cross-backend flake.
- [In Progress] Background jobs: Visibility timeout via `leased_until`, worker-owned `lease_owner` tracking, and async heartbeat in JobManager are live; PG path uses advisory locks where available. Outstanding: optional NOTIFY/LISTEN wakeups and dead-letter policy polish.
- [Todo] Reproducibility: Persist random seeds, provider/model identifiers, and env snapshot (e.g., tokenizer version, temperature) on evaluations/optimizations.

## API & Data Model
- [Done] Idempotency everywhere: Create endpoints accept `Idempotency-Key`, return canonical entities, and export hit/miss metrics.
- [In Progress] Stronger validation: Strategy-specific validators and tests exist, but JSON schema coverage for optimization_config + unknown-key rejection still pending.
- [Todo] Versioning improvements: Auto-create prompt version on “best result” and record lineage in join table.
- [Todo] Search: Wire test-case search to FTS (SQLite FTS5 / PG tsvector) with indexes and migrations.

## Reliability & Concurrency
- [In Progress] SQLite: Busy timeout and jittered retries exist, WAL toggle wired. Outstanding: identify remaining write hotspots and document guidance for WAL defaults.
- [In Progress] Postgres: Advisory locks on acquire implemented; contention tests and optional LISTEN/NOTIFY wakeups still open.
- [Todo] Cancellation: JobProcessor needs periodic cancellation checks and explicit aborted status handling.

## Performance
- [Todo] Bulk paths: Keep bulk test-case insert batch size adaptive (e.g., 500–1000 on PG, 100–200 on SQLite) with a single transaction for each batch.
- [In Progress] Indexes: Created_at indexes for optimizations/iterations done; remaining hot-path indexes (test_cases, evaluations, JSONB/tsvector) to add.
  - test_cases(project_id, is_golden), test_cases(project_id, tags) if normalized, evaluations(project_id, prompt_id), optimizations(project_id, status), optimization_iterations(optimization_id, created_at DESC).
  - PG: GIN on JSONB fields used for filtering; tsvector index for “search”.
- [Todo] Metrics-driven budgets: Accept optional max_tokens / max_cost per optimization and enforce caps per iteration.

## Observability
- [Done] Metrics: Counters/histograms instrumented (`prompt_studio.jobs.*`, idempotency hit/miss, advisory locks) with coverage in integration tests.
  - prompt_studio.tests.total/status, evaluations.duration_seconds, optimizations.iterations, jobs.duration_seconds/status, db.latency_ms{op=read/write}.
- [Todo] Tracing: Add span boundaries for each API call and each job iteration; tag with backend=sqlite|postgres, project_id, optimization_id.

## Security
- [Todo] Payload hardening: Reuse the code‑injection detection added elsewhere for prompt templates (Jinja sandboxed environment, no unsafe filters).
- [Todo] Rate limits: Add fine-grained limits on bulk endpoints and optimization creation; enforce user/project quotas.

## DX, Docs & Tests
- [In Progress] Docs: CI env vars documented; still need examples for sqlite/postgres runs, WAL opt-in, and `DISABLE_HEAVY_STARTUP`.
  - sqlite run, postgres run (with TLDW_TEST_POSTGRES_REQUIRED=1), WAL opt‑in, DISABLE_HEAVY_STARTUP=1 for tests.
- [Todo] Quick CLI: A small CLI to create projects/prompts, bulk import cases, run evals/optimizations locally with mock LLMs for demos.
- [Todo] Tests to add:
  - PG‑only integration that validates FTS search and JSONB filters.
  - Background‑task path without TEST_MODE: spawn job, poll status until done, assert iteration logs.
  - Concurrency: 3–5 parallel optimizations over a small set; verify no lock errors and correct iteration counts.
  - Idempotency: Duplicate submits across all create endpoints return the same IDs.

## Suggested Immediate Steps
- Harden job leasing: document worker-owned lease flow, add optional PG advisory heartbeat/listen-notify hook, and extend stress coverage if gaps remain.
- Close out SQLite tuning: document WAL guidance, confirm jittered retries handle remaining hotspots.
- Extend validation: add JSON schema enforcement/unknown-key rejection for optimization_config payloads.
- Update docs/examples: include full local vs postgres CLI samples with env var snippets.

---

## Phase 1 Progress Update (Incremental)

- CI matrix wired (sqlite|postgres):
  - Added `.github/workflows/prompt-studio.yml` with matrix over `TLDW_PS_BACKEND=sqlite|postgres`.
  - PG service provisioned; fixtures pick up `POSTGRES_TEST_*` and require PG in the postgres leg (`TLDW_TEST_POSTGRES_REQUIRED=1`).
  - Runs unit tests and non-slow integration tests for Prompt Studio.

- Strategy validation — next round:
  - beam_search: added `length_penalty` bounds [0,2] and `candidate_reranker` policy validation; kept `diversity_rate` and `max_candidates` checks.
  - anneal: added `step_size` (>0), `epochs` (>=1), and linear schedule consistency: `step_size * epochs` ≤ (`initial_temp - min_temp`).
  - genetic: added `crossover_operator` enum validation: `one_point|two_point|uniform`.
  - hyperparameter/random: added `max_tokens_range` validation `[min, max]` within `1..100000`.
  - Unit tests: `tests/prompt_studio/unit/test_strategy_validation_next.py` (positive/negative cases).

- Concurrency — multiprocessing harness:
  - Added `tests/prompt_studio/integration/test_concurrency_multiprocessing.py` to exercise parallel `acquire_next_job` across processes for both backends.
  - Reconnects to the same DB (sqlite path or PG config) per process; asserts uniqueness and full drain of the queue.
  - SQLite hardening: kept jittered retries on hot paths (create/update/acquire/retry) and added an atomic UPDATE guard mirroring the SELECT conditions to avoid racey updates.

- Lease ownership guard:
  - JobManager instances now normalise worker IDs and stamp `lease_owner` on acquisition so renewals are scoped to the active worker.
  - Renewals require matching workers; enforced via `tests/prompt_studio/integration/test_job_leasing.py::test_lease_owner_enforced_dual_backend`.

- Postgres advisory locks:
  - Acquire path already gates with `pg_try_advisory_lock` and immediately unlocks; terminal states attempt unlock.
  - Added tests to assert unlock behavior on completion and retry: `tests/prompt_studio/integration/test_pg_advisory_locks.py`.

- Metrics — wired end-to-end:
  - JobManager now updates per-type gauges on create/acquire/terminal state and observes `prompt_studio.jobs.duration_seconds`.
  - Queue latency observed on acquire for both backends: `prompt_studio.jobs.queue_latency_seconds{job_type}` (Postgres parity done).
  - Lease heartbeat increments `prompt_studio.jobs.lease_renewals_total{job_type}`.
  - Retries/failures increment `prompt_studio.jobs.retries_total{job_type}` and `prompt_studio.jobs.failures_total{job_type,reason}`; reclaims counted in PG path.
  - Idempotency metrics added in optimization create: `prompt_studio.idempotency.hit_total|miss_total{entity_type}`.
  - PG advisory lock metrics on acquire: `prompt_studio.pg_advisory.lock_attempts_total`, `locks_acquired_total`, `unlocks_total`.
  - Status endpoint refreshes per-type gauges (queued, processing, backlog) + `stale_processing` on each call.

- Metrics tests added:
  - Lifecycle metrics: `tests/prompt_studio/integration/test_metrics_job_paths.py` asserts queued/processing gauges, queue latency, and duration observation.
  - Idempotency hit/miss: `tests/prompt_studio/integration/test_idempotency_metrics.py` (dual-backend client; stubs metrics).
  - PG advisory lock metrics: `tests/prompt_studio/integration/test_pg_advisory_lock_metrics.py` (PG-only; skips if PG unavailable).

- Docs:
  - Added a “Metrics” section in `Docs/API-related/Prompt_Studio_API.md` and a quick reference in `README.md`.

### TODO (Phase 2+)
- PG advisory locks on acquire: deeper tests under contention and terminal unlock verification.
- Broaden bounds/schema for future strategy knobs (`beam_search` reranker policy details, anneal schedules, genetic operator options) as they are finalized.
- Observability: per-job-type counters and processing duration histogram.

## What Remains (Phase 1 wrap + Phase 2 seed)

- Phase 1 wrap (optional polish)
  - Add a PG-only stress test to hammer advisory locking under contention (multi-process), assert no double-processing and that unlock counters match.
  - Add an idempotency concurrency test (threads/processes) to ensure canonical entity is returned without duplicates.
  - Extend status endpoint example with metrics snapshot to aid validation.

- Phase 2 candidates
  - Background-task path test without TEST_MODE: spawn optimization and poll status until completion with small dataset, assert iteration logs.
  - PG FTS coverage for Prompt Studio search (tsvector) with a couple of targeted queries.
  - Tracing: spans around optimization iterations and DB hot paths; tag with backend, project_id, optimization_id.
  - Performance tuning: batching and connection settings for high-throughput runs; optional LISTEN/NOTIFY for PG job wakeups.
  - Additional strategy validation knobs once semantics are finalized.
