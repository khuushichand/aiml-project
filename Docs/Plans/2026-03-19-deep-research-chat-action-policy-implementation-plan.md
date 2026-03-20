# Deep Research Chat Action Policy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace duplicated chat-side deep-research action gating with one shared run-state policy helper consumed by the linked-run status stack and research handoff message surfaces.

**Architecture:** Keep this frontend-only and centered on the existing `research-run-status.ts` helper layer. Add one pure action-policy helper that returns conservative, run-state-driven action eligibility and reason labels, then refactor `ResearchRunStatusStack.tsx` and `PlaygroundChat.tsx` to consume it without changing user-facing behavior.

**Tech Stack:** React, TypeScript, Vitest, existing linked-run status helpers and message-action seams.

---

### Task 1: Add Red Helper Tests For Shared Policy

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts`

**Step 1: Add shared-policy expectations**

Extend `research-run-status.test.ts` with failing tests for a new shared action-policy helper and its exported type contract.

Cover at least:

- completed run:
  - `needsReview = false`
  - `canUseInChat = true`
  - `canFollowUp = true`
  - primary label `Open in Research`
- `waiting_human + awaiting_plan_review`:
  - `needsReview = true`
  - `reasonLabel = "Plan review needed"`
  - `canUseInChat = false`
  - `canFollowUp = false`
  - primary label `Review in Research`
- `waiting_human + awaiting_custom_review`:
  - fallback `Review needed`
- non-review running or failed run:
  - conservative `canUseInChat = false`
  - conservative `canFollowUp = false`
  - primary label `Open in Research`

**Step 2: Run the focused helper test to verify red**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
```

Expected:

- failures around missing shared action-policy exports and assertions

**Step 3: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
git commit -m "test(chat): cover research action policy helper"
```

### Task 2: Implement The Shared Policy Helper

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/research-run-status.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts`

**Step 1: Add a pure policy helper**

In `research-run-status.ts`, add:

- a named exported `ChatLinkedResearchActionPolicy` type
- a new pure helper that accepts `ChatLinkedResearchRun` and returns that type

Recommended fields:

- `needsReview`
- `reasonLabel`
- `primaryActionKind`
- `primaryActionLabel`
- `researchHref`
- `canUseInChat`
- `canFollowUp`

Keep:

- `getChatLinkedResearchReviewReason(...)`
- `buildChatLinkedResearchPath(...)`

as implementation building blocks if that keeps the file simpler.

**Step 2: Keep conservative defaults explicit**

Ensure:

- only completed runs enable `Use in Chat`
- only completed runs enable `Follow up`
- checkpoint-needed runs switch the primary action label to `Review in Research`
- unknown nonterminal states stay conservative

**Step 3: Run focused helper verification**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
```

Expected:

- helper tests pass

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/research-run-status.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
git commit -m "feat(chat): add shared research action policy helper"
```

### Task 3: Refactor Linked-Run Status Rows To Consume Shared Policy

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/ResearchRunStatusStack.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx`

**Step 1: Replace row-level ad hoc gating**

In `ResearchRunStatusStack.tsx`:

- call the shared helper for each visible run
- use returned booleans instead of row-local gating for:
  - `Use in Chat`
  - `Follow up`
  - primary research link label
- keep the existing status badge and row layout unchanged

**Step 2: Keep row-level behavior unchanged**

Do not add new UI states in this refactor. The point is to preserve existing linked-run behavior while removing duplicate policy logic.

**Step 3: Run focused row regression tests**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
```

Expected:

- row behavior remains green under the shared helper

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/ResearchRunStatusStack.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx
git commit -m "refactor(chat): share status-row research policy"
```

### Task 4: Refactor Research Handoff Messages To Consume Shared Policy

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx`

**Step 1: Keep message-origin eligibility outside the helper**

In `PlaygroundChat.tsx`:

- preserve genuine research-handoff detection exactly as it exists today
- resolve the current linked run for matching handoff messages
- if a current run exists, ask the shared helper for policy exactly once per message
- adapt that one policy object back into the existing `onUseInChat`, `onFollowUp`, `researchReviewReason`, and `researchReviewHref` props

**Step 2: Reuse helper output without broadening message scope**

Behavior:

- if the current run policy allows `Use in Chat`, keep the current message action
- if the current run policy allows `Follow up`, keep the current message action
- if the current run policy requires review, pass the reason label and review href through the existing message action seam
- if no current run is found, keep the current message behavior unchanged

Do not make unrelated assistant messages eligible for research actions.
Do not spread policy lookup back across multiple builder helpers that each repeat current-run lookup logic.

**Step 3: Run focused message regression tests**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts
```

Expected:

- message and row behavior both stay green
- no-current-run message regressions stay green under the new single-policy adapter

**Step 4: Commit**

```bash
git add \
  apps/packages/ui/src/components/Option/Playground/PlaygroundChat.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx
git commit -m "refactor(chat): share message research policy"
```

### Task 5: Final Verification And Docs

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-19-deep-research-chat-action-policy-implementation-plan.md`

**Step 1: Run the final focused frontend suite**

Run:

```bash
./apps/packages/ui/node_modules/.bin/vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-run-status.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.follow-up-research.test.tsx
```

Expected:

- all focused tests pass
- status rows and handoff messages still agree on research action eligibility

**Step 2: Record execution notes**

Add:

- what changed
- focused test commands
- resulting pass counts

**Step 3: Commit docs**

```bash
git add Docs/Plans/2026-03-19-deep-research-chat-action-policy-implementation-plan.md
git commit -m "docs(research): finalize chat action policy plan"
```

---

## Execution Notes

- Not started.
