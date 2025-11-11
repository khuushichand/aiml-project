# Async-Chat-Tools-Fix PRD

- Author: Core Chat Backend
- Date: 2025-11-11
- Status: Draft → Tracking

## Summary

Harden slash-command rate limiting and standardize chat orchestration on async paths to eliminate race conditions and reduce drift. Introduce an async command dispatcher and an async chat orchestrator (achat), migrate endpoint usage now, then phase in async across remaining call sites with a clear deprecation plan for the legacy sync path.

## Background

- Synchronous command routing in `command_router.dispatch_command` mutates `TokenBucket` fields directly, bypassing its internal asyncio lock, which is race-prone under concurrency.
- Initial fixes added:
  - `async_dispatch_command` using `await bucket.consume(1)` to respect locking.
  - Endpoint-level injection migrated to async dispatcher.
  - New `achat` orchestration that mirrors `chat()` but awaits async command dispatch and async provider calls.

Key references (current state):
- Async dispatcher: `tldw_Server_API/app/core/Chat/command_router.py:270`
- Endpoint using async dispatcher: `tldw_Server_API/app/api/v1/endpoints/chat.py:1119`
- Async chat orchestrator (achat): `tldw_Server_API/app/core/Chat/chat_orchestrator.py` (added below sync `chat`)

## Problem Statement

1. Rate-limit races: Direct mutation of token bucket fields in `dispatch_command` allows concurrent requests to bypass limits.
2. Drift risk: Duplicate sync/async orchestration paths increase maintenance burden and the chance of subtle divergences.
3. Inconsistent semantics: Some paths respect async rate limiting; others do not, depending on the caller.

## Goals

- Ensure all slash-command handling uses lock-safe token consumption (via async dispatcher).
- Consolidate orchestration on an async entrypoint (`achat`), retaining a safe sync wrapper for legacy callers.
- Maintain existing external API behavior; improve robustness under load.
- Preserve or improve test coverage, adding concurrency tests to verify rate-limiting correctness.

## Non-Goals

- Changing HTTP response shapes or endpoint contracts.
- Rewriting provider adapters or transport layers.
- Modifying streaming protocols.
- Altering injection mode semantics (system/preface/replace) beyond honoring configured modes.

## Stakeholders

- Backend/API maintainers (Chat, AuthNZ, Metrics)
- Frontend team (no API shape changes expected)
- QA/CI owners
- Downstream integrators using `Chat_Functions` shim

## User Stories

- As an API user, my `/chat/completions` calls with slash-commands are rate-limited consistently under concurrency.
- As a maintainer, I rely on a single async chat path, reducing drift and complexity.
- As a tester, I validate concurrency behavior deterministically without flaky tests.

## Requirements

### Functional
- All slash-command handling must route through `async_dispatch_command`.
- Async orchestrator `achat` provides parity with `chat` and is the canonical entry for new code.
- A safe sync wrapper remains available to avoid breaking legacy sync callers.
- No direct `TokenBucket` field writes outside rate-limiter internals.

### Quality
- Concurrency tests verify no token over-consumption under parallel load.
- No new flaky tests; CI stability maintained.
- Latency overhead is negligible (<5% p50 on slash-command path).

### Observability
- Preserve counters for invoked/success/error/rate_limited with command labels.
- Optionally log a one-time deprecation warning when sync `dispatch_command` is used.

## Success Metrics

- Concurrency test: N=20 parallel `/time` calls respect configured RPM; excess calls return `rate_limited`.
- Code search shows no direct writes to `TokenBucket.tokens/last_refill` outside rate-limiter code.
- Test pass rate unchanged; added coverage for async paths ≥80%.
- No “nested asyncio.run” or loop-related runtime errors.

## Technical Plan

### Phase 0 (Completed)
- Add `async_dispatch_command` and migrate endpoint to use it.
- Add `achat` that mirrors `chat` but awaits async command dispatch and `chat_api_call_async`.

Merged references:
- `tldw_Server_API/app/core/Chat/command_router.py:270`
- `tldw_Server_API/app/api/v1/endpoints/chat.py:1119`
- `tldw_Server_API/app/core/Chat/chat_orchestrator.py` (new `achat` function)

### Phase 1: Async-first orchestration
- Implement a robust sync wrapper for `chat` that internally runs `achat` safely:
  - If not in an event loop, run with `asyncio.run(achat(...))`.
  - If in a running loop, avoid `asyncio.run`; instead schedule and await appropriately (e.g., via `anyio` or loop task strategy) to prevent runtime errors in tests.
