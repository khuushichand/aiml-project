# Job System Unification PRD

Status: Draft
Owner: Core Maintainers
Target Release: 0.2.x

## 1. Summary
Unify all background job orchestration on the core Jobs subsystem (`tldw_Server_API/app/core/Jobs`) so Embeddings, Chatbooks, and Prompt Studio share a single job lifecycle, status model, and admin surface. This replaces parallel queue managers and temporary shims with one durable, observable job engine.

## 2. Problem Statement
Multiple job systems coexist with overlapping responsibilities:
- Core Jobs manager (SQLite/Postgres, leasing, retries, admin controls): `tldw_Server_API/app/core/Jobs/manager.py`
- Embeddings Redis job manager and queue schemas: `tldw_Server_API/app/core/Embeddings/job_manager.py`, `tldw_Server_API/app/core/Embeddings/queue_schemas.py`
- Prompt Studio job manager and DB tables: `tldw_Server_API/app/core/Prompt_Management/prompt_studio/job_manager.py`
- Chatbooks in-memory job queue shim: `tldw_Server_API/app/core/Chatbooks/job_queue_shim.py`

This duplication creates drift in status semantics, retry behavior, and admin tooling, and it forces each domain to maintain its own worker patterns.

## 3. Unifying Principle (Simplification Cascade)
All background work is a job. A single job model with domain/queue/job_type fields eliminates the need for separate queue implementations, status enums, and ad-hoc admin endpoints.

**Expected deletions**: Embeddings Redis job manager, Prompt Studio job manager, Chatbooks job queue shim, media_embedding_jobs_db, duplicate status enums, and redundant admin endpoints.

## 4. Goals & Success Criteria
- One canonical job lifecycle managed by the core Jobs module.
- A shared status model across domains (`queued`, `processing`, `completed`, `failed`, `cancelled`, `quarantined`).
- Domain-specific work is represented by `domain`, `queue`, and `job_type`, not custom status enums.
- All background job creation and admin actions route through core Jobs APIs.
- Ownership and visibility are enforced via `owner_user_id` scoping for non-admins, with admin endpoints able to view all jobs.

Success metrics:
- No runtime module instantiates its own job manager or queue backend outside `app/core/Jobs`.
- Embeddings, Chatbooks, and Prompt Studio workers use the Jobs worker SDK.
- Legacy job shims removed or reduced to thin adapters until full migration is complete.
- Multi-stage pipelines use idempotency keys and explicit chaining for 0.2.x; dependency edges land in Phase 4 post-adapter migration.
- Performance meets defined throughput/latency targets compared to baseline (see Testing Plan).

## 5. Non-Goals
- UI changes (no Admin UI or `tldw-frontend`).
- Rewriting the embeddings pipeline logic; only the orchestration layer changes.
- Adding new queue backends beyond the existing SQLite/Postgres Jobs storage.

## 6. In Scope
- Core Jobs becomes the single source of truth for background work.
- New adapters to migrate Embeddings, Chatbooks, and Prompt Studio job creation to Jobs.
- Status mapping and event streaming consistent across domains.
- Updated admin endpoints to operate on a single jobs table.

## 7. Out of Scope
- Changes to resource governance policies.
- Provider configuration or HTTP client changes.
- Database schema migrations beyond Jobs-related tables.

## 8. Functional Requirements
### 8.1 Canonical Job Model
- Jobs are identified by `{domain, queue, job_type}` with a unified status model.
- Pipeline stages (e.g., embeddings chunking/embedding/storing) are represented as separate job types or queues, not custom status values.
- Multi-stage pipelines create a root job record (e.g., `job_type=embeddings_pipeline`) that represents the public `job_id`; stage jobs reference `root_job_uuid` and `parent_job_uuid` in payloads for lineage.
- Public endpoints continue to expose coarse status values only; stage detail remains admin/internal via `job_type`/`queue` (or `current_stage`), not `status`.
- Embeddings priority (0-100) maps to Jobs priority (1-10) using `jobs_priority = clamp(1, 10, int(embedding_priority / 10))`.
- Payloads must be JSON-serializable and avoid large inline data (store large artifacts in DB/files and pass references).
- User-scoped jobs set `owner_user_id` for access control and quota enforcement.

