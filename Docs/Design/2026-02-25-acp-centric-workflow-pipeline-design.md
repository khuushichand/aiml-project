# ACP-Centric Workflow Pipeline Design (API-First)

Date: 2026-02-25
Status: Approved (brainstorming complete)
Owner: Codex + user

## 1. Context and Goal

The goal is to implement a workflow/pipeline pattern similar to `cyanluna.skills` in `tldw_server`, but anchored on existing platform modules and an API-first rollout.

Selected direction:
- Architecture: ACP-centric execution (Approach C)
- Entry point: Workflow templates via existing Workflows API
- Pipeline levels: L1/L2/L3 from day one
- Scope boundary: Domain-only now; no repo mutation workflows in MVP
- Forward target: Integrate with Sandbox + ACP modules to spin up instances/workspaces for stage execution
- UI: Deferred; create explicit post-MVP UI to-do

This design assumes there are no external consumers yet, so we optimize for internal correctness and architectural alignment over backward compatibility constraints.

## 2. Why ACP-Centric vs Template-Only Domain Flow

The ACP-centric approach is chosen because:
- It aligns directly with the medium-term requirement: workspace/instance-backed stage execution.
- It reuses existing ACP session lifecycle, governance integration, and workspace metadata (`workspace_id`, `workspace_group_id`).
- It keeps the Workflows engine as orchestration backbone while making stage execution backend-swappable (ACP now, other executors later if needed).

Trade-off accepted:
- Higher implementation complexity now than a pure domain-step template approach.

## 3. Architecture and Components

### 3.1 Pipeline Definition Layer
- Continue using `GET/POST /api/v1/workflows/templates*` and normal workflows run APIs.
- Add ACP-centric templates for:
  - `pipeline_l1`
  - `pipeline_l2`
  - `pipeline_l3`
- Keep template contracts versioned and explicit (required inputs, expected outputs, review gates).

### 3.2 Orchestration Layer
- Keep Workflows engine as canonical orchestrator:
  - run lifecycle
  - retries/timeouts
  - pause/resume/cancel
  - event sequencing
- Add ACP-backed stage execution steps/adapters for planning/review/implementation/testing stages.

### 3.3 Execution Layer
- Stage execution is done through ACP sessions.
- Stage context carries:
  - `workspace_id`
  - `workspace_group_id`
  - optional persona/scope metadata
- Sandbox-backed ACP remains a runtime option, with metadata attached to workflow step outputs.

### 3.4 State Layer
- Canonical state remains in workflow persistence:
  - `workflow_runs`
  - `workflow_step_runs`
  - `workflow_events`
  - `workflow_artifacts`
- ACP metadata is linked per stage:
  - ACP `session_id`
  - sandbox `session_id` / `run_id` (if present)
  - governance decision summary
- Kanban remains optional task/context surface, not primary executor of the ACP pipeline.

### 3.5 Governance Layer
- Use existing ACP governance coordinator behavior during prompt execution.
- Continue Resource Governor and AuthNZ checks at API boundaries.
- Human gates continue via existing workflows steps and endpoints (`wait_for_human`, approve/reject).

### 3.6 UI Scope (deferred)
- No UI in MVP.
- Post-MVP UI track defined in section 9.

## 4. Data Flow

### 4.1 Start
1. Caller selects `pipeline_l1|l2|l3` template.
2. Caller starts run via existing workflows run endpoint.
3. Inputs include task intent and optional ACP workspace metadata.

### 4.2 Stage Bootstrap
1. First ACP stage creates/reuses ACP session.
2. Session metadata is persisted in step outputs for downstream reuse.

### 4.3 Stage Execution Pattern
For each stage:
1. Workflow step prepares ACP prompt payload from context.
2. ACP session prompt executes.
3. Response + usage + governance outcome are normalized into structured step output.
4. Workflow emits events and stores artifacts as needed.

### 4.4 Level Routing
- L1: `req -> impl -> done`
- L2: `req -> plan -> impl -> impl_review -> done`
- L3: `req -> plan -> plan_review -> impl -> impl_review -> test -> done`

Routing uses existing workflows controls (`branch`, wait steps, explicit transitions), not a new engine primitive in MVP.

### 4.5 Human-in-the-loop
- Review checkpoints use `wait_for_human` or `wait_for_approval`.
- Approve/reject endpoints resume run.
- Optional `edited_fields` are fed into next ACP prompt context.

