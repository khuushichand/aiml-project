# Deep Research Workflow Checkpoint-Aware Wait Design

## Summary

This slice makes the existing `deep_research_wait` workflow step aware of human-review checkpoints in the linked research session.

Today the step only polls for terminal research states. If the research run enters `awaiting_plan_review`, `awaiting_source_review`, or `awaiting_outline_review`, the workflow worker keeps polling until timeout or cancellation. That wastes worker time, misuses the workflow timeout, and gives operators no clean workflow-level wait state.

The recommended change is to keep `deep_research_wait` as a normal polling adapter, but let it return a structured workflow `waiting_human` state when the linked research run enters a review checkpoint. The workflow engine will treat that adapter-returned wait state as a first-class human wait, store a durable workflow↔research linkage record, skip wall-clock human timeout scheduling for this special case, and auto-resume the same wait step after the research checkpoint is resolved in `/research`.

## Goals

- Let `deep_research_wait` pause workflow execution cleanly when the linked research run needs human review.
- Preserve `/research` as the only approval/edit surface for research checkpoints in v1.
- Auto-resume paused workflows after the linked research checkpoint is resolved.
- Keep `deep_research_wait.timeout_seconds` based on active polling time only.
- Avoid JSON scans or brittle heuristics when locating paused workflow runs that should resume.

## Non-Goals

- No workflow-side UI or API for approving research checkpoints.
- No SSE-driven workflow waiting logic.
- No generic workflow-engine callback system for every external wait source.
- No attempt to make research-service core logic import workflow engine internals directly.
- No change to the existing `deep_research` launch step or `deep_research_load_bundle` step contracts.

## Current Problems

### Adapter-returned waits are only partially honored

The engine already recognizes adapter outputs with `{"__status__": "waiting_human"}` or `{"__status__": "waiting_approval"}` in both `start_run(...)` and `continue_run(...)`, but the generic path only completes the step run and returns. It does not consistently treat those waits like the built-in human steps at the workflow-run level.

That means `deep_research_wait` cannot safely start returning `waiting_human` without stronger engine support.

### Existing human timeout handling is wall-clock based

The engine schedules `_schedule_human_timeout(...)` whenever an adapter returns `waiting_human` and the step config contains `timeout_seconds`.

That behavior is correct for native workflow human steps, but wrong for research-linked waits. If the user spends ten minutes editing a research checkpoint in `/research`, the workflow should not fail just because wall-clock time advanced while the workflow was intentionally paused.

### There is no durable linkage between workflow waits and research checkpoints

Right now the workflow subsystem has no indexed storage for:

- workflow run ID
- waiting step ID
- research run ID
- research checkpoint ID

Without that linkage, the obvious fallback would be scanning workflow step outputs or run outputs JSON to find paused runs that might need to resume. That is brittle and slow across both SQLite and Postgres backends.

### Auto-resume must re-enter the same wait step

`WorkflowEngine.continue_run(...)` resumes after `after_step_id` unless `next_step_id` is explicitly set.

If a bridge resumes the workflow after the `deep_research_wait` node instead of back into it, the workflow will skip the wait step entirely once the research checkpoint is resolved. The resumed workflow must re-enter the same step so `deep_research_wait` can resume polling and eventually return terminal research outputs.

## Recommended Approach

Use a polling-based checkpoint-aware wait plus a narrow async auto-resume bridge.

This is preferred over pushing SSE/event-log logic into workflow execution because:

- `deep_research_wait` is already a polling adapter
- the workflow runtime already understands adapter-returned wait statuses
- the research module already owns checkpoint creation and resolution
- the bridge only needs to reconnect a paused workflow run to the same wait step after the research checkpoint lifecycle advances

The high-level flow becomes:

