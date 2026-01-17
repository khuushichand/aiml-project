# PRD: Async Chat Tools Fix — Migrate to Async Slash-Command Rate Limiting and Orchestrator

> Tracking issue for the PRD at: `Docs/Design/Async-Chat-Tools-Fix.md`

## Summary
Harden slash-command rate limiting and standardize chat orchestration on async paths to eliminate race conditions and reduce drift, using `async_dispatch_command` and the new `achat` orchestrator.

## Problem
- Sync `dispatch_command` directly mutates `TokenBucket` fields (race-prone).
- Duplicate sync/async paths invite drift and inconsistent concurrency semantics.

## Goals
- All slash-commands use lock-safe `async_dispatch_command`.
- Canonical async orchestration via `achat`; keep a safe sync wrapper for legacy callers.
- Maintain API behavior; add concurrency tests to validate rate limiting.

## Acceptance Criteria
- All slash-command paths (endpoint + orchestrator) route through `async_dispatch_command`.
- `achat` used by async callers; `chat` acts as a safe sync wrapper.
- No direct `TokenBucket` field writes outside rate-limiter internals.
- Concurrency tests pass (no rate-limit bypass under parallel load).
- Deprecation warning emitted when `dispatch_command` is invoked (until removal).

## Phases & Tasks

- [x] Phase 0: Initial async path
  - [x] Add `async_dispatch_command` using `await bucket.consume(1)`.
  - [x] Migrate endpoint `/chat/completions` to async dispatcher.
  - [x] Add `achat` orchestrator (async) mirroring `chat`.

- [ ] Phase 1: Async-first orchestration
  - [ ] Implement robust sync wrapper: run `achat` via `asyncio.run` when no loop; handle running-loop case safely.
  - [x] Retire the legacy compatibility shim and route callers through `chat_orchestrator`/`chat_service`.

- [ ] Phase 2: Call-site migration
  - [ ] Replace remaining `dispatch_command` usage in async contexts with `await async_dispatch_command`.
  - [ ] Audit `Workflows.py` and other call sites; prefer `achat` or sync wrapper as appropriate.

- [ ] Phase 3: Deprecation & Hardening
  - [ ] Emit one-time deprecation warning when `dispatch_command` is used.
  - [ ] Update docs (README, refactoring plan) to describe `achat` as canonical.

- [ ] Phase 4: Removal (next major)
  - [ ] Remove sync-only token mutation logic and `dispatch_command`.

## Testing
- Unit: concurrent `consume` behavior; async dispatcher concurrency; metrics increments.
- Integration: `/chat/completions` with system/preface/replace modes; verify payloads and rate limits.
- Concurrency: 2× per-user RPM (+ jitter) returns rate-limited responses appropriately.

## References
- PRD: `Docs/Design/Async-Chat-Tools-Fix.md`
- Async dispatcher: `tldw_Server_API/app/core/Chat/command_router.py:270`
- Endpoint migration: `tldw_Server_API/app/api/v1/endpoints/chat.py:1119`
- Async orchestrator: `tldw_Server_API/app/core/Chat/chat_orchestrator.py` (function `achat`)

## Suggested Labels
`area:chat`, `type:enhancement`, `tech-debt`, `performance`, `stability`

## Optional: Create via gh (if authenticated)
```bash
gh issue create \
  --title "PRD: Async Chat Tools Fix — Migrate to Async Slash-Command Rate Limiting and Orchestrator" \
  --body "Tracking PRD: Docs/Design/Async-Chat-Tools-Fix.md\n\nSee issue file Docs/Issues/Async-Chat-Tools-Fix-Issue.md for tasks and details."
```
