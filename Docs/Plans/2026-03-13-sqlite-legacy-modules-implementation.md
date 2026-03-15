# SQLite Legacy Modules Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Standardize SQLite runtime PRAGMAs and outer write transaction behavior across legacy and user-feature database modules by introducing a shared SQLite policy helper and migrating duplicated connection setup to it.

**Architecture:** Add a small procedural helper module for SQLite connection configuration and outer transaction start behavior. Adopt it selectively in legacy runtime DB modules, keeping migration, backup, and explicit foreign-key-off maintenance flows unchanged. Use focused regression tests to prove the helper behavior and the most important module integrations.

**Tech Stack:** Python, sqlite3, aiosqlite, pytest

---

## Stage 1: Helper Design To Test Targets
**Goal**: Pin down the helper API and the exact module/test touch points.
**Success Criteria**: Plan includes the helper file, adoption targets, and the verification commands for the changed scope.
**Tests**: None.
**Status**: Complete

## Stage 2: Red Tests For Shared Policy And High-Risk Integrations
**Goal**: Add failing tests for helper behavior and representative module integrations before changing production code.
**Success Criteria**: New tests fail because the helper does not exist yet or legacy modules still use local duplicated behavior.
**Tests**:
- `python -m pytest tldw_Server_API/tests/DB_Management/test_sqlite_policy.py -v`
- `python -m pytest tldw_Server_API/tests/DB_Management/test_sqlite_policy_integrations.py -v`
- `python -m pytest tldw_Server_API/tests/Scheduler/test_sqlite_backend.py tldw_Server_API/tests/ChaChaNotesDB/test_chachanotes_db.py -k "begin_immediate or transaction_context_manager_uses_begin_immediate or sqlite_backend_transaction_uses_begin_immediate" -v`
**Status**: Complete

**Result**: Red-green cycle completed. The helper tests initially failed with `ModuleNotFoundError`, the integration suite initially failed across PRAGMA and transaction-mode assertions, and the scheduler/ChaChaNotes transaction tests initially failed on deferred `BEGIN`.

## Stage 3: Implement Shared Helper And Adopt In Runtime Modules
**Goal**: Add the helper module, migrate duplicated PRAGMA setup, and switch outer write transactions to `BEGIN IMMEDIATE` in the scoped runtime modules.
**Success Criteria**: Runtime SQLite modules use the shared helper where appropriate, and outer write transaction paths in scope no longer use deferred `BEGIN`.
**Tests**:
- Re-run the Stage 2 tests after each batch.
**Status**: Complete

**Result**: Added `tldw_Server_API/app/core/DB_Management/sqlite_policy.py`, migrated the scoped runtime connection factories to `configure_sqlite_connection()`, and converted the remaining outer transaction managers in scope to `BEGIN IMMEDIATE` or `begin_immediate_if_needed()`.

## Stage 4: Broader Regression Verification
**Goal**: Prove the helper adoption does not break existing DB behavior in touched modules.
**Success Criteria**: Existing targeted suites covering Scheduler, Personalization, Research, Prompts, Circuit Breaker, and ChaChaNotes continue to pass.
**Tests**:
- `python -m pytest tldw_Server_API/tests/TTS_NEW/unit/test_voice_registry_db.py tldw_Server_API/tests/Monitoring/test_topic_monitoring.py tldw_Server_API/tests/Guardian/test_guardian_db.py tldw_Server_API/tests/Personalization/test_companion_activity_db.py tldw_Server_API/tests/Research/test_research_sessions_db.py tldw_Server_API/tests/Meetings/test_meetings_db.py tldw_Server_API/tests/Agent_Orchestration/test_orchestration_db.py tldw_Server_API/tests/Infrastructure/test_circuit_breaker.py tldw_Server_API/tests/Prompt_Management/test_prompts_db_v2.py tldw_Server_API/tests/Workflows/test_workflows_db.py tldw_Server_API/tests/Scheduler/test_sqlite_backend.py tldw_Server_API/tests/ChaChaNotesDB/test_chachanotes_db.py -v`
**Status**: Complete

**Result**: Passed. `297 passed, 7 warnings in 16.18s`.

## Stage 5: Security Verification And Final Status
**Goal**: Run Bandit on the touched Python files and update plan status before claiming completion.
**Success Criteria**: Bandit output is reviewed and any new findings in changed code are fixed or reported accurately.
**Tests**:
- `python -m bandit -r tldw_Server_API/app/core/DB_Management/sqlite_policy.py tldw_Server_API/app/core/DB_Management/Voice_Registry_DB.py tldw_Server_API/app/core/DB_Management/TopicMonitoring_DB.py tldw_Server_API/app/core/DB_Management/Guardian_DB.py tldw_Server_API/app/core/DB_Management/Prompts_DB.py tldw_Server_API/app/core/DB_Management/Workflows_DB.py tldw_Server_API/app/core/DB_Management/Personalization_DB.py tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/app/core/DB_Management/Meetings_DB.py tldw_Server_API/app/core/DB_Management/Orchestration_DB.py tldw_Server_API/app/core/DB_Management/Circuit_Breaker_Registry_DB.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/core/Scheduler/backends/sqlite_backend.py -f json -o /tmp/bandit_sqlite_legacy_modules.json`
**Status**: Complete

**Result**: Bandit reviewed the touched scope. No findings were reported in the new helper or newly changed transaction/PRAGMA paths. Remaining findings were pre-existing low-confidence `B608` and low-severity `B101` issues in legacy `ChaChaNotes_DB.py` code outside the SQLite policy changes.

### Task 1: Add shared SQLite policy tests and helper scaffold