1. workflow launches a deep research run
2. workflow enters `deep_research_wait`
3. research run enters `awaiting_*_review`
4. `deep_research_wait` returns `waiting_human` with research checkpoint metadata
5. workflow engine stores a durable linkage record and pauses the workflow
6. user resolves the research checkpoint in `/research`
7. the research endpoint calls a narrow bridge that finds linked paused workflow runs and resumes them at the same wait step
8. `deep_research_wait` resumes polling until the research run becomes terminal

## Architecture

### `deep_research_wait` Behavior

The existing wait step remains a normal workflow adapter under:

- `tldw_Server_API/app/core/Workflows/adapters/research/wait.py`

It keeps terminal behavior unchanged:

- `completed` returns success metadata and optional bundle
- `failed` and `cancelled` keep their existing fail/allow config handling

New behavior:

- if the linked research session phase is `awaiting_plan_review`, `awaiting_source_review`, or `awaiting_outline_review`
- and the session status is `waiting_human`
- the adapter returns a structured wait payload instead of continuing to poll

Recommended payload shape:

```python
{
    "__status__": "waiting_human",
    "reason": "research_checkpoint",
    "run_id": "workflow-visible-research-run-id",
    "research_phase": "awaiting_source_review",
    "research_control_state": "running",
    "research_checkpoint_id": "checkpoint-123",
    "research_checkpoint_type": "sources_review",
    "research_console_url": "/research?run=research-session-1",
    "active_poll_seconds": 3.5,
}
```

The adapter should restore `active_poll_seconds` from `context["prev"]` when it is re-entered after workflow auto-resume.

### Engine Wait-State Handling

Update:

- `tldw_Server_API/app/core/Workflows/engine.py`

The engine should introduce one shared helper for adapter-returned wait states used by both `start_run(...)` and `continue_run(...)`.

That helper should:

- complete the active step run with `waiting_human` or `waiting_approval`
- update the workflow run status to the same wait state
- append the same class of run-level events the native human-step path emits
- preserve step outputs as the canonical wait payload
- keep secrets and finalize the run loop without marking the workflow terminal

For research-linked waits specifically:

- detect `reason == "research_checkpoint"`
- do not call `_schedule_human_timeout(...)`
- write or update the workflow↔research wait linkage record

This makes adapter-returned wait states first-class instead of half-pauses.

### Workflow↔Research Wait Linkage

Add a dedicated linkage table in:

- `tldw_Server_API/app/core/DB_Management/Workflows_DB.py`

Recommended table:

- `workflow_research_waits`

Recommended columns:

- `wait_id TEXT PRIMARY KEY`
- `tenant_id TEXT NOT NULL`
- `workflow_run_id TEXT NOT NULL`
- `step_id TEXT NOT NULL`
- `research_run_id TEXT NOT NULL`
- `checkpoint_id TEXT NOT NULL`
- `checkpoint_type TEXT NOT NULL`
- `wait_status TEXT NOT NULL`
- `wait_payload_json TEXT NOT NULL`
- `active_poll_seconds REAL NOT NULL DEFAULT 0`
- `created_at`
- `updated_at`
- `resumed_at`

Recommended indexes:

- unique `(workflow_run_id, step_id)`
- non-unique `(research_run_id, checkpoint_id, wait_status)`

Recommended `wait_status` values:

- `waiting`
- `resuming`
- `resumed`
- `cancelled`

Recommended DB helpers:

- `upsert_research_wait_link(...)`
- `get_research_wait_link(...)`
- `claim_research_waits_for_resume(...)`
- `mark_research_wait_resumed(...)`
- `cancel_research_wait_links_for_run(...)`

The link record should store the exact wait payload so the bridge can pass it back into `continue_run(...)` as `last_outputs` when resuming the same step.

### Timeout Semantics

`deep_research_wait.timeout_seconds` becomes active-polling-only for research-linked waits.

That means:

- time spent actively polling a running research session counts toward timeout
- time spent in workflow `waiting_human` because the research session is at a checkpoint does not count

Implementation approach:

- the adapter tracks cumulative active polling seconds
- the wait payload stores `active_poll_seconds`
- when the workflow resumes into the same wait step, the adapter restores that elapsed value from `context["prev"]`
- the adapter continues enforcing timeout against active poll time only

