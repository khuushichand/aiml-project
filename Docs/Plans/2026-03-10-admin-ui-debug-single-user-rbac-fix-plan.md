## Stage 1: Confirm Single-User Regression
**Goal**: Reproduce the debug access regression for single-user mode on the PR branch.
**Success Criteria**: Frontend and backend tests demonstrate that the default single-user admin loses debug access under the current guard logic.
**Tests**: `bunx vitest run admin-ui/app/debug/page.test.tsx`, `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_authnz_debug_admin_claims.py -q`
**Status**: Complete

## Stage 2: Restore Single-User Debug Access Safely
**Goal**: Preserve single-user admin access to debug tooling while keeping multi-user debug access restricted to `super_admin` and `owner`.
**Success Criteria**: Frontend route guard and backend authorization both allow single-user mode and still reject plain multi-user admins.
**Tests**: `bunx vitest run admin-ui/app/debug/page.test.tsx`, `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_authnz_debug_admin_claims.py -q`
**Status**: Complete

## Stage 3: Verify and Prepare Branch Update
**Goal**: Re-run focused verification and security scanning for the touched scope.
**Success Criteria**: Focused frontend/backend tests pass, lint/typecheck pass for touched frontend code, and Bandit reports no new findings for the backend endpoint.
**Tests**: `bun run lint`, `bun run typecheck`, `bunx vitest run admin-ui/app/debug/page.test.tsx`, `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_authnz_debug_admin_claims.py -q`, `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/authnz_debug.py -f json -o /tmp/bandit_authnz_debug_fix.json`
**Status**: Complete
