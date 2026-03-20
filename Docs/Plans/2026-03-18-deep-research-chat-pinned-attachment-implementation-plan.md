# Deep Research Chat Pinned Attachment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist one pinned deep-research attachment per saved server-backed chat thread and restore it as the default active attachment when no explicit active attachment exists.

**Architecture:** Extend the existing chat-settings attachment model with a separate `deepResearchPinnedAttachment` slot. Normalize and merge active, pinned, and history together with explicit slot precedence, then expose pin/unpin/restore affordances near the composer attachment chip.

**Tech Stack:** FastAPI, existing chat settings endpoints, React, TypeScript, package-side chat settings helpers, vitest, pytest.

---

### Task 1: Add Red Backend Tests For Pinned Attachment Validation And Merge

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/tests/AuthNZ/integration/test_chat_settings_endpoint.py`

**Step 1: Write the failing tests**

Add tests that prove:

- `deepResearchPinnedAttachment` accepts the same bounded nested shape as `deepResearchAttachment`
- pinned entries with unknown keys are rejected
- pinned merge uses its own `updatedAt`
- merged history excludes the pinned `run_id`
- multi-user ownership still applies when pinned state is present

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py \
  tldw_Server_API/tests/AuthNZ/integration/test_chat_settings_endpoint.py -q
```

Expected: failures around missing pinned-attachment validation and merge behavior.

**Step 3: Write minimal implementation**

In `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`:

- validate `deepResearchPinnedAttachment` entry-by-entry using the same bounded rules as the active attachment
- merge pinned by `updatedAt`
- normalize active/pinned/history together so history excludes duplicate `run_id`s already present in active or pinned

**Step 4: Re-run test to verify it passes**

Run the same pytest command.

Expected: new pinned-attachment endpoint tests pass.

**Step 5: Commit**

```bash
git add \
  tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py \
  tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py \
  tldw_Server_API/tests/AuthNZ/integration/test_chat_settings_endpoint.py
git commit -m "feat(chat): validate pinned research attachment"
```

### Task 2: Add Package-Side Pinned Types And Normalization

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/types/chat-session-settings.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/services/chat-settings.ts`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/services/__tests__/chat-settings.deep-research-pinned.test.ts`

**Step 1: Write the failing test**

Add tests that prove:

- valid pinned attachment survives normalization
- malformed pinned attachment is stripped
- pinned merge prefers newer `updatedAt`
- history excludes active and pinned `run_id`s after merge
- active, pinned, and history normalization share one bounded contract

**Step 2: Run test to verify it fails**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/services/__tests__/chat-settings.deep-research-pinned.test.ts
```

Expected: failures around missing pinned slot normalization/merge.

**Step 3: Write minimal implementation**

In `chat-session-settings.ts`:

- add `deepResearchPinnedAttachment?: DeepResearchAttachment | null`

In `chat-settings.ts`:

- sanitize pinned independently
- merge pinned by its own `updatedAt`
- normalize active/pinned/history together with slot precedence:
  - active
  - pinned
  - history
- keep history capped at 3 after removing duplicates covered by active/pinned

**Step 4: Re-run test to verify it passes**

Run the same vitest command.

Expected: pinned normalization tests pass.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/types/chat-session-settings.ts \
  apps/packages/ui/src/services/chat-settings.ts \
  apps/packages/ui/src/services/__tests__/chat-settings.deep-research-pinned.test.ts
git commit -m "feat(chat): normalize pinned research attachment"
```

### Task 3: Add Pure Active/Pinned/History Transition Helpers

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/research-chat-context.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts`

**Step 1: Write the failing test**

Add helper tests that prove:

- pinning active copies it into the pinned slot without changing active
- pinning history copies it into pinned without forcing it active
- unpin clears only pinned
- restoring pinned makes it active immediately
- restoring pinned resets baseline to the same restored attachment snapshot
- restoring history while pinned exists preserves slot precedence and dedupe
- baseline resets when pinned is restored into active

**Step 2: Run test to verify it fails**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts
```

Expected: failures around missing pinned transition helpers.

**Step 3: Write minimal implementation**

Add pure helpers for:

- pinning active or history entries
- unpinning
- restoring pinned into active
- rebuilding bounded deduped history after active/pinned transitions

Keep this logic pure so `Playground` and settings persistence share one transition contract.

**Step 4: Re-run test to verify it passes**

Run the same vitest command.

Expected: pinned transition helper tests pass.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/research-chat-context.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts
git commit -m "feat(chat): add pinned research context transitions"
```

### Task 4: Restore And Persist Active/Pinned/History In Playground

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`

**Step 1: Write the failing test**

Extend Playground integration tests to prove:

- saved thread restore loads active, pinned, and history together
- when active is absent and pinned exists, pinned auto-restores as the active attachment
- pin/unpin operations persist the pinned slot
- switching chats restores the correct trio per thread
- temporary/local chats never persist pinned state

**Step 2: Run test to verify it fails**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
```

Expected: failures around missing pinned restore/persist behavior.

**Step 3: Write minimal implementation**

In `Playground.tsx`:

- add local state for the pinned attachment alongside active/history
- restore pinned from reconciled server-scoped settings
- if active is absent and pinned exists, restore pinned into active on thread open
- when pinned is restored into active, reset baseline to the same restored snapshot
- persist committed changes to active/pinned/history together for saved chats only

**Step 4: Re-run test to verify it passes**

Run the same vitest command.

Expected: restore/persist integration tests pass.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/Playground.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
git commit -m "feat(chat): restore pinned research attachments"
```

### Task 5: Add Composer Pinning UI

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`

**Step 1: Write the failing test**

Add UI tests that prove:

- active chip shows `Pin` and `Unpin`
- pinned slot renders a compact `Pinned research` section
- if active and pinned share the same `run_id`, the UI does not render a duplicate pinned row
- clicking pinned immediately makes it active
- history items can be pinned without forcing activation
- when no active attachment exists but pinned does, the composer still shows the pinned affordance

**Step 2: Run test to verify it fails**

Run the focused chip/form integration scope.

Expected: failures around missing pinning UI.

**Step 3: Write minimal implementation**

In `AttachedResearchContextChip.tsx`:

- add `Pin`/`Unpin` actions
- add compact pinned section above recent history when present

In `PlaygroundForm.tsx`:

- add the no-active fallback pinned affordance near the composer controls

Keep pinning outside the transcript and status stack.

**Step 4: Re-run test to verify it passes**

Run the same vitest scope.

Expected: pinning UI tests pass.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
git commit -m "feat(chat): add pinned research attachment UI"
```

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
  apps/packages/ui/src/services/__tests__/chat-settings.deep-research-pinned.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx
```

**Step 2: Run Bandit on touched backend scope**

```bash
source .venv/bin/activate && python -m bandit -r \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py \
  -f json -o /tmp/bandit_deep_research_pinned_attachment.json
```

**Step 3: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py \
  tldw_Server_API/tests/Character_Chat/test_chat_settings_endpoints.py \
  tldw_Server_API/tests/AuthNZ/integration/test_chat_settings_endpoint.py \
  apps/packages/ui/src/types/chat-session-settings.ts \
  apps/packages/ui/src/services/chat-settings.ts \
  apps/packages/ui/src/services/__tests__/chat-settings.deep-research-pinned.test.ts \
  apps/packages/ui/src/components/Option/Playground/research-chat-context.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/components/Option/Playground/Playground.tsx \
  apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): add pinned deep research attachments"
```
