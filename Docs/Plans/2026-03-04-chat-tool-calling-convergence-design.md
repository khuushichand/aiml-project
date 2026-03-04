# Chat Tool-Calling Convergence Design (Approach C)

**Date:** 2026-03-04  
**Scope:** WebUI `/chat`, extension sidepanel chat, extension options/playground chat, and server chat orchestration paths.

## 1. Goal and Decision

This design adopts **Approach C: Full Agent-Loop Convergence** to improve:

- Reliability of tool-calling across chat paths.
- UX clarity for tool lifecycle and approval state.
- Safety with per-call approvals for risky tools.
- Behavioral parity across WebUI and extension surfaces.

Chosen policy:

- Default mode: **guided** (`tool_choice=auto` where executable tools are available).
- Safety model: **per-call approval** for risky tools; safe read-only tools auto-run.
- Rollout posture: aggressive, but with explicit compatibility and kill-switch guardrails.

## 2. Current-State Constraints (Verified)

The system already has mature tool-call and SSE behavior that must be preserved during migration:

- Server auto-exec for assistant tool calls exists in streaming and non-streaming chat flows.
- Streaming includes custom lifecycle and tool events (`stream_start`, `tool_results`, `stream_end`) plus OpenAI-style deltas and terminal `[DONE]`.
- Chat schemas and provider capability logic enforce `tool_choice`/`tools` compatibility rules.
- UI currently runs multiple specialized chat paths (normal, RAG, doc/tab, vision, compare), with partial duplication between WebUI and extension sidepanel.

## 3. Target Architecture

### 3.1 Unified Chat Loop Engine

Introduce a server-side **Chat Loop Engine** as the single orchestrator for tool-enabled chat turns:

`llm_step -> tool_proposed -> approval_gate -> tool_execute -> tool_result -> llm_step ... -> run_complete`

Loop state is represented as ordered events with stable sequencing.

### 3.2 Canonical Event Protocol

Define a canonical event envelope used by all clients:

- Required fields: `run_id`, `seq`, `ts`, `event`, `data`.
- Core events:
  - `run_started`
  - `llm_chunk`
  - `llm_complete`
  - `tool_proposed`
  - `approval_required`
  - `approval_resolved`
  - `tool_started`
  - `tool_finished`
  - `tool_failed`
  - `assistant_message_committed`
  - `run_complete`
  - `run_error`
  - `run_cancelled`

### 3.3 Shared Client Loop SDK

Create `apps/packages/ui/src/services/chat-loop/` to normalize loop events and expose shared state transitions for:

- WebUI `/chat`
- Extension sidepanel chat
- Extension options/playground chat

Surface-specific components remain, but they consume a common reducer/state machine.

## 4. Safety and Policy Model

### 4.1 Risk Tiers

Classify tool calls server-side:

- `safe_read`: read-only, non-destructive.
- `risky_write`: mutating operations.
- `risky_exec`: command/runtime-impact operations.

### 4.2 Approval Rules

- `safe_read` auto-executes in `auto` mode.
- `risky_write` and `risky_exec` require per-call approval.
- No risky tool executes without server-issued approval token.

### 4.3 Approval Token Binding

Approval token must bind:

- `run_id`
- `seq`
- `tool_call_id`
- `args_hash`
- `expiry`

Token is single-use and invalidated on mutation/race/replay.

## 5. Compatibility and Migration Strategy (Critical)

### 5.1 Dual-Emit Compatibility Phase (Required)

For at least one release, server emits:

- Existing SSE semantics (`stream_start`, OpenAI-style deltas, `tool_results`, `stream_end`, `[DONE]`), and
- New loop events (gated by a capability/header/flag).

This prevents immediate breakage of existing frontend/tests and third-party clients.

### 5.2 Single-Execution Gate (Required)

When loop mode is enabled for a request, **legacy auto-exec paths are disabled** for that request to avoid double execution.

### 5.3 `tool_choice` Normalization Rule (Required)

Server normalizes guided defaults safely:

- If executable tool set is empty/unavailable/unhealthy, coerce away invalid `tool_choice=auto` usage (omit or map to `none` as provider contract requires).
- Keep schema/capability compatibility deterministic across providers.

### 5.4 Mode Adapter Layer (Required)