- Keep symbol compatibility (`chat`) to minimize churn.

### Phase 2: Call-site migration
- Replace remaining sync `dispatch_command` in async-capable contexts with `await async_dispatch_command`.
- Identify orchestrator consumers:
  - `Workflows.py` (sync): continue to use the sync wrapper or add an async variant if workflows are made async.
  - `Chat_Functions.chat`: keep shim; internally route to `achat` via the safe wrapper.

### Phase 3: Deprecation + Hardening
- Mark `dispatch_command` deprecated; optionally call into async dispatcher internally (best effort) or emit a one-time deprecation warning.
- Documentation: migration guidance to prefer `achat` and async dispatcher.

### Phase 4: Removal (Major Version)
- Remove sync-only token mutation logic and the deprecated `dispatch_command`.
- Require async-based orchestration across the stack.

## Migration Impact (Code Map)

- Use async dispatcher in endpoints (DONE): `tldw_Server_API/app/api/v1/endpoints/chat.py:1119`.
- Orchestrator async path (DONE): `achat` in `tldw_Server_API/app/core/Chat/chat_orchestrator.py`.
- Remaining sync call sites to evaluate:
  - `tldw_Server_API/app/core/Chat/chat_orchestrator.py:550` (sync path uses legacy `dispatch_command`).
  - `tldw_Server_API/app/core/Chat/Workflows.py` (sync caller of `chat`).
  - `Chat_Functions.chat` shim (sync) → update to call async via safe wrapper.

## Testing Strategy

### Unit
- `TokenBucket` concurrency: concurrent `consume` with `asyncio.gather`; assert tokens consumed ≤ capacity + refill allowance.
- `async_dispatch_command`: launch concurrent invocations; assert `rate_limited` results as expected; verify metrics increments.

### Integration
- `/chat/completions` with `CHAT_COMMANDS_ENABLED=1` across `system/preface/replace` injection modes; verify payload mutations unchanged vs. baseline.
- Concurrency test at 2× per-user RPM (+ jitter): confirm rate-limited responses and aggregate counters.

### Regression
- Ensure existing `Chat_NEW` tests pass. Prefer switching to `achat` with `pytest-asyncio` where low effort; otherwise rely on sync wrapper.

### Non-functional
- Benchmark p50 latency before/after migration for slash-command flows; ensure within budget.

## Milestones & Timeline

- M1 (Week 1): Sync wrapper over `achat` + docs. Add initial concurrency test.
- M2 (Week 2): Migrate low-effort tests to use `achat` (async marks). Keep wrapper for the rest.
- M3 (Week 2): Deprecation warning for `dispatch_command`. Update docs/changelog.
- M4 (Next release): Remove deprecated sync path and direct token mutations.

## Risks & Mitigations

- Nested event loop errors (e.g., `asyncio.run` inside a running loop):
  - Mitigate with a robust wrapper that detects loop state and uses loop-safe scheduling.
- Test brittleness from async transitions:
  - Keep sync wrapper; migrate incrementally; use `pytest-asyncio` fixtures where needed.
- Performance regressions:
  - Benchmark; keep additional awaits minimal; maintain debug-level logging.

## Rollout Plan

- Two releases:
  - R1: Dual-path; warnings on sync use; docs published; encourage `achat` adoption.
  - R2: Remove deprecated path.
- Optional feature gate: `CHAT_COMMANDS_ASYNC_ONLY=1` in non-prod to catch residual sync usage before R2.

## Docs & Communication

- Update Chat README and `REFACTORING_PLAN.md` to make `achat` the canonical orchestration entry.
- Migration guide for maintainers: switching to `achat`, test patterns with `pytest-asyncio`.
- Changelog entries for deprecation (R1) and removal (R2).

## Dependencies

- `pytest-asyncio` / `anyio` already present for async tests.
- No new runtime dependencies required.

## Acceptance Criteria

- All slash-command paths (endpoint + orchestrator) use `async_dispatch_command`.
- `achat` used by new async callers; `chat` remains as a stable sync wrapper.
- No direct `TokenBucket` field mutation outside `rate_limiter` internals.
- Concurrency tests pass; no rate-limit bypass observed.
- Deprecation warning emitted when `dispatch_command` is invoked (until removal).

