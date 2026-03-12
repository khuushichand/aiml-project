# PR 866 Review Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Address every active review thread on PR #866 by fixing the remaining correctness gaps, preserving the already-landed readability refactors, and replying on each GitHub thread with the final disposition.

**Architecture:** Add narrow regression coverage around the reviewed document-workspace hooks/components, then make the smallest code changes needed to align runtime behavior with the review requirements. Keep the fixes localized to the document workspace UI package and reuse the already-added shared BibTeX utility rather than introducing more abstractions.

**Tech Stack:** React 18, Zustand, TanStack Query, Dexie, Vitest, Testing Library

---

## Stage 1: Map Threads To Concrete Changes
**Goal:** Confirm which review comments still require code changes versus verification/reply only.
**Success Criteria:** Each of the six review threads is mapped to a file/test action.
**Tests:** None.
**Status:** Complete

### Task 1: Capture the active thread map

**Files:**
- Reference: `apps/packages/ui/src/hooks/document-workspace/useResizablePanel.ts`
- Reference: `apps/packages/ui/src/hooks/document-workspace/usePdfSearch.ts`
- Reference: `apps/packages/ui/src/hooks/document-workspace/useDocumentQuiz.ts`
- Reference: `apps/packages/ui/src/components/DocumentWorkspace/RightPanel/QuizPanel.tsx`
- Reference: `apps/packages/ui/src/hooks/document-workspace/useDocumentTTS.ts`
- Reference: `apps/packages/ui/src/components/DocumentWorkspace/DocumentViewer/PdfSearch.tsx`
- Reference: `apps/packages/ui/src/components/DocumentWorkspace/LeftSidebar/ReferencesTab.tsx`
- Reference: `apps/packages/ui/src/hooks/document-workspace/useCitation.ts`

**Step 1: Verify current branch state against the six review threads**

Run: `gh api repos/rmusser01/tldw_server/pulls/866/comments --paginate`
Expected: Six actionable inline comments, with the Gemini readability comments already reflected in the current branch.

**Step 2: Record remaining code work**

Expected:
- `useResizablePanel.ts`: verify left-edge dragging and fix stale `edge` dependency if needed.
- `usePdfSearch.ts`: verify search/highlight option parity with tests.
- `useDocumentQuiz.ts` and `QuizPanel.tsx`: make resume persistence actually controlled and durable.
- `useDocumentTTS.ts`: verify storage reads are guarded.
- `ReferencesTab.tsx`, `PdfSearch.tsx`, `useCitation.ts`: verify existing refactors and reply in-thread.

## Stage 2: Add Failing Regression Tests
**Goal:** Lock in the reviewed behavior before changing implementation.
**Success Criteria:** New tests fail for the unfixed cases and cover the already-fixed behaviors.
**Tests:** Targeted `vitest run` commands listed below.
**Status:** Complete

### Task 2: Add hook tests for resize direction and TTS storage safety

**Files:**
- Create: `apps/packages/ui/src/hooks/document-workspace/__tests__/useResizablePanel.test.tsx`
- Create: `apps/packages/ui/src/hooks/document-workspace/__tests__/useDocumentTTS.test.tsx`
- Modify: `apps/packages/ui/src/hooks/document-workspace/useResizablePanel.ts`
- Modify: `apps/packages/ui/src/hooks/document-workspace/useDocumentTTS.ts`

**Step 1: Write the failing resize-direction test**

Cover:
- Right-edge handle grows with positive drag.
- Left-edge handle shrinks with positive drag and grows with negative drag.

**Step 2: Run the resize test to verify the reviewed behavior fails if `edge` handling regresses**

Run: `bunx vitest run apps/packages/ui/src/hooks/document-workspace/__tests__/useResizablePanel.test.tsx`
Expected: Fails if left-edge drag math or dependency wiring is wrong.

**Step 3: Write the failing TTS storage-safety test**

Cover:
- `localStorage.getItem` throwing for `tts-voice`, `tts-speed`, and `tts-volume` falls back to defaults.

**Step 4: Run the TTS test to verify the guard is meaningful**

Run: `bunx vitest run apps/packages/ui/src/hooks/document-workspace/__tests__/useDocumentTTS.test.tsx`
Expected: Fails if hook initialization still propagates storage errors.

### Task 3: Add search and quiz regression tests

**Files:**
- Create: `apps/packages/ui/src/hooks/document-workspace/__tests__/usePdfSearch.test.tsx`
- Create: `apps/packages/ui/src/components/DocumentWorkspace/RightPanel/__tests__/QuizPanel.test.tsx`
- Modify: `apps/packages/ui/src/hooks/document-workspace/usePdfSearch.ts`
- Modify: `apps/packages/ui/src/components/DocumentWorkspace/RightPanel/QuizPanel.tsx`
- Modify: `apps/packages/ui/src/hooks/document-workspace/useDocumentQuiz.ts`

