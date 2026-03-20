# Deep Research Chat Attachment-Surface Follow-Up Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let active, pinned, and recent attached research surfaces prepare a follow-up deep-research draft through the existing shared follow-up-preparation path.

**Architecture:** Keep this frontend-only. Add local `Follow up` confirmations to attachment-management surfaces near the composer, then route confirmed actions through the existing `Playground` follow-up-preparation callback. Reuse current attachment state, composer draft insertion, and explicit `Follow-up Research` launch behavior without adding new backend contracts.

**Tech Stack:** React, TypeScript, Vitest, existing playground attachment state and follow-up prep flow.

---

### Task 1: Add Red Attachment-Surface Follow-Up Tests

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`

**Step 1: Write the failing active-attachment test**

Add coverage that proves:

- active attachment surface shows `Follow up`
- clicking it opens a local confirmation
- confirming routes to the shared follow-up-preparation path

**Step 2: Write the failing pinned/history tests**

Add coverage that proves:

- pinned mini-card shows `Follow up`
- recent-history entries show `Follow up`
- cancelling does nothing
- confirming does not trigger `Use` implicitly

**Step 3: Extend secondary guard coverage**

Add assertions for:

- `Prepare follow-up?`
- `Prepare follow-up`

This remains secondary copy coverage only.

**Step 4: Run the focused frontend tests to verify they fail**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
```

Expected:

- failures around missing attachment-surface `Follow up` controls and missing confirmation UI

**Step 5: Confirm red state**

Do not implement production code yet.

**Step 6: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
git commit -m "test(chat): cover attachment-surface follow-up prep"
```

### Task 2: Add Local Confirmation Controls To Attachment Surfaces

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`

**Step 1: Extend the active attachment chip**

In `AttachedResearchContextChip.tsx`:

- add a `Follow up` action for the active attachment
- render a local confirmation UI when clicked
- call a narrow confirm callback only after confirmation

**Step 2: Extend pinned and history fallback surfaces**

In `PlaygroundForm.tsx`:

- add `Follow up` to the pinned mini-card
- add `Follow up` to each recent-history entry
- render local confirmation UI per target

**Step 3: Prevent accidental cross-actions**

Make sure:

- `Follow up` does not bubble into `Use`
- `Follow up` does not alter pin/history state by itself

**Step 4: Run the focused tests**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
```

Expected:

- tests pass or now fail only on missing shared callback wiring

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx
git commit -m "feat(chat): add attachment-surface follow-up controls"
```

### Task 3: Thread Confirmed Attachment Follow-Up Into Playground

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx`

**Step 1: Reuse the existing shared preparation path**

In `Playground.tsx`:

- thread a confirmed attachment follow-up callback into the same `handlePrepareResearchFollowUp(...)` path already used by run rows and completion messages
- do not duplicate bundle fetch or prompt building logic

**Step 2: Pass the callback into attachment surfaces**

In `PlaygroundForm.tsx` and `AttachedResearchContextChip.tsx`:

- connect confirm actions to the shared `Playground` callback
- keep attachment state changes separate from follow-up confirmation

**Step 3: Run focused verification**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx
```

Expected:

- attachment-surface tests pass
- existing run-surface follow-up tests stay green

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/Playground.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx
git commit -m "feat(chat): prepare follow-up from attachment surfaces"
```

### Task 4: Final Verification And Docs

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-19-deep-research-chat-attachment-follow-up-implementation-plan.md`

**Step 1: Run the final focused frontend suite**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts
```

Expected:

- all focused tests pass

**Step 2: Record execution notes**

Add:

- what changed
- focused test commands
- resulting pass counts

**Step 3: Commit docs**

```bash
git add Docs/Plans/2026-03-19-deep-research-chat-attachment-follow-up-implementation-plan.md
git commit -m "docs(research): finalize attachment-surface follow-up plan"
```

---

## Execution Notes

- Task 1 completed by extending the mocked `Playground` integration seam and guard coverage for attachment-surface follow-up preparation. The red test commit is `ed9640c43` (`test(chat): cover attachment-surface follow-up prep`).
- Task 2 added local `Follow up` confirmation controls to the active attachment chip, pinned mini-card, and recent-history rows in [AttachedResearchContextChip.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx) and [PlaygroundForm.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx).
- Task 3 reused the existing shared `handlePrepareResearchFollowUp(...)` callback in [Playground.tsx](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/Playground.tsx) instead of adding a second follow-up-preparation path, and tightened the mocked integration test seam to scope follow-up assertions by surface.
- Focused verification commands run:
  - `./apps/packages/ui/node_modules/.bin/vitest run apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts`
  - Result: `32/32` passed
  - `./apps/packages/ui/node_modules/.bin/vitest run apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts`
  - Result: `47/47` passed
- Bandit was not run for this slice because the change set is frontend/package TypeScript and docs only.
