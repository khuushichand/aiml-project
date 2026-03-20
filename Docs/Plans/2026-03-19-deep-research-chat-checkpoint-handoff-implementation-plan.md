# Deep Research Chat Checkpoint Handoff Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make checkpoint-needed linked research runs in chat show a clear review reason and a stronger `Review in Research` handoff while suppressing completion-only actions.

**Architecture:** Keep this frontend-only and scoped to the linked-run status stack. Extend the run-status helper layer to derive checkpoint review reason labels from existing `status` and `phase` fields, then update the row renderer to show review-needed intent without changing non-checkpoint rows.

**Tech Stack:** React, TypeScript, Vitest, existing linked-run status stack and playground chat integration.

---

### Task 1: Add Red Checkpoint-Handoff Tests

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx`

**Step 1: Add plan-review handoff coverage**

Write a failing test showing that a linked run with:

- `status: "waiting_human"`
- `phase: "awaiting_plan_review"`

renders:

- `Plan review needed`
- `Review in Research`

and does not render:

- `Use in Chat`
- `Follow up`

**Step 2: Add sources and outline review coverage**

Write failing tests showing:

- `awaiting_source_review` -> `Sources review needed`
- `awaiting_sources_review` -> `Sources review needed`
- `awaiting_outline_review` -> `Outline review needed`

**Step 3: Add fallback and non-checkpoint regression coverage**

Write tests showing:

- `waiting_human` with an unknown review-like phase falls back to `Review needed`
- completed runs still retain `Use in Chat`, `Follow up`, and `Open in Research`

**Step 4: Run the focused test file to verify red**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx
```

Expected:

- failures around missing reason labels and incorrect action rendering

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx
git commit -m "test(chat): cover checkpoint handoff status rows"
```

### Task 2: Extend Run-Status Helpers

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/research-run-status.ts`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts`

**Step 1: Add helper tests**

Create or extend helper tests covering:

- checkpoint-review eligibility detection
- reason-label derivation for:
  - `awaiting_plan_review`
  - `awaiting_source_review`
  - `awaiting_sources_review`
  - `awaiting_outline_review`
  - unknown `waiting_human` review phase fallback

**Step 2: Add minimal helper implementation**

In `research-run-status.ts`, add helpers such as:

- `isCheckpointReviewRun(run)`
- `getChatLinkedResearchReviewReason(run)`

Keep the logic centralized there rather than embedding it in JSX.

**Step 3: Keep current status behavior intact**

Do not change:

- terminal ordering
- polling intervals
- run path construction
- general completed/failed/cancelled labels

**Step 4: Run focused helper tests**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
```

Expected:

- helper tests pass

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/research-run-status.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
git commit -m "feat(chat): derive checkpoint review reasons"
```

### Task 3: Update Research Run Status Rows

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/ResearchRunStatusStack.tsx`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx`

**Step 1: Add checkpoint-needed row rendering**

In `ResearchRunStatusStack.tsx`:

- detect checkpoint-needed rows using the new helper
- render the compact reason label near the status area
- change the row action text to `Review in Research`

**Step 2: Gate actions by row state**

For checkpoint-needed rows:

- suppress `Use in Chat`
- suppress `Follow up`

For non-checkpoint rows:

- keep the current actions unchanged

**Step 3: Keep the existing row layout**

Do not introduce a new banner or panel. Keep this inside the existing row stack and adjust only the row action/copy treatment.

**Step 4: Run focused integration verification**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
```

Expected:

- checkpoint-needed rows show correct reason labels
- `Review in Research` replaces the generic handoff for those rows
- non-checkpoint rows remain green

**Step 5: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/ResearchRunStatusStack.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
git commit -m "feat(chat): improve checkpoint handoff rows"
```

### Task 4: Final Verification And Docs

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-19-deep-research-chat-checkpoint-handoff-implementation-plan.md`

**Step 1: Run the final focused frontend suite**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx
```

Expected:

- all focused tests pass
- checkpoint-needed rows are green without regressing completed-run chat actions

**Step 2: Record execution notes**

Add:

- what changed
- focused test commands
- resulting pass counts

**Step 3: Commit docs**

```bash
git add Docs/Plans/2026-03-19-deep-research-chat-checkpoint-handoff-implementation-plan.md
git commit -m "docs(research): finalize checkpoint handoff plan"
```