**Files:**
- Create: `tldw_Server_API/tests/DB_Management/test_sqlite_policy.py`
- Create: `tldw_Server_API/app/core/DB_Management/sqlite_policy.py`

**Step 1: Write the failing tests**

Add tests for:
- `configure_sqlite_connection()` applying `foreign_keys`, `busy_timeout`, `synchronous`, `temp_store`, and optional `cache_size`
- WAL skipped for in-memory connections by default
- `begin_immediate_if_needed()` starting only the outermost transaction

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/DB_Management/test_sqlite_policy.py -v`
Expected: FAIL because the helper module does not exist yet.

**Step 3: Write minimal implementation**

Implement the two helper functions with no module-specific behavior.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/DB_Management/test_sqlite_policy.py -v`
Expected: PASS

### Task 2: Migrate direct connection-factory modules

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Voice_Registry_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/TopicMonitoring_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Guardian_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Personalization_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Meetings_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Orchestration_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Circuit_Breaker_Registry_DB.py`

**Step 1: Write the failing tests**

Extend or create focused regression tests that prove representative modules now rely on the standard PRAGMA set through the helper and preserve their existing connection behavior.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/DB_Management/test_voice_registry_db.py tldw_Server_API/tests/Infrastructure/test_circuit_breaker.py tldw_Server_API/tests/Research/test_research_sessions_db.py -v`
Expected: FAIL on the new helper-driven assertions.

**Step 3: Write minimal implementation**

Replace local PRAGMA blocks with `configure_sqlite_connection()` and keep module-specific options local.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/DB_Management/test_voice_registry_db.py tldw_Server_API/tests/Infrastructure/test_circuit_breaker.py tldw_Server_API/tests/Research/test_research_sessions_db.py -v`
Expected: PASS

### Task 3: Convert remaining outer write transactions to `BEGIN IMMEDIATE`

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Voice_Registry_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/TopicMonitoring_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Guardian_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Prompts_DB.py`
- Modify: `tldw_Server_API/app/core/Scheduler/backends/sqlite_backend.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`

**Step 1: Write the failing tests**

Add regression tests that assert the first transaction-opening statement is `BEGIN IMMEDIATE` for the scoped outer transaction managers.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Scheduler/test_sqlite_backend.py tldw_Server_API/tests/DB_Management/test_voice_registry_db.py tldw_Server_API/tests/ChaChaNotesDB/test_chachanotes_db.py -k "begin_immediate or transaction" -v`
Expected: FAIL where deferred `BEGIN` remains.

**Step 3: Write minimal implementation**

Use `begin_immediate_if_needed()` or direct `BEGIN IMMEDIATE` where the surrounding logic requires it.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Scheduler/test_sqlite_backend.py tldw_Server_API/tests/DB_Management/test_voice_registry_db.py tldw_Server_API/tests/ChaChaNotesDB/test_chachanotes_db.py -k "begin_immediate or transaction" -v`
Expected: PASS

### Task 4: Migrate thread-local / shared-connection legacy modules

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Prompts_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/Workflows_DB.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`

**Step 1: Write the failing tests**

Add focused tests that prove runtime connection bootstraps use the helper-based PRAGMA setup without changing explicit maintenance or migration behavior.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Prompt_Management_NEW tldw_Server_API/tests/ChaChaNotesDB/test_chachanotes_db.py -k "transaction or pragma or connection" -v`
Expected: FAIL on the new policy assertions.

**Step 3: Write minimal implementation**

Integrate `configure_sqlite_connection()` into the runtime connection initialization paths only, preserving explicit `foreign_keys=OFF` flows and migration logic.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Prompt_Management_NEW tldw_Server_API/tests/ChaChaNotesDB/test_chachanotes_db.py -k "transaction or pragma or connection" -v`
Expected: PASS

### Task 5: Full targeted regression and security verification

**Files:**
- Modify: `docs/plans/2026-03-13-sqlite-legacy-modules-implementation.md`

**Step 1: Run the targeted regression suites**

Run: `python -m pytest tldw_Server_API/tests/DB_Management/test_sqlite_policy.py tldw_Server_API/tests/Scheduler/test_sqlite_backend.py tldw_Server_API/tests/Infrastructure/test_circuit_breaker.py tldw_Server_API/tests/Research/test_research_sessions_db.py tldw_Server_API/tests/Personalization/test_companion_activity_db.py tldw_Server_API/tests/Prompt_Management_NEW tldw_Server_API/tests/ChaChaNotesDB/test_chachanotes_db.py -v`
Expected: PASS

**Step 2: Run Bandit on the touched Python files**

Run: `python -m bandit -r tldw_Server_API/app/core/DB_Management/sqlite_policy.py tldw_Server_API/app/core/DB_Management/Voice_Registry_DB.py tldw_Server_API/app/core/DB_Management/TopicMonitoring_DB.py tldw_Server_API/app/core/DB_Management/Guardian_DB.py tldw_Server_API/app/core/DB_Management/Prompts_DB.py tldw_Server_API/app/core/DB_Management/Workflows_DB.py tldw_Server_API/app/core/DB_Management/Personalization_DB.py tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/app/core/DB_Management/Meetings_DB.py tldw_Server_API/app/core/DB_Management/Orchestration_DB.py tldw_Server_API/app/core/DB_Management/Circuit_Breaker_Registry_DB.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/app/core/Scheduler/backends/sqlite_backend.py -f json -o /tmp/bandit_sqlite_legacy_modules.json`
Expected: Review results and fix any new findings in changed code.

**Step 3: Update plan status**

Mark each stage complete with actual verification results before reporting completion.
