# Deep Research Chat Launch Integration Implementation Plan

**Goal:** Launch deep research from chat through a shared frontend launch contract, while keeping the existing `/research` console as the canonical run-inspection surface.

**Architecture:** Keep this slice frontend-only. Add a shared research launch-path builder in the route-path helpers, teach `/research` to consume launch query params safely, and wire chat entry points to that helper without inventing a second research runtime.

**Tech Stack:** React, Next.js pages router, React Router, existing research API client, Vitest, Testing Library.

---

### Task 1: Add Red Tests For The Launch Contract And Entry Points

**Status:** Complete

**Files:**
- Add: `apps/packages/ui/src/routes/__tests__/route-paths.research.test.ts`
- Modify: `apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundEmpty.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx`

**Step 1: Add route helper tests**

Cover:
- `/research` base path export
- launch path with encoded `query`
- optional `source_policy`, `autonomy_mode`, `autorun`, and `from`
- omission of empty values

**Step 2: Add research page launch-param tests**

Cover:
- prefill from `?query=...`
- auto-create from `?query=...&autorun=1`
- replacement of transient launch params after auto-create

**Step 3: Add chat entry-point tests**

Cover:
- empty-state `Deep Research` starter navigates to `/research`
- composer toolbar can render a supplied `Deep Research` control in the actions row

**Step 4: Run tests to verify they fail**

Run:
- `cd apps/packages/ui && bunx vitest run src/routes/__tests__/route-paths.research.test.ts src/components/Option/Playground/__tests__/PlaygroundEmpty.test.tsx src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx`
- `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx`

Expected: FAIL for missing launch helper, missing research-page query-param handling, and missing chat entry points.

### Task 2: Implement Shared Launch Helper And Research Page Consumption

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/routes/route-paths.ts`
- Add or modify tests from Task 1
- Modify: `apps/tldw-frontend/pages/research.tsx`

**Step 1: Add the shared helper**

In `route-paths.ts`:
- export `RESEARCH_PATH = "/research"`
- add `buildResearchLaunchPath(...)`

The helper should support:
- `query`
- `sourcePolicy`
- `autonomyMode`
- `autorun`
- `from`
- `run`

**Step 2: Teach `/research` to consume launch params**

In `research.tsx`:
- read query params from `window.location.search` safely after mount
- prefill the question input from `query`
- auto-create a run once when `autorun=1` and `query` are present
- support selecting an existing run from `?run=...`
- replace transient launch params after auto-create so refreshes do not duplicate work

Keep:
- existing manual creation flow
- existing selected-run console behavior

**Step 3: Run focused research page tests**

Run:
- `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx`

Expected: PASS

### Task 3: Wire Chat Entry Points

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundEmpty.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/ComposerToolbar.tsx`
- Modify: related tests from Task 1

**Step 1: Add the empty-state handoff**

In `PlaygroundEmpty.tsx`:
- add a `Deep Research` starter card
- navigate to `/research`

**Step 2: Add the composer handoff**

In `PlaygroundForm.tsx`:
- create a compact `Deep Research` control using the shared launch helper
- if the draft message is non-empty, navigate to `/research?...&autorun=1`
- if the draft message is empty, navigate to plain `/research`

In `ComposerToolbar.tsx`:
- accept a pre-rendered research launch control prop
- place it in the actions row for mobile, casual, and pro layouts

**Step 3: Re-run chat-focused tests**

Run:
- `cd apps/packages/ui && bunx vitest run src/routes/__tests__/route-paths.research.test.ts src/components/Option/Playground/__tests__/PlaygroundEmpty.test.tsx src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx`

Expected: PASS

### Task 4: Focused Verification And Finish

**Status:** Complete

**Files:**
- Modify: `Docs/Plans/2026-03-07-deep-research-chat-launch-integration-implementation-plan.md`

**Step 1: Run focused frontend verification**

Run:
- `cd apps/packages/ui && bunx vitest run src/routes/__tests__/route-paths.research.test.ts src/components/Option/Playground/__tests__/PlaygroundEmpty.test.tsx src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx`
- `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx __tests__/pages/researchers-page.test.tsx __tests__/navigation/landing-layout.test.tsx`

Expected: PASS

**Step 2: Record verification results in this plan**

Update statuses and append the actual commands/results.

**Step 3: Commit**

```bash
git add apps/packages/ui/src/routes/route-paths.ts \
  apps/packages/ui/src/routes/__tests__/route-paths.research.test.ts \
  apps/packages/ui/src/components/Option/Playground/PlaygroundEmpty.tsx \
  apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx \
  apps/packages/ui/src/components/Option/Playground/ComposerToolbar.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundEmpty.test.tsx \
  apps/packages/ui/src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx \
  apps/tldw-frontend/pages/research.tsx \
  apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx
git commit -m "feat(frontend): launch deep research from chat"
```

Then:

```bash
git add Docs/Plans/2026-03-07-deep-research-chat-launch-integration-implementation-plan.md
git commit -m "docs(research): finalize chat launch integration plan"
```

## Notes

- This slice intentionally stops at chat launch/handoff. Workflow step integration is a later product-integration slice.
- No backend API changes are required for this slice.
- Bandit is not applicable unless Python files are touched.

## Verification Run

- `cd apps/packages/ui && bunx vitest run src/routes/__tests__/route-paths.research.test.ts src/components/Option/Playground/__tests__/PlaygroundEmpty.test.tsx src/components/Option/Playground/__tests__/ComposerToolbar.test.tsx`
  - Result: `25/25` tests passed
- `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx`
  - Result: `13/13` tests passed
- `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx __tests__/pages/researchers-page.test.tsx __tests__/navigation/landing-layout.test.tsx`
  - Result: `15/15` tests passed

## Outcome

- Added a shared `/research` launch-path helper for cross-surface handoffs.
- Added launch-param consumption on the research run console, including prefill, one-shot autorun, and transient launch-param cleanup.
- Added chat entry points for deep research from both the empty state and the composer toolbar.
