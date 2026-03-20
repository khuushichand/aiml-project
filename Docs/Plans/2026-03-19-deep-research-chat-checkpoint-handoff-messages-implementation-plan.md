# Deep Research Chat Checkpoint Handoff Messages Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make genuine deep-research handoff messages in chat show checkpoint-aware review actions that stay consistent with the linked-run status stack.

**Architecture:** Keep this frontend-only and scoped to the existing message-action seam in `PlaygroundChat.tsx`. Reuse the checkpoint helper logic already added for linked-run status rows to decide whether a research-origin handoff message keeps `Use in Chat` / `Follow up` or instead shows a reason label plus `Review in Research`.

**Tech Stack:** React, TypeScript, Vitest, existing `PlaygroundChat` message action wiring and run-status helpers.

---

### Task 1: Add Red Message-Handoff Tests

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx`

**Step 1: Add checkpoint-needed handoff coverage**

Write failing tests showing that a genuine research handoff message whose current linked run is checkpoint-needed:

- shows the correct reason label
- shows `Review in Research`
- does not show `Use in Chat`
- does not show `Follow up`

Cover at least:

- `awaiting_plan_review`
- `awaiting_source_review` or `awaiting_sources_review`
- `awaiting_outline_review`

**Step 2: Add fallback and regression coverage**

Write tests showing:

- unknown `waiting_human` review phase falls back to `Review needed`
- genuine handoff messages with no current linked-run match keep the old actions
- unrelated assistant messages still do not get research handoff actions

**Step 3: Run the focused message integration test to verify red**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx
```

Expected:

- failures around missing checkpoint-aware reason labels and stale completion actions on research handoff messages

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx
git commit -m "test(chat): cover checkpoint handoff messages"
```

### Task 2: Reuse Checkpoint Helpers In PlaygroundChat

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx`

**Step 1: Add a current-run lookup for handoff messages**

In `PlaygroundChat.tsx`:

- resolve the current linked run for a handoff message by `run_id`
- keep the lookup local to the message-action decision path

**Step 2: Gate message actions with the helper layer**

Reuse:

- `isCheckpointReviewRun(...)`
- `getChatLinkedResearchReviewReason(...)`
- `buildChatLinkedResearchPath(...)`

Behavior:

- checkpoint-needed handoff message:
  - no `Use in Chat`
  - no `Follow up`
  - show reason label
  - show `Review in Research`
- no matching current run:
  - keep existing message actions unchanged

**Step 3: Keep genuine-handoff detection unchanged**

Do not broaden which messages are treated as research-origin handoffs. Only extend the existing `deep_research_completion` path.

**Step 4: Run focused verification**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
```

Expected:

- message-handoff checkpoint tests pass
- status-stack checkpoint tests remain green

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx
git commit -m "feat(chat): add checkpoint-aware handoff messages"
```

### Task 3: Final Verification And Docs

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-19-deep-research-chat-checkpoint-handoff-messages-implementation-plan.md`

**Step 1: Run the final focused frontend suite**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx
```

Expected:

- all focused tests pass
- checkpoint-aware behavior stays consistent between status rows and handoff messages

**Step 2: Record execution notes**

Add:

- what changed
- focused test commands
- resulting pass counts

**Step 3: Commit docs**

```bash
git add Docs/Plans/2026-03-19-deep-research-chat-checkpoint-handoff-messages-implementation-plan.md
git commit -m "docs(research): finalize checkpoint handoff messages plan"
```