### 8.2 Standard Lifecycle Operations
- create, acquire, renew, complete, fail, cancel, quarantine via `JobManager`.
- Worker leasing and retries must match existing Jobs semantics.
- Admin controls (pause/resume/drain, retry-now, reschedule, prune) remain available for all domains.

### 8.3 Domain Adapters
- Embeddings: replace Redis queues with Jobs entries; each stage becomes a job_type or queue transition.
- Chatbooks: replace `JobQueueShim` with a Jobs-backed adapter (domain: `chatbooks`).
- Prompt Studio: replace its internal job manager with Jobs (domain: `prompt_studio`).

### 8.4 Compatibility and Migration
- Provide thin compatibility adapters where needed to preserve API behavior during migration.
- Maintain existing endpoint contracts; only internal job orchestration changes.
- Document a per-domain status/field mapping matrix to make adapter behavior explicit and reviewable.

### 8.5 Job Chaining and Idempotency
- Use separate job_type values per stage; do not add custom status values.
- Stage completion is idempotent in the domain DB (unique constraint on `(artifact_id, stage, config_version)`); handlers must no-op if already completed.
- Enqueue the next stage only after the current stage's durable write; use idempotency_key = `f"{artifact_id}:{stage}:{config_version}"` for the next job to avoid duplicates.
- Track lineage via trace_id and include `parent_job_uuid`/`root_job_uuid` (Jobs uuid) in job payloads for debugging and public job lookups (no schema change needed).
- Root job status is derived from the latest stage job; update root job `status`, `progress_percent`, and `result` fields as stage jobs advance.
- For fan-out/fan-in, use a "join" job_type that checks child completion counts in the domain DB before enqueueing the next stage; it remains idempotent using the same key scheme.

Root job update example (embeddings):
```json
{
  "root_job": {
    "job_type": "embeddings_pipeline",
    "payload": {
      "media_id": 123,
      "root_job_uuid": "uuid-root",
      "current_stage": "embedding"
    },
    "result": {
      "embedding_model": "text-embedding-3-small",
      "embedding_count": 420,
      "chunks_processed": 420,
      "total_chunks": 420
    },
    "progress_percent": 100.0,
    "status": "completed"
  }
}
```

### 8.6 DAG Dependencies (Phase 4, post-adapter migration)
- Deferred until after adapters; 0.2.x relies on explicit chaining + idempotency keys only.
- Add a `job_dependencies` table to model edges by `jobs.uuid` (`job_uuid`, `depends_on_job_uuid`) with a composite unique constraint and indexes on both columns.
- Update job acquisition to only return jobs whose dependencies are completed.
- If any dependency fails or is cancelled, downstream jobs are cancelled with a `dependency_failed` reason unless explicitly overridden.
- Enqueue-time validation rejects self-dependencies, cycles, and cross-owner or cross-domain edges (dependencies must share `owner_user_id` and `domain`).

Sample DDL (SQLite):
```sql
CREATE TABLE IF NOT EXISTS job_dependencies (
  job_uuid TEXT NOT NULL,
  depends_on_job_uuid TEXT NOT NULL,
  created_at TEXT DEFAULT (DATETIME('now')),
  PRIMARY KEY (job_uuid, depends_on_job_uuid),
  FOREIGN KEY (job_uuid) REFERENCES jobs(uuid) ON DELETE CASCADE,
  FOREIGN KEY (depends_on_job_uuid) REFERENCES jobs(uuid) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_job_dependencies_job ON job_dependencies(job_uuid);
CREATE INDEX IF NOT EXISTS idx_job_dependencies_dep ON job_dependencies(depends_on_job_uuid);
```

