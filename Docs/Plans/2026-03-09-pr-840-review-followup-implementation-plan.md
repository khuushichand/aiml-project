# PR 840 Review Follow-Up Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Resolve the remaining actionable review feedback on PR #840 by syncing the branch with its current `dev` base, fixing any real remaining UI issue, and re-running focused verification.

**Architecture:** First update the branch against the current PR base so stale sandbox/admin review comments disappear from the diff if they have already landed on `dev`. Then use TDD on the remaining reading-pane navigation behavior, keeping the fix local to the media-review components and tests. Finish with targeted UI verification and scope-limited security checks only if backend files change during conflict resolution.

**Tech Stack:** Git, React, TypeScript, Vitest, Testing Library, Python Bandit (conditional)

---

### Task 1: Capture Current Review Scope

**Files:**
- Create: `Docs/Plans/2026-03-09-pr-840-review-followup-implementation-plan.md`
- Inspect: `apps/packages/ui/src/components/Review/MediaReviewReadingPane.tsx`
- Inspect: `apps/packages/ui/src/components/Review/ContentRenderer.tsx`
- Inspect: `apps/packages/ui/src/components/Review/SectionNavigator.tsx`

**Step 1: Confirm the branch and review-comment inventory**

Run: `git status --short --branch && git log --oneline --decorate -5`
Expected: clean PR worktree on `feat/media-review-three-panel-redesign` with the two existing review-fix commits visible.

**Step 2: Read the current reading-pane section navigation implementation**

Run: `sed -n '720,820p' apps/packages/ui/src/components/Review/MediaReviewReadingPane.tsx`
Expected: current implementation uses text/heading lookup and `scrollIntoView`, not character offsets.

**Step 3: Record the only still-actionable behavior to verify**

Behavior: selecting a section from `SectionNavigator` should scroll to the rendered heading/timestamp anchor in the reading pane.

### Task 2: Sync the PR Branch with Current `dev`

**Files:**
- Modify: merge state on current branch only

**Step 1: Merge the latest `dev` into the PR branch**

Run: `git merge origin/dev`
Expected: merge commit created cleanly, or conflicts reported in files that overlap with this PR.

**Step 2: Resolve conflicts minimally**

Rule: keep the media-review redesign behavior from this branch, accept `dev` for unrelated sandbox/admin/docs files unless the PR still requires branch-specific edits.

**Step 3: Verify the post-merge diff**

Run: `git diff --stat origin/dev...HEAD`
Expected: only files that still belong to the PR remain in the diff; stale sandbox/admin-only diffs should disappear if they were already merged to `dev`.

### Task 3: Add the Failing Regression Test First

**Files:**
- Modify: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage7.three-panel.test.tsx`
- Modify: `apps/packages/ui/src/components/Review/MediaReviewReadingPane.tsx`
- Optional Modify: `apps/packages/ui/src/components/Review/ContentRenderer.tsx`

**Step 1: Write a failing test for section navigation**

Test behavior:
- Render a reading pane with markdown headings or transcript sections.
- Open the section navigator.
- Select a section.
- Assert the corresponding rendered element receives `scrollIntoView`.

**Step 2: Run only that test and watch it fail**

Run: `source .venv/bin/activate && bunx vitest run apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage7.three-panel.test.tsx -t "section navigator scrolls to rendered anchors"`
Expected: FAIL for the new test before implementation changes.

### Task 4: Implement the Minimal Fix

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewReadingPane.tsx`
- Optional Modify: `apps/packages/ui/src/components/Review/ContentRenderer.tsx`

**Step 1: Implement stable anchor lookup for section navigation**

Preferred approach:
- Use actual rendered DOM anchors or deterministic query targets.
- Avoid character-offset-to-pixel math.
- Keep the fix scoped to the reading pane/content renderer.

**Step 2: Re-run the targeted test**

Run: `source .venv/bin/activate && bunx vitest run apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage7.three-panel.test.tsx -t "section navigator scrolls to rendered anchors"`
Expected: PASS.

### Task 5: Verify Review Fixes End-to-End

**Files:**
- Verify: `apps/packages/ui/src/components/Review/hooks/useMediaReviewActions.tsx`
- Verify: `apps/packages/ui/src/components/Review/hooks/useMediaReviewKeyboard.ts`
- Verify: `apps/packages/ui/src/components/Review/hooks/useSyncedScroll.ts`
- Verify: `apps/packages/ui/src/components/Review/interaction-context.ts`
- Verify: `apps/packages/ui/src/components/Review/MediaReviewReadingPane.tsx`

**Step 1: Run focused media-review tests**

Run: `source .venv/bin/activate && bunx vitest run apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage1.selectionLimit.test.tsx apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.keyboard-scope.test.tsx apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage7.three-panel.test.tsx apps/packages/ui/src/components/Review/__tests__/ComparisonSplit.test.tsx`
Expected: all targeted tests pass.

**Step 2: Run Bandit only if backend files changed during merge/conflict resolution**

Run: `source .venv/bin/activate && python -m bandit -r <touched_backend_paths> -f json -o /tmp/bandit_pr840_review_followup.json`
Expected: no new findings in touched backend scope.

**Step 3: Inspect final diff**

Run: `git status --short && git diff --stat`
Expected: only intentional PR review-follow-up changes remain.
