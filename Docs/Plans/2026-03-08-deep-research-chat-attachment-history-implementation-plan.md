# Deep Research Chat Attachment History Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist up to three prior deep-research attachments per saved server-backed chat thread and allow immediate restore from history.

**Architecture:** Extend the existing persisted attachment model in chat settings with a bounded `deepResearchAttachmentHistory` list. Normalize and merge that list explicitly, then expose it in the composer attachment surface as a recent-history selector that immediately replaces the active attachment.

**Tech Stack:** FastAPI, existing chat settings endpoints, React, TypeScript, package-side chat settings helpers, vitest, pytest.

**Status:** Complete

---

### Task 1: Add Red Backend Tests For Attachment History Validation

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/AuthNZ/integration/test_chat_settings_endpoint.py`

**Step 1: Write the failing tests**

Add endpoint tests that prove:

- `deepResearchAttachmentHistory` accepts a valid bounded list of attachment objects
- history entries use the same nested shape rules as `deepResearchAttachment`
- history entries with unknown keys are rejected
- a history list longer than 3 is rejected
- repeated settings updates merge history by per-entry `updatedAt`
- the current active `run_id` is excluded from merged history
- multi-user ownership still applies when history is present

**Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py \
  tldw_Server_API/tests/AuthNZ/integration/test_chat_settings_endpoint.py -q
```

**Step 3: Write minimal implementation**

Extend backend chat settings handling so `deepResearchAttachmentHistory` is:

- validated entry-by-entry using the same bounded rules as the active attachment
- merged by per-entry `updatedAt`
- rebuilt as newest-first, deduped, capped
- filtered to exclude the current active `run_id`

**Step 4: Re-run tests**

Expected:

- new history validation tests pass

### Task 2: Add Package-Side History Types And Normalization

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/types/chat-session-settings.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/services/chat-settings.ts`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/services/__tests__/chat-settings.deep-research-history.test.ts`

**Step 1: Write the failing tests**

Add tests that prove:

- valid history entries survive normalization
- malformed history entries are stripped
- history is deduped by `run_id`
- history is capped at 3
- active attachment `run_id` is excluded from normalized history
- history merge prefers newer per-entry `updatedAt`
- combined active-plus-history payload still fails cleanly if the resulting chat settings object exceeds the existing byte cap on write

**Step 2: Run tests to verify they fail**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/services/__tests__/chat-settings.deep-research-history.test.ts
```

**Step 3: Write minimal implementation**

In `chat-session-settings.ts`:

- add `deepResearchAttachmentHistory?: DeepResearchAttachment[]`

In `chat-settings.ts`:

- add bounded history normalization
- add entry-by-entry history sanitization
- rebuild history as newest-first, deduped, capped
- exclude the current active `run_id`
- merge history by per-entry `updatedAt`
- keep active/history merge semantics aligned with the backend settings merge contract

**Step 4: Re-run tests**

Expected:

- history normalization tests pass

### Task 3: Add Active/History State Helpers

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/research-chat-context.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts`

**Step 1: Write the failing tests**

Add helper tests that prove:

- attaching a different run pushes the old active attachment into history
- attaching the same `run_id` does not churn history
- restoring a history entry swaps it into active immediately
- removing the active attachment preserves history
- attach and restore both reset the baseline to the new active attachment
- history stays deduped and capped after each transition

**Step 2: Run tests to verify they fail**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts
```

**Step 3: Write minimal implementation**

Add pure helpers for:

- moving active attachment into history on true replacement
- restoring a history entry into active
- rebuilding bounded deduped history after swaps/removals

Keep this logic pure so the component and settings helpers share one transition contract.

**Step 4: Re-run tests**

Expected:

- transition helper tests pass

### Task 4: Restore And Persist History In Playground

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`

**Step 1: Write the failing tests**

Extend the Playground integration tests to prove:

- restoring a saved thread restores both active attachment and bounded history
- attaching a new run persists the updated active/history pair
- editing active attachment does not create history churn
- removing active attachment leaves persisted history available
- selecting a history item immediately replaces active and persists the swap

**Step 2: Run tests to verify they fail**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
```

**Step 3: Write minimal implementation**

In `Playground.tsx`:

- add local state for bounded history
- restore history from reconciled server-scoped settings
- persist active/history on committed transitions only
- keep temporary/local chats non-persistent

**Step 4: Re-run tests**

Expected:

- restore/persist integration tests pass

### Task 5: Add Composer History UI

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx`

**Step 1: Write the failing tests**

Add UI tests that prove:

- `Recent research` appears when history exists
- history items show query snippets
- selecting one activates it immediately
- no history affordance appears when neither active nor historical attachment exists
- when no active attachment exists but history does, the fallback affordance still renders near the composer

**Step 2: Run tests to verify they fail**

Run the focused vitest scope covering the chip/form components.

**Step 3: Write minimal implementation**

Add a compact recent-history menu/dropdown near the existing attachment chip or composer controls.

Keep it read-only and immediate-action only.

**Step 4: Re-run tests**

Expected:

- history affordance tests pass

### Task 6: Verification And Closeout

**Step 1: Run focused verification**

Backend:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py \
  tldw_Server_API/tests/AuthNZ/integration/test_chat_settings_endpoint.py -q
```

Frontend:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/services/__tests__/chat-settings.deep-research-history.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx
```

**Step 2: Run Bandit on touched backend scope**

```bash
source .venv/bin/activate && python -m bandit -r \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py \
  -f json -o /tmp/bandit_deep_research_attachment_history.json
```

**Step 3: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py \
  tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py \
  tldw_Server_API/tests/AuthNZ/integration/test_chat_settings_endpoint.py \
  apps/packages/ui/src/types/chat-session-settings.ts \
  apps/packages/ui/src/services/chat-settings.ts \
  apps/packages/ui/src/services/__tests__/chat-settings.deep-research-history.test.ts \
  apps/packages/ui/src/components/Option/Playground/research-chat-context.ts \
  apps/packages/ui/src/components/Option/Playground/Playground.tsx \
  apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx \
  Docs/Plans/2026-03-08-deep-research-chat-attachment-history-implementation-plan.md
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): add research attachment history"
```

### Execution Outcome

- Backend verification passed: `8 passed, 1 skipped`
- Focused frontend verification passed: `22 passed`
- Bandit on the touched backend scope reported only pre-existing low-severity findings in unrelated legacy lines of `character_chat_sessions.py`; no new findings were introduced by this slice
