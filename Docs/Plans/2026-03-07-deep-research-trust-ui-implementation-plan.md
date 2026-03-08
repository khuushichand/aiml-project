# Deep Research Trust UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Surface deep-research trust outputs in the existing `/research` run console with read-only verification, unsupported-claim, contradiction, and source-trust panels.

**Architecture:** Keep this slice frontend-only. Extend the research client types in `apps/tldw-frontend/lib/api/researchRuns.ts`, then add one normalized trust-view path in `apps/tldw-frontend/pages/research.tsx` that renders from loaded bundle data first and lazily fetches trust artifacts only when needed.

**Tech Stack:** React, Next.js pages router, `@tanstack/react-query`, existing research API client, existing research run console reducer, Vitest, Testing Library.

---

### Task 1: Extend Frontend Trust Types

**Files:**
- Modify: `apps/tldw-frontend/lib/api/researchRuns.ts`
- Test: `apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx`

**Step 1: Write the failing test**

Add or update a page-level fixture in `research-run-console.test.tsx` that includes trust fields in a loaded bundle payload and expects the page to render from typed trust data instead of generic bundle JSON.

Example assertion shape:

```ts
expect(screen.getByText('Supported claims: 2')).toBeInTheDocument()
expect(screen.getByText('metadata_excerpt')).toBeInTheDocument()
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx`

Expected: FAIL because trust types and render paths are not defined yet.

**Step 3: Write minimal implementation**

In `researchRuns.ts`, add explicit types for:

- `ResearchVerificationSummary`
- `ResearchUnsupportedClaim`
- `ResearchContradiction`
- `ResearchSourceTrust`

Also add a typed bundle trust shape suitable for the page to consume.

Do not change backend requests in this task.

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx`

Expected: PASS for the new typed fixture path or fail for the next missing UI behavior.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/lib/api/researchRuns.ts apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx
git commit -m "feat(frontend): add research trust view types"
```

### Task 2: Add Failing Trust Console Tests

**Files:**
- Modify: `apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx`

**Step 1: Write the failing tests**

Add focused page tests for:

- empty trust state before synthesis
- trust rendering from a completed bundle
- lazy trust artifact loading when bundle is not loaded
- unsupported-claim rendering
- contradiction rendering
- source-trust rendering

Use the existing mocked research client seam.

Example assertions:

```ts
expect(screen.getByText('Trust signals will appear after synthesis')).toBeInTheDocument()
await user.click(screen.getByRole('button', { name: 'Load trust details' }))
expect(mocks.getResearchArtifact).toHaveBeenCalledWith('rs_1', 'verification_summary.json')
```

**Step 2: Run tests to verify they fail**

Run: `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx`

Expected: FAIL because the trust section and lazy-load behavior do not exist yet.

**Step 3: Write minimal implementation**

Do not implement yet. Stop after the tests fail for the expected trust-UI reasons.

**Step 4: Commit**

Do not commit in red state.

### Task 3: Implement Trust Normalization And Rendering

**Files:**
- Modify: `apps/tldw-frontend/pages/research.tsx`
- Modify: `apps/tldw-frontend/lib/api/researchRuns.ts`
- Test: `apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx`

**Step 1: Write minimal implementation**

In `research.tsx`:

- add a small normalization helper that derives one trust view from:
  - `state.bundle`, or
  - lazy-loaded trust artifacts in `state.artifactContents`
- add a `Research Trust` section below checkpoints and above the raw artifact list
- render:
  - verification summary
  - unsupported claims
  - contradictions
  - source trust
- add a `Load trust details` button when trust data is not yet loaded but should be fetchable
- lazy-load:
  - `verification_summary.json`
  - `unsupported_claims.json`
  - `contradictions.json`
  - `source_trust.json`

Use compact read-only rendering. Do not add mutating actions.

**Step 2: Run tests to verify they pass**

Run: `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx`

Expected: PASS

**Step 3: Refactor carefully**

If the page grows unwieldy:

- extract tiny render helpers inside `research.tsx`
- do not create a new component tree unless the tests become hard to follow

Keep behavior identical while simplifying the page code.

**Step 4: Re-run tests**

Run: `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add apps/tldw-frontend/pages/research.tsx apps/tldw-frontend/lib/api/researchRuns.ts apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx
git commit -m "feat(frontend): surface research trust signals"
```

### Task 4: Run Focused Verification And Finish

**Files:**
- Modify: `Docs/Plans/2026-03-07-deep-research-trust-ui-implementation-plan.md`

**Step 1: Run the focused frontend suite**

Run: `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx`

Expected: PASS

**Step 2: Run the broader research console frontend subset**

Run: `cd apps/tldw-frontend && bunx vitest run __tests__/pages/research-run-console.test.tsx __tests__/navigation/landing-layout.test.tsx __tests__/pages/researchers-page.test.tsx`

Expected: PASS with no regressions to nearby research/discovery surfaces.

**Step 3: Record verification in this plan**

Update the task statuses and append the verification commands that were actually run.

**Step 4: Commit**

```bash
git add Docs/Plans/2026-03-07-deep-research-trust-ui-implementation-plan.md
git commit -m "docs(research): finalize trust ui implementation plan"
```

## Notes

- This slice intentionally does not change backend APIs.
- Bandit is not applicable unless Python files are touched during implementation.
- If bundle and artifact trust shapes drift during implementation, normalize them in one helper rather than branching the rendering logic throughout the page.