Sample DDL (Postgres):
```sql
CREATE TABLE IF NOT EXISTS job_dependencies (
  job_uuid TEXT NOT NULL,
  depends_on_job_uuid TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (job_uuid, depends_on_job_uuid),
  FOREIGN KEY (job_uuid) REFERENCES jobs(uuid) ON DELETE CASCADE,
  FOREIGN KEY (depends_on_job_uuid) REFERENCES jobs(uuid) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_job_dependencies_job ON job_dependencies(job_uuid);
CREATE INDEX IF NOT EXISTS idx_job_dependencies_dep ON job_dependencies(depends_on_job_uuid);
```

### 8.7 Access Control and Visibility
- Non-admin API calls must scope job reads/writes by `owner_user_id` (and any domain allowlist).
- Admin endpoints can view and manage jobs across all users.
- Bulk operations (cancel/retry/reschedule) enforce the same scoping rules as list/detail actions.
- Job events/audit logs include `owner_user_id` for traceability.
- Dependency edges are constrained to the same `owner_user_id` and `domain`; cross-owner/domain edges are rejected.
- Single-user mode: set `owner_user_id = SINGLE_USER_FIXED_ID` for all user-initiated jobs to preserve consistent scoping.
- System jobs (maintenance, pruning, migrations) use `owner_user_id = "system"` and are admin-only in read/list endpoints.
- Admin actions on behalf of a user set `owner_user_id` to the target user id and include `actor_user_id` in payload/audit metadata.
- Migration/backfill jobs must either use the target `owner_user_id` or `"system"`; never leave `owner_user_id` null.

### 8.8 Storage, Indexing, and Retention
- Maintain indexes on `(domain, queue, job_type, status, available_at)` and `owner_user_id` to support common queries.
- `job_dependencies` must index both columns and support fast "all deps completed" checks.
- Enforce payload size guardrails with a configurable maximum and JSON truncation metrics.
- Define a retention policy for completed/failed/cancelled jobs (with optional archive) to prevent unbounded growth.

Retention defaults (proposed):
- Completed jobs: retain 30 days (default `jobs/prune` payload: `older_than_days=30`).
- Failed/cancelled jobs: retain 60 days.
- Quarantined jobs: retain 90 days (requires prune support for `quarantined` status).
- Prune cadence: daily scheduled job (off-peak), using `/api/v1/jobs/prune` with explicit domain/queue scopes.
- Archive policy: default `JOBS_ARCHIVE_BEFORE_DELETE=false`; enable with `JOBS_ARCHIVE_BEFORE_DELETE=true` and `JOBS_ARCHIVE_COMPRESS=true` in production.

### 8.9 Endpoint Contract Mapping
- Provide a mapping table per domain that lists old status/fields and new Jobs equivalents.
- Adapters must translate legacy status to canonical statuses without changing external API behavior.
- External endpoints currently expose only coarse job statuses for media embeddings; stage detail is limited to admin orchestrator/metrics and internal job managers. Preserve this by mapping stage detail to `job_type`/`current_stage`, not `status`, in public responses. `/api/v1/media/embeddings/jobs` should move from `media_embedding_jobs_db` to the Jobs table.
- Public `/api/v1/media/embeddings/jobs` responses should continue to return legacy `chunks_processed`/`embedding_count`. Add `progress_percent` and `total_chunks` only when `EMBEDDINGS_JOBS_EXPOSE_PROGRESS=true` (feature flag), otherwise omit these new fields to preserve legacy behavior.

