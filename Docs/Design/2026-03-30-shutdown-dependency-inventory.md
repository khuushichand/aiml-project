# Shutdown Dependency Inventory

## Scope

This note inventories the shutdown behavior currently embedded in `tldw_Server_API/app/main.py` so the new shadow-mode adapter can observe the existing teardown graph without replacing it yet.

## Implicit Shutdown Groups In `main.py`

1. Transition gate
   - Flip lifecycle readiness to draining.
   - Gate new job acquisition through `JobManager.set_acquire_gate(True)`.

2. Background worker drain
   - Cancel or signal shutdown for cleanup tasks and job workers.
   - Includes ephemeral cleanup, chatbooks cleanup, core/file/data-table/prompt-studio/privilege/audio/presentation/media ingest/readiness digest/reminder/admin backup/notifications and related workers.

3. Scheduler and helper shutdown
   - Stop usage aggregators.
   - Stop workflow, reading-digest, admin-backup, companion-reflection, reminders, and connectors sync schedulers.
   - Stop AuthNZ scheduler.

4. Service and cache cleanup
   - Stop storage cleanup service.
   - Reset storage and cleanup services.
   - Reset AuthNZ limiter and other singleton helpers.

5. Transport, session, and client owners
   - Shut down session manager, MCP server, HTTP client sessions, and TTS/resource manager owners.
   - Stop provider/request queue owners and local LLM cleanup hooks.

6. Final process cleanup
   - Close database pools, caches, audit services, evaluators, executors, and CPU pools.
   - Clear the media DB cache and content backend pool.

## Duplicate Owners / Duplicate Stop Paths

- `JobManager.set_acquire_gate(False)` is the startup default, then the shutdown path flips it to `True`, and the very end flips it back to `False` again. That makes the gate both a transition concern and a process-finalization concern.
- `AuthNZ scheduler` is a lifecycle-owned component that is stopped in the later shutdown block, while the transition gate is handled earlier. The scheduler itself is not duplicated, but its shutdown dependency is split across two separate ownership regions.
- `storage_cleanup_service` has both an explicit `stop()` call and separate singleton reset helpers afterward. That is two stop-related ownership paths for one service boundary.
- `audit` cleanup is split between dependency-injection managed shutdown and explicit adapter/service shutdown calls, which makes the ownership boundary easy to misread.

## Aggregate Helpers Hiding Serial Work

- `stop_usage_aggregator()` and `stop_llm_usage_aggregator()` hide work behind single helper calls even though they wrap task lifecycle management.
- `shutdown_all_audit_services()` hides multiple service instances behind one helper.
- `shutdown_all_registered_executors()` hides potentially many executor pools and thread/process resources.
- `shutdown_content_backend()`, `shutdown_http_client()`, `shutdown_evaluations_pool_if_initialized()`, and `shutdown_webhook_manager_if_initialized()` each hide multiple concrete cleanup steps behind a single call.
- The final teardown block reads as linear, but some of the helpers inside it are aggregate cleanups with their own internal ordering.

## Long-Lived Transport / Session Owners

- `session_manager`
- `mcp_server`
- `shutdown_http_client()`
- `provider_manager`
- `request_queue`
- `tts_resource_manager`
- `voice_manager`

These owners are likely to hold connections or long-lived background state, so their relative ordering matters more than the call sites suggest.

## Unknown Ordering Edges

- Whether `usage_aggregator` and `llm_usage_aggregator` must stop before or after `AuthNZ scheduler`.
- Whether `storage_cleanup_service.stop()` must complete before the later singleton reset helpers run.
- Whether `mcp_server.shutdown()` should precede `shutdown_rate_limiter()` or vice versa.
- Whether session/client shutdown should happen before or after executor teardown to avoid lingering callbacks.
- Whether the final database/cache cleanup should run before or after audit service shutdown in all environments.

## Shadow-Mode Adapter Targets

The first shadow inventory only needs to make the legacy graph visible, not replace it. The initial adapter set should keep the transition gate, `usage_aggregator`, `llm_usage_aggregator`, `storage_cleanup_service`, `chatbooks_cleanup`, and `authnz_scheduler` explicit so later work can split the graph into smaller executable phases without guessing at the current ownership.