**Step 1: Write the failing PDF search parity test**

Cover:
- `matchCase` and `wordBoundary` produce the same match set for search results and highlighted spans.

**Step 2: Run the PDF search test to verify the mismatch is caught**

Run: `bunx vitest run apps/packages/ui/src/hooks/document-workspace/__tests__/usePdfSearch.test.tsx`
Expected: Fails if highlights disagree with results under search options.

**Step 3: Write the failing quiz resume test**

Cover:
- Saved history answers repopulate the rendered question state.
- Answer changes persist immediately through `persistAnswer`.
- Completed quizzes set `completedAt` and score.

**Step 4: Run the quiz test to verify the current resume flow is incomplete**

Run: `bunx vitest run apps/packages/ui/src/components/DocumentWorkspace/RightPanel/__tests__/QuizPanel.test.tsx`
Expected: Fails while `QuestionCard` keeps its own unsynced state or answer changes are not persisted.

## Stage 3: Implement Minimal Fixes
**Goal:** Make the new regression tests pass with the smallest localized changes.
**Success Criteria:** The remaining review issues are fixed without widening scope.
**Tests:** Re-run the targeted tests after each change.
**Status:** Complete

### Task 4: Finish the runtime fixes

**Files:**
- Modify: `apps/packages/ui/src/hooks/document-workspace/useResizablePanel.ts`
- Modify: `apps/packages/ui/src/hooks/document-workspace/usePdfSearch.ts`
- Modify: `apps/packages/ui/src/hooks/document-workspace/useDocumentQuiz.ts`
- Modify: `apps/packages/ui/src/components/DocumentWorkspace/RightPanel/QuizPanel.tsx`

**Step 1: Fix any resize-hook dependency or direction issues**

Expected implementation:
- Keep `edge`-aware delta math.
- Include `edge` in the drag listener effect dependencies.

**Step 2: Keep search regex logic shared between result discovery and highlighting**

Expected implementation:
- Reuse the same regex builder/match helper for both paths.

**Step 3: Make quiz answer state controlled from `QuizPanel`**

Expected implementation:
- Remove per-card answer ownership.
- Pass `answer`, `showAnswer`, and change/check/reset handlers from the panel.
- Persist answer changes through `persistAnswer`.
- Persist `completedAt`/score when all questions have answers.

**Step 4: Re-run the targeted tests**

Run: `bunx vitest run apps/packages/ui/src/hooks/document-workspace/__tests__/useResizablePanel.test.tsx apps/packages/ui/src/hooks/document-workspace/__tests__/usePdfSearch.test.tsx apps/packages/ui/src/hooks/document-workspace/__tests__/useDocumentTTS.test.tsx apps/packages/ui/src/components/DocumentWorkspace/RightPanel/__tests__/QuizPanel.test.tsx`
Expected: PASS.

## Stage 4: Verify, Scan, And Close Review Threads
**Goal:** Prove the fixes and respond on every review thread.
**Success Criteria:** Tests pass, Bandit is run on the touched scope, and each GitHub thread gets a concrete reply.
**Tests:** Targeted Vitest suite plus Bandit.
**Status:** Complete

### Task 5: Final verification and GitHub responses

**Files:**
- Modify: `docs/plans/2026-03-11-pr-866-review-fixes.md`

**Step 1: Run the targeted UI test suite**

Run: `bunx vitest run apps/packages/ui/src/hooks/document-workspace/__tests__/useResizablePanel.test.tsx apps/packages/ui/src/hooks/document-workspace/__tests__/usePdfSearch.test.tsx apps/packages/ui/src/hooks/document-workspace/__tests__/useDocumentTTS.test.tsx apps/packages/ui/src/components/DocumentWorkspace/RightPanel/__tests__/QuizPanel.test.tsx apps/packages/ui/src/components/DocumentWorkspace/LeftSidebar/__tests__/ReferencesTab.test.tsx`
Expected: PASS.

**Step 2: Run Bandit on the touched Python scope**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API -f json -o /tmp/bandit_pr866_review_fixes.json`
Expected: Completes successfully; report any findings that affect touched code. If no Python files are touched, record that Bandit was run per repository policy and that no touched Python scope exists.

**Step 3: Update this plan status**

Expected: Mark all stages `Complete` once verification succeeds.

**Step 4: Reply in every GitHub review thread**

Expected:
- Qodo bug threads: reply with the exact fix.
- Gemini readability/duplication threads: reply that the branch now uses `reduce`, extracted `handleExportBibTeX`, and shared `referenceToBibTeX`.
