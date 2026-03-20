# Deep Research Chat Message Research Actions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the deep-research handoff message prop bundle with one narrow `researchActions` contract so transcript handoff messages render from one structured seam without changing behavior.

**Architecture:** Keep this frontend-only and scoped to the transcript message path. Add a small `researchActions` view-model prop to `Message.tsx`, build it once in `PlaygroundChat.tsx`, and preserve the existing no-current-run fallback and non-handoff behavior.

**Tech Stack:** React, TypeScript, Vitest, existing deep-research handoff message helpers.

---

### Task 1: Add Red Message-Seam Tests For `researchActions`

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx`

**Step 1: Switch the mocked message seam to `researchActions`**

Update the mocked `PlaygroundMessage` in `PlaygroundChat.research-use-in-chat.integration.test.tsx` so it consumes:

- `researchActions?.reasonLabel`
- `researchActions?.primaryLink`
- `researchActions?.onUseInChat`
- `researchActions?.onFollowUp`

Do not leave the old four-prop mock in place.

**Step 2: Preserve current behavior expectations**

Keep the existing behavior coverage:

- completed handoff messages still show `Use in Chat`
- completed handoff messages still show `Follow up`
- checkpoint-needed handoff messages still show the reason label and `Review in Research`
- no-current-run handoff messages still preserve fallback actions
- unrelated assistant messages still show no deep-research actions

Expected red failure:

- `PlaygroundChat` / `Message` do not yet provide `researchActions`

**Step 3: Run the focused red test**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx
```

Expected:

- failures around missing `researchActions` wiring

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx
git commit -m "test(chat): cover message research actions contract"
```

### Task 2: Add `researchActions` To `Message.tsx`

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Common/Playground/Message.tsx`

**Step 1: Add the new message-level contract**

Add a narrow prop to `PlaygroundMessage`:

- `researchActions?: {`
- `reasonLabel?: string`
- `primaryLink?: { href: string; label: string }`
- `onUseInChat?: () => void`
- `onFollowUp?: () => void`
- `}`

Prefer a named exported type if that keeps the seam clearer.

**Step 2: Make `researchActions` authoritative for deep-research message rendering**

Refactor the deep-research handoff action row so:

- it renders from `researchActions` only
- it no longer separately depends on `deepResearchCompletion` metadata for `Use in Chat` / `Follow up` visibility once this object is present

Do not change unrelated generic message actions elsewhere in the component.

**Step 3: Run the focused seam test**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx
```

Expected:

- still failing until `PlaygroundChat.tsx` provides the object

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Common/Playground/Message.tsx
git commit -m "refactor(chat): add message research actions contract"
```

### Task 3: Build One `researchActions` Adapter In `PlaygroundChat.tsx`

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx`

**Step 1: Add one local adapter**

In `PlaygroundChat.tsx`, add one helper such as:

- `buildMessageResearchActions(metadataExtra?: Record<string, unknown>)`

It should:

- preserve genuine deep-research handoff detection
- resolve the current linked run once
- ask the shared action-policy helper for run-state policy when current linked-run state exists
- preserve the no-current-run fallback
- return `undefined` for non-handoff messages

Do not rebuild the object inline at each `PlaygroundMessage` call site.

**Step 2: Replace the four separate message props**

At all three `PlaygroundMessage` call sites inside `PlaygroundChat.tsx`, replace:

- `onUseInChat`
- `onFollowUp`
- `researchReviewReason`
- `researchReviewHref`

with:

- `researchActions={buildMessageResearchActions(...)}`

**Step 3: Keep unrelated message consumers unchanged**

Do not modify:

- prompt-related `onUseInChat` flows elsewhere in the app
- non-playground `PlaygroundMessage` call sites

This slice is only about the deep-research handoff message seam inside `PlaygroundChat.tsx`.

**Step 4: Run focused regression tests**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
```

Expected:

- completed, checkpoint-needed, unrelated-message, and no-current-run fallback behaviors stay green

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Common/Playground/Message.tsx
git commit -m "refactor(chat): share message research actions"
```

### Task 4: Final Verification And Docs

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-19-deep-research-chat-message-research-actions-implementation-plan.md`

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
- no-current-run handoff fallback remains intact

**Step 2: Record execution notes**

Add:

- what changed
- focused test commands
- resulting pass counts
- any behavior-preservation adjustments needed during the refactor

**Step 3: Commit docs**

```bash
git add Docs/Plans/2026-03-19-deep-research-chat-message-research-actions-implementation-plan.md
git commit -m "docs(research): finalize message research actions plan"
```

---

## Execution Notes

- Not started.
