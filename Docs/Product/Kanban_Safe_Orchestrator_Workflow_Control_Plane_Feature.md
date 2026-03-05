# Kanban Safe Orchestrator Workflow Control Plane

Date: 2026-03-04  
Status: Implemented and merged  
Audience: Product, platform, API integrators, MCP tool consumers

## Summary

This feature adds a first-class workflow control plane for Kanban so orchestrators can execute task pipelines safely and deterministically.

The key model change is explicit separation between:

- canonical workflow state: `card.workflow_status` (`kanban_card_workflow_state.workflow_status_key`)
- visual lane placement: `card.list_id` (projection side effect only)

Orchestrator logic should read and write workflow status, not infer lifecycle from list placement.

## Why This Feature Exists

Before this change, Kanban had strong CRUD/search behavior but lacked a centralized workflow engine with explicit transition policies, leases, approval gates, and deterministic recovery primitives.

This feature closes that gap by exposing:

- policy-enforced transitions
- CAS + idempotency controls on writes
- lease ownership for exclusive mutation
- approval and rejection paths
- append-only workflow event history
- pause/drain/recovery operations for incidents and maintenance

## What Shipped

## 1) Policy Model (Per Board)

Workflow policy is now explicit and versioned per board, with:

- status catalog
- transition graph
- gate behavior (`requires_claim`, `requires_approval`)
- projection mapping (`auto_move_list_id`)
- runtime controls (`is_paused`, `is_draining`, `default_lease_ttl_sec`, `strict_projection`)

## 2) Runtime State (Per Card)

Each card has workflow runtime state including:

- `workflow_status_key`
- lease owner and expiry
- approval state and pending transition
- retry counters
- monotonic `version` for optimistic concurrency

## 3) Workflow Event Stream

Every workflow mutation writes append-only events for audit and deterministic replay/recovery.

## 4) Recovery and Control Operations

Operational primitives were added for:

- stale lease discovery
- force reassignment (admin)
- pause/resume/drain controls (admin)

## REST API Surface

Base path prefix: `/api/v1/kanban`

Policy and metadata:

- `GET /workflow/boards/{board_id}/policy`
- `PUT /workflow/boards/{board_id}/policy`
- `GET /workflow/boards/{board_id}/statuses`
- `GET /workflow/boards/{board_id}/transitions`

Task workflow lifecycle:

- `GET /workflow/cards/{card_id}/state`
- `PATCH /workflow/cards/{card_id}/state` (admin repair path)
- `POST /workflow/cards/{card_id}/claim`
- `POST /workflow/cards/{card_id}/release`
- `POST /workflow/cards/{card_id}/transition`
- `POST /workflow/cards/{card_id}/approval`
- `GET /workflow/cards/{card_id}/events`

Recovery and operational controls:

- `GET /workflow/recovery/stale-claims`
- `POST /workflow/recovery/cards/{card_id}/force-reassign` (admin)
- `POST /workflow/control/boards/{board_id}/pause` (admin)
- `POST /workflow/control/boards/{board_id}/resume` (admin)
- `POST /workflow/control/boards/{board_id}/drain` (admin)

## MCP Primitive Surface

Equivalent MCP tools are available under `kanban.workflow.*`:

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
- `kanban.workflow.control.pause`
- `kanban.workflow.control.resume`
- `kanban.workflow.control.drain`
- `kanban.workflow.recovery.list_stale_claims`
- `kanban.workflow.recovery.force_reassign`

## Safety Contract for Orchestrators

For workflow writes, the contract is:

- use `expected_version` (CAS)
- use unique `idempotency_key`
- use `correlation_id` for transition/approval/recovery writes
- claim lease when policy requires claim
- re-read state before retry

Stable conflict/error codes:

- `version_conflict`
- `lease_required`
- `lease_mismatch`
- `policy_paused`
- `transition_not_allowed`
- `approval_required`
- `projection_failed`
- `idempotency_conflict`

## Execution Model (Intentional)

This feature does not impose an autonomous, fixed 7-stage loop.

Instead, it exposes strict low-level primitives so teams can implement their own orchestrator strategy safely:

1. read policy + task state
2. claim lease if required
3. execute transition with CAS + idempotency
4. resolve approval if pending
5. write task notes/comments/checklists as needed
6. release lease
7. audit via event stream

This keeps the control plane generic while preserving safety and auditability.

## Security and Authorization

Admin-only operations:

- state patch (`PATCH /workflow/cards/{card_id}/state`)
- force reassign
- pause/resume/drain controls

Non-admin callers receive `403` with `{"code":"forbidden","message":"Admin privileges required"}` for those endpoints.

## Backward Compatibility Notes

- Existing boards can be bootstrap-seeded with default workflow policy/statuses/transitions.
- Existing cards can lazily initialize runtime workflow state on first workflow access.
- Existing list/card CRUD behavior remains available; workflow state is now the orchestrator source of truth.

## Verification Coverage

Primary coverage added for:

- workflow API endpoint behavior and authz
- policy/status/transition/state DB contract
- idempotency and concurrency behavior
- projection failure handling
- MCP workflow tool wiring

Representative tests:

- `tldw_Server_API/tests/kanban/test_workflow_endpoints.py`
- `tldw_Server_API/tests/kanban/test_workflow_authz.py`
- `tldw_Server_API/tests/kanban/test_workflow_transition_contract.py`
- `tldw_Server_API/tests/kanban/test_workflow_idempotency_and_concurrency.py`
- `tldw_Server_API/tests/kanban/test_workflow_projection_failures.py`
- `tldw_Server_API/app/core/MCP_unified/tests/test_kanban_module.py`

## Related Docs

- `Docs/User_Guides/WebUI_Extension/Kanban_Board_Guide.md`
- `Docs/MCP/Unified/User_Guide.md` (Kanban Workflow Control section)
- `Docs/Prompts/Skills/kanban/SKILL.md`
- `Docs/Plans/2026-03-04-kanban-safe-orchestrator-workflow-primitives-design.md`
- `Docs/Plans/2026-03-04-kanban-safe-orchestrator-workflow-primitives-implementation-plan.md`
