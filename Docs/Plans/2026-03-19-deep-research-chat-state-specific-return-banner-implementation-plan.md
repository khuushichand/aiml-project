# Deep Research Chat State-Specific Return Banner Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the explicit `Returned from Research` chat banner adapt its copy and primary CTA to the returned run's current state, especially after checkpoint review has been cleared.

**Architecture:** Keep the existing `researchReturnRunId` return flow intact. Add a small frontend-only banner adapter that combines explicit return context with the current linked-run action policy to derive one of four banner modes: `completed`, `review_required`, `review_cleared`, or `generic`.

**Tech Stack:** React, package chat linked-run state, shared research action policy helpers, Vitest.

---

### Task 1: Add Red Banner-Mode Helper Tests

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts`

**Step 1: Write the failing helper tests**

Add tests for a new return-banner adapter/helper covering:
- completed run -> `completed` mode
- checkpoint-blocked run -> `review_required` mode
- explicit-return non-completed, non-review run -> `review_cleared` mode
- unknown nonterminal run -> `generic` mode

The helper should be fed current `ChatLinkedResearchRun` state plus an explicit-return flag.

**Step 2: Run the focused red test**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
```

Expected:
- failures around missing return-banner mode logic

**Step 3: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
git commit -m "test(chat): cover return banner state modes"
```

### Task 2: Implement The Return-Banner Adapter

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/research-run-status.ts`

**Step 1: Add a return-banner adapter/helper**

Implement a small helper that accepts:
- current `ChatLinkedResearchRun`
- explicit-return context

Return a narrow contract such as:
- `mode`
- `supportingText`
- `primaryActionLabel`
- booleans controlling whether the banner should expose:
  - attach-style CTA
  - follow-up CTA
  - only the research link

Do not fold this into `getChatLinkedResearchActionPolicy(...)`. The shared policy remains the run-state truth source; this helper is banner UX only.

**Step 2: Keep the mapping conservative**

Use:
- `review_required` when current shared policy says review is required
- `completed` when current run is completed
- `review_cleared` only when:
  - the banner is being shown because of explicit return
  - current run is not review-blocked
  - current run is not completed
- `generic` otherwise

**Step 3: Re-run the focused test**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
```

Expected:
- new helper tests pass

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/research-run-status.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
git commit -m "feat(chat): add return banner state adapter"
```

### Task 3: Add Red Banner Rendering Tests

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx`

**Step 1: Add failing banner behavior tests**

Cover:
- completed returned run keeps:
  - `Use in Chat`
  - `Follow up`
  - `Open in Research`
- review-required returned run keeps:
  - `Review in Research`
- review-cleared returned run shows:
  - `Continue with reviewed research`
  - `Open in Research`
  - no generic `Use in Chat` label in that banner
- `Continue with reviewed research` still routes through the existing attach handler

Use banner-scoped queries so the linked-run status stack does not make the assertions ambiguous.

**Step 2: Run the focused red test**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx
```

Expected:
- failures around missing `review_cleared` banner wording/behavior

**Step 3: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx
git commit -m "test(chat): cover state-specific return banner actions"
```

### Task 4: Implement State-Specific Banner Actions

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`

**Step 1: Apply the adapter to the existing return banner**

For the existing returned-run banner:
- resolve the returned run as today
- resolve the shared action policy as today
- derive the banner adapter mode

**Step 2: Update CTA rendering by mode**

Implement:
- `completed`
  - unchanged action set
- `review_required`
  - unchanged review-only action set
- `review_cleared`
  - supporting copy like `Your review is reflected in this run.`
  - primary CTA label `Continue with reviewed research`
  - CTA still calls the same attach handler used by `Use in Chat`
- `generic`
  - conservative `Open in Research` + `Dismiss`

Do not change the linked-run status stack or message-surface behavior in this task.

**Step 3: Re-run the focused banner test**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx
```

Expected:
- all banner behavior tests pass

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx
git commit -m "feat(chat): adapt returned research banner actions"
```

### Task 5: Final Verification And Docs

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-19-deep-research-chat-state-specific-return-banner-implementation-plan.md`

**Step 1: Run final focused verification**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx
```

Expected:
- helper and banner behavior agree
- completed and still-blocked return flows remain intact
- review-cleared flow gets the stronger CTA

**Step 2: Record execution notes**

Add:
- helper location
- final mode contract
- how `review_cleared` was determined
- focused commands and pass counts
- whether any existing return-banner tests needed tightening

**Step 3: Commit docs**

```bash
git add Docs/Plans/2026-03-19-deep-research-chat-state-specific-return-banner-implementation-plan.md
git commit -m "docs(research): finalize state-specific return banner plan"
```
