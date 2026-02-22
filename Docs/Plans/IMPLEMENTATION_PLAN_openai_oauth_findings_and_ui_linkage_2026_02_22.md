## Stage 1: Baseline + Test Scaffolding
**Goal**: Capture the current behavior gaps and add/adjust tests that fail for the identified OAuth findings.
**Success Criteria**: Targeted AuthNZ/chat/embeddings/audio tests cover the 7 review findings and at least one UI linkage test target is identified.
**Tests**: `pytest` targeted AuthNZ/chat/embeddings/audio tests (new/updated); UI unit test updates under `apps/packages/ui/src`.
**Status**: Complete

## Stage 2: Backend OAuth Findings Remediation
**Goal**: Implement fixes for findings 1-7, including strict-plan error propagation after failed OAuth retry.
**Success Criteria**: Backend code paths satisfy plan requirements: refresh lock backend setting, redirect/state validation, state lifecycle controls, retry metric, correct retry error propagation, and audio force-refresh wiring.
**Tests**: Targeted `pytest` suites for AuthNZ endpoints/runtime and chat/embeddings/audio retry behavior.
**Status**: Complete

## Stage 3: Frontend UI Linkage Completion
**Goal**: Add/finish OpenAI OAuth account-linking controls in settings UI using the new backend endpoints.
**Success Criteria**: UI shows OpenAI OAuth status and supports connect/refresh/disconnect/source-switch flows with safe fallbacks.
**Tests**: Frontend unit/integration tests in `apps/packages/ui/src` for service calls and settings component behavior.
**Status**: Complete

## Stage 4: Verification + Hardening
**Goal**: Run verification and security checks on touched paths and ensure no regressions in changed areas.
**Success Criteria**: Targeted tests pass; Bandit run on touched backend paths; no unresolved high-severity issues in touched code.
**Tests**: `pytest` targeted runs, frontend test runs, and Bandit JSON report for touched backend scope.
**Status**: Complete

### Verification Notes
- Passed:
  - `python -m pytest tldw_Server_API/tests/Audio/test_audio_tts_oauth_retry_unit.py -q`
  - `ULTRA_MINIMAL_APP=1 MINIMAL_TEST_APP=1 TESTING=1 python -m pytest tldw_Server_API/tests/AuthNZ_SQLite/test_byok_oauth_state_repo_sqlite.py -q`
  - `MINIMAL_TEST_APP=1 ULTRA_MINIMAL_APP=0 TESTING=1 OPENAI_OAUTH_REDIRECT_URI=https://app.example.com/api/v1/users/keys/openai/oauth/callback python -m pytest tldw_Server_API/tests/AuthNZ_SQLite/test_byok_endpoints_sqlite.py -k "openai_oauth_endpoints_sqlite" -q` (outside sandbox)
  - `MINIMAL_TEST_APP=1 ULTRA_MINIMAL_APP=0 TESTING=1 OPENAI_OAUTH_REDIRECT_URI=https://app.example.com/api/v1/users/keys/openai/oauth/callback python -m pytest tldw_Server_API/tests/AuthNZ_Postgres/test_byok_oauth_endpoints_pg.py -q` (outside sandbox)
  - `bunx vitest run src/services/__tests__/tldw-api-client.openai-oauth.test.ts` (from `apps/packages/ui`)
- Security scan:
  - `python -m bandit -r <touched backend paths> -f json -o /tmp/bandit_openai_oauth_strict_2026_02_22_v2.json`
  - Findings: 3 low-severity `B311` findings in existing embeddings sampling code; no high-severity findings in touched OAuth paths.
- Environment constraints observed:
  - Full-app targeted pytest runs that import the complete media/audio stack abort in this environment during `torch`/`ctranslate2` import.
  - Ultra-minimal mode excludes the full OAuth route set, so endpoint integration tests there can return `404` despite implementation being present in normal mode.
  - Running endpoint integration suites outside sandbox removed the shared-memory (`OMP ... SHM2`) failure and produced clean passes for SQLite and Postgres OAuth endpoint tests.