Mapping matrix template:
| Domain | Legacy Endpoint | Legacy Status | Legacy Field | Jobs Status | Jobs Field | Adapter Rule | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <domain> | <path> | <legacy_status> | <legacy_field> | <jobs_status> | <jobs_field> | <translation_rule> | <notes> |
Example rows (current codebase):
| Domain | Legacy Endpoint | Legacy Status | Legacy Field | Jobs Status | Jobs Field | Adapter Rule | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| embeddings | internal: Embeddings JobManager.get_job_status (Redis) | pending | status | queued | status | map `pending` -> `queued` | JobStatus in tldw_Server_API/app/core/Embeddings/queue_schemas.py |
| embeddings | internal: Embeddings JobManager.get_job_status (Redis) | chunking/embedding/storing/processing | status | processing | status | map stage statuses -> `processing`; stage becomes `job_type` | stage values become job_type |
| embeddings | internal: Embeddings JobManager.get_job_status (Redis) | completed | status | completed | status | pass-through | |
| embeddings | internal: Embeddings JobManager.get_job_status (Redis) | failed | status | failed | status | pass-through | |
| embeddings | internal: Embeddings JobManager.get_job_status (Redis) | cancelled | status | cancelled | status | pass-through | |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | processing | status | processing | status | map `processing` -> `processing` | job_id maps to root job uuid |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | completed | status | completed | status | pass-through | job_id maps to root job uuid |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | failed | status | failed | status | pass-through | job_id maps to root job uuid |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | n/a | embedding_model | n/a | result.embedding_model | copy from root job result | preserve legacy field |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | n/a | embedding_count | n/a | result.embedding_count | copy from root job result | preserve legacy field |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | n/a | chunks_processed | n/a | result.chunks_processed | copy from root job result | preserve legacy field |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | n/a | error | n/a | error_message | map error_message -> error | preserve legacy field |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | n/a | total_chunks | n/a | result.total_chunks | copy from root job result | gated by EMBEDDINGS_JOBS_EXPOSE_PROGRESS |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | n/a | progress_percent | n/a | progress_percent | copy from root job | gated by EMBEDDINGS_JOBS_EXPOSE_PROGRESS |
| chatbooks | /api/v1/chatbooks/export/jobs/{job_id} | pending | status | queued | status | map `pending` -> `queued` | ExportStatus in tldw_Server_API/app/core/Chatbooks/chatbook_models.py |
| chatbooks | /api/v1/chatbooks/export/jobs/{job_id} | in_progress | status | processing | status | map `in_progress` -> `processing` | |
| chatbooks | /api/v1/chatbooks/export/jobs/{job_id} | expired | status | cancelled | status | map `expired` -> `cancelled` (reason=expired) | |
| chatbooks | /api/v1/chatbooks/export/jobs/{job_id} | n/a | job_id | n/a | uuid | map job_id -> jobs.uuid | |
| chatbooks | /api/v1/chatbooks/import/jobs/{job_id} | validating | status | processing | status | map `validating` -> `processing`; job_type=`validate_chatbook` | ImportStatus in chatbook_models.py |
| prompt_studio | /api/v1/prompt-studio/optimizations/{job_id} | queued | status | queued | status | 1:1 mapping for queued/processing/completed/failed/cancelled | JobStatus in prompt_studio/job_manager.py |
| prompt_studio | /api/v1/prompt-studio/optimizations/{job_id} | n/a | job_type | n/a | job_type | map evaluation/optimization/generation -> same job_type values | JobType in prompt_studio/job_manager.py |

Expanded mapping matrix (draft, per domain):

Embeddings (public endpoints)
| Domain | Legacy Endpoint | Legacy Status | Legacy Field | Jobs Status | Jobs Field | Adapter Rule | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| embeddings | /api/v1/media/embeddings/jobs | pending/processing/chunking/embedding/storing/completed/failed/cancelled | status | queued/processing/completed/failed/cancelled | status | map stage statuses -> `processing`; `pending` -> `queued` | list endpoint |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | pending/processing/chunking/embedding/storing/completed/failed/cancelled | status | queued/processing/completed/failed/cancelled | status | map stage statuses -> `processing`; `pending` -> `queued` | job_id maps to root job uuid |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | n/a | job_id | n/a | uuid | map job_id -> jobs.uuid | preserve legacy job_id format |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | n/a | embedding_model | n/a | result.embedding_model | copy from root job result | preserve legacy field |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | n/a | embedding_count | n/a | result.embedding_count | copy from root job result | preserve legacy field |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | n/a | chunks_processed | n/a | result.chunks_processed | copy from root job result | preserve legacy field |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | n/a | error | n/a | error_message | map error_message -> error | preserve legacy field |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | n/a | total_chunks | n/a | result.total_chunks | copy from root job result | gated by EMBEDDINGS_JOBS_EXPOSE_PROGRESS |
| embeddings | /api/v1/media/embeddings/jobs/{job_id} | n/a | progress_percent | n/a | progress_percent | copy from root job | gated by EMBEDDINGS_JOBS_EXPOSE_PROGRESS |
| embeddings | /api/v1/media/{media_id}/embeddings/status | n/a | has_embeddings | n/a | n/a | no change; read from media DB | Jobs not in this path |

