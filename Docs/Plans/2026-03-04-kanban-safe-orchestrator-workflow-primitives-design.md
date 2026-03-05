# Kanban Safe Orchestrator Workflow Primitives Design

Date: 2026-03-04  
Status: Approved (brainstorming)

## Goal

Expose a complete, policy-enforced workflow-control surface for Kanban tasks so autonomous orchestrators can safely run multi-stage pipelines with deterministic transitions, strict concurrency control, and full auditability.

This design explicitly separates workflow state from board lane placement:

- Source of truth: `card.workflow_status` (runtime state table)
- Projection: optional status-to-list mapping applied during transitions

## Scope

In scope:

- Explicit workflow policy model per board
- Explicit task workflow runtime-state model
- Explicit transition and approval primitives with server-side enforcement
- Lease/claim controls for exclusive task ownership
- Immutable workflow event stream
- Pause/resume/drain operational controls
- Recovery primitives for stale claims
- MCP tooling surface for the above

Out of scope:

- Full implementation details for UI workflows
- Automatic migration of existing boards into policy-backed workflows
- Cross-board/global orchestration policy inheritance

## Current-State Summary

Current Kanban API/DB support includes optimistic locking on selected updates, archive/delete/restore mechanics, metadata blobs, and activity logs. However, there is no first-class workflow engine with centralized transition-policy enforcement, nor a complete MCP surface for orchestrator-safe control.

## Design Decisions (Locked)

1. Workflow state model
- Store workflow state explicitly and independently of `list_id`.
- `workflow_status` is canonical.

2. Lane behavior
- Use status-driven projection.
- Status transitions may auto-move cards to mapped lists.
- Manual list moves do not mutate status.

3. Policy storage
- Use dedicated relational policy tables (not free-form metadata).

4. Transition representation
- Use normalized transition edges table.

5. Runtime task state
- Use dedicated `kanban_card_workflow_state` table.

6. Audit history
- Use dedicated append-only `kanban_card_workflow_events` table.

7. Projection failures
- Transition fails if configured projection target list is invalid (missing/archived).

8. Lease enforcement
- Strict lease requirement for workflow-mutating operations (except explicit admin override path).

9. Idempotency
- DB-enforced idempotency key storage and uniqueness for workflow-mutating ops.

10. Review gates
- First-class approval records and approval actions.

11. Rejection routing
- Policy-defined reject target per gated transition.

12. Status vocabulary
- Per-board status catalog (not fixed global enum).

## Data Model

### 1) `board_workflow_policies`

One active workflow policy per board.

Representative fields:

- `id` PK
- `board_id` UNIQUE FK
- `version` (policy version)
- `is_paused` bool
- `is_draining` bool
- `default_lease_ttl_sec` int
- `strict_projection` bool (default true)
- `created_at`, `updated_at`

### 2) `board_workflow_statuses`

Per-board status catalog.

Representative fields:

- `id` PK
- `policy_id` FK
- `status_key` (machine key)
- `display_name`
- `is_terminal` bool
- `sort_order` int
- `is_active` bool

Constraints:

- UNIQUE(`policy_id`, `status_key`)

### 3) `board_workflow_transitions`

Normalized allowed edges and gate behavior.

Representative fields:

- `id` PK
- `policy_id` FK
- `from_status_key`
- `to_status_key`
- `requires_claim` bool
- `requires_approval` bool
- `approve_to_status_key` nullable
- `reject_to_status_key` nullable
- `auto_move_list_id` nullable FK to list
- `max_retries` int
- `is_active` bool

Constraints:

- UNIQUE(`policy_id`, `from_status_key`, `to_status_key`)

### 4) `kanban_card_workflow_state`

Canonical runtime state for each card.

Representative fields:

- `card_id` PK FK
- `policy_id` FK
- `workflow_status_key`
- `lease_owner` nullable
- `lease_expires_at` nullable
- `approval_state` enum-like (`none|awaiting_approval|approved|rejected`)
- `pending_transition_id` nullable
- `retry_counters` JSON
- `last_transition_at` nullable
- `last_actor` nullable
- `version` int

### 5) `kanban_card_workflow_events` (append-only)

Immutable workflow audit trail.

Representative fields:

- `id` PK
- `card_id` FK
- `event_type`
- `from_status_key` nullable
- `to_status_key` nullable
- `actor`
- `reason` nullable
- `idempotency_key`
- `correlation_id` nullable
- `before_snapshot` JSON
- `after_snapshot` JSON
- `created_at`

