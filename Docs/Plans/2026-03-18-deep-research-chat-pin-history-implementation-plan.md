# Deep Research Chat Pin-From-History Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users pin a recent deep-research history entry directly from the composer attachment surface without making it active first.

**Architecture:** Reuse the existing active/pinned/history chat-settings model and the existing pure transition helper path. Limit the slice to the composer UI surfaces and focused regression coverage so pinning from history remains explicit, non-activating, and persistence-compatible.

**Tech Stack:** React, TypeScript, Vitest, existing package-side chat settings helpers, existing chat attachment transition helpers.

---

### Task 1: Add Red UI Tests For Direct History Pinning

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`

**Step 1: Write the failing tests**

Add tests that prove:

- clicking `Pin` on a history item does not activate it
- pinning a history item updates the persisted pinned slot
- history ordering stays unchanged except for dedupe of the pinned `run_id`
- fallback recent-history UI supports direct pinning too

**Step 2: Run test to verify it fails**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
```

Expected: failures around missing history-entry pin controls and/or incorrect activation behavior.

**Step 3: Write minimal implementation**

Touch only the tests first. Do not change production code yet.

**Step 4: Re-run test to confirm red state**

Run the same command again.

Expected: still failing, now on the new direct-pinning expectations.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
git commit -m "test(chat): cover pin from research history"
```

### Task 2: Add Direct Pin Actions To Composer History Surfaces

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`

**Step 1: Implement the minimal UI**

In `AttachedResearchContextChip.tsx`:

- add a direct `Pin` control beside each recent-history item
- if the history item already matches the pinned slot, show `Pinned` or `Unpin`
- ensure the button click does not trigger the history-entry select handler

In `PlaygroundForm.tsx`:

- add the same direct `Pin` affordance to the no-active fallback history surface
- thread the existing pin/unpin callbacks through the fallback history UI

**Step 2: Reuse existing callbacks**

Do not add new state models. Reuse the current props/callback path that already supports:

- pinning the active slot
- unpinning
- restoring pinned
- selecting history

If new props are required, keep them narrowly scoped to history-entry pinning.

**Step 3: Run focused tests**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
```

Expected: direct history pinning tests pass.

**Step 4: Add or update small signal guard expectations**

If UI text/props changed materially, update:

- `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
```

Expected: pass.

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
git commit -m "feat(chat): add direct pin actions for research history"
```

### Task 3: Wire History Pinning Through Playground State Transitions

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/research-chat-context.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`

**Step 1: Add any missing pure-helper regression tests**

If the existing helper tests do not already prove the desired invariant, add one that proves:

- `pinAttachedResearchContext({ nextPinned })` leaves active unchanged
- history order remains unchanged except for removal of the pinned `run_id`

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts
```

Expected: fail only if the helper contract is missing.

**Step 2: Write minimal implementation**

In `Playground.tsx`:

- add a handler for pinning a specific history entry via `nextPinned`
- reuse the existing persisted active/pinned/history patch path
- do not mutate active when pinning a history entry

Only touch `research-chat-context.ts` if the current helper contract is insufficient.

**Step 3: Run focused tests**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
```

Expected: all history-pinning state tests pass.

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/Playground.tsx \
  apps/packages/ui/src/components/Option/Playground/research-chat-context.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
git commit -m "feat(chat): persist direct pinning from research history"
```

### Task 4: Run Focused Verification And Record Outcome

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-18-deep-research-chat-pin-history-implementation-plan.md`

**Step 1: Run focused frontend verification**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts
```

Expected: all pass.

**Step 2: Run adjacent regression scope**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/services/__tests__/chat-settings.deep-research-pinned.test.ts \
  apps/packages/ui/src/services/__tests__/chat-settings.deep-research.test.ts
```

Expected: pass; no persistence regressions.

**Step 3: Update the plan record**

Append a short execution note with:

- commands run
- pass/fail status
- any residual risks

**Step 4: Commit**

```bash
git add \
  Docs/Plans/2026-03-18-deep-research-chat-pin-history-implementation-plan.md
git commit -m "docs(research): finalize pin from history plan"
```
