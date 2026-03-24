## Stage 1: Pin The New Regressions
**Goal**: Add focused tests for ACP Playground canonical connection usage and Agent Tasks unsupported-route handling.
**Success Criteria**: The stale localhost/auth path and the raw `HTTP 404` experience are covered by failing tests.
**Tests**:
- `bunx vitest -c vitest.config.ts run src/components/Option/ACPPlayground/__tests__/ACPPlayground.connection.test.tsx`
- `bunx vitest -c vitest.config.ts run src/components/Option/AgentTasks/__tests__/AgentTasksPage.connection.test.tsx`
**Status**: Complete

## Stage 2: Fix ACP Playground Connection Resolution
**Goal**: Route ACP Playground surfaces through the shared canonical connection hook.
**Success Criteria**: ACP session hydration and related ACP REST calls use the active web connection config instead of stale legacy storage keys.
**Tests**:
- `bunx vitest -c vitest.config.ts run src/components/Option/ACPPlayground/__tests__/ACPPlayground.connection.test.tsx`
**Status**: Complete

## Stage 3: Add Agent Tasks Unsupported-State Guard
**Goal**: Replace raw orchestration-route `404` errors with an explicit unsupported state when the server does not expose those endpoints.
**Success Criteria**: `/agent-tasks` no longer surfaces `HTTP 404` as a generic alert and instead explains that orchestration is unavailable on the current server.
**Tests**:
- `bunx vitest -c vitest.config.ts run src/components/Option/AgentTasks/__tests__/AgentTasksPage.connection.test.tsx`
**Status**: Complete

## Stage 4: Verify And Reaudit
**Goal**: Re-run focused tests, security checks, and Playwright on ACP/agent routes, then continue scanning additional pages.
**Success Criteria**: Focused tests pass, no new security findings are introduced in touched Python files, and the live ACP/agent routes reflect the new UX.
**Tests**:
- Combined focused Vitest command for touched suites
- `source .venv/bin/activate && python -m bandit -r <touched_scope> -f json -o /tmp/bandit_acp_agent_followup.json`
**Status**: Complete
