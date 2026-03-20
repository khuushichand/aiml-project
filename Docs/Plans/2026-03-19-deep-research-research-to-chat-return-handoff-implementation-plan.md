# Deep Research Research-To-Chat Return Handoff Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a validated `Back to Chat` return path from the web research console to the exact originating saved chat thread for linked runs.

**Architecture:** Extend the owned research run read model with a validated optional `chat_id`, null stale/inaccessible linkage at read time, and wire the web research console to one explicit chat-thread route helper. Keep this slice navigation-only with no transcript or composer mutation.

**Tech Stack:** FastAPI, Pydantic, SQLite-backed research/chat linkage reads, React, Next.js web UI, existing route helpers.

---

### Task 1: Add Red Backend Tests For Validated `chat_id` On Run Reads

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Research/test_research_runs_api.py`
- Modify or create as needed: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py`

**Step 1: Add read-model tests**

Write failing backend tests that cover:

- a linked run read includes `chat_id`
- an unlinked run read omits or nulls `chat_id`
- a run with persisted chat linkage whose chat no longer exists returns `chat_id = null`

Use real service/API seams, not hand-built dict assertions disconnected from the route.

**Step 2: Run the focused backend red tests**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Research/test_research_runs_api.py \
  tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py -q
```

Expected:

- failures around missing `chat_id` on the read payload

**Step 3: Commit**

```bash
git add \
  tldw_Server_API/tests/Research/test_research_runs_api.py \
  tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py
git commit -m "test(research): cover return handoff chat linkage"
```

### Task 2: Expose Validated `chat_id` On The Research Run Read Model

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/core/Research/service.py`
- Modify if needed: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/api/v1/endpoints/research_runs.py`

**Step 1: Extend the schema**

Add:

- `chat_id: str | None = None`

to the owned run read response model.

Do not add it to unrelated payloads unless they already derive from the same safe owned run response type and that exposure is intended.

**Step 2: Add backend-owned validity filtering**

Implement one read-time path that:

- looks up persisted research chat handoff linkage
- validates the linked chat still exists and is accessible for the owner
- returns `chat_id = null` when the linkage is stale

Do not just echo the raw persisted handoff table value.

**Step 3: Run focused backend verification**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Research/test_research_runs_api.py \
  tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py -q
```

Expected:

- read-model tests pass

**Step 4: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py \
  tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py \
  tldw_Server_API/app/core/Research/service.py \
  tldw_Server_API/app/api/v1/endpoints/research_runs.py
git commit -m "feat(research): expose validated chat return linkage"
```

### Task 3: Add A Concrete Chat-Thread Return Helper

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/routes/route-paths.ts`
- Modify as needed: web chat route/bootstrap seams in the web app if a helper target is not already supported

**Step 1: Define the return path explicitly**

Add one helper that builds the exact web chat-thread return path.

The helper must include enough information to reopen the saved server-backed thread. Do not hardcode an ad hoc URL string directly in `research.tsx`.

**Step 2: Verify chat-thread bootstrap support**

If `/chat` does not already support selecting a saved chat via URL/search params or route state, add the minimal support needed in the correct web bootstrap seam.

Do not ship a `Back to Chat` button that only lands on the generic chat home screen.

**Step 3: Add focused tests for the helper/bootstrap path**

Write or update the smallest relevant frontend tests to prove the helper or bootstrap logic targets the exact thread.

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/routes/route-paths.ts \
  [any minimal web chat bootstrap file changes]
git commit -m "feat(chat): add return handoff thread path"
```

### Task 4: Wire `Back to Chat` Into The Web Research Console

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/tldw-frontend/lib/api/researchRuns.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/tldw-frontend/pages/research.tsx`
- Add tests in the closest existing research page test seam

**Step 1: Update the web client type**

Extend the web `ResearchRun` / read payload typing so `chat_id` is available to the research console.

Keep package/web client parity where shared types overlap.

**Step 2: Render the affordance conditionally**

In `research.tsx`:

- show `Back to Chat` only when `chat_id` is present
- place it in the run header/action area
- use the shared route helper from Task 3

Do not add a fallback button for unlinked runs.

**Step 3: Add focused UI tests**

Cover:

- linked run shows `Back to Chat`
- unlinked run does not
- clicking uses the exact thread return path

**Step 4: Run focused frontend verification**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  [research page test file] \
  [route helper/bootstrap test file if added]
```

Expected:

- research console return affordance works only for valid linked runs

**Step 5: Commit**

```bash
git add \
  apps/tldw-frontend/lib/api/researchRuns.ts \
  apps/tldw-frontend/pages/research.tsx \
  [frontend tests]
git commit -m "feat(research): add back to chat return handoff"
```

### Task 5: Final Verification And Docs

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-19-deep-research-research-to-chat-return-handoff-implementation-plan.md`

**Step 1: Run the final focused verification**

Backend:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Research/test_research_runs_api.py \
  tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py -q
```

Frontend:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  [research page test file] \
  [route helper/bootstrap test file if added]
```

Expected:

- linked run read payload exposes validated `chat_id`
- stale linkage is nulled
- the web research console returns to the exact saved thread path

**Step 2: Run Bandit on touched backend scope**

Run:

```bash
source .venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/research_runs.py \
  tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py \
  tldw_Server_API/app/core/Research/service.py \
  tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py \
  -f json -o /tmp/bandit_research_back_to_chat.json
```

Expected:

- no new findings in touched code

**Step 3: Record execution notes**

Add:

- what changed
- focused test commands
- resulting pass counts
- any route/bootstrap decisions required to make exact-thread return work

**Step 4: Commit docs**

```bash
git add Docs/Plans/2026-03-19-deep-research-research-to-chat-return-handoff-implementation-plan.md
git commit -m "docs(research): finalize return handoff plan"
```

---

## Execution Notes

- Not started.
