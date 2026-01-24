## Stage 1: Admin Cleanup Principal Resolution
**Goal**: Ensure evaluations admin cleanup resolves AuthPrincipal via dependency injection to honor overrides.
**Success Criteria**: Admin cleanup tests return 403/200 instead of 401 when using stub principals.
**Tests**:
- tldw_Server_API/tests/AuthNZ/integration/test_evaluations_permissions_claims.py::test_evaluations_admin_cleanup_forbidden_without_admin_role
- tldw_Server_API/tests/AuthNZ/integration/test_evaluations_permissions_claims.py::test_evaluations_admin_cleanup_allowed_with_admin_role
- tldw_Server_API/tests/AuthNZ_Unit/test_evaluations_heavy_admin_claims.py::test_admin_cleanup_idempotency_forbidden_without_admin_role
- tldw_Server_API/tests/AuthNZ_Unit/test_evaluations_heavy_admin_claims.py::test_admin_cleanup_idempotency_allowed_for_admin
- tldw_Server_API/tests/AuthNZ_Unit/test_evaluations_heavy_admin_claims.py::test_admin_cleanup_idempotency_allows_roles_admin_without_is_admin
**Status**: In Progress

## Stage 2: API Key Auth Test Compatibility
**Goal**: Prevent API-key auth from raising 500s in test contexts by supporting stubbed user lookups and non-JWT bearer paths.
**Success Criteria**: API key unit tests return expected 400/200 outcomes; JWT-path unit test exercises verify_jwt_and_fetch_user stub.
**Tests**:
- tldw_Server_API/tests/AuthNZ/unit/test_user_db_handling_api_keys.py::test_get_request_user_rejects_inactive_api_key_user
- tldw_Server_API/tests/AuthNZ/unit/test_user_db_handling_api_keys.py::test_get_request_user_allows_active_api_key_user
- tldw_Server_API/tests/AuthNZ/unit/test_user_db_handling_api_keys.py::test_api_key_principal_subject_single_user_only_in_single_user_mode[multi_user-None]
- tldw_Server_API/tests/AuthNZ/unit/test_user_db_handling_api_keys.py::test_api_key_principal_subject_single_user_only_in_single_user_mode[single_user-single_user]
- tldw_Server_API/tests/AuthNZ_Unit/test_auth_principal_resolver.py::test_get_auth_principal_jwt_path
**Status**: In Progress

## Stage 3: AuthGovernor & Rate Limit Dependencies
**Goal**: Restore AuthGovernor delegation behavior and add rate-limit dependency hooks expected by tests.
**Success Criteria**: AuthGovernor and admin rate-limit bypass tests pass.
**Tests**:
- tldw_Server_API/tests/AuthNZ_Unit/test_auth_deps_hardening.py::test_admin_rate_limit_bypass_is_principal_first[check_rate_limit]
- tldw_Server_API/tests/AuthNZ_Unit/test_auth_deps_hardening.py::test_admin_rate_limit_bypass_is_principal_first[check_auth_rate_limit]
- tldw_Server_API/tests/AuthNZ_Unit/test_auth_governor_budget.py::test_auth_governor_lockout_checks_rate_limiter
- tldw_Server_API/tests/AuthNZ_Unit/test_auth_governor_budget.py::test_auth_governor_record_auth_failure_respects_limiter
- tldw_Server_API/tests/AuthNZ_Unit/test_auth_governor_budget.py::test_auth_governor_rate_limit_delegates_to_limiter
- tldw_Server_API/tests/AuthNZ_Unit/test_auth_governor_budget.py::test_auth_governor_rate_limit_fails_open_when_limiter_missing
**Status**: Not Started

## Stage 4: Targeted Re-run
**Goal**: Re-run the affected unit/integration tests and confirm fixes.
**Success Criteria**: Targeted tests above pass in the current environment.
**Tests**: See stages 1-3.
**Status**: Not Started
