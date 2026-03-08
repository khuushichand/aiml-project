# Deep Research Chat Request Preview And Debug Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make attached deep research context visible and editable from the composer request preview/debug surfaces while keeping the composer chip, preview JSON, and outbound request on the same active attachment state.

**Architecture:** Keep the active and run-derived attached research context in `Playground.tsx`, add small pure helpers in `research-chat-context.ts` for sanitizing and resetting edits, extend the existing raw request modal in `PlaygroundForm.tsx` with a structured attached-context editor, and route all edits back through the existing attached-context state setter. This slice is frontend-only and does not change the backend request contract.

**Tech Stack:** React, TypeScript, existing package-side playground components, vitest, Testing Library.

---

### Task 1: Add Red Tests For Structured Preview And Edit State

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`

**Step 1: Write the failing tests**

Extend the integration coverage so it proves:

- the request preview/debug modal renders an `Attached Research Context` section when an attachment exists
- that panel shows the attached run identity and editable bounded fields
- `Apply` updates the active attached context seen by the form/chip seam
- `Reset to Attached Run` restores the original run-derived snapshot
- switching threads clears or invalidates the editor state

Extend the signal guard so it proves `PlaygroundForm.tsx` keeps the new attached-context preview strings and editor controls present.

**Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
bunx vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
```

Expected:

- failures for the missing preview/editor UI and missing guard strings

**Step 3: Write minimal implementation**

Do not touch the raw JSON behavior yet. Implement only enough test scaffolding and rendering seams to make the first assertions possible.

**Step 4: Run tests to verify partial progress**

Re-run the same vitest command.

Expected:

- some preview/editor assertions still fail until Tasks 2 and 3

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "test(chat): add research preview editor coverage"
```

### Task 2: Add Pure Helpers For Edit Sanitization And Reset Behavior

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/research-chat-context.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts`

**Step 1: Write the failing tests**

Add helper tests that prove:

- editable list fields strip empty entries on sanitize
- read-only identity fields stay unchanged during edit application
- reset restores the run-derived baseline
- the sanitized attached context remains compatible with `toChatResearchContext(...)`

Use concrete values such as:

```ts
const active = {
  attached_at: "2026-03-08T20:00:00Z",
  run_id: "run_123",
  query: "Battery recycling supply chain",
  question: "Battery recycling supply chain",
  outline: [{ title: "Overview" }],
  key_claims: [{ text: "Claim one" }],
  unresolved_questions: ["What changed in Europe?"],
  verification_summary: { unsupported_claim_count: 0 },
  source_trust_summary: { high_trust_count: 2 },
  research_url: "/research?run=run_123"
}
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
bunx vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts
```

Expected:

- failures for missing sanitize/apply/reset helpers

**Step 3: Write minimal implementation**

In `research-chat-context.ts` add pure helpers such as:

- `sanitizeAttachedResearchContext(...)`
- `applyAttachedResearchContextEdits(...)`
- `resetAttachedResearchContext(...)`

Keep editing narrow:

- editable: `question`, `outline`, `key_claims`, `unresolved_questions`, summary counts
- read-only: `run_id`, `query`, `research_url`, `attached_at`

**Step 4: Run tests to verify they pass**

Re-run the same vitest command.

Expected:

- helper tests pass

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  apps/packages/ui/src/components/Option/Playground/research-chat-context.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): add research preview edit helpers"
```

### Task 3: Track Active And Baseline Attached Context In Playground State

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/Playground.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`

**Step 1: Write the failing tests**

Extend the playground integration tests to prove:

- attaching a new completed run sets both active and baseline snapshots
- editing from the preview updates only the active snapshot
- reset restores from the baseline snapshot
- thread switch clears both active and baseline snapshots

**Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
bunx vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
```

Expected:

- failures showing missing baseline/reset state behavior

**Step 3: Write minimal implementation**

In `Playground.tsx`:

- keep the existing active attached context state
- add baseline run-derived attachment state
- set both when `Use in Chat` attaches a new run
- expose a callback for applying edited active context
- expose a callback for resetting from the baseline

**Step 4: Run tests to verify they pass**

Re-run the same vitest command.

Expected:

- playground integration tests pass for baseline/reset semantics

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  apps/packages/ui/src/components/Option/Playground/Playground.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): track research preview baseline state"
```

### Task 4: Extend The Raw Request Modal With Structured Research Editing

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`

**Step 1: Write the failing tests**

Add or extend integration tests that prove:

- the chip exposes a preview/edit action
- the raw request modal renders a structured `Attached Research Context` panel above the JSON
- `Apply` updates the composer-visible attachment
- `Reset to Attached Run` restores the baseline
- the modal hides the panel or shows a neutral state when no attachment exists

**Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
bunx vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
```

Expected:

- failures for missing chip action and missing structured editor panel

**Step 3: Write minimal implementation**

In `PlaygroundForm.tsx`:

- add local editor state initialized from active attached context
- render read-only identity fields
- render bounded editable fields
- add `Apply` and `Reset to Attached Run`
- keep raw JSON below the structured panel

In `AttachedResearchContextChip.tsx`:

- add a `Preview` or `Edit` action that opens the existing raw request modal

**Step 4: Run tests to verify they pass**

Re-run the same vitest command.

Expected:

- preview/editor integration tests pass

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/AttachedResearchContextChip.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): add research request preview editor"
```

### Task 5: Keep Raw Request Preview Honest For Suppressed Flows

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx`

**Step 1: Write the failing tests**

Add or extend tests that prove:

- when the current preview path is image-command or compare-mode, the structured panel indicates the attachment is active but suppressed for this request
- the raw JSON preview omits `research_context`
- standard text preview still includes the updated `research_context`

**Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
bunx vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx
```

Expected:

- failures for missing suppression messaging or inconsistent preview behavior

**Step 3: Write minimal implementation**

In `PlaygroundForm.tsx`:

- detect when the current preview path suppresses `research_context`
- surface a small inline note in the structured panel
- keep `Refresh` using the latest active attached context

Do not change the existing suppression semantics for outbound requests.

**Step 4: Run tests to verify they pass**

Re-run the same vitest command.

Expected:

- preview suppression tests pass

**Step 5: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "feat(chat): clarify suppressed research preview state"
```

### Task 6: Final Verification And Plan Closure

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr/Docs/Plans/2026-03-08-deep-research-chat-request-preview-debug-implementation-plan.md`

**Step 1: Run focused frontend verification**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
bunx vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/research-chat-context.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx
```

Expected:

- all targeted tests pass

**Step 2: Run broader adjacent regression coverage**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr
bunx vitest run \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.research-context.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-use-in-chat.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundChat.research-status.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.search.integration.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.signals.guard.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx \
  apps/packages/ui/src/services/__tests__/tldw-chat.message-sanitization.test.ts
```

Expected:

- all adjacent research-context and playground tests pass

**Step 3: Update plan status**

Mark each task complete and record any deviations or follow-ups directly in this plan file.

**Step 4: Commit**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr add \
  Docs/Plans/2026-03-08-deep-research-chat-request-preview-debug-implementation-plan.md
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/deep-research-collecting-dev-pr commit -m "docs(research): finalize chat request preview debug plan"
```
