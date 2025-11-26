# Async-Chat-Tools-Fix PRD

- Author: Core Chat Backend
- Date: 2025-11-11
- Status: Tracking (Phase 0–4 complete)

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

### Phase 1: Async-first orchestration (Completed)
- Implement a robust sync wrapper for `chat` that internally runs `achat` safely using stdlib-only primitives (no new runtime deps):
  - If not in an event loop, run with `asyncio.run(achat(...))`.
  - If in a running loop on the current thread, do not call `asyncio.run` or `loop.run_until_complete` (would error/deadlock). Offload to a worker thread that runs a private loop via `asyncio.run` and block for result.
  - If invoking from a different thread and you hold a reference to the target loop, schedule with `asyncio.run_coroutine_threadsafe` and block on `future.result()`.
- Keep symbol compatibility (`chat`) to minimize churn.

#### Phase 1 Implementation Details

Decision: Do not add `anyio` as a runtime dependency for the wrapper. Prefer stdlib-only (`asyncio`, `threading`/`concurrent.futures`). `pytest-asyncio` remains for tests; `anyio` may be used in tests only if already present, but is not required.

Current implementation (2025-11-23):
- `achat(...)` is the canonical async orchestrator in `chat_orchestrator.py` and mirrors `chat(...)` behavior, including:
  - Slash-command handling via `async_dispatch_command`.
  - Image-history modes (`tag_past`, `send_all`, `send_last_user_image`) and RAG prefix construction aligned with the legacy sync path.
- `chat(...)` is now a sync wrapper with two code paths:
  - Non-streaming: routes through `_run_achat_sync(...)`, which calls `achat(...)` using:
    - `asyncio.run` when no event loop is running on the calling thread.
    - A `ThreadPoolExecutor` worker that owns its own event loop when a loop is already running.
  - Streaming: delegates to a preserved sync implementation `_chat_sync_impl(...)` so existing generator-based streaming behavior remains unchanged for legacy callers.
- `Chat_Functions.chat` remains a compatibility shim but internally calls `chat_orchestrator.chat`; it temporarily patches `chat_orchestrator.chat_api_call`, `chat_api_call_async`, and `load_and_log_configs` so tests that monkeypatch `Chat_Functions.chat_api_call` continue to work.
- `Workflows.py` imports `chat` from `chat_orchestrator`; sync workflows now transitively use `achat(...)` for non-streaming calls via the wrapper.
- New unit tests cover:
  - Sync-context invocation of `chat(...)` delegating to `achat(...)`.
  - Safe use of `chat(...)` from within a running event loop via `asyncio.to_thread(chat, ...)`.

Reference implementation (pseudocode):

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

# async canonical entry
async def achat(request: ChatRequest) -> ChatResponse:
    ...

def chat(request: ChatRequest) -> ChatResponse:
    """Sync wrapper around async `achat`.
    Safe across contexts: no loop, running loop (same thread), or cross-thread.
    """

    async def _runner() -> ChatResponse:
        return await achat(request)

    # Case A: no running loop on this thread → just run it
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_runner())

    # Case B: we are on a thread that already runs an event loop
    # Do NOT attempt asyncio.run() or loop.run_until_complete() here.
    # Option B1: offload to a worker thread and run a private loop there.
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(lambda: asyncio.run(_runner()))
        return fut.result()

def chat_on_loop(loop: asyncio.AbstractEventLoop, request: ChatRequest) -> ChatResponse:
    """Optional helper when you have a handle to a loop running on another thread.
    Safe to call from non-loop threads. Schedules onto `loop` and blocks for result.
    """
    cfut = asyncio.run_coroutine_threadsafe(achat(request), loop)
    return cfut.result()

# For async-aware callers, prefer using the async API directly:
async def achat_entry(request: ChatRequest) -> ChatResponse:
    return await achat(request)
