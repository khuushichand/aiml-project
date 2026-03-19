# Deep Research Chat Follow-Up Launch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let saved chat threads launch a new linked deep-research run from the composer, optionally seeded from the active attached research context.

**Architecture:** Add a direct package-side research-run create client, extend the backend research run create contract with persisted bounded `follow_up` metadata, and add a small composer confirmation surface in `PlaygroundForm.tsx`. Keep normal send behavior unchanged and let the existing linked-run status stack surface the new run.

**Tech Stack:** FastAPI, Pydantic, SQLite, React, TypeScript, TanStack Query, Vitest, pytest.

---

### Task 1: Add Red Backend Tests For Follow-Up Launch Contract And Planning

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Research/test_research_runs_endpoint.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Research/test_research_jobs_service.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Research/test_research_planner.py`

**Step 1: Write the failing endpoint and service tests**

Add coverage that proves:

- `POST /api/v1/research/runs` accepts bounded `follow_up` and passes it to `ResearchService.create_session(...)`
- `POST /api/v1/research/runs` rejects invalid or foreign `chat_handoff.chat_id`
- `ResearchService.create_session(...)` persists `follow_up_json`
- malformed follow-up payloads are rejected at the schema boundary
- oversized follow-up background payloads are rejected at the schema boundary

Add a planner test that proves:

- `build_initial_plan(...)` changes focus-area selection when bounded follow-up background is provided
- the plain no-follow-up path stays unchanged

**Step 2: Run the backend tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Research/test_research_runs_endpoint.py \
  tldw_Server_API/tests/Research/test_research_jobs_service.py \
  tldw_Server_API/tests/Research/test_research_planner.py -q
```

Expected:

- failures around unknown `follow_up` request fields, missing session persistence, and planner signature/behavior gaps

**Step 3: Confirm red state**

Do not implement backend code yet.

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/tests/Research/test_research_runs_endpoint.py \
  tldw_Server_API/tests/Research/test_research_jobs_service.py \
  tldw_Server_API/tests/Research/test_research_planner.py
git commit -m "test(research): cover chat follow-up launches"
```

### Task 2: Implement Backend Follow-Up Schema, Persistence, And Planning Hook

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/Research/service.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/Research/planner.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/Research/jobs.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/api/v1/endpoints/research_runs.py`

**Step 1: Extend the create contract**

In `research_runs_schemas.py`:

- add bounded follow-up models:
  - outline item
  - key claim item
  - verification summary
  - source trust summary
  - follow-up background
  - follow-up create request
- add optional `follow_up` to `ResearchRunCreateRequest`
- reject unknown keys in the nested follow-up models
- enforce explicit list and string caps on the nested follow-up background models

**Step 2: Persist follow-up metadata**

In `ResearchSessionsDB.py`:

- add `follow_up_json TEXT NOT NULL DEFAULT '{}'` to `research_sessions`
- include it in `ResearchSessionRow`
- parse it with the same defensive JSON dict helper
- thread it through `create_session(...)`

In `service.py`:

- accept `follow_up`
- pass normalized `follow_up_json` into DB session creation
- validate `chat_handoff.chat_id` ownership before persisting follow-up launch linkage

**Step 3: Use follow-up background in planning**

In `planner.py`:

- extend `build_initial_plan(...)` with optional follow-up background input
- keep the draft query authoritative
- bias focus areas using attached `question`, `key_claims`, and `unresolved_questions`
- preserve current bounded focus-area limits

In `jobs.py`:

- pass `session.follow_up_json` into the planning hook during `drafting_plan`

**Step 4: Run the backend tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Research/test_research_runs_endpoint.py \
  tldw_Server_API/tests/Research/test_research_jobs_service.py \
  tldw_Server_API/tests/Research/test_research_planner.py -q
```

Expected:

- all targeted backend tests pass

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py \
  tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py \
  tldw_Server_API/app/core/Research/service.py \
  tldw_Server_API/app/core/Research/planner.py \
  tldw_Server_API/app/core/Research/jobs.py
git commit -m "feat(research): support chat follow-up launch metadata"
```

### Task 3: Add Red Package-Client And Composer Tests

Execution notes:

- Completed on 2026-03-19.
- Added red package/client/form coverage in:
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/services/tldw/__tests__/TldwApiClient.research-runs.test.ts`
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx`
  - `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`