### 4.6 Completion
- Final stage emits consolidated record:
  - decisions
  - review outcomes
  - test summary
  - governance events
- Run transitions to terminal status and emits completion hooks/events normally.

## 5. Error Handling and Safety

### 5.1 ACP Failure Typing
Normalize stage failures to explicit categories:
- `acp_session_error`
- `acp_prompt_error`
- `acp_timeout`
- `acp_governance_blocked`

### 5.2 Governance Blocks
- Treat governance deny as explicit blocked outcome, not generic failure.
- Template decides whether blocked flows route to human review or terminate.

### 5.3 Sandbox Runtime Failures
- Capture sandbox metadata and error payloads in step outputs.
- Keep runtime failures distinguishable from content-quality failures.

### 5.4 Loop Protection
Implement review loop counters in run context:
- `plan_review_count` max 3
- `impl_review_count` max 3
- On exceed: force `wait_for_human` checkpoint (circuit breaker behavior).

### 5.5 Cancel and Timeout
- Workflow cancel should attempt ACP cancel for active stage session before final cancel state.
- Stage timeout produces explicit timeout reason and consistent events.

### 5.6 Secrets and Audit
- Keep per-run secret injection model (no secrets persisted).
- Persist governance summary events and ACP permission outcomes for auditability.

## 6. Proposed MVP Building Blocks

### 6.1 New/Extended Workflow Templates
Add ACP-focused templates in `tldw_Server_API/Samples/Workflows/`:
- `pipeline_l1_acp.workflow.json`
- `pipeline_l2_acp.workflow.json`
- `pipeline_l3_acp.workflow.json`

### 6.2 ACP Stage Adapter Contract
Introduce/extend a workflow step adapter that:
- accepts stage prompt config + ACP session control config
- executes ACP prompt via existing ACP client path
- returns stable structured output shape for downstream steps

### 6.3 Output Contract (stable)
Each ACP stage output should include:
- `stage`
- `session_id`
- `workspace_id`
- `workspace_group_id`
- `response`
- `usage`
- `governance`
- `status`

This contract is required before UI work starts.

## 7. Testing Plan

### 7.1 Unit Tests
- ACP stage adapter:
  - success
  - governance block
  - timeout
  - malformed ACP response
  - cancel propagation
- input/context mapping tests for workspace metadata.

### 7.2 Integration Tests
- end-to-end L1/L2/L3 template runs with ACP client mocked.
- human approval/reject resume flow tests.
- review loop circuit-breaker tests.

### 7.3 Contract Tests
- template schema validation tests.
- stage output contract tests to guarantee downstream compatibility.

### 7.4 Operational Tests
- scheduler-triggered ACP pipeline runs.
- concurrency and quota behavior with parallel runs.

### 7.5 Security Validation
- RBAC + tenant ownership checks for ACP session usage from workflows.
- Bandit on touched code paths in venv before completion.

## 8. Rollout Strategy

### 8.1 Phase 1 (Internal MVP)
- ship ACP-backed L1/L2/L3 templates
- ship ACP stage adapter + tests
- no UI

### 8.2 Phase 2 (Hardening)
- richer observability fields
- stronger retry/backoff policies per stage type
- scheduler presets for recurring runs

### 8.3 Phase 3 (Workspace-first expansion)
- deepen sandbox-instance/workspace orchestration
- optional per-stage backend selection (ACP sandbox vs non-sandbox ACP)

## 9. Post-MVP UI To-Do (explicit backlog)

Create UI epic: **ACP Pipeline Console**

Scope:
- run timeline view (stage-by-stage)
- review/approval actions for wait steps
- ACP session + workspace metadata inspector
- governance decisions and failure reason visualization
- quick links to artifacts/events per stage

This UI epic is intentionally after API/engine stabilization.

## 10. Open Decisions (implementation phase)

- Whether ACP stage adapter is one generic `acp_stage` type or multiple typed wrappers (`acp_plan`, `acp_review`, ...).
- Final shape of review loop counters (context-only vs persisted extension fields).
- Minimal required metadata fields for first-class UI readiness.

## 11. Definition of Done for This Design

- ACP-centric direction chosen and documented.
- L1/L2/L3 flow agreed.
- Domain-only now + workspace/instance future path explicitly captured.
- API-first entrypoint confirmed.
- UI deferred with concrete backlog item.