```

Notes and variations:
- Tests or CLIs that own their loop can explicitly use `create_task` + `run_until_complete` on a loop they control:
  ```python
  loop = asyncio.new_event_loop()
  try:
      asyncio.set_event_loop(loop)
      task = loop.create_task(achat(req))
      result = loop.run_until_complete(task)
  finally:
      loop.close()
      asyncio.set_event_loop(None)
  ```
- From async contexts where you must not block the event loop, call the async API directly or offload the sync wrapper:
  - Python 3.9+: `result = await asyncio.to_thread(chat, req)`
  - Python 3.8: `loop = asyncio.get_running_loop(); result = await loop.run_in_executor(None, chat, req)`

  A small helper for external callers:

  ```python
  # Async code that needs to use the sync `chat(...)` wrapper without blocking the event loop.
  from tldw_Server_API.app.core.Chat import chat_orchestrator

  async def call_chat_from_async(req: ChatRequest) -> ChatResponse:
      # Prefer this pattern over calling chat(...) directly from async code.
      return await asyncio.to_thread(chat_orchestrator.chat, req.message, req.history, ...)
  ```

Test validation patterns (add under Testing Strategy):
- No-loop context: plain pytest test calls `chat(...)`; assert response; ensure no loop-related errors.
- Running-loop context: `pytest.mark.asyncio` test calls both:
  - `await achat(...)` (preferred async path) and
  - `res = await asyncio.to_thread(chat, ...)` to validate the sync wrapper path without blocking the loop.
- Nested-loop simulation: inside a running task (`asyncio.create_task(...)`), invoke `await asyncio.to_thread(chat, ...)` and ensure no deadlock; also verify that directly calling `chat(...)` completes (wrapper offloads to thread) albeit blocking the caller.
- FastAPI contexts:
  - Async endpoint uses `await achat(...)` (recommended). Validate with `fastapi.TestClient`.
  - Sync endpoint uses `chat(...)`; FastAPI runs sync endpoints in a threadpool, so wrapper takes the no-loop path (`asyncio.run`). Validate 200 and response parity.
  - Explicitly avoid calling `chat(...)` from within an async endpoint to prevent blocking the server loop; if present for legacy reasons, tests should still pass but mark as deprecated usage.

Python version constraint:
- Target Python >= 3.12 for development and CI.
- Compatible behaviors for 3.8–3.11:
  - Use `ThreadPoolExecutor` + `asyncio.run` as shown (available since 3.7).
  - Prefer `asyncio.to_thread` when available (3.9+); fall back to `loop.run_in_executor` on 3.8.
  - `asyncio.run_coroutine_threadsafe` is available across these versions and should only be used from threads other than the loop’s thread.

### Phase 2: Call-site migration
- Status: Complete (streaming + non-streaming slash-commands now async-rate-limited)
- Changes:
  - Introduced `_run_coro_sync(coro)` helper in `chat_orchestrator.py` to run async coroutines from sync code in a loop-safe manner (uses `asyncio.run` when no loop is running; otherwise offloads to a worker thread with its own loop).
  - Refactored `_run_achat_sync(...)` to delegate to `_run_coro_sync(achat(...))`, removing duplicate loop-detection logic.
  - Updated `_chat_sync_impl(...)` (streaming path) to replace `command_router.dispatch_command(...)` with:
    - `_run_coro_sync(command_router.async_dispatch_command(ctx, cmd_name, cmd_args))`
    - This keeps the public streaming API and generator semantics unchanged while ensuring slash-commands go through the async, lock-safe dispatcher.
  - Verified that:
    - FastAPI `/chat/completions` endpoint already uses `async_dispatch_command`.
    - Non-streaming sync `chat(...)` calls route through `_run_achat_sync(...)` → `achat(...)` → `async_dispatch_command`.
    - Streaming sync `chat(..., streaming=True, ...)` now uses `async_dispatch_command` via `_chat_sync_impl(...)` + `_run_coro_sync(...)`.
  - Added tests in `tests/Chat_NEW/unit`:
    - `test_run_coro_sync_inside_running_loop` exercises `_run_coro_sync` while a loop is active, via `asyncio.to_thread`.
    - `test_streaming_path_uses_async_dispatcher` patches both `command_router.async_dispatch_command` and `command_router.dispatch_command`, invokes `chat(..., streaming=True, message='/time', ...)`, exhausts the generator, and asserts that only the async dispatcher is called.
- Remaining sync surfaces:
  - `command_router.dispatch_command` remains for direct/legacy usage and is still responsible for its own internal rate-limiting behavior. It is no longer used by chat orchestration paths.
  - Deprecation and eventual removal of `dispatch_command` is tracked under Phase 3–4.

### Phase 3: Deprecation + Hardening

- Status: Complete (deprecation + core hardening applied prior to Phase 4 removal)

**Deprecation semantics for `dispatch_command`**

- `command_router.dispatch_command` now emits a `DeprecationWarning` the first time it is invoked in a process:
  - Implemented via a simple module-level guard `_DISPATCH_DEPRECATED_EMITTED` and `warnings.warn(..., DeprecationWarning, stacklevel=2)`.
  - The warning message notes that chat orchestration no longer uses `dispatch_command` and directs callers to `async_dispatch_command(...)` or the chat orchestrator (`achat` / its sync wrapper).
  - Function signature and behavior remain unchanged for legacy/internal callers.

**Rate-limiter hardening & TokenBucket usage**

- Removed direct `TokenBucket.tokens` / `last_refill` mutation from `dispatch_command` (prior to its removal in Phase 4):
  - Per-user, per-command rate limiting was moved behind TokenBucket methods so that all field mutations occur inside `TokenBucket` itself (via `consume` / related helpers), not in the router.

**Concurrency & deprecation-focused tests**

- Extended tests around command routing and rate limiting:
  - Deprecation behavior:
    - `tests/Chat_NEW/unit/test_command_router.py::test_dispatch_command_emits_deprecation_warning`:
      - Resets `_DISPATCH_DEPRECATED_EMITTED`, calls `dispatch_command`, and asserts a `DeprecationWarning` is captured with a “deprecated” message.
  - Async rate limiting robustness:
    - `tests/Chat_NEW/unit/test_command_router.py::test_async_dispatch_command_concurrent_respects_rate_limit`:
      - Sets `CHAT_COMMANDS_RATE_LIMIT=5`, issues 10 concurrent `async_dispatch_command` calls for `/time` with the same user id, and asserts exactly 5 succeed and 5 are rate-limited.
  - TokenBucket concurrency:
    - `tests/Chat_NEW/unit/test_rate_limiter.py::test_token_bucket_concurrent_consume_does_not_over_consume`:
      - Creates a `TokenBucket` with `capacity=5`, launches 10 concurrent `consume(1)` calls via `asyncio.gather`, and asserts that at most `capacity` calls succeed.

**Documentation & migration notes**

- With Phase 0–3 changes:
  - All chat orchestration paths (`achat`, sync `chat`, `/chat/completions`) now rely exclusively on `async_dispatch_command` for slash-commands and never call `dispatch_command`.
  - `dispatch_command` was temporarily preserved for direct/legacy usage and emitted a deprecation warning on first use in the vX.Y prerelease branch; it was removed entirely when Phase 4 shipped.
- Migration guidance (to be reflected in release notes):
  - New and existing async code should call `async_dispatch_command(...)` directly.
  - Chat-related integrations should prefer `achat` (async) or the sync `chat` wrapper instead of invoking the command router manually.
  - Callers still using `dispatch_command` should plan to migrate before the Phase 4 removal.

### Phase 4: Removal (Major Version)

- Status: Complete (legacy sync router removed; async dispatcher is the only supported entrypoint)

**Goal**

Eliminate the legacy sync command router path and any sync-only token mutation, making `async_dispatch_command` the only supported slash-command entrypoint.

**Success Criteria**

- No production code imports or calls `command_router.dispatch_command`.
- `dispatch_command` is removed (or stubbed to raise a clear runtime error) in a major release.
- All tests use `async_dispatch_command` or chat orchestrator (`achat` / `chat`) for slash-commands.
- TokenBucket usage outside rate-limiter internals is limited to well-defined helpers (including `try_consume_nowait`), with no stray field mutations.

**Stage 1: Final call-site audit and gating**

- Run a final repository-wide search for `dispatch_command(`:
  - Confirm remaining usages exist only in tests that explicitly cover deprecation/removal behavior.
- If any non-test call sites remain:
  - Migrate them to `async_dispatch_command` (async contexts) or to the chat orchestrator (`achat` / sync `chat`) as appropriate.
- Optional feature flag for early adopters:
  - Example: `CHAT_COMMANDS_SYNC_ROUTER_DISABLED=1` turns `dispatch_command` into a hard failure (e.g., raises `RuntimeError("dispatch_command removed; use async_dispatch_command")`).
  - Default off until the major release.

**Stage 2: Remove `dispatch_command` and sync router path**

- In `command_router.py`:
  - For the major release:
    - Either:
      - Remove `dispatch_command` entirely, or
      - Replace it with a small stub that raises a `RuntimeError` with a clear migration message.
  - Remove `_DISPATCH_DEPRECATED_EMITTED` and related warning logic once removal is active.
- Clean up tests:
  - Update `tests/Chat_NEW/unit/test_command_router.py`:
    - Replace tests that directly call `dispatch_command` with equivalents against `async_dispatch_command` where behavior is still relevant (time/weather/RBAC/rate-limit).
    - Keep a small test that asserts the removal behavior (e.g., calling `dispatch_command` raises).
  - Remove or adjust any tests that specifically assumed `dispatch_command` as a supported surface.

**Stage 3: TokenBucket API consolidation**

- Review `TokenBucket` usage:
  - Ensure all callers use:
    - `consume`, `wait_for_tokens`, or `refund` in async contexts.
    - `try_consume_nowait` only where sync, best-effort behavior is explicitly acceptable (if any such callers remain).
- If `try_consume_nowait` becomes unused:
  - Consider deprecating or removing it in a follow-up minor/major step.
- Confirm via code search:
  - No direct writes to `tokens` / `last_refill` outside `TokenBucket` methods.

**Stage 4: Test and migration verification**

- Unit:
  - Ensure all `command_router` unit tests pass using `async_dispatch_command` only.
  - If `dispatch_command` now raises, add a small unit test verifying the error message and type.
- Integration:
  - Re-run Chat and Chat_NEW suites with `CHAT_COMMANDS_ENABLED=1` to confirm:
    - Slash-commands behave as before through the orchestrator.
    - No deprecation warnings; only the async path is exercised.
- Optional (if using a feature flag):
  - With flag disabled: `dispatch_command` import still fails/raises as documented.
  - With flag enabled (prior to removal): `dispatch_command` raises immediately, but other paths remain functional.

**Stage 5: Documentation & versioning**

- PRD (`Async-Chat-Tools-Fix.md`):
  - Update Phase 4 section status to “Complete” once done.
  - Note the version where `dispatch_command` was removed/stubbed.
- Public docs / changelog:
  - Add a breaking change note:
    - “`command_router.dispatch_command` has been removed. Use `async_dispatch_command` or the chat orchestrator (`achat` / `chat`) instead.”
  - Provide a short migration snippet for legacy code that previously called `dispatch_command` directly.
- Versioning:
  - Tie the removal to a major version bump (or clearly marked breaking release) to respect semver expectations.

## Migration Impact (Code Map)

- Use async dispatcher in endpoints (DONE): `tldw_Server_API/app/api/v1/endpoints/chat.py:1119`.
- Orchestrator async path (DONE): `achat` in `tldw_Server_API/app/core/Chat/chat_orchestrator.py`.
- Sync wrapper over async orchestrator (DONE):
  - `chat(...)` in `chat_orchestrator.py` acts as a sync wrapper over `achat(...)` for non-streaming calls via `_run_achat_sync(...)`.
  - Streaming sync behavior is preserved via `_chat_sync_impl(...)` for legacy generator-based consumers.
- Current remaining sync/legacy surfaces:
  - `_chat_sync_impl(...)` in `chat_orchestrator.py` still uses `dispatch_command` for slash-commands on the streaming path.
  - `tldw_Server_API/app/core/Chat/command_router.dispatch_command` still mutates `TokenBucket` fields directly (to be addressed in Phases 2–3).
  - Async-capable call sites that still use `dispatch_command` (outside orchestrator streaming) must migrate to `async_dispatch_command` in Phase 2.

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

- No new runtime dependencies required.
- Sync wrapper uses stdlib-only (`asyncio`, `threading`/`concurrent.futures`); do not add `anyio` for runtime bridging.
- `pytest-asyncio` remains for async tests; `anyio` may be used in tests only if already present, but is not required.

## Acceptance Criteria

- All slash-command paths (endpoint + orchestrator) use `async_dispatch_command`.
- `achat` used by new async callers; `chat` remains as a stable sync wrapper.
- No direct `TokenBucket` field mutation outside `rate_limiter` internals.
- Concurrency tests pass; no rate-limit bypass observed.
- Deprecation warning emitted when `dispatch_command` is invoked (until removal).