Chatbooks (public endpoints)
| Domain | Legacy Endpoint | Legacy Status | Legacy Field | Jobs Status | Jobs Field | Adapter Rule | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| chatbooks | /api/v1/chatbooks/export/jobs | pending/in_progress/completed/failed/cancelled/expired | status | queued/processing/completed/failed/cancelled | status | map `pending` -> `queued`; `in_progress` -> `processing`; `expired` -> `cancelled` | list endpoint |
| chatbooks | /api/v1/chatbooks/export/jobs/{job_id} | pending/in_progress/completed/failed/cancelled/expired | status | queued/processing/completed/failed/cancelled | status | same as export list mapping | job_id maps to jobs.uuid |
| chatbooks | /api/v1/chatbooks/export/jobs/{job_id} | n/a | download_url | n/a | result.download_url | copy from job result | preserve legacy field |
| chatbooks | /api/v1/chatbooks/export/jobs/{job_id} | n/a | expires_at | n/a | result.expires_at | copy from job result | preserve legacy field |
| chatbooks | /api/v1/chatbooks/import/jobs | pending/validating/in_progress/completed/failed/cancelled | status | queued/processing/completed/failed/cancelled | status | map `pending` -> `queued`; `validating`/`in_progress` -> `processing` | list endpoint |
| chatbooks | /api/v1/chatbooks/import/jobs/{job_id} | pending/validating/in_progress/completed/failed/cancelled | status | queued/processing/completed/failed/cancelled | status | validating -> job_type `validate_chatbook`; in_progress -> `import_chatbook` | job_id maps to jobs.uuid |
| chatbooks | /api/v1/chatbooks/import/jobs/{job_id} | n/a | items_imported | n/a | result.items_imported | copy from job result | preserve legacy field |
| chatbooks | /api/v1/chatbooks/import/jobs/{job_id} | n/a | conflicts_found | n/a | result.conflicts_found | copy from job result | preserve legacy field |
| chatbooks | /api/v1/chatbooks/import/jobs/{job_id} | n/a | progress | n/a | progress_percent | copy from job | preserve legacy field |

Prompt Studio (public endpoints)
| Domain | Legacy Endpoint | Legacy Status | Legacy Field | Jobs Status | Jobs Field | Adapter Rule | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| prompt_studio | /api/v1/prompt-studio/optimizations/{job_id} | queued/processing/completed/failed/cancelled | status | queued/processing/completed/failed/cancelled | status | 1:1 mapping | job_id maps to jobs.uuid |
| prompt_studio | /api/v1/prompt-studio/optimizations/{job_id} | n/a | job_type | n/a | job_type | map evaluation/optimization/generation -> same | preserve legacy field |
| prompt_studio | /api/v1/prompt-studio/optimizations/{optimization_id}/history | queued/processing/completed/failed/cancelled | status | queued/processing/completed/failed/cancelled | status | map legacy job status in timeline entries | job_id maps to jobs.uuid |

### 8.10 Backpressure, Quotas, and Payload Guardrails (Defaults)
Payload guardrails (defaults):
- `JOBS_MAX_JSON_BYTES=1048576` (1 MiB) for payload and result JSON blobs.
- `JOBS_JSON_TRUNCATE=false` in production; if enabled, log truncation metrics and set `result.truncated=true`.

Recommended per-domain quotas (env keys support domain/user overrides; see `JobManager._quota_get`):
| Domain | JOBS_QUOTA_MAX_QUEUED | JOBS_QUOTA_MAX_INFLIGHT | JOBS_QUOTA_SUBMITS_PER_MIN | Notes |
| --- | --- | --- | --- | --- |
| embeddings | 5000 | 200 | 600 | Higher limits to avoid starving media pipelines |
| chatbooks | 50 | 2 | 20 | Aligns with chatbooks concurrent-job caps |
| prompt_studio | 500 | 20 | 120 | Suitable for evaluations/optimizations |