The engine should not schedule its normal wall-clock human timeout for this case.

### Auto-Resume Bridge

Add a narrow bridge under the workflows domain, for example:

- `tldw_Server_API/app/core/Workflows/research_wait_bridge.py`

This bridge should:

1. look up waiting workflow links for `(research_run_id, checkpoint_id)`
2. atomically claim eligible links by moving `wait_status` from `waiting` to `resuming`
3. instantiate `WorkflowEngine(db)`
4. schedule `continue_run(...)` with:
   - `after_step_id=<stored step_id>`
   - `last_outputs=<stored wait_payload_json>`
   - `next_step_id=<stored step_id>`
5. mark the link `resumed` with `resumed_at`

If resume scheduling fails, the bridge should log and leave the research approval successful. The bridge is best-effort and must not cause the research approval endpoint to fail.

### Endpoint Integration

Keep core research service sync and workflow-agnostic.

Modify:

- `tldw_Server_API/app/api/v1/endpoints/research_runs.py`

After successful `service.approve_checkpoint(...)`, the endpoint should call the bridge asynchronously with the resolved research run ID and checkpoint ID.

That keeps the async side effect at the API boundary and avoids importing workflow engine internals into `ResearchService`.

### Cancellation And Idempotency

The bridge must only resume workflow runs that are still:

- in workflow `waiting_human`
- linked to the same research run
- linked to the same checkpoint ID
- in linkage status `waiting`

If a workflow run was cancelled while waiting, the bridge should skip it.

If a duplicate approval or replayed bridge call arrives, `claim_research_waits_for_resume(...)` should return nothing because the link is no longer in `waiting`.

## Testing Strategy

### Backend Adapter Tests

Update:

- `tldw_Server_API/tests/Workflows/adapters/test_research_adapters.py`

Add coverage for:

- research-checkpoint wait payloads from `deep_research_wait`
- restoration of `active_poll_seconds` from `context["prev"]`
- timeout being based on active poll time only

### Workflow DB Tests

Update:

- `tldw_Server_API/tests/Workflows/test_workflows_db.py`

Add coverage for:

- creating/updating wait links
- claiming links for resume
- idempotent claim behavior
- resume/cancel state transitions

### Engine Tests

Update:

- `tldw_Server_API/tests/Workflows/test_engine_scheduler.py`

Add coverage for:

- adapter-returned `waiting_human` updating the workflow run status properly
- no wall-clock human timeout scheduling for `reason == "research_checkpoint"`
- continuing the same step via `next_step_id == step_id`

### Research Endpoint / Integration Tests

Update:

- `tldw_Server_API/tests/Research/test_research_runs_endpoint.py`
- `tldw_Server_API/tests/Workflows/test_workflows_api.py`

Add coverage for:

- approving a research checkpoint triggering the bridge
- launch -> wait -> checkpoint pause -> `/research` approve -> same-step auto-resume -> workflow completion
- stale or unrelated waits not resuming

## Risks And Tradeoffs

### Engine Surface Area

This slice touches the core workflow engine. The helper for adapter-returned waits should stay narrow and shared between `start_run(...)` and `continue_run(...)` so the behavior is consistent and reviewable.

### Cross-Domain Coupling

The bridge is intentionally thin and async. It should live in the workflow domain, not the research service. That keeps research approval semantics stable even if workflow auto-resume fails.

### Timeout Complexity

Active-poll-only timeout accounting is more complex than the current wall-clock model, but it is necessary here. Reusing the current `_schedule_human_timeout(...)` logic would produce false failures during legitimate human review.

## Open Follow-Ups

- Add workflow-admin visibility into linked research waits if operators need to inspect them later.
- Consider a future workflow-side research checkpoint review surface only after the `/research`-only v1 path proves stable.
- Consider eventual SSE or event-log wakeups only if polling + bridge becomes a bottleneck.