- Verified red with:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/services/tldw/__tests__/TldwApiClient.research-runs.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
```

- Red reasons are expected:
  - `TldwApiClient.createResearchRun(...)` does not exist yet
  - `PlaygroundForm.tsx` does not yet expose `Follow-up Research`
  - `apps/tldw-frontend/lib/api/researchRuns.ts` does not yet include `follow_up?:`

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/services/tldw/__tests__/TldwApiClient.research-runs.test.ts`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/tldw-frontend/lib/api/researchRuns.ts`

**Step 1: Write the failing package-client test**

Add coverage that proves `TldwApiClient.createResearchRun(...)`:

- posts to `/api/v1/research/runs`
- sends `chat_handoff.chat_id`
- sends optional bounded `follow_up`

Add a small contract test or type-alignment assertion for `apps/tldw-frontend/lib/api/researchRuns.ts` so the web research client request shape stays in sync with the backend create contract.

**Step 2: Write the failing real-form test**

In a new `PlaygroundForm.follow-up-research.test.tsx`:

- render the real `PlaygroundForm`
- assert `Follow-up Research` is disabled for empty drafts
- assert it is disabled or unavailable for temporary chats
- assert a saved thread with draft text can open the confirmation surface
- assert the attached-background toggle appears only when attached context exists
- assert `Start research` calls the follow-up launch path with the bounded payload
- assert `Start research` is single-flight while launch is pending
- assert the normal send button still uses the normal send path

Use the same real-form harness style as the other `PlaygroundForm` integration tests so this verifies real DOM and callbacks, not only prop plumbing.

**Step 3: Update secondary guard coverage**

Add assertions for:

- `Follow-up Research`
- `Use attached research as background`
- `Start research`

This remains secondary copy coverage only.

**Step 4: Run the frontend tests to verify they fail**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/services/tldw/__tests__/TldwApiClient.research-runs.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
```

Expected:

- failures around missing client method and missing composer follow-up UI

**Step 5: Confirm red state**

Do not implement frontend code yet.

**Step 6: Commit**

```bash
git add \
  apps/packages/ui/src/services/tldw/__tests__/TldwApiClient.research-runs.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
git commit -m "test(chat): cover follow-up research launch"
```

### Task 4: Implement Direct Follow-Up Launch In The Package Client And Composer

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/ComposerToolbar.tsx` only if the existing toolbar prop surface needs a small extension for the new action placement
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/tldw-frontend/lib/api/researchRuns.ts`

**Step 1: Add the package-side research create client**

In `TldwApiClient.ts`:

- add typed request helpers for bounded follow-up launch
- add `createResearchRun(...)`
- keep the request shape aligned with backend `chat_handoff` and `follow_up`

In `apps/tldw-frontend/lib/api/researchRuns.ts`:

- extend `ResearchRunCreateRequest` with the same optional `follow_up` type

**Step 2: Add the composer confirmation surface**

In `PlaygroundForm.tsx`:

- add `Follow-up Research` in the existing tools/send-options area
- require:
  - non-empty draft
  - saved `serverChatId`
- show a small confirmation surface with:
  - draft query preview
  - optional `Use attached research as background` checkbox
  - `Start research`
  - `Cancel`

**Step 3: Launch and refresh**

On successful launch:

- call `tldwClient.createResearchRun(...)`
- include `chat_handoff.chat_id = serverChatId`
- include optional bounded `follow_up`
- invalidate the linked-runs query for the active chat thread
- close the confirmation surface
- preserve the draft and attached context

While launch is in flight:

- disable `Start research`
- ignore repeated clicks so the same draft cannot create duplicate runs

Do not navigate to `/research`, send a chat message, or alter the normal send flow.

**Step 4: Run the focused frontend tests to verify they pass**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/services/tldw/__tests__/TldwApiClient.research-runs.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx
```

Expected:

- all targeted frontend tests pass

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/services/tldw/TldwApiClient.ts \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/ComposerToolbar.tsx
git commit -m "feat(chat): launch follow-up research from composer"
```

### Task 5: Run Focused Verification And Record Outcome

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-19-deep-research-chat-follow-up-launch-implementation-plan.md`

**Step 1: Run focused backend verification**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Research/test_research_runs_endpoint.py \
  tldw_Server_API/tests/Research/test_research_jobs_service.py \
  tldw_Server_API/tests/Research/test_research_planner.py -q
```

Expected:

- all targeted backend tests pass

**Step 2: Run focused frontend verification**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/services/tldw/__tests__/TldwApiClient.research-runs.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx
```

Expected:

- all targeted frontend tests pass

**Step 3: Run Bandit On The Touched Backend Scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py \
  tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py \
  tldw_Server_API/app/core/Research/service.py \
  tldw_Server_API/app/core/Research/planner.py \
  tldw_Server_API/app/core/Research/jobs.py \
  -f json -o /tmp/bandit_deep_research_chat_follow_up_launch.json
```

Expected:

- no new findings in touched backend code

**Step 4: Update the execution note**

Append:

- commands run
- results
- any residual UX risks around duplicate query semantics or saved-thread-only launch

**Step 5: Commit**

```bash
git add \
  Docs/Plans/2026-03-19-deep-research-chat-follow-up-launch-implementation-plan.md
git commit -m "docs(research): finalize chat follow-up launch plan"
```