Do not flatten all chat modes at once. Keep existing mode-specialized pre/post processing (RAG, doc/tab, vision, compare) and route only the tool lifecycle through the unified loop initially.

## 6. Persistence, Replay, and Performance

### 6.1 Append-Only Event Log

Persist ordered run events with cursor-based replay from `last_seq + 1`.

### 6.2 Checkpoint + Compaction Policy (Required)

Avoid unbounded token-event storage:

- Persist semantic milestones and bounded chunk summaries.
- Periodically checkpoint aggregate assistant text and tool state.
- Support replay from nearest checkpoint + tail events.

### 6.3 Reconnect Semantics

- Client reconnects with `run_id` + `last_seq`.
- Server returns event tail or snapshot+tail if history window rolled.
- Rebuild pending approvals and in-flight tool states exactly.

## 7. Error Model and Recovery

Typed failure events:

- `llm_error`
- `tool_error`
- `approval_timeout`
- `policy_denied`
- `run_cancelled`

UI action mapping is deterministic:

- Retry turn
- Edit and retry
- Approve/reject pending calls
- Cancel run
- Inspect failure reason

## 8. API Surface

Proposed loop endpoints (versioned under `/api/v1/chat/loop`):

- `POST /start`
- `GET /{run_id}/events` (SSE replay-aware)
- `POST /{run_id}/approve`
- `POST /{run_id}/reject`
- `POST /{run_id}/cancel`

Backward compatibility:

- Keep `/api/v1/chat/completions`.
- Tool-enabled calls can internally route to loop engine while preserving legacy response semantics in compat mode.

## 9. Observability and Audit

Metrics:

- run success/failure rate
- approval-required rate and approval latency
- tool success/failure by tool and risk tier
- replay/reconnect success rate
- parity mismatch counter across surfaces

Structured logs keyed by:

- `run_id`
- `tool_call_id`
- `approval_id`

Audit record includes:

- tool proposals
- approvals/rejections
- execution outcomes
- policy allow/deny reason

## 10. Testing Strategy

### 10.1 Contract Tests

- Event schema validation.
- Sequence monotonicity.
- Approval token binding and one-time usage.
- Replay cursor correctness.

### 10.2 Integration Tests

- Safe tool auto-run.
- Risky tool approval gating.
- Policy deny path.
- Cancel mid-tool.
- Reconnect recovery.
- Legacy dual-emit compatibility.

### 10.3 Frontend State Tests

- Shared loop reducer transitions.
- Pending approvals and resolution states.
- Snapshot + tail replay restoration.

### 10.4 E2E Parity Tests

Across WebUI `/chat`, extension sidepanel, extension options:

- Same prompt + settings => same tool lifecycle.
- Risky calls require approval in all surfaces.
- Consistent cancel/retry outcomes.

## 11. Implementation Slices

### Slice 1: Loop protocol + event store

- Run model, sequence model, event persistence, replay cursors.

### Slice 2: Loop executor + policy broker

- LLM/tool loop, risk tiering, approval gate, single-execution gate.

### Slice 3: Shared client loop SDK

- Common event reducer/service in `apps/packages/ui`.

### Slice 4: Surface migrations

- WebUI `/chat`, extension sidepanel/options to shared loop SDK.

### Slice 5: Compatibility hardening and cleanup

- Dual-emit complete, tests green, metrics/audit validated, deprecate legacy duplication.

## 12. Release Gates

Aggressive rollout is allowed only when all are true:

- Contract + integration + parity E2E pass.
- Zero P0/P1 regressions in streaming, approvals, or persistence.
- Emergency kill-switch verified.
- No observed double-execution in canary logs.

## 13. Risks and Mitigations Summary

1. Protocol breakage risk -> dual-emit compatibility phase.
2. Double-execution risk -> request-scoped single-execution gate.
3. `tool_choice` contract mismatch -> server normalization when tool set is empty.
4. Event-store growth risk -> checkpoint/compaction policy.
5. Multi-mode regression risk -> mode adapter layer during migration.
6. Approval replay/race risk -> strict token binding to run+seq+args hash.

## 14. Open Questions for Implementation Plan

- Exact DB schema for event checkpoints and retention windows.
- Whether loop endpoints are introduced as new routes or as action verbs on one route.
- Decommission timing for legacy client-side tool-call extraction paths.

