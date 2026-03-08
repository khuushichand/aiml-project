# Deep Research Chat-Linked Runs Status Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a thread-local deep research status surface to chat that shows all linked runs above the transcript without inserting progress messages into the conversation.

**Architecture:** Add a compact chat-facing endpoint that lists linked research runs for a chat by joining `research_chat_handoffs` with current research session state, then render those rows in `PlaygroundChat.tsx` using lightweight polling keyed by `serverChatId`. Keep the status outside the transcript and link each row back to `/research?run=<id>`.

**Tech Stack:** FastAPI, Pydantic, `ResearchSessionsDB`, `ResearchService`, existing chat session endpoints, package-side `TldwApiClient`, React, React Query, Vitest, pytest.

---

### Task 1: Add Red Backend Tests For Chat-Linked Run Listing

**Files:**
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_service.py`
- Modify: `tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py`

**Step 1: Write the failing service-level tests**

Cover:

- listing linked runs for a `chat_id` returns only that user’s runs
- runs include compact fields only
- terminal history is server-side bounded while nonterminal runs are preserved
- linked runs are ordered newest first by updated time
- chats with no linked runs return an empty list

**Step 2: Write the failing endpoint test**

Cover:

- `GET /api/v1/chats/{chat_id}/research-runs` returns `200`
- unauthorized or non-owner access is rejected through normal chat ownership checks

**Step 3: Run tests to verify they fail**

Run:

- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py -q`

Expected: FAIL for missing DB/service query path and missing endpoint/schema support.

**Step 4: Commit**

Commit after the backend tests are green later in this task group:

- `git add tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py`
- `git commit -m "test(chat): cover linked research run status list"`

### Task 2: Implement Backend Query Path And Chat Endpoint

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`

**Step 1: Add compact DB query support**

In `ResearchSessionsDB.py` add a helper that:

- filters by `owner_user_id`
- filters by `chat_id`
- joins `research_chat_handoffs` to `research_sessions`
- returns compact linked-run rows ordered by `updated_at DESC`
- bounds terminal rows server-side to all nonterminal plus latest `10` terminal runs

Do not return full bundle, artifact, or checkpoint payload data.

**Step 2: Add service wrapper**

In `ResearchService`, add a `list_chat_linked_runs(...)` helper that:

- accepts `owner_user_id`
- accepts `chat_id`
- maps DB rows into a stable compact shape

Use the existing research service construction pattern so per-user DB resolution remains correct in multi-user mode.

**Step 3: Add response schemas**

In `chat_session_schemas.py`, add:

- `ChatLinkedResearchRunResponse`
- `ChatLinkedResearchRunsResponse`

Include only:

- `run_id`
- `query`
- `status`
- `phase`
- `control_state`
- `latest_checkpoint_id`
- `updated_at`

**Step 4: Add the endpoint**

In `character_chat_sessions.py`, add:

- `GET /api/v1/chats/{chat_id}/research-runs`

The endpoint must:

- load and ownership-check the chat
- call `ResearchService.list_chat_linked_runs(...)`
- return the compact response

Do not construct `/research` URLs in the backend response.

**Step 5: Run tests to verify they pass**

Run:

- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py -q`

Expected: PASS

**Step 6: Commit**

- `git add tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/app/core/Research/service.py tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py`
- `git commit -m "feat(chat): add linked research run status api"`

### Task 3: Add Red Frontend Tests For Thread-Level Research Status

**Files:**
- Modify or add: `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.search.integration.test.tsx` only if an existing harness is easier to extend
- Modify or add: `apps/packages/ui/src/services/tldw/__tests__/TldwApiClient.research-runs.test.ts`

**Step 1: Add failing API client test**

Cover:

- `tldwClient.listChatResearchRuns(chatId)` hits `/api/v1/chats/{chat_id}/research-runs`

**Step 2: Add failing chat UI tests**

Cover:

- when `serverChatId` exists, the chat renders a status block above messages
- when the thread is otherwise empty, the status block still renders below empty-state scaffolding and above the transcript region
- multiple linked runs render as stacked rows
- waiting/completed/failed rows render distinct labels
- `Open in Research` links are built through the shared research route helper
- the status block does not appear for temporary chats or chats without a server ID

