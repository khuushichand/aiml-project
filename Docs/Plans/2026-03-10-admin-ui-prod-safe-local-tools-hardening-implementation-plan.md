# Admin UI Prod-Safe Local Tools Hardening Implementation Plan

## Stage 1: Lock Safe-Mode Policy In Tests
**Goal**: Add failing tests for the shared unsafe-local-tools flag, debug RBAC, and default-safe behavior in Data Ops and Monitoring.
**Success Criteria**: Tests require local-only admin workflows to be disabled unless an explicit env flag is enabled.
**Tests**: `bunx vitest run admin-ui/components/data-ops/DataSubjectRequestsSection.test.tsx admin-ui/components/data-ops/BackupsSection.test.tsx admin-ui/app/monitoring/use-alert-rules.test.tsx admin-ui/app/monitoring/use-alert-actions.test.tsx admin-ui/app/monitoring/components/AlertsPanel.test.tsx admin-ui/app/monitoring/components/MonitoringManagementPanels.test.tsx`; `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_authnz_debug_admin_claims.py -q`
**Status**: Complete

## Stage 2: Add Shared Unsafe-Local-Tools Gating
**Goal**: Introduce a client-side helper for unsafe local tools and use it to disable non-authoritative DSR, backup scheduling, and monitoring mutations by default.
**Success Criteria**: Safe mode is the default; unsafe local behaviors only run when the env flag is explicitly true.
**Tests**: Stage 1 test commands
**Status**: Complete

## Stage 3: Tighten Debug RBAC
**Goal**: Align frontend and backend debug access to `super_admin`/`owner`.
**Success Criteria**: The debug page route guard and backend endpoints both reject plain `admin` principals.
**Tests**: Stage 1 backend/frontend test commands
**Status**: Complete

## Stage 4: Verify Touched Scopes
**Goal**: Run focused and broader verification for the affected frontend and backend files.
**Success Criteria**: Focused tests, broader `admin-ui` lint/typecheck/test/a11y/build, the backend auth test, and Bandit on the touched backend scope all pass.
**Tests**: `bunx vitest run lib/admin-ui-flags.test.ts components/data-ops/DataSubjectRequestsSection.test.tsx components/data-ops/BackupsSection.test.tsx app/monitoring/use-alert-rules.test.tsx app/monitoring/use-alert-actions.test.tsx app/monitoring/components/AlertsPanel.test.tsx app/monitoring/components/MonitoringManagementPanels.test.tsx app/monitoring/use-monitoring-management-panels-props.test.tsx app/debug/page.test.tsx`; `bun run lint`; `bun run typecheck`; `bun run test`; `bun run test:a11y`; `bun run build`; `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_authnz_debug_admin_claims.py -q`; `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/authnz_debug.py -f json -o /tmp/bandit_authnz_debug.json`
**Status**: Complete
