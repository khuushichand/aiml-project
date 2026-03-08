# Deep Research Chat Completion Handoff Implementation Plan

**Goal:** Return completed deep research runs to the originating chat thread with one concise linked assistant message, and fall back to one deduped notification plus global toast when that chat is no longer available.

**Architecture:** Add a first-class `research_chat_handoffs` record in the research DB, extend the research create request with optional chat linkage, trigger a backend-owned completion bridge after research packaging completes, use the plain chat message create path for delivery, and move notification-to-toast handling into an app-level notifications bridge mounted from `AppProviders`.

**Tech Stack:** FastAPI, existing research service/jobs stack, SQLite-backed `ResearchSessionsDB`, existing chat DB abstractions, existing notifications endpoints/SSE, Next.js pages router, React, Vitest, pytest.

---

## Task 1: Add Red Tests For Durable Chat Handoff Records

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_service.py`
- Modify: `tldw_Server_API/tests/e2e/test_deep_research_runs.py`

**Step 1: Add create-session request/DB tests**

Cover:

- creating a research run with `chat_handoff.chat_id`
- handoff row is stored in a dedicated table
- non-chat launches do not create a handoff row

**Step 2: Add ownership/idempotency expectation tests**

Cover:

- one handoff row per research session
- repeated create logic does not produce duplicate linkage rows

**Step 3: Run focused tests to verify failure**

Run:

- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -q`

Expected: FAIL for missing schema support and missing handoff persistence.

## Task 2: Add Chat Handoff Schema And Research DB Persistence

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- Modify: `tldw_Server_API/app/core/Research/service.py`

**Step 1: Extend the create request**

Add an optional `chat_handoff` object with:

- `chat_id`
- `launch_message_id`

Do not overload:

- `limits_json`
- `provider_overrides`

**Step 2: Add the dedicated DB table**

Add `research_chat_handoffs` with:

- unique `session_id`
- `owner_user_id`
- `chat_id`
- `launch_message_id`
- `handoff_status`
- `delivered_chat_message_id`
- `delivered_notification_id`
- `last_error`
- timestamps

Add lookup/update helpers:

- `create_chat_handoff(...)`
- `get_chat_handoff(session_id)`
- `mark_chat_handoff_chat_inserted(...)`
- `mark_chat_handoff_notification_only(...)`
- `mark_chat_handoff_failed(...)`

**Step 3: Persist linkage during research run creation**

In `ResearchService.create_session(...)`:

- store the handoff row when `chat_handoff` is present
- keep the core session row unchanged except for the new request parsing

**Step 4: Re-run focused backend tests**

Expected: PASS for persistence tests.

## Task 3: Add Red Tests For Completion Delivery And Fallback

**Status:** Not Started

**Files:**
- Modify: `tldw_Server_API/tests/Research/test_research_jobs_worker.py`
- Modify: `tldw_Server_API/tests/Research/test_research_runs_endpoint.py`
- Modify: `tldw_Server_API/tests/e2e/test_deep_research_runs.py`

**Step 1: Add chat insertion tests**

Cover:

- completed linked run inserts exactly one assistant message
- repeated completion handling remains idempotent

**Step 2: Add fallback notification tests**

Cover:

- invalid or missing chat falls back to one notification
- fallback notification uses a stable dedupe key and deep link

**Step 3: Add non-fatal bridge behavior tests**

Cover:

- bridge failure does not fail the research run

**Step 4: Run focused tests to verify failure**

Expected: FAIL for missing bridge and fallback logic.

## Task 4: Implement The Backend Completion Bridge

**Status:** Not Started

**Files:**
- Add: `tldw_Server_API/app/core/Research/chat_handoff.py`
- Modify: `tldw_Server_API/app/core/Research/jobs.py`
- Modify: `tldw_Server_API/app/core/Research/service.py`
- Modify: supporting chat/notification abstractions only if necessary

**Step 1: Add a narrow handoff service**

Implement a backend-owned handoff helper that:

- loads the handoff row
- no-ops when absent
- no-ops when already delivered
- attempts chat insertion first
- falls back to notification only when chat delivery is impossible
- records status and delivery IDs

**Step 2: Use the plain chat message create path**

Do not use:

- `/{chat_id}/completions/persist`

Instead use the plain message-create semantics equivalent to:

- `POST /chats/{chat_id}/messages`

If implemented directly through DB/service code, keep it equivalent to plain assistant message insertion and owner-checked conversation access.

For v1, insert plain content only:

- concise completion line
- direct `/research?run=<id>` URL

Do not require message metadata on write.

**Step 3: Add deduped notification fallback**

Use `create_user_notification(...)` with:

- `kind = "deep_research_completed"`
- `link_type = "deep_research_run"`
- `link_id = session_id`
- `link_url = /research?run=<session_id>`
- `dedupe_key = deep_research_completed:<session_id>`

**Step 4: Hook the bridge into research completion**

Invoke the bridge after packaging completion and terminal transition handling.

Rules:

- best effort only
- do not fail the research run if the bridge fails
- persist `last_error` on handoff failure

**Step 5: Re-run backend delivery tests**

Expected: PASS

## Task 5: Add Red Tests For Chat Launch Linkage And Global Notification Toasts

**Status:** Not Started

**Files:**
- Modify: `apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx`
- Add or modify: notification page/provider tests under `apps/tldw-frontend/__tests__/pages/` or `apps/tldw-frontend/components/`

**Step 1: Add research launch-param tests**

Cover:

- chat launch carries transient `chat_id`
- research autorun passes chat linkage to run creation
- transient `chat_id` is removed after autorun

**Step 2: Add app-level notification bridge tests**

Cover:

- notification SSE event triggers one toast outside `/notifications`
- `/notifications` no longer duplicates the same toast

**Step 3: Run focused frontend tests to verify failure**

Expected: FAIL for missing transient chat linkage handling and missing app-level notification bridge.

## Task 6: Implement Frontend Launch Linkage And Global Notification Bridge

**Status:** Not Started

**Files:**
- Modify: `apps/packages/ui/src/routes/route-paths.ts`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `apps/tldw-frontend/pages/research.tsx`
- Add: app-level notification bridge component under `apps/tldw-frontend/components/`
- Modify: `apps/tldw-frontend/components/AppProviders.tsx`
- Modify: `apps/tldw-frontend/pages/notifications.tsx`

**Step 1: Propagate transient chat linkage**

Extend the chat launch helper to carry:

- `chat_id`
- optional `launch_message_id`

Then in `research.tsx`:

- include that linkage in `createResearchRun(...)`
- remove it from the URL after autorun

**Step 2: Add a shared notifications-to-toast bridge**

Mount a shared subscriber from `AppProviders.tsx` that:

- subscribes to the notifications SSE stream once
- emits toasts through `ToastProvider`

**Step 3: Remove duplicate page-level toasts**

Adjust `pages/notifications.tsx` so it no longer owns the only notification toast behavior.

The notifications page may keep:

- inbox refresh
- list rendering
- mark-read/snooze/dismiss actions

But it should not duplicate toasts already emitted by the global bridge.

**Step 4: Re-run focused frontend tests**

Expected: PASS

## Task 7: End-To-End Verification And Plan Finalization

**Status:** Not Started

**Files:**
- Modify: `Docs/Plans/2026-03-08-deep-research-chat-completion-handoff-implementation-plan.md`

**Step 1: Run focused backend verification**

Run:

- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_jobs_worker.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -q`

**Step 2: Run focused frontend verification**

Run:

- `bunx vitest run apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx apps/tldw-frontend/__tests__/pages/notifications.test.tsx`

Add any new provider/app-level notification bridge tests to that command.

**Step 3: Run Bandit on touched backend scope**

Run:

- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Research tldw_Server_API/app/api/v1/schemas/research_runs_schemas.py -f json -o /tmp/bandit_deep_research_chat_handoff.json`

**Step 4: Record actual results in this plan**

Update statuses and append real commands/results.

## Notes

- This slice intentionally keeps the chat completion message concise and link-only.
- This slice intentionally does not inline bundle content into chat.
- This slice intentionally uses a dedicated handoff table instead of hiding cross-domain linkage inside generic JSON session fields.
- This slice intentionally treats fallback notification as durable inbox state first, with a real global toast subscriber added explicitly to satisfy the app-wide toast requirement.
