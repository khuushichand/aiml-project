# SQLite Residual Runtime Cleanup

Date: 2026-03-13
Status: Complete

## Scope

Finish the last meaningful runtime SQLite drift after the broader centralization passes:

- Move remaining direct Media DB SQLite bootstrap PRAGMAs onto the shared helper.
- Move ChaChaNotes API dependency SQLite tuning and health-probe timeout setup onto the shared helper.
- Switch the Topic Monitoring schema-migration write transaction from `BEGIN` to `BEGIN IMMEDIATE`.

Explicitly out of scope:

- Embedded migration SQL bodies.
- Backup and restore locking flows using `BEGIN EXCLUSIVE`.
- Prompt Studio local journal-mode override behavior.

## Stages

### Stage 1: Red Tests
Status: Complete

Added focused tests for:

- Media DB transaction bootstrap delegation and in-memory persistent connection helper adoption.
- ChaChaNotes API dependency tuning and health-check helper adoption.
- Topic Monitoring schema migration transaction mode.

Observed expected red failures before implementation.

### Stage 2: Implementation
Status: Complete

Updated:

- `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- `tldw_Server_API/app/api/v1/API_Deps/ChaCha_Notes_DB_Deps.py`
- `tldw_Server_API/app/core/DB_Management/TopicMonitoring_DB.py`

Behavior changes:

- Media DB now delegates transaction bootstrap and in-memory persistent connection PRAGMAs through the shared SQLite policy helper and uses `begin_immediate_if_needed(...)`.
- ChaChaNotes API dependency SQLite tuning and health checks now use `configure_sqlite_connection(...)` with narrow, behavior-preserving options.
- Topic Monitoring schema migration now starts with `BEGIN IMMEDIATE`.

### Stage 3: Verification
Status: Complete

Targeted red/green check:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py::test_media_database_transaction_delegates_sqlite_bootstrap_to_helpers \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py::test_media_memory_persistent_connection_uses_sqlite_policy_helper \
  tldw_Server_API/tests/Chat/test_chacha_notes_db_deps_sqlite_policy.py::test_chacha_dependency_tuning_uses_shared_sqlite_policy_helper \
  tldw_Server_API/tests/Chat/test_chacha_notes_db_deps_sqlite_policy.py::test_chacha_dependency_health_check_uses_shared_sqlite_policy_helper \
  tldw_Server_API/tests/DB_Management/test_sqlite_policy_integrations.py::test_topic_monitoring_schema_migration_uses_begin_immediate -v
```

Result:

- `5 passed, 6 warnings`

Broader regression sweep:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py \
  tldw_Server_API/tests/DB_Management/test_sqlite_policy_integrations.py \
  tldw_Server_API/tests/Monitoring/test_topic_monitoring.py \
  tldw_Server_API/tests/Chat/test_chacha_notes_db_deps_sqlite_policy.py -v
```

Result:

- `48 passed, 6 warnings`

Bandit:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/API_Deps/ChaCha_Notes_DB_Deps.py \
  tldw_Server_API/app/core/DB_Management/Media_DB_v2.py \
  tldw_Server_API/app/core/DB_Management/TopicMonitoring_DB.py \
  -f json -o /tmp/bandit_sqlite_residual_runtime.json
```

Result:

- `0` findings in the touched application scope.

## Remaining Intentional SQLite Exceptions

The remaining raw SQLite transaction or PRAGMA usage is intentional and not addressed in this pass:

- Backup and restore locking in `DB_Backups.py`.
- Generic and embedded migration SQL using plain `BEGIN`.
- Prompt Studio’s local journal-mode selection path.
- Kanban’s custom critical/best-effort PRAGMA error contract.
