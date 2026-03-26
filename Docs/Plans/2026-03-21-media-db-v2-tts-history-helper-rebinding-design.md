# Media DB V2 TTS History Helper Rebinding Design

## Summary

Rebind the TTS history CRUD cluster onto a package-owned runtime helper module
so the canonical `MediaDatabase` no longer owns those methods through legacy
globals, while preserving `Media_DB_v2` as a live-module compatibility shell.

## Scope

In scope:

- add one package runtime helper module for:
  - `create_tts_history_entry(...)`
  - `_build_tts_history_filters(...)`
  - `list_tts_history(...)`
  - `count_tts_history(...)`
  - `get_tts_history_entry(...)`
  - `update_tts_history_favorite(...)`
  - `soft_delete_tts_history_entry(...)`
  - `mark_tts_history_artifacts_deleted_for_output(...)`
  - `mark_tts_history_artifacts_deleted_for_file_id(...)`
  - `purge_tts_history_for_user(...)`
  - `list_tts_history_user_ids(...)`
- rebind canonical `MediaDatabase` methods for that cluster
- convert legacy `Media_DB_v2` methods into live-module compat shells
- add direct ownership/delegation regressions
- add focused helper-path tests asserting:
  - filter construction still preserves condition and parameter ordering
  - JSON artifact matching still tolerates malformed payloads and only updates
    matching rows
  - purge still applies retention deletion before max-row trimming
  - PostgreSQL create still returns the inserted `id`

Out of scope:

- changing `_ensure_postgres_tts_history(...)`
- changing audio API endpoint behavior
- changing cleanup scheduler behavior
- changing TTS hashing, normalization, or artifact storage models
- changing sync-log or file-artifact semantics outside this cluster

## Why This Slice

This is the cleanest remaining medium-sized domain cluster: eleven contiguous
methods with strong existing unit, integration, and service coverage. It is
substantially more valuable than another singleton helper, but still bounded
enough to move without mixing claims, data tables, or email state.

## Risks

Medium. The main behavioral invariants are:

- JSON serialization for `voice_info`, `params_json`, `segments_json`, and
  `artifact_ids` must remain unchanged
- list/count filtering must preserve deleted handling, favorite/provider/model
  filters, case-insensitive text search, and cursor pagination conditions
- artifact-deletion updates must continue to ignore malformed JSON rows and
  clear both `output_id` and `artifact_ids`
- purge ordering must remain retention pass first, row-cap pass second
- SQLite/Postgres create behavior must remain split at the `RETURNING id` path
- instance-level monkeypatching of these methods must remain intact for endpoint
  and service callers

## Test Strategy

Add:

1. canonical ownership regressions for all eleven methods
2. legacy compat-shell delegation regressions for all eleven methods
3. focused helper-path tests for:
   - filter condition/parameter assembly
   - artifact file-id matching and malformed JSON tolerance
   - purge retention-then-cap behavior
   - PostgreSQL `create_tts_history_entry(...)` return-path behavior
4. reuse existing caller-facing guards in:
   - `tldw_Server_API/tests/MediaDB2/test_sqlite_db.py`
   - `tldw_Server_API/tests/TTS_NEW/unit/test_tts_history_endpoints.py`
   - `tldw_Server_API/tests/TTS_NEW/integration/test_tts_history_artifact_purge.py`
   - `tldw_Server_API/tests/Services/test_tts_history_cleanup_service.py`

## Success Criteria

- canonical TTS history methods are package-owned
- legacy `Media_DB_v2` TTS history methods remain live-module compat shells
- focused helper-path tests pass
- existing TTS history caller-facing tests stay green
- normalized ownership count drops from `162` to `151`
