# SQLite Shared Runtime Centralization Implementation Plan

> **Required sub-skill:** Use superpowers:subagent-driven-development to implement this plan task-by-task in the current session.

**Goal:** Centralize the remaining shared-module SQLite runtime PRAGMA setup behind the shared helper while preserving intentional module-local tuning and failure behavior.

**Architecture:** Reuse `sqlite_policy.py` for live connection bootstrap in the scheduler SQLite backend, evaluations DB adapter, embeddings metadata/batches DBs, RAG connection pool, and Slides DB. Apply the Slides helper in `get_connection()` so every runtime connection is standardized, and preserve RAG's existing whole-connection failure semantics. Keep local-only tuning such as `mmap_size`, `cache_size`, and shorter timeouts beside the helper calls. Leave migration/bootstrap-only paths unchanged.

**Tech Stack:** Python, sqlite3, aiosqlite, pytest

---

## Stage 1: Finalize Design And Runtime Scope
**Goal**: Capture the remaining shared runtime modules and explicitly exclude migrations and maintenance helpers.
**Success Criteria**: Design doc lists the touched modules, helper usage pattern, local exceptions, and verification plan.
**Tests**: None.
**Status**: Complete

## Stage 2: Red Tests For Remaining Shared Runtime Integrations
**Goal**: Add failing tests that prove the remaining shared modules still hand-roll runtime PRAGMAs or bypass the helper contract.
**Success Criteria**: New assertions fail before production code changes.
**Tests**:
- `python -m pytest tldw_Server_API/tests/Scheduler/test_sqlite_backend.py -v`
- `python -m pytest tldw_Server_API/tests/Evaluations/test_db_adapter.py -v`
- `python -m pytest tldw_Server_API/tests/VectorStores/test_vector_stores_admin_users.py tldw_Server_API/tests/DB_Management/test_sqlite_memory_no_artifacts.py -v`
- `python -m pytest tldw_Server_API/tests/Slides/test_slides_db.py -v`
**Status**: Complete
**Results**:
- Confirmed intended red failures before production changes in Scheduler helper adoption, Evaluations adapter helper adoption, VectorStore metadata/batches helper adoption, RAG helper adoption for WAL toggle, and Slides runtime PRAGMA propagation.

## Stage 3: Implement Helper Adoption In Remaining Shared Runtime Modules
**Goal**: Replace duplicated runtime PRAGMA blocks with helper calls while preserving module-local behavior.
**Success Criteria**: Scheduler, evaluations adapter, embeddings vector-store DBs, RAG pool, and Slides use the shared runtime policy for SQLite bootstrap.
**Tests**:
- Re-run the Stage 2 commands after each module batch.
**Status**: Complete
**Results**:
- Scheduler now uses `configure_sqlite_connection_async(...)` with local `cache_size` and timeout overrides.
- Evaluations adapter now uses `configure_sqlite_connection(...)` plus local `mmap_size`.
- VectorStore metadata and batches DBs now use the shared helper in best-effort mode with their lightweight overrides.
- RAG connection creation now uses the shared helper while preserving conditional WAL and `synchronous`.
- Slides now applies the shared runtime policy in `get_connection()` so every thread-local connection is configured.

## Stage 4: Broader Regression Verification
**Goal**: Prove the runtime centralization does not change expected behavior outside the touched PRAGMA setup.
**Success Criteria**: Targeted existing suites for scheduler, evaluations, vector stores, RAG memory behavior, Slides, and SQLite policy integrations pass.
**Tests**:
- `python -m pytest tldw_Server_API/tests/Scheduler/test_sqlite_backend.py tldw_Server_API/tests/Evaluations/test_db_adapter.py tldw_Server_API/tests/Evaluations/test_connection_pool.py tldw_Server_API/tests/VectorStores/test_vector_stores_admin_users.py tldw_Server_API/tests/DB_Management/test_sqlite_memory_no_artifacts.py tldw_Server_API/tests/Slides/test_slides_db.py -v`
**Status**: Complete
**Results**:
- `35 passed, 5 warnings in 96.93s`

## Stage 5: Security Verification And Status Update
**Goal**: Run Bandit on the touched scope and update this plan with actual results.
**Success Criteria**: New findings in changed code are fixed or accurately reported before completion.
**Tests**:
- `python -m bandit -r tldw_Server_API/app/core/Scheduler/backends/sqlite_backend.py tldw_Server_API/app/core/Evaluations/db_adapter.py tldw_Server_API/app/core/Embeddings/vector_store_meta_db.py tldw_Server_API/app/core/Embeddings/vector_store_batches_db.py tldw_Server_API/app/core/RAG/rag_service/connection_pool.py tldw_Server_API/app/core/Slides/slides_db.py tldw_Server_API/app/core/DB_Management/sqlite_policy.py -f json -o /tmp/bandit_sqlite_shared_runtime_centralization.json`
**Status**: Complete
**Results**:
- Bandit completed successfully with `0` findings in the touched runtime SQLite modules.
