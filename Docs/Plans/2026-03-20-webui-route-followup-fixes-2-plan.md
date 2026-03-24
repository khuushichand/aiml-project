## Stage 1: Reproduce And Pin The Regressions
**Goal**: Add focused tests that capture the four route issues discovered in the live walkthrough.
**Success Criteria**: Agent Registry, Agent Tasks, Prompt Studio settings query sizing, and Sources capability gating all have failing/targeted coverage.
**Tests**:
- `bunx vitest -c vitest.config.ts run src/components/Option/AgentRegistry/__tests__/AgentRegistryPage.connection.test.tsx`
- `bunx vitest -c vitest.config.ts run src/components/Option/AgentTasks/__tests__/AgentTasksPage.connection.test.tsx`
- `bunx vitest -c vitest.config.ts run src/components/Option/Prompt/__tests__/StudioTabContainer.stage6-navigation.test.tsx`
- `bunx vitest -c vitest.config.ts run src/components/Option/Sources/__tests__/SourcesWorkspacePage.test.tsx`
**Status**: Complete

## Stage 2: Fix Connection And Response Shape Mismatches
**Goal**: Route agent pages through the real web connection state, normalize the agent-tasks project/task payloads, and cap Prompt Studio settings queries to the backend limit.
**Success Criteria**: `/agents` and `/agent-tasks` stop targeting stale localhost defaults, agent tasks load real project lists, and Prompt Studio stops triggering `422` on settings load.
**Tests**:
- Targeted Vitest suites from Stage 1
**Status**: Complete

## Stage 3: Stop Unsupported Sources From Fetching
**Goal**: Prevent the Sources workspace from issuing ingestion-source queries when server capabilities already mark the feature unsupported.
**Success Criteria**: The unsupported Sources state renders without triggering the ingestion-sources query.
**Tests**:
- `bunx vitest -c vitest.config.ts run src/components/Option/Sources/__tests__/SourcesWorkspacePage.test.tsx`
**Status**: Complete

## Stage 4: Verify And Reaudit
**Goal**: Re-run targeted verification, Bandit on touched backend/frontend-adjacent scope as applicable, and re-check the live routes with Playwright.
**Success Criteria**: Targeted tests pass, no new Bandit findings are introduced in touched Python files, and the live pages no longer reproduce the tracked failures.
**Tests**:
- Combined targeted Vitest command for touched suites
- `source .venv/bin/activate && python -m bandit -r <touched_python_paths> -f json -o /tmp/bandit_webui_route_followup_2.json`
**Status**: Complete
