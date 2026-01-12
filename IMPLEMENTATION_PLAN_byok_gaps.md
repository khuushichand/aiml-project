## Stage 1: Scope + Schema Changes
**Goal**: Define and implement BYOK audit/revocation fields across SQLite/Postgres schemas and repo interfaces.
**Success Criteria**: New columns exist in SQLite and PG migrations; repos read/write audit fields; soft-revoke replaces hard delete; tests updated/added.
**Tests**: `python -m pytest -m "unit" tldw_Server_API/tests/AuthNZ_SQLite/test_authnz_user_provider_secrets_repo_sqlite.py -v`; `python -m pytest -m "unit" tldw_Server_API/tests/AuthNZ_SQLite/test_authnz_org_provider_secrets_repo_sqlite.py -v`.
**Status**: Not Started

## Stage 2: Endpoint Behavior Alignment
**Goal**: Remove per-request `api_key` overrides and standardize missing-credentials errors/metrics across endpoints.
**Success Criteria**: API endpoints ignore/remove explicit `api_key` overrides; missing key errors return 503 with `error_code=missing_provider_credentials`; metrics emitted consistently.
**Tests**: `python -m pytest -m "integration" tldw_Server_API/tests/AuthNZ_SQLite/test_byok_endpoints_sqlite.py -v`; targeted endpoint tests for chat/evals/doc generation.
**Status**: Not Started

## Stage 3: Provider Metadata Validation
**Goal**: Enforce required credential fields and default-auth requirements using provider metadata.
**Success Criteria**: `validate_credential_fields` validates provider-specific requirements; unknown providers default to `requires_auth=True` unless explicitly configured.
**Tests**: Add/update unit tests for `byok_helpers`/`byok_runtime`; run `python -m pytest -m "unit" tldw_Server_API/tests/AuthNZ_Unit/test_byok_crypto.py -v` plus new tests.
**Status**: Not Started

## Stage 4: Rotation Tooling
**Goal**: Provide a CLI/maintenance script to rotate BYOK encryption keys using primary/secondary keys.
**Success Criteria**: Script re-encrypts all BYOK rows in batches; supports dry-run; logs counts; docs updated.
**Tests**: New unit test for re-encryption utility; manual dry-run on a temp SQLite DB in tests.
**Status**: Not Started

## Stage 5: Documentation + Cleanup
**Goal**: Update BYOK docs and config references, and remove stale PRD divergences.
**Success Criteria**: Docs reflect audit fields, rotation tooling, and no per-request overrides; PRD updated if needed.
**Tests**: N/A (doc-only).
**Status**: Not Started
