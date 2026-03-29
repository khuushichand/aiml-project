# Targeted Test Failure Fixes Plan

## Stage 1: Isolated Repository And Test Double Fixes
**Goal**: Fix the deterministic failures in MCP Hub repo helpers and flashcards test doubles.
**Success Criteria**: `test_mcp_hub_repo` representative case passes; flashcards admin-permission tests pass.
**Tests**:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py::test_repo_credential_binding_is_unique_per_target_and_server -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_flashcards_admin_permissions_claims.py -q`
**Status**: Complete

## Stage 2: Audiobook Pipeline Fixes
**Goal**: Fix audiobook job defaults and fresh collections schema behavior so the worker can complete representative jobs.
**Success Criteria**: representative audiobook worker test passes and output artifacts are created.
**Tests**:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audiobooks/integration/test_audiobook_worker_pipeline.py::test_audiobook_worker_creates_outputs -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audiobooks/integration/test_audiobook_worker_pipeline.py::test_audiobook_worker_allows_non_kokoro_item_with_null_subtitles -q`
**Status**: Complete

## Stage 3: Postgres-Oriented Logic And Expectation Fixes
**Goal**: Patch Postgres timestamp coercion and align the MCP Hub PG ensure expectation with the current schema naming.
**Success Criteria**: code paths are corrected for Postgres, and local non-Postgres tests stay green.
**Tests**:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py::test_ensure_mcp_hub_tables_pg_creates_required_tables -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/integration/test_authnz_admin_monitoring_repo_postgres.py::test_authnz_admin_monitoring_repo_postgres_round_trip -q`
**Status**: Complete

## Stage 4: Verification And Security Checks
**Goal**: Re-run touched tests together and run Bandit on the touched scope.
**Success Criteria**: targeted tests pass in this environment; Bandit reports no new findings in touched files.
**Tests**:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_mcp_hub_repo.py tldw_Server_API/tests/AuthNZ_Unit/test_flashcards_admin_permissions_claims.py tldw_Server_API/tests/Audiobooks/integration/test_audiobook_worker_pipeline.py -q`
- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/AuthNZ/repos tldw_Server_API/app/services/audiobook_jobs_worker.py tldw_Server_API/app/core/DB_Management/Collections_DB.py tldw_Server_API/tests/AuthNZ_Unit/test_flashcards_admin_permissions_claims.py tldw_Server_API/tests/AuthNZ_Postgres/test_mcp_hub_pg_ensure.py -f json -o /tmp/bandit_targeted_test_fixes.json`
**Status**: Complete

## Stage 5: Full-Suite Isolation And Fixture Drift Fixes
**Goal**: Eliminate the remaining suite-order failures caused by global module state, shared per-user DB paths, and stale SQLite/Postgres test schema setup.
**Success Criteria**: ordered Watchlists→AuthNZ reload checks pass; audio contamination tests pass in isolation after local stubbing/reload; SQLite monitoring test passes; Postgres-backed AuthNZ budget/chat tests skip cleanly instead of failing when Postgres is unavailable.
**Tests**:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_qwen3_asr.py::test_get_torch_dtype -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_streaming_metadata.py tldw_Server_API/tests/Audio/test_streaming_diarizer.py -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/integration/test_monitoring_metrics_summary.py::test_metrics_summary_uses_boolean_revoked_filter -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Watchlists/test_admin_runs_roles_normalization.py tldw_Server_API/tests/AuthNZ/test_consent_endpoints.py::TestConsentRouterWiring::test_production_app_includes_consent_routes -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/integration/test_chat_research_runs_endpoint.py::test_chat_research_runs_endpoint_enforces_chat_ownership -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/integration/test_chat_settings_endpoint.py::test_chat_settings_endpoint_enforces_chat_ownership -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/integration/test_chat_settings_endpoint.py::test_chat_settings_endpoint_enforces_chat_ownership_with_pinned_attachment -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/integration/test_admin_budgets.py::test_admin_budgets_list_and_update tldw_Server_API/tests/AuthNZ/integration/test_org_budgets.py::test_org_budgets_get_and_update -q`
- `source .venv/bin/activate && python -m bandit -f json -o /tmp/bandit_remaining_test_fixes.json tldw_Server_API/tests/Watchlists/conftest.py tldw_Server_API/tests/Audio/test_qwen3_asr.py tldw_Server_API/tests/Audio/test_streaming_metadata.py tldw_Server_API/tests/Audio/test_streaming_diarizer.py tldw_Server_API/tests/AuthNZ/integration/test_monitoring_metrics_summary.py tldw_Server_API/tests/AuthNZ/conftest.py`
**Status**: Complete
