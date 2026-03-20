# KnowledgeQA Blank Answer And Note Filter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent KnowledgeQA from rendering a blank `AI Answer` shell when the backend returns whitespace-only answer content, and restore correct note-specific source filtering by propagating note UUIDs instead of numeric placeholders.

**Architecture:** Fix the UI contract at the boundary where KnowledgeQA normalizes RAG responses so whitespace-only answers are treated as absent, then align the frontend note-filter types and picker normalization with the backend schema. Add focused regression tests at the provider, panel, and end-to-end contract layers so the bug cannot silently reappear.

**Tech Stack:** React, TypeScript, Vitest, Playwright, FastAPI schema contracts

---

### Task 1: Lock In The Blank-Answer Failure With Tests

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx`

**Step 1: Write the failing tests**

Add one `AnswerPanel` test that sets `state.answer = "   "` and `state.results = [{...}]`, then asserts the blank `AI Answer` card does not render and the no-answer guidance renders instead.

Add one `KnowledgeQAProvider` test that mocks `/api/v1/rag/search` to return `answer: "   "` plus one result, then asserts `latestContext.answer` becomes `null` and the search still completes with results.

**Step 2: Run tests to verify they fail**

Run:

```bash
bunx vitest run src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx
```

Expected: the new whitespace-answer assertions fail against current behavior.

**Step 3: Keep the failing assertions minimal**

Do not add implementation in this step. Adjust only the test fixtures if needed so the failure is specifically about whitespace answers, not unrelated mocks.

**Step 4: Re-run the same tests**

Run:

```bash
bunx vitest run src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx
```

Expected: still failing for the intended reason.

**Step 5: Commit**

Do not commit yet. Combine with the matching implementation in Task 2.

### Task 2: Normalize Blank Answers At The KnowledgeQA Boundary

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx`

**Step 1: Implement minimal response normalization**

In `extractRagResponse`, trim `generated_answer` / `answer` / `response` candidates and return `null` when the best candidate is empty after trimming.

Keep the normalization local to KnowledgeQA first so the regression is fixed without changing unrelated consumers.

**Step 2: Keep rendering behavior aligned**

Do not add a new blank-answer UI branch in `AnswerPanel`. The existing `if (!answer)` branch should become correct automatically once the provider stores `null` instead of whitespace.

**Step 3: Run the focused tests**

Run:

```bash
bunx vitest run src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx
```

Expected: the new whitespace-answer tests pass.

**Step 4: Self-review for collateral effects**

Check that persistence, history, and citation parsing still use `null` for missing answers and do not require an additional code change.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx
git commit -m "fix: normalize blank KnowledgeQA answers"
```

### Task 3: Lock In Note UUID Source Filters With Tests

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`

**Step 1: Write the failing tests**

Update the existing pinned-source-filter test so it expects UUID note IDs to be preserved end to end.

Add or adjust a layout/static test so `include_note_ids` is modeled as string IDs, not numbers.

**Step 2: Run the focused tests to verify failure**

Run:

```bash
bunx vitest run src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
```

Expected: failure because the current implementation still produces numeric note IDs.

**Step 3: Keep the test data realistic**

Use UUID-like strings such as `note-base-uuid` and `note-pinned-uuid` rather than integers.

**Step 4: Re-run to confirm the same failure**

Run the same command again if you had to adjust the fixtures.

**Step 5: Commit**

Do not commit yet. Combine with the implementation in Task 4.

### Task 4: Propagate Note UUIDs Through The KnowledgeQA Source Picker

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/services/rag/unified-rag.ts`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/types.ts`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/context/KnowledgeContextBar.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/SettingsPanel/ExpertSettings.tsx`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`

**Step 1: Align the frontend types**

Change `RagSettings.include_note_ids` and KnowledgeQA note filter types from `number[]` to `string[]`.

Introduce or reuse a `mergeStringFilters` path for note IDs instead of `mergeNumberFilters`.

**Step 2: Fix note option normalization**

Update `normalizeNoteOptions` in `KnowledgeContextBar.tsx` to read note IDs as strings from `record.id` / `record.note_id`, preserve UUID values, and keep labels/meta unchanged.

**Step 3: Update the picker and layout plumbing**

Change `includeNoteIds`, `onIncludeNoteIdsChange`, selected note sets, and note toggle handlers to use strings consistently.

Update the expert settings type metadata so the UI no longer treats `include_note_ids` as numeric.

**Step 4: Run the focused tests**

Run:

```bash
bunx vitest run src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
```

Expected: the UUID note filter assertions pass.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/rag/unified-rag.ts apps/packages/ui/src/components/Option/KnowledgeQA/types.ts apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx apps/packages/ui/src/components/Option/KnowledgeQA/context/KnowledgeContextBar.tsx apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx apps/packages/ui/src/components/Option/KnowledgeQA/SettingsPanel/ExpertSettings.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
git commit -m "fix: use note UUIDs in KnowledgeQA source filters"
```

### Task 5: Strengthen End-To-End Coverage And Final Verification

**Status:** Complete

**Files:**
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/KnowledgeQAPage.ts`
- Modify: `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`
- Test: `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`

**Step 1: Tighten the page-object contract**

Update `getAnswerText()` to read `data-testid="knowledge-answer-content"` instead of broad container selectors, so header-only `AI Answer` shells cannot satisfy the workflow checks.

**Step 2: Add a deterministic blank-answer regression**

In the workflow spec, stub `/api/v1/rag/search` to return one result plus `answer: "   "`, then assert the UI shows the no-answer guidance instead of a blank answer body.

**Step 3: Run the focused UI tests**

Run:

```bash
bunx vitest run src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
```

If the frontend dev server and backend fixtures are available, also run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && bunx playwright test e2e/workflows/knowledge-qa.spec.ts --reporter=line
```

**Step 4: Run Bandit on touched backend scope if backend files changed**

For this plan, Bandit is only required if backend Python files are touched. If you end up modifying backend RAG normalization, run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r /Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/api/v1/endpoints/rag_unified.py /Users/macbook-dev/Documents/GitHub/tldw_server2/tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py -f json -o /tmp/bandit_knowledgeqa_blank_answer.json
```

**Step 5: Final verification**

Run:

```bash
bunx vitest run src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
```

Document any Playwright or backend-environment blockers explicitly in the final summary.
