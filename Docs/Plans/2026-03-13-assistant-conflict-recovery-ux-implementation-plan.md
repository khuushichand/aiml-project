# Assistant Conflict Recovery UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make flashcard and quiz assistant threads recover gracefully from `409` version conflicts by reloading the latest thread, preserving the failed request, and offering explicit retry actions.

**Architecture:** Keep the backend contract unchanged. Add conflict recovery state to the shared `FlashcardStudyAssistantPanel`, pass query `refetch` handlers from the flashcards and quiz surfaces, and prove the behavior with end-to-end UI tests on both surfaces.

**Tech Stack:** React, TanStack Query, Vitest, Ant Design, existing flashcards/quizzes assistant hooks

---

### Task 1: Add failing flashcard-assistant conflict tests

**Files:**
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx`

**Step 1: Write the failing tests**

Add tests that prove:
- a `409` assistant send refetches context and shows a conflict-specific banner
- `Retry my message` resends the preserved request
- transcript fact-check conflicts use a transcript-specific retry label and preserve the transcript payload

**Step 2: Run the tests to verify they fail**

Run:

```bash
bunx vitest run src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx
```

Expected: the new conflict-recovery assertions fail because the panel only shows the generic unavailable state.

**Step 3: Commit the failing-test checkpoint**

```bash
git add apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx
git commit -m "test(flashcards): add assistant conflict recovery coverage"
```

### Task 2: Implement shared assistant conflict recovery in the panel

**Files:**
- Modify: `apps/packages/ui/src/components/Flashcards/components/FlashcardStudyAssistantPanel.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx`

**Step 1: Add the minimal panel API and conflict state**

Extend the panel with:
- `onReloadContext: () => Promise<unknown>`
- local conflict state for the pending request and reload status
- helpers to detect `409` responses

**Step 2: Implement the minimal conflict UX**

When `onRespond` throws a `409`:
- store the failed `StudyAssistantRespondRequest`
- call `onReloadContext`
- render the conflict banner and recovery buttons

Keep non-409 errors on the existing generic error path.

**Step 3: Wire the flashcard review surface**

Pass `assistantQuery.refetch` from `ReviewTab` into the panel.

**Step 4: Run the flashcard tests**

Run:

```bash
bunx vitest run src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx
```

Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Flashcards/components/FlashcardStudyAssistantPanel.tsx apps/packages/ui/src/components/Flashcards/tabs/ReviewTab.tsx apps/packages/ui/src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx
git commit -m "fix(flashcards): recover assistant threads after conflict"
```

### Task 3: Add failing quiz-remediation conflict tests

**Files:**
- Modify: `apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx`

**Step 1: Write the failing tests**

Add tests that prove:
- remediation assistant `409` keeps the active question in place
- the panel reloads the latest thread and shows conflict recovery actions
- `Reload latest` clears the pending request without resending

**Step 2: Run the tests to verify they fail**

Run:

```bash
bunx vitest run src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
```

Expected: FAIL because the remediation flow still treats the conflict like a generic assistant failure.

**Step 3: Commit the failing-test checkpoint**

```bash
git add apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
git commit -m "test(quiz): add remediation assistant conflict coverage"
```

### Task 4: Wire quiz remediation into the shared recovery path

**Files:**
- Modify: `apps/packages/ui/src/components/Quiz/components/QuizRemediationPanel.tsx`
- Modify: `apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts`

**Step 1: Pass context reload to the shared panel**

Use `assistantQuery.refetch` in `QuizRemediationPanel` and pass it to `FlashcardStudyAssistantPanel`.

**Step 2: Keep mutation behavior compatible with conflict retry**

Do not rewrite the mutation flow. Preserve the existing hook behavior where it pulls `expected_thread_version` from the refreshed query cache. Only make sure the query refetch path is reachable and clean.

**Step 3: Run the quiz remediation tests**

Run:

```bash
bunx vitest run src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
```

Expected: PASS

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Quiz/components/QuizRemediationPanel.tsx apps/packages/ui/src/components/Quiz/hooks/useQuizQueries.ts apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
git commit -m "fix(quiz): recover remediation assistant conflicts"
```

### Task 5: Run the focused regression matrix

**Files:**
- Verify only

**Step 1: Run the focused matrix**

Run:

```bash
bunx vitest run \
  src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx \
  src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx \
  src/components/Flashcards/tabs/__tests__/SchedulerTab.editor.test.tsx
```

Expected: PASS

**Step 2: Run an adjacent spot-check**

Run:

```bash
bunx vitest run \
  src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx \
  src/components/Quiz/tabs/__tests__/ResultsTab.details.test.tsx
```

Expected: PASS

**Step 3: Check formatting cleanliness**

Run:

```bash
git diff --check
```

Expected: no output

**Step 4: Commit any follow-up fixes**

```bash
git add <touched files>
git commit -m "test(ui): verify assistant conflict recovery slice"
```

### Task 6: Update docs

**Files:**
- Modify: `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md`

**Step 1: Document the new recovery behavior**

Add a short note that assistant conflicts reload the latest thread and offer retry instead of failing generically.

**Step 2: Run a focused docs/link sanity check**

Run:

```bash
bunx vitest run src/components/Flashcards/constants/__tests__/help-links.test.ts
```

Expected: PASS

**Step 3: Commit**

```bash
git add Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md
git commit -m "docs(flashcards): document assistant conflict recovery"
```
