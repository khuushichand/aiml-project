# SQLite Shared Runtime Centralization Design

**Date:** 2026-03-13

## Goal

Finish centralizing SQLite runtime connection policy for the remaining shared service modules that still hand-roll PRAGMA setup.

## Scope

This pass covers runtime connection bootstrap in:

- `tldw_Server_API/app/core/Scheduler/backends/sqlite_backend.py`
- `tldw_Server_API/app/core/Evaluations/db_adapter.py`
- `tldw_Server_API/app/core/Embeddings/vector_store_meta_db.py`
- `tldw_Server_API/app/core/Embeddings/vector_store_batches_db.py`
- `tldw_Server_API/app/core/RAG/rag_service/connection_pool.py`
- `tldw_Server_API/app/core/Slides/slides_db.py`
- `tldw_Server_API/app/core/DB_Management/sqlite_policy.py`

## Non-Goals

- Reworking PostgreSQL backends
- Changing migration or schema-rebuild behavior
- Touching one-shot maintenance/bootstrap helpers such as Jobs migrations, audit shared migration, or AuthNZ startup integrity
- Refactoring large legacy modules like `ChaChaNotes_DB.py`

## Recommended Approach

Use the existing shared SQLite policy helper for live connection bootstrap only, then keep intentional per-module differences local after the helper call.

### Why this approach

- It completes the runtime policy sweep without dragging migration code into the same risk envelope.
- It preserves module-specific tuning such as `mmap_size`, custom `cache_size`, and shorter `busy_timeout` values.
- It keeps the helper procedural and small instead of turning it into a module-aware abstraction.

## Design

### Shared helper contract

Reuse the existing helper functions:

- `configure_sqlite_connection(...)`
- `configure_sqlite_connection_async(...)`
- `begin_immediate_if_needed(...)`

The helper should remain generic. Any local tuning stays at the call site.

### Scheduler SQLite backend

Replace the async PRAGMA loop in `connect()` with `configure_sqlite_connection_async(...)`, passing:

- `busy_timeout_ms=5000`
- `cache_size=10000`
- `temp_store="MEMORY"`

Keep the current `BEGIN IMMEDIATE` transaction behavior and foreign-key assertions unchanged.

### Evaluations DB adapter

Replace the local PRAGMA list in `_init_connection()` with `configure_sqlite_connection(...)`, then keep:

- `PRAGMA mmap_size=268435456`

as a local post-helper statement.

### Embeddings vector store metadata and batches DBs

Replace the `_prime()` implementations in:

- `vector_store_meta_db.py`
- `vector_store_batches_db.py`

with the shared sync helper using:

- `busy_timeout_ms=3000`
- `temp_store=None`
- `synchronous=None`
- `foreign_keys=False`

This preserves their current lightweight behavior while still moving WAL and timeout setup through the shared policy path.

### RAG connection pool

Replace the runtime PRAGMAs in `MultiDatabasePool._create_connection()` with the shared sync helper. Preserve the current behavior that only enables WAL/synchronous when `enable_wal` is true, while keeping foreign keys enabled. Do not introduce per-PRAGMA suppression here; the current behavior is that SQLite setup failures abort connection creation.

### Slides DB

Apply the shared sync helper in `get_connection()`, not only in `_ensure_schema()`, so every thread-local runtime connection gets the same policy. Slides should adopt the full shared runtime policy, and `_ensure_schema()` should remain focused on schema initialization only.

## Error Handling

- Strict modules stay strict: scheduler, evaluations, and RAG should continue to surface connection/bootstrap failures.
- Best-effort modules stay best-effort: the embeddings metadata/batches DBs should continue suppressing PRAGMA failures where they already do.
- Local post-helper statements should inherit the existing module error policy rather than introducing a new one.

## Testing Strategy

Prefer extending existing suites:

- `tldw_Server_API/tests/Scheduler/test_sqlite_backend.py`
- `tldw_Server_API/tests/Evaluations/test_db_adapter.py`
- `tldw_Server_API/tests/Evaluations/test_connection_pool.py`
- `tldw_Server_API/tests/VectorStores/test_vector_stores_admin_users.py`
- `tldw_Server_API/tests/DB_Management/test_sqlite_memory_no_artifacts.py`
- `tldw_Server_API/tests/Slides/test_slides_db.py`

Add small focused regression tests only where needed:

- scheduler runtime PRAGMA assertions beyond foreign keys
- evaluations DB adapter helper delegation / runtime PRAGMAs
- vector-store metadata and batches connection PRAGMAs
- RAG pool runtime PRAGMAs, especially no-WAL behavior for `:memory:` and the disabled-WAL path
- slides runtime PRAGMAs for the shared policy on every runtime connection

## Verification

After implementation:

- run the new focused red/green tests first
- run a targeted pytest sweep for scheduler, evaluations, vector stores, RAG memory behavior, and Slides
- run Bandit on the touched Python files
