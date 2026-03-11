# Workflows Diagnostics and Improvements Design

Date: 2026-03-11
Status: Approved

## Summary

Improve the Workflows module with equal weight for workflow authors, operators, and API consumers, while making failed-run diagnosis the first vertical slice. The current runtime already persists substantial execution state, but troubleshooting is still exposed as low-level events, logs, and DB-oriented runbook steps rather than a coherent diagnostics model.

The recommended design adds a structured diagnostics layer on top of the existing run/event/artifact ledger. It introduces explicit step replay capabilities, separates logical step runs from per-attempt retry records, defines a layered failure taxonomy, and exposes a first-class run investigation API plus shared run-inspection UI. The first milestone should also add server-authoritative preflight validation so author-time failures move earlier in the lifecycle.

## Investigated Context

- Runtime and state management already exist in:
  - `tldw_Server_API/app/core/Workflows/engine.py`
  - `tldw_Server_API/app/core/DB_Management/Workflows_DB.py`
- Public API already exposes run summaries, events, artifacts, control, approvals, and DLQ endpoints:
  - `tldw_Server_API/app/api/v1/endpoints/workflows.py`
  - `tldw_Server_API/app/api/v1/schemas/workflows.py`
- Existing operational and design docs are present, but they are still largely raw and operator-oriented:
  - `Docs/Operations/Workflows_Debugging.md`
  - `Docs/Operations/Workflows_Runbook.md`
  - `Docs/Design/Workflows.md`
- Existing workflow editor execution UX is not yet a real server-backed run inspector:
  - `apps/packages/ui/src/components/WorkflowEditor/ExecutionPanel.tsx`
  - `apps/packages/ui/src/store/workflow-editor.ts`

## User-Confirmed Scope

1. Review the Workflows module and brainstorm improvements with equal weight for authors, operators, and API users.
2. Prioritize failed-run diagnostics as the first vertical slice.
3. Allow additive API/schema/model changes and, if necessary, larger model changes.
4. Pressure-test the design before freezing it, then incorporate revisions.

## Problem Statement

The module has meaningful runtime depth but a weak diagnostics experience.

- Execution evidence is fragmented across `workflow_runs`, `workflow_step_runs`, `workflow_events`, artifacts, logs, and DLQ rows.
- Retry history is collapsed into mutable step-run state rather than modeled as a first-class attempt ledger.
- Failure semantics are not authoritative; reason codes, retryability, and remediation hints are inferred inconsistently from free-text errors and event payloads.
- The primary troubleshooting path is still raw event polling, debug env flags, and DB inspection.
- The current editor execution UI is local/mock, so there is no shared product-grade run inspector for authors or operators.

## Goals

- Add a coherent failed-run investigation model that answers:
  - what failed
  - why it failed
  - what evidence exists
  - what next action is safe
- Keep equal value for three audiences:
  - workflow authors in the WebUI
  - operators debugging production runs
  - API clients automating runs externally
- Make preflight validation authoritative and server-backed.
- Preserve existing execution primitives where practical, rather than rewriting the entire engine.
- Keep the first rollout additive and backward-compatible where possible.

## Non-Goals

- Full orchestration engine redesign for distributed workers or general DAG execution.
- Replacing the raw event ledger with a diagnostics-only model.
- Shipping an editor-only diagnostics surface.
- Persisting unrestricted raw internal exceptions, secrets, or large payload copies as diagnostics.

## Approaches Considered

### 1. Diagnostics Facade Over Existing Surfaces

Add a single aggregated debug endpoint and a lightweight UI that composes existing run, event, and artifact data without deeper data-model changes.

Pros:
- Fastest path.
- Lowest migration risk.

Cons:
- Keeps failure meaning implicit.
- Leaves retry/attempt history underspecified.
- Produces a brittle diagnostics layer that still depends on parsing raw events and error strings.

### 2. Structured Diagnostics Layer Beside the Current Runtime

Keep the current run/event/artifact ledger as the source of truth, but add explicit attempt records, failure taxonomy, replay capability metadata, and a first-class investigation API and UI.

Pros:
- Solves the actual user problem instead of only improving visibility.
- Reuses most existing runtime behavior.
- Supports all three audiences with one coherent interpretation layer.

Cons:
- Requires schema, API, and UI work.
- Requires careful projection/versioning rules to avoid drift.

### 3. Full Execution Model Redesign

Replace the current model with a more opinionated orchestration plane centered on explicit graph execution, attempts, compensation, and richer lifecycle rules.

Pros:
- Cleanest long-term architecture.

Cons:
- Too large for the immediate diagnostics problem.
- High migration and delivery risk.

## Recommended Approach

Use Approach 2: a structured diagnostics layer beside the current runtime.

This yields the best balance between delivery risk and long-term value. The current engine and persistence model already provide enough operational signal to support a better diagnostics system, but the interpretation layer is missing. The proposed work should refine the existing runtime into a coherent run-investigation product rather than replace it outright.

## Architecture

### 1. Raw Execution Ledger Remains the Source of Truth

