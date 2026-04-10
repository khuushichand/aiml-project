# Shared SQLite Backend Reuse Design

Date: 2026-04-09
Status: Approved for planning
Owner: Codex brainstorming session
Supersedes: `Docs/superpowers/specs/2026-04-06-sqlite-backend-log-noise-design.md`

## Summary

Reduce repeated `Creating sqlite backend` log noise by fixing the underlying churn instead of aggregating logs. The design makes SQLite backend reuse a first-class responsibility of the shared backend factory, so repeated requests for the same normalized SQLite target resolve to one shared backend instance. Wrapper objects remain disposable, but SQLite backend pools become process-scoped shared resources with centralized cleanup.

## Problem

The current log noise is a symptom of repeated backend construction:

- [factory.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/backends/factory.py) logs `Creating sqlite backend` on every `DatabaseBackendFactory.create_backend(...)` call.
- The media request path already has a higher-level cache in [DB_Deps.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py), but repeated SQLite backend creation still occurs when that cache is bypassed, reset, or duplicated by other call sites.
- Multiple DB helpers, including [Collections_DB.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/Collections_DB.py) and [ChaChaNotes_DB.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py), call the shared factory directly and currently assume they own any SQLite backend they construct.

This creates two linked issues:

- low-value `INFO` noise from repeated backend creation
- unnecessary SQLite backend and pool churn for the same DB path/config

## Goals

- Reuse one SQLite backend per normalized SQLite target and effective SQLite policy.
- Reduce `Creating sqlite backend` log noise as a consequence of real reuse.
- Apply the reuse model to both the media DB request path and direct SQLite-using DB helpers.
- Centralize SQLite backend shutdown and reset behavior.
- Preserve existing PostgreSQL behavior.

## Non-Goals

- Redesign PostgreSQL backend ownership.
- Change higher-level wrapper lifetimes or make wrappers singleton objects.
- Introduce log aggregation or rate-limited duplicate summaries as the primary fix.
- Expand this work into unrelated DB abstraction refactors.

## Requirements Confirmed With User

- Do not optimize for log suppression alone.
- Target both the media DB request path and direct factory callers in one design.
- Share SQLite backends by normalized target and config.
- Treat centralized shutdown as the new ownership model.
- Allow helper `close()` paths to become release or no-op style for shared SQLite pools.

## Current State

### Shared reuse exists only in selected places

- [DB_Deps.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py) caches `MediaDbFactory` objects per user.
- [session.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/media_db/runtime/session.py) lets a `MediaDbFactory` own one SQLite backend for a single DB path.

This already proves the codebase can safely reuse SQLite backends in some paths, but the reuse boundary is inconsistent and incomplete.

### Many wrappers still build SQLite backends directly

Representative direct callers include:

- [Collections_DB.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/Collections_DB.py)
- [ChaChaNotes_DB.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py)
- [UserDatabase_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/UserDatabase_v2.py)
- [Watchlists_DB.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/Watchlists_DB.py)
- [Workflows_Scheduler_DB.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/Workflows_Scheduler_DB.py)
- [media_db/runtime/backend_resolution.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/media_db/runtime/backend_resolution.py)

Because these paths all use `DatabaseBackendFactory.create_backend(...)`, the current factory log repeats even when the effective SQLite target is identical.

### Ownership semantics are local, not centralized

Some helpers currently assume that if they resolved the backend, they can close its pool directly in their own `close()` or teardown path. That assumption prevents safe process-wide reuse for SQLite.

## Approaches Considered

### Approach 1: Keep behavior the same and only suppress or aggregate logs

Pros:

- Smallest code change.
- Low risk to runtime behavior.

Cons:

- Does not address repeated backend creation.
- Keeps the system paying the churn cost.
- Turns an implementation issue into a logging policy workaround.

### Approach 2: Fix only the media DB request path

Pros:

- Narrower change set.
- Likely removes a large share of the repeated events.

Cons:

- Leaves direct SQLite helper construction untouched.
- Produces two incompatible ownership models in one subsystem.

### Approach 3: Centralize shared SQLite backend reuse in the factory

Pros:

- Solves both the hot request path and direct caller churn.
- Makes the factory responsible for the resource it creates.
- Reduces log noise naturally because creation only happens on cache miss.

Cons:

- Requires an ownership contract change for wrapper `close()` paths.
- Needs careful reset and shutdown handling.

## Recommendation

Use Approach 3.

The correct boundary is not “aggregate the message” but “stop constructing the same SQLite backend repeatedly.” The shared backend factory already sits at the point where all these callers converge, so it is the right place to define canonical reuse, locking, and cleanup.

## Proposed Design

### 1. Add a factory-owned shared SQLite registry

`DatabaseBackendFactory.create_backend(...)` should keep its current API but change SQLite behavior:

- For PostgreSQL, keep the current create-and-return behavior.
- For SQLite, compute a canonical signature and return the shared backend for that signature.

The SQLite signature should include:

- backend type
- normalized SQLite target
- effective SQLite settings that materially affect connection behavior

For the current implementation, the planning assumption is:

- include `sqlite_wal_mode`
- include `sqlite_foreign_keys`
- do not include non-functional correlation fields such as `client_id`
- do not include settings the current SQLite backend does not use to shape connection behavior, such as `pool_size` or `echo`

The signature should use normalized file paths or canonical SQLite URIs so logically identical configurations converge on one key.

### 2. Normalize SQLite identity before lookup

Add a dedicated normalization helper in [factory.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/backends/factory.py) so identity rules are not spread across call sites.

Normalization should distinguish:

- file-backed paths
- `:memory:` databases
- SQLite file URIs

It should preserve meaningful differences but collapse trivial textual ones such as equivalent absolute paths.

In-memory policy must be explicit:

- raw `:memory:` remains per-construction and is excluded from shared reuse
- anonymous in-memory targets that only preserve process-local isolation semantics are also excluded from shared reuse
- explicit named shared-cache memory URIs may participate in reuse, but only when their normalized URI identity matches exactly

This keeps the new registry from breaking the current use of `:memory:` as a test and helper isolation boundary.

### 3. Change ownership from local to centralized

Wrapper objects remain short-lived, but the underlying SQLite backend becomes a shared process resource.

That means:

- helper constructors may still call `DatabaseBackendFactory.create_backend(...)`
- wrapper `close()` methods should stop closing shared SQLite pools directly
- wrapper teardown should instead release their local claim or become a no-op when the backend is factory-managed
- actual pool shutdown happens only through centralized reset and shutdown paths

To support this cleanly, the factory should expose a release helper for managed backends so higher-level callers do not need to inspect private registry state.

### 4. Keep existing higher-level caches, but make them secondary

The per-user `MediaDbFactory` cache in [DB_Deps.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py) still provides value and should remain.

Its role changes from “the only thing stopping backend churn” to “a higher-level object cache on top of shared backend reuse.”

This gives two benefits:

- repeated request resolution stays cheap
- even if that higher-level cache misses or resets, the same SQLite backend can still be reused underneath

### 5. Make factory logging reflect actual creation

Once SQLite reuse is centralized, `Creating sqlite backend` should only be emitted when a new shared backend is actually created, not when the factory returns an existing one.

No separate aggregation layer is needed. Log noise reduction becomes a direct consequence of real resource reuse.

## Component Responsibilities

### Shared backend factory

Responsible for:

- canonical SQLite signature generation
- thread-safe lookup-or-create for SQLite backends
- managed backend release bookkeeping
- centralized bulk shutdown of managed backends

The new SQLite registry should coexist with the existing named backend cache in [factory.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/backends/factory.py), not create a second competing ownership model. `get_backend(name, ...)` may still cache named handles, but when it resolves a SQLite backend it should land on the same canonical shared backend instance used by direct `create_backend(...)` callers.

### Wrapper and helper classes

Responsible for:

- asking the factory for a backend
- treating returned SQLite backends as shared unless explicitly injected otherwise
- releasing or ignoring shared backend cleanup locally
- keeping their existing schema/setup behavior

The first wave of ownership updates should be limited to the paths already confirmed to own or close SQLite resources directly:

