# SQLite Infrastructure Runtime Centralization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Centralize the remaining infrastructure/runtime SQLite PRAGMA setup behind the shared helper while preserving intentional module-specific tuning.

**Architecture:** Reuse `sqlite_policy.py` for live SQLite connection bootstrap in the remaining service and infrastructure modules, then keep local-only extras such as `auto_vacuum`, `query_only`, `mmap_size`, longer timeouts, and in-memory WAL suppression beside the call sites. Leave migration and PostgreSQL paths unchanged.

**Tech Stack:** Python, sqlite3, aiosqlite, pytest

---

## Stage 1: Finalize Design And Runtime Scope
**Goal**: Capture the remaining runtime-only modules and explicitly exclude migrations and PostgreSQL paths.
**Success Criteria**: Design doc lists the touched modules, helper usage pattern, local exceptions, and verification plan.
**Tests**: None.
**Status**: Complete

**Result**: Scoped the pass to live SQLite bootstrap in Audit, Jobs, Sandbox, ACP, Chat Workflows, Kanban, and Evaluations. Explicitly excluded migration/DDL-only transaction blocks and PostgreSQL paths.

## Stage 2: Red Tests For Remaining Runtime Integrations
**Goal**: Add failing tests that prove the remaining modules still hand-roll runtime PRAGMAs or miss the helper contract.
**Success Criteria**: New assertions fail before production code changes.
**Tests**:
- `python -m pytest tldw_Server_API/tests/DB_Management/test_sqlite_policy_integrations.py -k "audit or jobs or sandbox or kanban or acp or chat_workflows or evaluations" -v`
- `python -m pytest tldw_Server_API/tests/Audit/test_unified_audit_service.py -k "pragma or read_db or pool" -v`
- `python -m pytest tldw_Server_API/tests/Jobs/test_jobs_quotas_sqlite.py -v`
- `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_management.py -k "audit or session" -v`
- `python -m pytest tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_db.py tldw_Server_API/tests/kanban/test_kanban_db.py -v`
**Status**: Complete

**Result**: Added coverage in `test_sqlite_policy_integrations.py` and `tests/Audit/test_sqlite_runtime_pragmas.py`. The initial red run failed in the expected hotspots: Jobs, Sandbox, Kanban, ACP Sessions, ACP Audit, Chat Workflows, and Audit read-only connections. Evaluations already matched the desired runtime behavior and passed before code changes.

## Stage 3: Implement Helper Adoption In Remaining Runtime Modules
**Goal**: Replace duplicated runtime PRAGMA blocks with helper calls while preserving module-local behavior.
**Success Criteria**: Audit, Jobs, Sandbox, Kanban, ACP, Chat Workflows, and Evaluations use the shared runtime policy for SQLite bootstrap.
**Tests**:
- Re-run the Stage 2 commands after each module batch.
**Status**: Complete

**Result**: Migrated Audit, Jobs, Sandbox, ACP Sessions, ACP Audit, Chat Workflows, and Evaluations onto `sqlite_policy`. Kanban kept its explicit critical-PRAGMA error contract locally, but now also applies `temp_store=MEMORY` so its runtime behavior matches the shared policy without weakening its existing failure semantics.

## Stage 4: Broader Regression Verification
**Goal**: Prove the runtime centralization does not change expected behavior outside the touched PRAGMA setup.
**Success Criteria**: Targeted existing suites for Audit, Jobs, Sandbox, Kanban, ACP, Chat Workflows, Evaluations, and SQLite policy integrations pass.
**Tests**:
- `python -m pytest tldw_Server_API/tests/DB_Management/test_sqlite_policy_integrations.py tldw_Server_API/tests/Audit/test_unified_audit_service.py tldw_Server_API/tests/Jobs/test_jobs_quotas_sqlite.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_management.py tldw_Server_API/tests/Chat_Workflows/test_chat_workflows_db.py tldw_Server_API/tests/kanban/test_kanban_db.py -v`
**Status**: Complete

**Result**: Focused runtime-policy tests passed (`24 passed`). The broader targeted sweep also passed after restoring Kanban’s error-message contract: `359 passed, 2 skipped, 1 xfailed, 6 warnings in 252.36s`.

## Stage 5: Security Verification And Status Update
**Goal**: Run Bandit on the touched scope and update this plan with actual results.
**Success Criteria**: New findings in changed code are fixed or accurately reported before completion.
**Tests**:
- `python -m bandit -r tldw_Server_API/app/core/Audit/unified_audit_service.py tldw_Server_API/app/core/Jobs/manager.py tldw_Server_API/app/core/Sandbox/store.py tldw_Server_API/app/core/DB_Management/Kanban_DB.py tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py tldw_Server_API/app/core/DB_Management/ACP_Audit_DB.py tldw_Server_API/app/core/DB_Management/ChatWorkflows_DB.py tldw_Server_API/app/core/Evaluations/connection_pool.py tldw_Server_API/app/core/DB_Management/sqlite_policy.py -f json -o /tmp/bandit_sqlite_infrastructure_runtime_centralization.json`
**Status**: Complete

**Result**: Bandit reported no findings in the new helper wiring itself. The remaining results are pre-existing issues in older touched files: six low-severity `B105` hits in `unified_audit_service.py` and three medium-severity `B608` hits in legacy dynamic SQL within `ACP_Audit_DB.py` and `ACP_Sessions_DB.py`. No new security issues were introduced by this runtime PRAGMA centralization pass.
