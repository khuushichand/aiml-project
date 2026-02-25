# Workflow Hardening Epic + Follow-On Tracks Design

Date: 2026-02-25
Status: Approved (brainstorming complete)
Owner: Codex + user

## 1. Scope and Outcome

This design defines the next backend work after ACP pipeline baseline delivery.

Primary focus: **Track 2 (workflow orchestration hardening)**, delivered as one epic in three sequential phases:

1. State contract hardening
2. Reliability hardening
3. Observability hardening

Additional planning output included in this design:
- Create GitHub TODO issue structures for follow-on tracks:
  - Track 1: sandbox/workspace lifecycle integration
  - Track 3: API surface expansion for pipeline control/status
- Use one epic + child issues per track for Tracks 1 and 3.

Non-goals for this hardening epic:
- Frontend/UI implementation.
- New product domains unrelated to workflow orchestration hardening.

## 2. Architecture and Components

### 2.1 Workflow Engine Contract Layer (state machine + idempotency)
- Define canonical run/step states and allowed transitions as a versioned state-machine spec.
- Enforce transitions through a single guard path (no direct status mutation outside guard APIs).
- Normalize terminal reason codes:
  - `success`
  - `blocked`
  - `timed_out`
  - `cancelled`
  - `failed_validation`
  - `failed_runtime`
  - `retry_exhausted`
- Introduce idempotency keys for lifecycle mutations:
  - `run_id + step_id + operation + attempt`
- Duplicate lifecycle operations return deterministic `already_applied` instead of replaying side effects.

### 2.2 ACP Adapter Contract Layer (`acp_stage`)
- Freeze normalized adapter output schema and include explicit version:
  - `acp_output_schema_version`
  - `status`, `error_type`, `error`, `stage`
  - `session_id`, `workspace_id`, `workspace_group_id`
  - `response`, `usage`, `governance`
- Validate output shape on all return paths (success/error/blocked/timeout/cancel).
- Use explicit status/terminal translation mapping into workflow branching semantics.
- Support backward-safe parse path for prior schema version during migration window.

### 2.3 Atomicity and Side-Effect Boundary Layer
- Define transaction boundary between workflow DB state mutation and ACP side effects.
- Use outbox/event-journal semantics:
  - persist intent
  - execute ACP side effect
  - persist outcome/compensation marker
- Add reconciliation worker to repair partial failures:
  - detect orphan ACP side effects
  - reattach to run/step when possible
  - otherwise transition to controlled `failed_runtime` with audit evidence

### 2.4 Reliability Policy Layer
- Classify retryability by error taxonomy.
- Never retry:
  - validation/authz failures
  - governance blocks
  - session ownership denials
  - invariant violations
- Conditionally retry:
  - transient transport/runtime failures
  - bounded timeout class failures
- Apply stage-specific retry policy:
  - capped attempts
  - exponential backoff with jitter
  - max elapsed retry budget
- Enforce cancel propagation contract:
  - run cancel intent
  - ACP cancel for active stage
  - cancellation acknowledgement persisted before terminal cancel
- Enforce review loop guards with bounded counters and mandatory human escalation on threshold.

### 2.5 Observability and Operations Layer
- Emit low-cardinality metrics keyed by stage class and normalized reason code.
- Emit structured events with stable fields:
  - `run_id`, `step_id`, `attempt`, `reason_code`, `retryable`, `schema_version`
- Ensure audit coverage for:
  - approval/reject/resume
  - cancel propagation
  - governance block
  - retry exhaustion
- Define SLO/alert signals:
  - timeout rate
  - retry exhaustion rate
  - stuck run age
  - invalid transition reject count

### 2.6 Rollout and Compatibility Controls
- Feature flags:
  - strict transition enforcement
  - adapter schema strict mode
  - retry strict mode
- Rollout path:
  - log-only
  - soft-enforce
  - hard-enforce
- Run migration checks for existing templates/runs before hard enforcement.

### 2.7 Follow-On Issue Management Output (Tracks 1 and 3)
- Create issue structures in GitHub:
  - Track 1 epic + child issues (sandbox/workspace lifecycle)
  - Track 3 epic + child issues (pipeline API expansion)
- Link both tracks as follow-on dependencies to Track 2 hardening epic.

## 3. Data Flow and Phase Execution