Retain the current raw execution entities as authoritative records:

- `workflow_runs`
- `workflow_step_runs`
- `workflow_events`
- `workflow_artifacts`
- `workflow_webhook_dlq`

These tables remain the execution ledger used for control flow, auditing, and low-level troubleshooting.

### 2. Separate Logical Step Runs From Step Attempts

Current step retries mutate a single `workflow_step_runs.attempt` value in place. That is acceptable for runtime flow control but insufficient for diagnosis.

The revised model should be:

- `workflow_step_runs`
  - one logical step execution record per step occurrence within a run
  - stable anchor for routing, approvals, and human-in-the-loop semantics
- `workflow_step_attempts`
  - one child row per actual attempt or retry
  - authoritative ledger for retry history, per-attempt status, timing, evidence, and failure semantics

This split is required to avoid ambiguity in:

- retry-from-step behavior
- approval and reject flows
- timeout and retry analysis
- per-attempt evidence capture

### 3. Add Explicit Replay and Idempotency Capabilities Per Step Type

Safe reruns cannot be inferred from reason code alone. Each step type must declare a small capability contract:

- `replay_safe`
- `idempotency_strategy`
- `compensation_supported`
- `requires_human_review_for_rerun`
- `evidence_level`

Default behavior for unknown or side-effecting steps is `unsafe`.

Examples:

- `prompt`, `rag_search`, and pure transforms may be replay-safe when inputs are unchanged.
- `webhook`, `notify`, `mcp_tool`, `kanban`, and ingestion-like steps should default to unsafe or conditional unless explicit idempotency guarantees exist.

### 4. Add a Derived Run Investigation Read Model

Expose a first-class `run investigation` surface that answers the main user questions without replacing the raw ledger.

The investigation model should be computed on demand or stored as a projection with explicit versioning:

- `schema_version`
- `derived_from_event_seq`
- `generated_at`
- stale/rebuild semantics

If projection generation fails, the raw run, attempts, events, and artifacts must remain available.

## Data Model

### `workflow_step_attempts`

Representative fields:

- `attempt_id`
- `tenant_id`
- `run_id`
- `step_run_id`
- `step_id`
- `attempt_number`
- `status`
- `started_at`
- `ended_at`
- `duration_ms`
- `reason_code_core`
- `reason_code_detail`
- `category`
- `blame_scope`
- `retryable`
- `retry_recommendation`
- `error_summary`
- `error_detail_redacted`
- `provider_name`
- `provider_request_id`
- `workdir`
- `stdout_path`
- `stderr_path`
- `metadata_json`

### `workflow_run_investigations` (optional materialized projection)

Representative fields:

- `run_id`
- `schema_version`
- `derived_from_event_seq`
- `generated_at`
- `primary_failure_json`
- `failed_step_json`
- `evidence_refs_json`
- `recommended_actions_json`
- `stale`

If the projection is materialized, rebuild tooling and migration/version checks are mandatory.

## Failure Semantics

### Layered Taxonomy

Use layered failure semantics instead of a single flat canonical list:

- `reason_code_core`
  - stable top-level code such as `validation_error`, `policy_blocked`, `provider_timeout`, `runtime_error`
- `reason_code_detail`
  - narrower adapter-specific detail such as `template_render_error`, `webhook_blocked_private_ip`, `llm_provider_429`
- `category`
  - `user_config`, `external_dependency`, `policy`, `runtime`, `platform`
- `blame_scope`
  - `workflow_definition`, `run_input`, `provider`, `system`, `operator_action`
- `retryable`
  - boolean
- `retry_recommendation`
  - `safe`, `unsafe`, `requires_input_change`, `requires_operator_review`

### Audience-Safe Explanations

Every failed or blocked attempt should support:

- `user_message`
  - concise, safe explanation for authors and ordinary API callers
- `operator_message`
  - more precise remediation-oriented explanation
- `internal_detail`
  - privileged raw exception or deep context, if retained at all
- `suggested_actions`
  - structured next steps such as `fix_input`, `change_timeout`, `retry_from_step`, `replay_webhook`, `contact_operator`

## Evidence Capture

Evidence must be structured, bounded, and redacted by default.

### Evidence Refs

Prefer typed references and excerpts over duplicating full payloads:

- event refs
  - exact `event_seq` values
- attempt refs
  - specific failed attempt ids
- artifact refs
  - stdout, stderr, output, logs, manifests
- config refs
  - validation error output, schema path, step config hash or bounded snapshot
- external refs
  - provider request id, webhook delivery code, approval record, policy decision id

### Retention and Redaction Rules

Do not persist unrestricted rendered prompts, provider payloads, or secrets in diagnostics records.

The design must include:

- bounded excerpts for stdout/stderr
- redaction of known secret-bearing fields
- restricted access to raw deep detail
- explicit retention windows for per-attempt diagnostics

## API Surface

Retain existing low-level APIs, but add investigation-oriented endpoints:

