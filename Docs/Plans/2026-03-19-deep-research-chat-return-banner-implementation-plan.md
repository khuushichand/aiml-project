# Deep Research Chat Return Banner Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a one-time, non-transcript chat banner for runs explicitly returned from `/research` via `Back to Chat`.

**Architecture:** Extend the existing exact-thread chat return helper to carry an optional `researchReturnRunId`, then resolve that run against the linked-run query in chat and render a one-time banner that reuses the existing shared research action policy and action handlers.

**Tech Stack:** React, Next.js, existing package route helpers, package chat linked-run state, Vitest.

---

### Task 1: Add Red Route And Research Console Tests For Return Marker Propagation

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/routes/__tests__/route-paths.research.test.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx`

**Step 1: Add the route-helper failing test**

Add a test that expects the chat-thread route helper to include both:
- `settingsServerChatId`
- `researchReturnRunId`

**Step 2: Add the research console failing test**

Add a test that expects `Back to Chat` on a linked run to target the exact thread path with the returned run marker.

**Step 3: Run the focused frontend red tests**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/routes/__tests__/route-paths.research.test.ts

./apps/tldw-frontend/node_modules/.bin/vitest run \
  apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx
```

Expected:
- failures around missing `researchReturnRunId`

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/routes/__tests__/route-paths.research.test.ts \
  apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx
git commit -m "test(chat): cover research return banner navigation"
```

### Task 2: Extend `Back to Chat` Navigation With Return Marker

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/routes/route-paths.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/tldw-frontend/pages/research.tsx`

**Step 1: Extend the chat-thread route helper**

Update the helper so it accepts:
- `serverChatId`
- optional `researchReturnRunId`

Do not change the existing exact-thread semantics.

**Step 2: Update `Back to Chat`**

In `research.tsx`, include the selected run id when building the `Back to Chat` href.

**Step 3: Re-run the focused tests**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/routes/__tests__/route-paths.research.test.ts

./apps/tldw-frontend/node_modules/.bin/vitest run \
  apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx
```

Expected:
- navigation tests pass

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/routes/route-paths.ts \
  apps/tldw-frontend/pages/research.tsx
git commit -m "feat(research): carry return banner context to chat"
```

### Task 3: Add Red Chat Banner Tests

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`

**Step 1: Add failing banner tests**

Cover:
- explicit return URL marker shows the banner for the matching linked run
- completed returned runs show `Use in Chat` and `Follow up`
- checkpoint-needed returned runs show `Review in Research`
- dismiss hides the banner
- the query param is cleared after resolution

Split the coverage intentionally:
- `Playground.research-context.integration.test.tsx` proves the real URL -> coordinator -> banner flow
- `PlaygroundChat.research-status.integration.test.tsx` proves banner action behavior against linked-run state and shared policy

**Step 2: Run the focused red tests**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
```

Expected:
- failures around missing banner behavior

**Step 3: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
git commit -m "test(chat): cover returned research banner"
```

### Task 4: Implement The One-Time Return Banner In Chat

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`
- Create if needed: a small dedicated banner component under `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/`

**Step 1: Resolve return marker in chat**

In `Playground.tsx` or the closest owning seam:
- read `researchReturnRunId` from the URL
- capture it into local coordinator state before URL cleanup
- wait for linked runs to resolve
- match the returned run
- clear the query param after consumption

Do not replay the marker on refresh after it is consumed.

The same owner seam should also track dismissal state for the current page session.

**Step 2: Build the banner from shared policy**

Use the existing research action policy helper so the banner derives:
- reason label
- primary action
- `canUseInChat`
- `canFollowUp`

Do not reimplement run-state gating locally.

**Step 3: Reuse existing action handlers**

Wire banner actions through the same existing chat handlers used by:
- linked-run status rows
- handoff messages

**Step 4: Support dismiss**

Keep dismiss in `Playground.tsx` page-session state only. Do not persist it in storage or push it down into a child-local-only flag that can replay on remount.

**Step 5: Run focused frontend verification**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
```

Expected:
- return banner behavior passes with no regressions in linked-run actions

**Step 6: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/Playground.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx \
  [any new banner component]
git commit -m "feat(chat): add returned research banner"
```

### Task 5: Final Verification And Docs

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-19-deep-research-chat-return-banner-implementation-plan.md`

**Step 1: Run final focused verification**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/routes/__tests__/route-paths.research.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx

./apps/tldw-frontend/node_modules/.bin/vitest run \
  apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx
```

Expected:
- return marker navigation works
- chat shows the one-time banner only for explicit returns
- banner action eligibility matches shared policy
- banner dismissal does not replay on child remount during the same page session

**Step 2: Record execution notes**

Add:
- what changed
- focused commands
- pass counts
- whether the banner lived in `Playground` or a child component
- how URL marker clearing was implemented
- how ownership between `Playground` and `PlaygroundChat` was divided

**Step 3: Commit docs**

```bash
git add Docs/Plans/2026-03-19-deep-research-chat-return-banner-implementation-plan.md
git commit -m "docs(research): finalize chat return banner plan"
```

## Execution Notes

- `Back to Chat` now carries both `settingsServerChatId` and `researchReturnRunId` through the shared package route helper.
- `Playground.tsx` owns URL consumption for `researchReturnRunId`, captures it into coordinator state before cleanup, clears the query param from the URL, and keeps dismissal state page-local so the banner does not replay on child remount.
- `PlaygroundChat.tsx` owns the visible `Returned from Research` banner. It resolves the returned run id against the current linked-run query, reuses `getChatLinkedResearchActionPolicy(...)`, and wires `Use in Chat` / `Follow up` / `Review in Research` through the same handlers already used by linked-run status rows.
- No backend files changed in this slice, so Bandit was not applicable.

Focused verification that passed:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/routes/__tests__/route-paths.research.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx
# 37/37 passed

./apps/tldw-frontend/node_modules/.bin/vitest run \
  apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx
# 15/15 passed
```

---

## Execution Notes

- Not started.