### 3.1 Phase 1: State Contract Foundation
1. Run starts with template-defined graph + contract version.
2. Transition request hits guard layer.
3. Guard validates transition edge + idempotency key.
4. Result is `applied` or `already_applied`.
5. `acp_stage` output is schema-version validated pre-persist.
6. Terminal reason is normalized + audited.

### 3.2 Phase 2: Reliability Hardening
1. Step failure enters retry classifier.
2. Retriable failures are retried with bounded policy.
3. Non-retriable failures transition directly to controlled terminal reason.
4. Cancel requests propagate workflow cancel -> ACP cancel -> terminal cancel.
5. Review loops increment bounded counters and escalate to human step on threshold.

### 3.3 Phase 3: Observability Hardening
1. Each transition emits metrics + structured event.
2. Retry/cancel/governance outcomes emit reason-coded telemetry.
3. SLO monitors evaluate timeout spikes, stuck runs, retry exhaustion, invalid transitions.

## 4. Error Handling and Safety

### 4.1 Error Taxonomy (authoritative)
- `validation_error`
- `authz_error`
- `acp_session_error`
- `acp_prompt_error`
- `acp_timeout`
- `acp_governance_blocked`
- `cancelled`
- `retry_exhausted`
- `invariant_violation`

### 4.2 Retry Rules
- Never retry:
  - `validation_error`
  - `authz_error`
  - `acp_governance_blocked`
  - session access denial variants
  - `invariant_violation`
- Conditionally retry:
  - `acp_timeout`
  - transient runtime/transport classes
- Enforce both max attempts and max elapsed retry window.

### 4.3 Invariant Enforcement
- Invalid transition attempts are rejected and logged as invariant violations.
- Schema-invalid adapter outputs fail closed with controlled error transition.
- Duplicate lifecycle operations return idempotent `already_applied` outcomes.

### 4.4 Compensation and Reconciliation
- If side effect succeeds but persistence fails:
  - write reconciliation marker
  - repair asynchronously
  - if unrecoverable, transition to controlled failure with audit context
- Orphan ACP artifacts must be trace-linked where possible.

### 4.5 Security and Audit
- No raw internal exception text in external workflow outputs.
- Governance denies are explicit blocked outcomes with non-sensitive reason code.
- Audit records required for approval/reject/resume, cancel propagation, governance blocks, retry exhaustion.

## 5. Verification, Rollout, and Definition of Done

### 5.1 Phase 1 Gate (state contracts)
- Transition guard tests (allowed/disallowed + replay idempotency) pass.
- `acp_stage` schema/version contract tests pass.
- State-machine/property tests pass.

### 5.2 Phase 2 Gate (reliability)
- Retry classifier tests pass.
- Cancel propagation integration tests pass.
- Loop-guard escalation tests pass.

### 5.3 Phase 3 Gate (observability)
- Metrics emission assertions pass.
- Structured event schema tests pass.
- Alert-rule smoke checks pass for timeout, stuck-run, retry-exhaustion signals.

### 5.4 Security/Quality Gates (all phases)
- Run Bandit in project venv on touched scope before completion.
- No new raw exception leakage in user-facing payloads.
- Backward-compat schema parser validated during migration period.

### 5.5 Rollout Policy
- Log-only -> soft-enforce -> hard-enforce progression with telemetry gates between phases.

### 5.6 Definition of Done
- State contracts enforced by one authoritative guard path.
- Reliability controls provide bounded retries, deterministic cancellation, and loop circuit breakers.
- Observability provides actionable, stable, reason-coded operational signals.
- Track 1 and Track 3 issue structures (epic + child issues) exist in GitHub and are linked as follow-on work.

## 6. Planned GitHub Issue Structure (to create)

### 6.1 Track 1: Sandbox/Workspace Lifecycle Integration
- Epic: ACP sandbox/workspace lifecycle integration for pipeline stages.
- Child issues:
  1. Workspace/session provisioning contract for workflow-run bootstrap.
  2. Stage-level workspace binding + metadata propagation.
  3. Workspace lifecycle teardown/reconciliation behavior.
  4. Sandbox diagnostic linkage and failure-mode normalization.

### 6.2 Track 3: API Surface Expansion
- Epic: Pipeline control/status API expansion for ACP-centric runs.
- Child issues:
  1. Run control endpoints contract review (pause/resume/cancel/retry).
  2. Stage-level status and reason-code response schema.
  3. Artifact/event query APIs for run timeline consumers.
  4. API authz/rate-limit/audit hardening for new control surfaces.