- `GET /api/v1/workflows/runs/{run_id}/investigation`
- `GET /api/v1/workflows/runs/{run_id}/steps`
- `GET /api/v1/workflows/runs/{run_id}/steps/{step_id}/attempts`
- `POST /api/v1/workflows/preflight`

Existing APIs such as:

- `GET /runs/{run_id}`
- `GET /runs/{run_id}/events`
- `GET /runs/{run_id}/artifacts`
- `POST /runs/{run_id}/retry`
- approval/reject endpoints

remain available as the raw or control surfaces.

### Auth Model

Diagnostic detail must be layered by authorization.

- Base response:
  - safe summaries, stable reason codes, bounded evidence metadata
- Elevated operator/admin response:
  - richer remediation detail, excerpts, provider correlation ids where appropriate
- Privileged internal detail:
  - tightly restricted, redacted, and ideally separated from ordinary responses

Do not rely solely on endpoint-level owner/admin gating without field-level response design.

## User Surfaces

### Shared Run Inspector

The first diagnostics UI must be a shared run inspector, not an editor-only feature.

It should include:

- failure summary card
- step graph or ordered step list with failed node highlighted
- attempt timeline
- evidence tabs
  - logs
  - artifacts
  - webhook deliveries
  - approvals
- next-action panel
  - retry
  - retry from step
  - inspect config
  - operator escalation

This shared inspector can then be embedded or linked from the workflow editor.

### Workflow Editor Integration

The editor should not own the diagnostics model. Instead, it should:

- link to the shared run inspector for real runs
- highlight failed nodes using investigation data
- show preflight warnings before execution

### Runs Index Improvements

Add run filtering and triage based on structured diagnostics fields:

- `reason_code_core`
- `category`
- `blame_scope`
- `retryable`
- `workflow_id`
- `provider_name`
- stuck age

These filters require explicit denormalization and indexes rather than expensive event scans.

## Preflight Validation

Preflight must be server-authoritative.

Do not implement client-only preflight logic as the main source of truth.

The preflight endpoint should reuse server-side:

- definition schema validation
- DAG and routing validation
- template/input resolution where possible
- capability-based replay/rerun warnings
- environment and step-compatibility warnings

The UI may still provide immediate local hints, but only the server decides what is valid or dangerous.

## Operational Improvements

The first rollout should also make operations more coherent:

- reason-code-aware dashboards and alerts
- better stuck-run and retry-exhaustion reporting
- DLQ and approval evidence linked from the run inspector
- docs rewritten around investigation flows instead of raw DB spelunking as the default path

## Rollout Plan

### Phase 1: Capability and Attempt Foundation

- Introduce per-step replay/idempotency capability metadata.
- Add `workflow_step_attempts` and migrations.
- Preserve current control flow while dual-writing attempt information.

### Phase 2: Failure Taxonomy and Investigation API

- Emit layered failure semantics from engine and adapters.
- Add investigation service and APIs.
- Add denormalized fields and indexes needed for triage.

### Phase 3: Shared Run Inspector and Preflight

- Build a shared run inspector UI and data client.
- Integrate it into the workflow editor.
- Add server-authoritative preflight UX.

### Phase 4: Docs and Operational Hardening

- Update runbook and debugging docs.
- Update alerts and dashboards to use reason codes and retryability classes.

## Risks and Mitigations

### Risk: Projection Drift

Mitigation:
- treat investigation as a derived read model
- include `schema_version` and `derived_from_event_seq`
- support rebuild and stale detection

### Risk: Retry Safety Misclassification

Mitigation:
- do not infer replay safety from reason code alone
- require explicit step capability declarations
- default to unsafe

### Risk: Secret Leakage

Mitigation:
- store evidence refs and excerpts
- redact known sensitive fields
- restrict raw internal detail
- define retention windows

### Risk: UI Built Before Authoritative Data Contract

Mitigation:
- build investigation API and auth model before editor integration
- make the shared run inspector the first real UI consumer

## Testing Strategy

### Unit Tests

- step capability contract evaluation
- attempt record creation and status transitions
- failure envelope normalization
- investigation summary generation
- replay-safety decisioning

### Integration Tests

- failed run produces attempt rows and investigation summary
- approval/reject flows still anchor correctly on logical step runs
- retry-from-step respects step replay capabilities
- preflight returns validation errors and warnings consistent with runtime behavior
- field-level auth and redaction rules are enforced

### UI Tests

- shared run inspector renders failed-run summary and attempts
- workflow editor links to or embeds the shared inspector
- preflight warnings render deterministically

### Operational Verification

- alerts pivot on reason-code-aware metrics
- debugging docs reflect investigation-first workflows
- indexes support expected triage queries

## Acceptance Criteria

- Failed runs can be investigated through a first-class API and shared UI without parsing raw events manually.
- Retry/partial-rerun safety is explicit per step type and defaults to unsafe.
- Logical step runs and retry attempts are represented as separate entities.
- Investigation data cannot silently drift from the raw ledger without detection.
- Diagnostic evidence is bounded, redacted, and authorization-aware.
- Preflight validation is server-authoritative.
- Operators, authors, and API consumers all gain usable diagnostics in the first milestone.
