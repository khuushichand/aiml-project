## Stage 1: Reproduce and Guard
**Goal**: Add focused regressions for the four confirmed user-facing failures.
**Success Criteria**: Tests cover prompt route render, world-books route render, research session rollback on enqueue failure, and media auxiliary/progress request behavior.
**Tests**:
- `bunx vitest -c vitest.config.ts run apps/packages/ui/src/components/Option/Prompt/__tests__/PromptBody.search-pagination.test.tsx`
- `bunx vitest -c vitest.config.ts run apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.stage4.test.tsx`
- `bunx vitest -c vitest.config.ts run apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.stage12.performance.test.tsx`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Media/test_reading_progress_endpoint.py -q`
**Status**: In Progress

## Stage 2: Implement Minimal Fixes
**Goal**: Remove the crashes and contradictory states without redesigning the affected features.
**Success Criteria**:
- `/prompts` no longer throws on initial render.
- `/world-books` no longer throws on initial render.
- Failed research job enqueue does not leave behind a visible orphan run.
- `/media` stops calling missing endpoints, and reading progress calls no longer 500.
**Tests**:
- Re-run all Stage 1 tests after code changes.
**Status**: Not Started

## Stage 3: Verify and Resume Walkthrough
**Goal**: Verify the touched scope and continue a live Playwright pass across additional pages.
**Success Criteria**:
- Focused tests and Bandit pass on touched paths.
- A new Playwright walkthrough confirms the original issues are fixed and documents any newly discovered bugs.
**Tests**:
- `source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/Prompt apps/packages/ui/src/components/Option/WorldBooks apps/packages/ui/src/components/Review/hooks tldw_Server_API/app/core/Research tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/app/api/v1/endpoints/media/reading_progress.py -f json -o /tmp/bandit_webui_followup.json`
- Host Playwright walkthrough on `http://[::1]:3000`
**Status**: Not Started
