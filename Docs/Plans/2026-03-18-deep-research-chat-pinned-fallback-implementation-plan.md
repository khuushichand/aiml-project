# Deep Research Chat Pinned-Only Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the no-active chat fallback clearer when a pinned research attachment exists by rendering a dedicated pinned mini-card above recent history.

**Architecture:** Keep the slice frontend-only and scoped to the composer fallback in `PlaygroundForm.tsx`. Reuse existing pinned restore/unpin actions and preserve the active chip, persistence model, and recent-history behavior.

**Tech Stack:** React, TypeScript, Vitest, existing attachment chip/fallback components.

---

### Task 1: Add Red Tests For Pinned-Only Mini-Card Fallback

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.pinned-fallback.test.tsx`

**Step 1: Write the failing test**

In the new real-form fallback test, add coverage that proves:

- pinned-only no-active fallback renders a dedicated pinned mini-card surface
- `Use now` restores pinned into active
- `Unpin` clears only the pinned slot
- `Open in Research` points at the pinned run URL
- pinned and recent-history sections render separately when both exist

In the existing mocked `Playground` integration test, add only the minimal wiring coverage needed to prove the correct pinned/history state reaches the form surface.

**Step 2: Run test to verify it fails**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.pinned-fallback.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
```

Expected: failures around missing pinned-only fallback structure and actions.

**Step 3: Confirm red state**

Do not implement production code yet.

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.pinned-fallback.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
git commit -m "test(chat): cover pinned research fallback"
```

### Task 2: Implement The Pinned-Only Mini-Card In PlaygroundForm

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`

**Step 1: Write the minimal fallback UI**

In `PlaygroundForm.tsx`:

- when there is no active attachment but a pinned one exists, render:
  - `Pinned research`
  - pinned query
  - short explanatory line
  - `Use now`
  - `Open in Research`
  - `Unpin`
- if history exists too, render it as a separate block below the pinned mini-card
- use distinct containers or test ids for:
  - the pinned mini-card
  - the recent-history block

**Step 2: Reuse existing callbacks**

Use the existing props:

- `onRestorePinnedResearchContext`
- `onUnpinAttachedResearchContext`
- pinned `research_url`

Do not add new persistence or state logic.

**Step 3: Run the focused test**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
```

Expected: the new pinned-only fallback tests pass.

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
git commit -m "feat(chat): clarify pinned research fallback"
```

### Task 3: Add Guard Coverage For The Composer Surface

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`

**Step 1: Update guard expectations**

Add assertions for the new pinned fallback strings, such as:

- `Pinned research`
- `Use now`
- default-context explanation copy

This is secondary coverage only. Do not rely on the guard test as the main acceptance test for interactive fallback behavior.

**Step 2: Run the guard test**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
```

Expected: pass.

**Step 3: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
git commit -m "test(chat): guard pinned fallback copy"
```

### Task 4: Run Focused Verification And Record Outcome

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-18-deep-research-chat-pinned-fallback-implementation-plan.md`

**Step 1: Run focused frontend verification**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.pinned-fallback.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx
```

Expected: all pass.

**Step 2: Run adjacent regression scope**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/services/__tests__/chat-settings.deep-research-pinned.test.ts \
  apps/packages/ui/src/services/__tests__/chat-settings.deep-research.test.ts
```

Expected: pass; no attachment persistence regressions.

**Step 3: Update the execution note**

Append:

- commands run
- results
- any residual UX risks

**Step 4: Commit**

```bash
git add \
  Docs/Plans/2026-03-18-deep-research-chat-pinned-fallback-implementation-plan.md
git commit -m "docs(research): finalize pinned fallback plan"
```

---

## Execution Notes

- Added a real-form fallback test in `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.pinned-fallback.test.tsx`.
- Restructured the no-active fallback in `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx` into:
  - `data-testid="pinned-research-fallback-card"`
  - `data-testid="pinned-research-history-block"`
- Updated secondary copy/structure guard coverage in `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`.

Commands run:

```bash
./node_modules/.bin/vitest run src/components/Option/Playground/__tests__/PlaygroundForm.pinned-fallback.test.tsx
./node_modules/.bin/vitest run src/components/Option/Playground/__tests__/PlaygroundForm.pinned-fallback.test.tsx src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts src/components/Option/Playground/__tests__/AttachedResearchContextChip.test.tsx
./node_modules/.bin/vitest run src/services/__tests__/chat-settings.deep-research-pinned.test.ts src/services/__tests__/chat-settings.deep-research.test.ts
```

Results:

- Initial red run: `PlaygroundForm.pinned-fallback.test.tsx` failed `2/2` due to missing pinned-only fallback structure and actions.
- Focused frontend verification: `17/17` passed.
- Adjacent persistence regressions: `7/7` passed.

Residual UX risk:

- The pinned-only mini-card is intentionally more prominent; if the composer fallback grows further, copy density may need a later trim pass to keep the area compact.