Constraints:

- UNIQUE(`card_id`, `event_type`, `idempotency_key`)

### 6) `kanban_card_workflow_approvals`

First-class approval records.

Representative fields:

- `id` PK
- `card_id` FK
- `transition_id` FK
- `state` (`pending|approved|rejected`)
- `reviewer`
- `decision_reason` nullable
- `created_at`, `updated_at`

## Server-Side Safety Contract

## Transition command (`workflow.task.transition`)

Must be atomic and enforce all of the following in one transaction:

- policy not paused/draining-blocked
- lease ownership valid (unless explicit admin override primitive is used)
- edge allowed by policy
- expected version matches
- approval gate requirements
- projection target list validity when `auto_move_list_id` is configured

On success:

- update `kanban_card_workflow_state`
- apply optional list projection
- append workflow event
- increment state version

### Approval flow

If transition requires approval:

- create pending approval record
- set `approval_state=awaiting_approval`
- do not finalize status advance until decision

Approval decision primitive (`workflow.task.approval.decide`):

- `approved` routes to `approve_to_status_key`
- `rejected` routes to `reject_to_status_key`
- both append immutable events and increment version

### Lease model

- `claim` acquires or renews lease (`lease_owner`, `lease_expires_at`)
- `release` clears lease
- stale-lease recovery through dedicated recovery/admin primitives
- strict lease requirement for workflow-mutating calls

### Idempotency and CAS

All workflow-mutating operations require:

- `expected_version`
- `idempotency_key`

Idempotency is persisted in DB constraints (not cache-only).

### Stable machine error reasons

- `version_conflict`
- `lease_required`
- `lease_mismatch`
- `policy_paused`
- `transition_not_allowed`
- `approval_required`
- `projection_failed`
- `idempotency_conflict`

## MCP Primitive Surface

Policy/config:

- `kanban.workflow.policy.get`
- `kanban.workflow.policy.upsert`
- `kanban.workflow.statuses.list`
- `kanban.workflow.transitions.list`

Task runtime state:

- `kanban.workflow.task.state.get`
- `kanban.workflow.task.state.patch` (allowlisted mutable fields only)

Execution control:

- `kanban.workflow.task.claim`
- `kanban.workflow.task.release`
- `kanban.workflow.task.transition`
- `kanban.workflow.task.approval.decide`

Observability/recovery:

- `kanban.workflow.task.events.list`
- `kanban.workflow.control.pause`
- `kanban.workflow.control.resume`
- `kanban.workflow.control.drain`
- `kanban.workflow.recovery.list_stale_claims`
- `kanban.workflow.recovery.force_reassign` (admin-only)

Write-tool argument requirements:

- `expected_version`
- `idempotency_key`
- `correlation_id` (required for orchestrator paths)

## Architecture and Data Flow

1. Orchestrator acquires card lease.
2. Orchestrator requests transition with CAS + idempotency key.
3. Server validates policy, lease, version, approval constraints, projection validity.
4. Server commits state/projection/event atomically.
5. Orchestrator reads updated runtime state and events for next decision.

## Testing Strategy

Unit:

- transition policy matrix enforcement
- version conflict behavior
- idempotency replay behavior
- lease ownership and expiry handling
- approval routing (approve/reject targets)
- projection failure behavior

Integration:

- end-to-end transition lifecycle via MCP tools
- pause/resume/drain effects
- stale-claim recovery flows
- event stream completeness and ordering

Property-based:

- transition invariants over random edge graphs and state sequences
- monotonic version increments under concurrent attempts

## Risks and Mitigations

1. Drift between status and lane
- Mitigation: strict projection failures and atomic status+projection commit.

2. Duplicate side effects under retries
- Mitigation: DB-level idempotency uniqueness + structured replay semantics.

3. Concurrent orchestrator contention
- Mitigation: strict leases + CAS + clear error reasons for retry logic.

4. Policy misconfiguration
- Mitigation: normalized schema + validation (terminal-state rules, approval route completeness, edge integrity).

## Acceptance Criteria

- All workflow transitions are centrally policy-enforced server-side.
- Workflow runtime state is stored and controlled in one place.
- Every workflow mutation is lease-protected, CAS-protected, and idempotent.
- Every successful mutation emits immutable workflow events.
- MCP exposes the full safe orchestrator primitive set.

## Next Step

Create implementation plan covering staged rollout:

- schema/migrations
- DB service methods
- API endpoints
- MCP module extensions
- tests and docs updates
