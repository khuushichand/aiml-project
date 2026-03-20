# PR 920 Review Follow-Ups Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the remaining valid PR `#920` review comments with targeted fixes, regression coverage, and verification.

**Architecture:** Keep the changes localized to the public/private boundary checker, its test module, and one focused Playground hook regression test. Avoid widening the underlying refactor; reply to GitHub threads only after the branch state and test results support the response.

**Tech Stack:** Python, pytest, React, Vitest, Testing Library, GitHub CLI

---

### Task 1: Document The Approved Scope

**Files:**
- Create: `Docs/Plans/2026-03-19-pr-920-review-followups-design.md`
- Create: `Docs/Plans/2026-03-19-pr-920-review-followups-implementation-plan.md`

**Step 1: Save the design**

Write the approved scope, non-goals, approach, and verification steps.

**Step 2: Save the implementation plan**

Document the execution sequence below before changing code.

**Step 3: Verify files exist**

Run: `ls Docs/Plans/2026-03-19-pr-920-review-followups-*.md`
Expected: both files are listed

**Status:** Complete

### Task 2: Add Red Tests For Boundary Checker Gaps

**Files:**
- Modify: `tldw_Server_API/tests/test_public_private_boundary.py`
- Test: `tldw_Server_API/tests/test_public_private_boundary.py`

**Step 1: Add a module docstring**

Describe the public/private boundary policy enforced by the test module.

**Step 2: Add focused unit tests**

Add tests that load `Helper_Scripts/docs/check_public_private_boundary.py` and verify:
- `.example`, `Dockerfile.*`, and `Caddyfile*` files are scanned
- denylist matching catches real references but not larger-token false positives

**Step 3: Run the targeted tests to verify RED**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -q`
Expected: FAIL because the current checker does not yet satisfy the new unit tests

**Status:** Not Started

### Task 3: Fix The Boundary Checker

**Files:**
- Modify: `Helper_Scripts/docs/check_public_private_boundary.py`
- Test: `tldw_Server_API/tests/test_public_private_boundary.py`

**Step 1: Add missing function docstrings**

Document `_iter_candidate_files()`, `_should_skip()`, `_find_violations()`, and `main()`.

**Step 2: Add explicit candidate-file classification**

Implement a helper that includes:
- the existing text suffixes
- `.example`
- `Dockerfile*`
- `Caddyfile*`

**Step 3: Replace raw substring matching**

Use regex-based matching that preserves import/path-prefix detection while avoiding obvious embedded-token false positives.

**Step 4: Run the targeted tests to verify GREEN**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -q`
Expected: PASS

**Status:** Not Started

### Task 4: Add Playground Attachment Regression Coverage

**Files:**
- Create: `apps/packages/ui/src/components/Option/Playground/hooks/__tests__/usePlaygroundAttachments.test.ts`
- Test: `apps/packages/ui/src/components/Option/Playground/hooks/__tests__/usePlaygroundAttachments.test.ts`

**Step 1: Add a hook-level regression test**

Verify repeated selection of the same file still triggers the upload path because the native file input value is cleared after each change event.

**Step 2: Run the targeted test**

Run: `bunx vitest run apps/packages/ui/src/components/Option/Playground/hooks/__tests__/usePlaygroundAttachments.test.ts`
Expected: PASS

**Status:** Not Started

### Task 5: Verify Security And Close Threads

**Files:**
- Modify: `Helper_Scripts/docs/check_public_private_boundary.py`
- Modify: `tldw_Server_API/tests/test_public_private_boundary.py`
- Create: `apps/packages/ui/src/components/Option/Playground/hooks/__tests__/usePlaygroundAttachments.test.ts`

**Step 1: Run Bandit on touched Python paths**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r Helper_Scripts/docs/check_public_private_boundary.py tldw_Server_API/tests/test_public_private_boundary.py -f json -o /tmp/bandit_pr920_review_followups.json`
Expected: JSON report written to `/tmp/bandit_pr920_review_followups.json` with no new actionable findings in touched code

**Step 2: Re-run targeted verification**

Run:
- `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/test_public_private_boundary.py -q`
- `bunx vitest run apps/packages/ui/src/components/Option/Playground/hooks/__tests__/usePlaygroundAttachments.test.ts`

Expected: PASS

**Step 3: Reply to and resolve GitHub review threads**

Use `gh api` replies for the open review comments and resolve the threads once the branch contains the fix or confirmed existing behavior.

**Status:** Not Started
