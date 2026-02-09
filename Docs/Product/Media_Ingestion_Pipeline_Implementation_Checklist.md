# Media Ingestion Pipeline Implementation Checklist (Remaining Work)

Status: Active as of 2026-02-09 (Stage 3+ remaining scope)
Owner: Core Maintainers
Scope: Remaining delivery for advanced automation, artifact generation, quality scoring, and streaming persistence hardening

## How to Use
- Treat this as the execution companion to `Docs/Product/Media_Ingestion_Pipeline_PRD.md` (remaining scope only).
- Use `Docs/Product/Completed/Media_Ingestion_Pipeline_Completed_PRD.md` and `Docs/Product/Completed/Media_Ingestion_Pipeline_Completed_Checklist.md` for shipped scope.
- Deliver each item with tests and doc updates in the same PR when practical.

## Completed Scope (Archived)
- Foundations through Stage 2 plus initial Stage 3 streaming transcript persistence are archived in:
  - `Docs/Product/Completed/Media_Ingestion_Pipeline_Completed_PRD.md`
  - `Docs/Product/Completed/Media_Ingestion_Pipeline_Completed_Checklist.md`

## Remaining Checklist Items

### 1) Stage 3A: Agentic Ingestion Workflows
- Priority: P1
- Status: Not Started
- Goal: Support policy-gated auto-derived follow-up ingestion actions from initial media signals.
- Primary code areas:
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/`
  - `tldw_Server_API/app/services/media_ingest_jobs_worker.py`
  - Existing Jobs/Scheduler orchestration paths (no parallel infra)
- Acceptance criteria:
  - Follow-up actions are attributable to initiating `media_id`/job context.
  - Resource Governor limits apply via existing controls.
  - Actions are auditable and permission-aware.
- Test requirements:
  - Unit tests for action-plan generation and policy gating.
  - Integration tests for follow-up execution and lineage attribution.

### 2) Stage 3B: Built-in Summary + Highlight Artifacts
- Priority: P1
- Status: Not Started
- Goal: Persist summaries/highlights as version-linked ingestion artifacts.
- Primary code areas:
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py`
  - `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
  - Relevant media endpoint/service orchestration paths
- Acceptance criteria:
  - Artifacts are tied to media/version provenance.
  - Artifact generation failures are non-fatal by default.
  - Artifacts are discoverable to downstream retrieval/UX consumers.
- Test requirements:
  - Unit tests for artifact payload/build and persistence semantics.
  - Integration tests for end-to-end ingest -> artifact availability.

### 3) Stage 3C: Inline Quality Scoring + Remediation
- Priority: P2
- Status: Not Started
- Goal: Emit ingestion quality assessments and actionable remediation suggestions.
- Primary code areas:
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/`
  - `tldw_Server_API/app/core/Metrics/metrics_manager.py`
  - Ingestion result serialization paths
- Acceptance criteria:
  - Quality output includes stable taxonomy fields.
  - Low-quality outcomes include remediation hints.
  - Metrics/logs make degraded patterns observable.
- Test requirements:
  - Unit tests for scoring and remediation mapping.
  - Integration tests validating surfaced quality payloads.

### 4) Stage 3D: Streaming Transcript Persistence Completion
- Priority: P1
- Status: In Progress (initial opt-in partial/final snapshot persistence shipped for `/api/v1/audio/stream/transcribe`)
- Goal: Harden streaming persistence lifecycle semantics beyond initial snapshot writes.
- Current behavior:
  - Opt-in partial/final transcript snapshot upserts are available.
  - Fail-open persistence behavior is implemented.
- Remaining target behavior:
  - Stronger model/media/session metadata normalization.
  - Improved recovery/idempotency semantics and operator visibility.
  - Broader edge/failure/recovery coverage.
- Primary code areas:
  - `tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py`
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Streaming_Unified.py`
  - `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Test requirements:
  - Unit tests for metadata normalization and persistence edge cases.
  - Integration tests for reconnect/recovery/fail-open behavior.

## Suggested Delivery Order
1. Stage 3D persistence hardening (complete the partially shipped slice)
2. Stage 3A agentic workflows
3. Stage 3B summary/highlight artifacts
4. Stage 3C quality scoring/remediation

## Definition of Done for This Checklist
- Each completed item includes:
  - Code changes
  - Unit/integration tests
  - Updated product/design docs
  - Backward-compatibility notes for API/DB behavior