- `MediaDbSession.release_context_connection()` and `MediaDbFactory.close()` in [session.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/media_db/runtime/session.py)
- `CollectionsDatabase.close()` in [Collections_DB.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/Collections_DB.py)
- the `CharactersRAGDB` close and pool-shutdown path in [ChaChaNotes_DB.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py)

Other direct factory callers such as `Watchlists_DB`, `UserDatabase_v2`, and scheduler-adjacent wrappers remain in scope for compatibility review, but they do not need to be part of the first ownership-migration slice unless they are confirmed to close managed shared pools directly.

### Reset and shutdown paths

Responsible for:

- closing each managed shared backend once
- clearing the registry
- preserving test isolation and process teardown semantics

## Data Flow

### Media DB request path

1. Request code resolves the current user in [DB_Deps.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py).
2. `MediaDbFactory` is fetched or created for that user.
3. The factory asks `DatabaseBackendFactory.create_backend(...)` for the SQLite backend for that user DB path.
4. The shared backend registry returns the existing backend if the signature matches.
5. Request-scoped wrapper objects are created on top of that shared backend.

### Direct helper paths

1. A helper such as `CollectionsDatabase` or `CharactersRAGDB` resolves a SQLite path.
2. It calls `DatabaseBackendFactory.create_backend(...)`.
3. The shared registry returns the canonical backend for that normalized target.
4. The helper uses the shared backend and later releases the handle without closing the shared pool.

## Lifecycle And Failure Handling

### Concurrency

The SQLite registry must be protected by a lock so concurrent lookup-or-create calls for the same signature cannot create duplicate pools.

### Failed initialization

If backend creation fails:

- no partial registry entry should remain
- the exception should propagate unchanged to the caller
- future attempts for that same signature should be able to retry cleanly

### Release behavior

Release bookkeeping may track active holders for diagnostics, but zero active holders does not automatically close the backend. Actual closure is centralized and explicit.

### Reset behavior

Central reset paths such as:

- [reset_media_db_cache()](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py)
- [close_all_backends()](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/backends/factory.py)

should close each managed backend once and clear the registry. Existing wrapper instances after reset may become stale, which is acceptable because reset is already a lifecycle boundary used for tests or teardown.

## Testing

### Factory-level unit tests

- same normalized SQLite target returns the same backend instance
- different SQLite targets return different backend instances
- different effective SQLite policies that materially change connection behavior produce distinct instances
- failed SQLite creation does not poison the registry

### Ownership and cleanup tests

- helper `close()` paths no longer close shared SQLite pools directly
- centralized reset closes shared pools exactly once
- release of a shared backend does not break another active consumer using the same backend

### Media DB regression tests

- repeated media DB resolution for the same user reuses the same underlying SQLite backend
- resetting the media DB cache clears higher-level factories without leaving the shared backend registry in an inconsistent state

### Cross-wrapper regression tests

- one direct helper path and one media path can both resolve the same underlying SQLite backend safely when pointed at the same normalized target

## Rollout Plan

1. Add the shared SQLite registry and canonical signature logic in [factory.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/DB_Management/backends/factory.py) with focused unit tests.
2. Update the first-wave ownership paths to stop directly closing managed shared SQLite pools: media runtime session/factory cleanup, `CollectionsDatabase.close()`, and the `CharactersRAGDB` close path.
3. Verify the media DB request path still behaves correctly under cache hits, cache resets, and test isolation.
4. Sweep remaining direct SQLite factory callers in `DB_Management` for ownership compatibility. The exit criterion is not “every caller changed,” but “every caller reviewed, and only callers that directly close or invalidate a factory-managed SQLite pool changed.”

## Risks

- A too-broad signature could incorrectly merge backends that should stay distinct.
- A too-narrow signature could reduce reuse and preserve some churn.
- Missing one direct close path could allow one wrapper to shut down a shared pool unexpectedly.
- Test helpers that assume per-instance teardown may need small updates to use centralized reset.

## Open Questions

None for planning. The key decisions were confirmed during brainstorming:

- fix the structural churn, not just the log line
- cover both media and direct helper paths
- share SQLite backends by normalized target and config
- centralize cleanup
