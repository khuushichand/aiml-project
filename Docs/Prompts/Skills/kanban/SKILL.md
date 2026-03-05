---
name: kanban
description: Manage tldw_server Kanban boards via MCP with explicit workflow-status control, safe transitions, lease/approval gates, and recovery primitives for orchestrators.
license: MIT
---

Manages Kanban boards in **tldw_server** using MCP tools from the `kanban` module.

## Core Rule: Workflow State Is Canonical

For orchestration, treat `card.workflow_status` as source of truth.

- Canonical state: `kanban_card_workflow_state.workflow_status_key`
- List placement is projection side effect only (`auto_move_list_id`)
- Never infer workflow state from list column placement

## MCP Tooling

### Board/List/Card primitives

- `kanban.boards.list`
- `kanban.boards.get`
- `kanban.boards.create`
- `kanban.lists.list`
- `kanban.lists.create`
- `kanban.cards.list`
- `kanban.cards.create`
- `kanban.cards.move`
- `kanban.cards.search`
- `kanban.comments.list`
- `kanban.comments.create`

### Workflow control primitives

- `kanban.workflow.policy.get`
- `kanban.workflow.policy.upsert`
- `kanban.workflow.statuses.list`
- `kanban.workflow.transitions.list`
- `kanban.workflow.task.state.get`
- `kanban.workflow.task.state.patch`
- `kanban.workflow.task.claim`
- `kanban.workflow.task.release`
- `kanban.workflow.task.transition`
- `kanban.workflow.task.approval.decide`
- `kanban.workflow.task.events.list`
- `kanban.workflow.control.pause` (admin)
- `kanban.workflow.control.resume` (admin)
- `kanban.workflow.control.drain` (admin)
- `kanban.workflow.recovery.list_stale_claims`
- `kanban.workflow.recovery.force_reassign` (admin)

## Safety Contract (Always Enforce)

For workflow write operations:

- Always pass `expected_version` (CAS)
- Always pass unique `idempotency_key`
- Always pass `correlation_id` on transitions/approval/recovery writes
- Re-read state before retries (`kanban.workflow.task.state.get`)

Stable conflict codes to handle:

- `version_conflict`
- `lease_required`
- `lease_mismatch`
- `policy_paused`
- `transition_not_allowed`
- `approval_required`
- `projection_failed`
- `idempotency_conflict`

## Suggested Status Pipeline (Optional Policy)

Use if the project wants a 7-stage flow:

`req -> plan -> review_plan -> impl -> review_impl -> test -> done`

Suggested transitions:

- `req -> plan`
- `plan -> review_plan`
- `review_plan -> impl`
- `review_plan -> plan` (reject)
- `impl -> review_impl`
- `review_impl -> test`
- `review_impl -> impl` (reject)
- `test -> done`
- `test -> impl` (fail)

Implement this using `kanban.workflow.policy.upsert` with explicit statuses/transitions.

## Default Execution Pattern

No autonomous 7-stage loop is assumed by default.
Use explicit step-wise orchestration:

1. Load policy and task state (`policy.get`, `task.state.get`)
2. Claim lease (`task.claim`) when required by transition policy
3. Transition (`task.transition`) with CAS + idempotency + correlation
4. If approval is pending, resolve with `task.approval.decide`
5. Append card comments/checklists as execution notes
6. Release lease (`task.release`) when complete
7. Audit/replay via `task.events.list`

## Pause/Drain/Recovery Runbook

- Pause writes during incidents: `kanban.workflow.control.pause`
- Resume when safe: `kanban.workflow.control.resume`
- Drain board for controlled shutdown: `kanban.workflow.control.drain`
- Find orphaned claims: `kanban.workflow.recovery.list_stale_claims`
- Reassign ownership when needed: `kanban.workflow.recovery.force_reassign`

## Minimal MCP Call Shapes

Transition:

```json
{
  "name": "kanban.workflow.task.transition",
  "arguments": {
    "card_id": 123,
    "to_status_key": "impl",
    "actor": "builder",
    "expected_version": 4,
    "idempotency_key": "wf-123-transition-0001",
    "correlation_id": "run-2026-03-05-001",
    "reason": "begin implementation"
  }
}
```

Approval decision:

```json
{
  "name": "kanban.workflow.task.approval.decide",
  "arguments": {
    "card_id": 123,
    "reviewer": "inspector",
    "decision": "approved",
    "expected_version": 5,
    "idempotency_key": "wf-123-approval-0001",
    "correlation_id": "run-2026-03-05-001",
    "reason": "checks passed"
  }
}
```

## Notes

- Prefer explicit transitions over direct state patching for normal lifecycle flow.
- Use `task.state.patch` only for controlled admin repair operations.
- Keep admin-only tools out of general-purpose agent catalogs.