**Step 3: Add polling behavior test**

Cover:

- the query refetch interval is active for nonterminal runs
- it slows when all rows are terminal

**Step 4: Add non-blocking failure test**

Cover:

- linked-run query failure does not break chat rendering
- no transcript mutation or toast is emitted for that failure in v1

**Step 5: Run tests to verify they fail**

Run:

- `bunx vitest run apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx apps/packages/ui/src/services/tldw/__tests__/TldwApiClient.research-runs.test.ts`

Expected: FAIL for missing API client method and missing UI status block.

**Step 6: Commit**

Commit after the frontend tests are green later in this task group:

- `git add apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx apps/packages/ui/src/services/tldw/__tests__/TldwApiClient.research-runs.test.ts`
- `git commit -m "test(chat): cover linked research status banner"`

### Task 4: Implement Frontend API Client And Stacked Status Block

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`
- Modify: `apps/packages/ui/src/routes/route-paths.ts`
- Add if needed: `apps/packages/ui/src/components/Option/Playground/ResearchRunStatusStack.tsx`
- Add if needed: `apps/packages/ui/src/components/Option/Playground/research-run-status.ts`

**Step 1: Add compact API client method**

Implement:

- `listChatResearchRuns(chatId: string)`

It should call:

- `/api/v1/chats/${chatId}/research-runs`

and return the compact list response.

**Step 2: Add a small presenter/helper if needed**

Keep row normalization and grouping out of the main render body if `PlaygroundChat.tsx` becomes unreadable.

That helper should:

- group nonterminal rows ahead of terminal rows
- preserve backend order within each group
- derive row labels like `Running`, `Needs review`, `Completed`, `Failed`, `Cancelled`
- build `Open in Research` links through the shared route helper

**Step 3: Render the stacked status block**

In `PlaygroundChat.tsx`:

- do nothing for temporary chats
- do nothing when `serverChatId` is absent
- fetch linked runs with a lightweight query
- render the compact stacked rows above the transcript
- include `Open in Research` links through the shared route helper
- keep query errors non-blocking and silent in v1

**Step 4: Add terminal overflow handling**

If there are many terminal rows:

- show active/waiting rows first
- collapse older terminal rows behind a `Show more` affordance

Keep v1 simple and deterministic.

**Step 5: Re-run focused frontend tests**

Run:

- `bunx vitest run apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx apps/packages/ui/src/services/tldw/__tests__/TldwApiClient.research-runs.test.ts`

Expected: PASS

**Step 6: Commit**

- `git add apps/packages/ui/src/services/tldw/TldwApiClient.ts apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx apps/packages/ui/src/routes/route-paths.ts apps/packages/ui/src/components/Option/Playground/ResearchRunStatusStack.tsx apps/packages/ui/src/components/Option/Playground/research-run-status.ts apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx apps/packages/ui/src/services/tldw/__tests__/TldwApiClient.research-runs.test.ts`
- `git commit -m "feat(chat): show linked deep research runs in thread"`

### Task 5: Focused Verification And Plan Finalization

**Files:**
- Modify: `Docs/Plans/2026-03-08-deep-research-chat-linked-runs-status-implementation-plan.md`

**Step 1: Run focused backend verification**

Run:

- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py -q`

**Step 2: Run focused frontend verification**

Run:

- `bunx vitest run apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx apps/packages/ui/src/services/tldw/__tests__/TldwApiClient.research-runs.test.ts`

Add any existing related playground test file if the implementation extends a shared harness.

**Step 3: Run Bandit on the touched backend scope**

Run:

- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Research tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py -f json -o /tmp/bandit_deep_research_chat_linked_runs_status.json`

**Step 4: Record actual commands and outcomes**

Update this plan with:

- status for each task
- actual verification commands
- actual pass/fail results

## Notes

- This slice intentionally keeps research state outside the transcript.
- This slice intentionally uses polling, not research SSE, in chat.
- This slice intentionally links out to `/research` instead of reproducing checkpoint or bundle UI inside chat.
