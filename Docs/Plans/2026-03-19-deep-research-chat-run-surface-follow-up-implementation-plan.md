# Deep Research Chat Run-Surface Follow-Up Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let completed deep-research surfaces prepare a follow-up research draft in chat by attaching the selected run and prefilling the composer with a deterministic prompt.

**Architecture:** Keep this frontend-only. Add `Follow up` actions to completed linked-run rows and completion handoff messages, route those actions through a single shared handler in the chat/playground layer, and reuse the existing composer draft insertion and explicit `Follow-up Research` launch flow. No backend contract changes are required.

**Tech Stack:** React, TypeScript, TanStack Query, Vitest, existing playground/chat state.

---

### Task 1: Add Red Surface Tests For Follow-Up Actions

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`

**Step 1: Write the failing linked-run status test**

Add coverage that proves:

- completed linked-run rows show `Follow up`
- non-completed rows do not
- clicking `Follow up` prepares a composer draft rather than launching immediately

**Step 2: Write the failing completion-message test**

Add coverage that proves:

- completion handoff messages show `Follow up`
- unrelated assistant messages do not
- clicking `Follow up` goes through the same preparation path as linked-run rows

**Step 3: Extend secondary guard coverage**

Add assertions for:

- `Follow up on this research:`
- `Follow up`

This remains secondary copy coverage only.

**Step 4: Run the frontend tests to verify they fail**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
```

Expected:

- failures around missing `Follow up` actions and missing shared follow-up preparation flow

**Step 5: Confirm red state**

Do not implement production code yet.

**Step 6: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
git commit -m "test(chat): cover run-surface follow-up actions"
```

### Task 2: Add Shared Follow-Up Preparation Helpers

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/research-chat-context.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/research-run-status.ts` only if it is the cleanest shared location for prompt text helpers
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts`

**Step 1: Write the failing helper test**

Add tests for:

- deterministic prompt builder returns `Follow up on this research: <query>`
- blank or whitespace queries normalize safely

**Step 2: Implement the helper**

Add a small shared helper that:

- accepts a run query
- returns the deterministic prompt string

Keep it pure and boring.

**Step 3: Run the helper tests**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts
```

Expected:

- helper tests pass

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/research-chat-context.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts
git commit -m "feat(chat): add follow-up prompt helper"
```

### Task 3: Implement Run-Row And Message Follow-Up Actions

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/ResearchRunStatusStack.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Common/Playground/Message.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`

**Step 1: Extend the linked-run row surface**

In `ResearchRunStatusStack.tsx`:

- add an `onFollowUp?: (run) => void` prop
- render `Follow up` only for completed runs
- keep `Use in Chat` and `Open in Research`

**Step 2: Extend completion handoff message actions**

In `Message.tsx`:

- add `Follow up` only for genuine completion handoff messages
- keep `Use in Chat`
- route through a parent callback rather than embedding run-selection logic in the message component

**Step 3: Thread callbacks through chat surface**

In `PlaygroundChat.tsx`:

- route linked-run and message `Follow up` actions into a single callback prop for the higher-level playground container
- avoid duplicating prompt-building or attachment logic in the chat component

**Step 4: Run the targeted tests**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx
```

Expected:

- surface tests pass or now fail only on missing playground/composer integration

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/ResearchRunStatusStack.tsx \
  apps/packages/ui/src/components/Common/Playground/Message.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx
git commit -m "feat(chat): add run-surface follow-up actions"
```

### Task 4: Integrate Follow-Up Preparation With Playground Draft And Attachment State

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Test: existing relevant playground/chat integration tests

**Step 1: Add a shared prepare-follow-up callback**

In `Playground.tsx`:

- accept a selected research run
- restore/attach it as active context if needed
- build the deterministic prompt
- route the prompt into `PlaygroundForm`

**Step 2: Reuse existing draft insertion behavior**

In `PlaygroundForm.tsx`:

- expose or reuse the current overwrite/append prompt insertion flow
- if draft is empty, replace directly
- if draft is non-empty, show the overwrite/append confirmation
- focus the textarea after insertion

Do not trigger the actual research launch here. Keep the current explicit `Follow-up Research` button as the only launch path.

**Step 3: Run focused frontend verification**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts
```

Expected:

- all targeted tests pass

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/Playground.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx
git commit -m "feat(chat): prepare follow-up research from completed runs"
```

### Task 5: Record Verification And Finalize

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-19-deep-research-chat-run-surface-follow-up-implementation-plan.md`

**Step 1: Record execution notes**

Add:

- what changed
- focused test commands
- resulting pass counts

**Step 2: Commit docs**

```bash
git add Docs/Plans/2026-03-19-deep-research-chat-run-surface-follow-up-implementation-plan.md
git commit -m "docs(research): finalize run-surface follow-up plan"
```

---

## Execution Notes

- Task 1 corrected the red tests to assert the approved shared `onPrepareResearchFollowUp` seam instead of the existing attach-context path. The focused red run failed only on the missing `Follow up` controls and missing deterministic prompt copy in `PlaygroundForm.tsx`.
- Task 2 added `buildResearchFollowUpPrompt(...)` to `research-chat-context.ts` with whitespace normalization and a safe blank-query fallback.
- Task 3 added completed-only `Follow up` actions to linked research rows and deep-research completion handoff messages, then threaded both into a single `PlaygroundChat` callback without embedding draft or attach logic in the chat surfaces.
- Task 4 integrated the callback in `Playground.tsx` by best-effort reattaching the selected run, seeding `selectedQuickPrompt` with the deterministic prompt, and reusing the existing overwrite/append insertion flow in `PlaygroundForm.tsx`. The form now also refocuses the textarea after follow-up prompt insertion.

## Verification

- Red Task 1 check:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
```

Result:
- `3` failed, `8` passed
- intended failures were:
  - missing `Follow up` button on completed linked-run rows
  - missing `Follow up` button on completion handoff messages
  - missing `Follow up on this research:` copy in `PlaygroundForm.tsx`

- Task 2 helper check:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts
```

Result:
- `1` file passed
- `15` tests passed

- Task 3 surface check:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx
```

Result:
- `2` files passed
- `10` tests passed

- Final focused verification:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
```

Result:
- `6` files passed
- `43` tests passed

## Commits

- `7b1c49e12` `test(chat): cover run-surface follow-up actions`
- `9eba2ed4a` `feat(chat): add follow-up prompt helper`
- `e9b1008ef` `feat(chat): add run-surface follow-up actions`
- `d26e0d416` `feat(chat): prepare follow-up research from completed runs`