Backpressure behavior:
- On quota exceed, creation returns 429 with `Retry-After` (1s default, configurable).
- Quotas can be disabled by setting the value to `0` (current JobManager behavior).

## 9. Design Overview
### 9.1 Core Jobs as Canonical Engine
- Core Jobs already provides leasing, retries, admin tools, metrics, and event streams. It becomes the only backend used by background work.
- Domains define job types and queues; shared worker SDK handles polling and acknowledgments.

### 9.2 Payload and Artifact Strategy
- Large job data (embedding chunks, large transcripts) must be stored in the appropriate domain database or file store.
- Jobs payloads store references: `media_id`, `artifact_id`, `stage`, `config_version`.

### 9.3 Worker SDK Standardization
- Workers across domains use `app/core/Jobs/worker_sdk.py` to acquire and acknowledge jobs.
- Retry and quarantine behavior is driven by Jobs config and shared policies.

### 9.4 Dependency Model for DAGs
- `job_dependencies` stores edges; a job is eligible for acquisition only when all dependencies are `completed`.
- Dependency evaluation happens in the acquire query to avoid workers handling blocked jobs.
- Dependency queries must be indexed to avoid full-table scans on large job graphs.

## 10. Migration Plan
### Phase 0: Inventory and Mapping
- Inventory all job types/status enums across domains.
- Define canonical `domain/queue/job_type` mappings and payload reference schemas.
- Capture baseline throughput and latency metrics for current job systems (Redis embeddings pipeline).
- Inventory media_embedding_jobs_db usage and enumerate external job status contracts.

### Phase 1: Core Jobs Adapters
- Implement adapters for Embeddings, Chatbooks, and Prompt Studio that map their APIs to Jobs.
- Add migration flags (per-domain) to allow staged cutover.
- Produce the status/field mapping matrix as part of adapter implementation.
- Prompt Studio job history remains read-only during migration; no backfill into Jobs for 0.2.x.
- Add a Jobs-backed adapter for `/api/v1/media/embeddings/jobs` and migrate reads to Jobs table.

### Phase 2: Worker Migration
- Migrate embeddings workers to Jobs worker SDK.
- Migrate chatbooks import/export workers to Jobs worker SDK.
- Migrate prompt studio workers to Jobs worker SDK.

### Phase 3: Delete Legacy Systems
- Remove Embeddings Redis job manager, Prompt Studio job manager, and Chatbooks job queue shim.
- Remove media_embedding_jobs_db and related persistence helpers.
- Remove duplicated status enums and admin paths.

### Phase 4: DAG Dependencies (Post-Adapter Migration)
- Add `job_dependencies` table and indexes.
- Gate job acquisition on dependency completion; implement dependency_failed cascades.
- Enforce same-owner/domain constraints and cycle checks at enqueue time.
- Add tests and metrics for dependency eligibility and fan-out/fan-in joins.

### Rollback and Cutover Rules
- Cutover sequence: stop legacy workers, drain or cancel legacy queues, enable Jobs-backed adapters, then start Jobs workers.
- If regressions are detected, stop Jobs workers, disable Jobs adapters via flags, and restore legacy workers (dev-only fallback).
- Avoid dual writers; only one system should enqueue or mutate jobs for a domain at a time.

### Cutover Flags and In-Flight Handling (Defaults)
Proposed flags (env):
- `EMBEDDINGS_JOBS_BACKEND=redis|jobs` (default `redis` until Phase 2 cutover).
- `PROMPT_STUDIO_JOBS_BACKEND=prompt_studio|core` (default `prompt_studio` until Phase 2 cutover).
- `CHATBOOKS_JOBS_BACKEND=core|prompt_studio` (default `core`; keep as-is, no cutover required).
- `JOBS_ADAPTER_READ_LEGACY_{DOMAIN}=true|false` (default `true` during Phase 1-2; `false` after legacy removal).
- `JOBS_ADAPTER_WRITE_LEGACY=false` (always; no dual writes).

In-flight handling:
- Freeze legacy enqueue first (`*_BACKEND=jobs`, `JOBS_ADAPTER_WRITE_LEGACY=false`).
- Let legacy workers drain for a fixed window (recommend 24h); after that, cancel remaining legacy jobs with `reason="migration_cutover"`.
- Read-path fallback during transition: if a job id is not found in Jobs and `JOBS_ADAPTER_READ_LEGACY_{DOMAIN}=true`, consult legacy storage and map status; Jobs always take precedence.

## 11. Risks & Mitigations
- Risk: Embeddings throughput regresses without Redis streams.
  - Mitigation: keep queue concurrency configurable and tune Jobs polling/lease sizes; use artifact references to avoid large payloads.
- Risk: Payload size exceeds Jobs storage limits.
  - Mitigation: require large data externalization and enforce payload size checks.
- Risk: Jobs table growth degrades query performance.
  - Mitigation: define retention/archival policies and prune completed jobs on a schedule.
- Risk: Dependency edges cause acquisition bottlenecks or deadlocks if dependency state is incorrect.
  - Mitigation: enforce dependency integrity checks at enqueue time; add periodic audits to flag jobs blocked beyond SLA.
- Risk: Join jobs incorrectly advance pipelines due to missing child records.
  - Mitigation: require join jobs to read authoritative child completion counts from domain DB with idempotent checkpoints.

## 12. Testing Plan
- Unit tests for adapters mapping job types and statuses.
- Integration tests for each domain using Jobs lifecycle (submit, process, complete, fail).
- Load test embeddings worker throughput with Jobs backend against baseline targets.
- Phase 4: unit tests for dependency eligibility (blocked vs. ready), cancellation cascades, and join job idempotency.
- Phase 4: integration tests for multi-stage pipelines with fan-out/fan-in (including retries) using dependency edges.
- Performance gates: throughput >= 90% of baseline; p95 queue latency <= 1.5x baseline under equivalent load.

### 12.1 Embeddings Throughput Validation (Redis vs Jobs)
Goal: Validate that Jobs can sustain embeddings pipeline throughput without a high-throughput transport requirement.

Benchmark design:
- Workload: 3-stage pipeline (chunking → embedding → storage) on a fixed corpus (e.g., 1k media items, 50k chunks total).
- Baseline: Redis streams pipeline with current worker config.
- Candidate: Jobs-backed pipeline with equivalent worker concurrency and batch sizes.
- Environment: same hardware, same model/provider, same vector store, same input corpus.
- Metrics:
  - Throughput: chunks/sec and media items/sec per stage and end-to-end.
  - Latency: p50/p95 queue age and end-to-end job duration.
  - Error rate: failed jobs per 1k items.
- Pass criteria: >= 90% baseline throughput and <= 1.5x p95 queue latency; no error-rate regression.
- Artifacts: store run config, commit hash, and metrics summary in a short doc under `Docs/Performance/` for repeatability.

## 13. Acceptance Criteria
- All new background work is created through core Jobs APIs.
- Embeddings, Chatbooks, and Prompt Studio no longer instantiate their own job managers.
- Jobs admin endpoints report all domains accurately.
- Admin endpoints provide cross-user visibility; non-admin endpoints enforce owner_user_id scoping.
- Domain adapters include an explicit status/field mapping matrix.
- Multi-stage pipelines use idempotency keys to prevent duplicate processing; dependency edges ship in Phase 4 post-adapter migration.
- Public endpoints preserve coarse status semantics; stage detail remains admin/internal.
- Retention policy is implemented and validated for completed/failed/cancelled jobs.
- Performance targets in Testing Plan are met.
- Embeddings throughput validation results are documented with baseline vs Jobs comparison.
- `/api/v1/media/embeddings/jobs` reads from the Jobs table; media_embedding_jobs_db is removed.

## 14. Open Questions
- Do any embedding stages require a high-throughput transport that Jobs cannot provide today? - Validated via Section 12.1 benchmark; mark resolved after results are recorded.
