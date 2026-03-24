# PR 916 Review Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the remaining valid PR `#916` review findings with targeted fixes, regression coverage, and verification from an isolated worktree.

**Architecture:** Split the work into backend correctness/security, frontend state-management and UX hardening, and low-risk workflow/package/doc cleanup. For code changes, write or extend focused failing tests first, then implement the minimal production change that makes those tests pass.

**Tech Stack:** Python, pytest, FastAPI, TypeScript, React, Vitest, Playwright, GitHub Actions YAML, Bandit

---

### Task 1: Document The Approved Scope

**Files:**
- Create: `Docs/Plans/2026-03-22-pr-916-review-hardening-design.md`
- Create: `Docs/Plans/2026-03-22-pr-916-review-hardening-implementation-plan.md`

**Step 1: Save the design**

Write the approved scope, non-goals, implementation approach, and verification plan.

**Step 2: Save the implementation plan**

Document the execution sequence below before changing code.

**Step 3: Verify the docs exist**

Run: `ls Docs/Plans/2026-03-22-pr-916-review-hardening-*.md`
Expected: both files are listed

**Status:** Complete

### Task 2: Add Red Tests For Backend Review Findings

**Files:**
- Modify: `tldw_Server_API/tests/...` relevant DB deps, sharing, AuthNZ, and orchestration test modules
- Modify: `tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/users_repo.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/agent_orchestration.py`
- Modify: any directly implicated sharing/RAG modules if the tests prove they still need changes

**Step 1: Identify the narrowest existing test modules**

Use existing AuthNZ, DB deps, sharing, and orchestration tests instead of creating broad new suites.

**Step 2: Write failing tests for still-valid backend issues**

Cover:
- owner media DB cleanup is guaranteed
- shared-backend owner media access does not route RAG through a bogus SQLite `:memory:` path
- role-removal commit failures are not silently suppressed
- any still-valid path traversal/path-expression issue in `agent_orchestration`

**Step 3: Run the targeted tests to verify RED**

Run the narrow `pytest` selectors for the new/updated tests.
Expected: FAIL for the intended missing or incorrect behavior

**Status:** Complete

### Task 3: Implement And Verify Backend Fixes

**Files:**
- Modify: `tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/repos/users_repo.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/agent_orchestration.py`
- Modify: sharing/RAG files only if still required by the failing tests

**Step 1: Fix owner media DB lifecycle**

Guarantee release of context-bound DB connections for non-dependency owner access.

**Step 2: Fix shared-backend RAG path propagation**

Ensure shared/Postgres-backed media access does not fall back into SQLite `:memory:` retrieval paths.

**Step 3: Remove silent commit suppression**

Handle commit failures deterministically in role removal.

**Step 4: Harden path handling if the scanner finding is still valid**

Constrain user-controlled path components to safe repository-relative or sandbox-approved locations.

**Step 5: Re-run the targeted backend tests**

Expected: PASS

**Status:** Complete

### Task 4: Add Red Tests For Frontend Review Findings

**Files:**
- Modify: targeted test files under `apps/packages/ui/src/components/.../__tests__/`
- Modify: `apps/extension/tests/e2e/watchlists.spec.ts` if the behavior is only covered there
- Modify: `apps/packages/ui/src/components/Layouts/header-shortcut-items.ts`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/*.tsx`
- Modify: `apps/packages/ui/src/components/Option/Collections/Templates/TemplatePreview.tsx`

**Step 1: Add or extend targeted frontend tests**

Cover:
- hosted chat shortcut visibility and unique shortcut preference IDs
- unique export-dialog session keys and thread-change state reset
- stale Enter key handling in Knowledge QA suggestions
- restored-scope rerun behavior
- SourceCard teardown protection against async clipboard completion after unmount
- TemplatePreview sanitization memoization where practical

**Step 2: Update the watchlists E2E assertions**

Make the nullish-coalescing change in the E2E helper flow if the current code still uses `||` fallbacks.

**Step 3: Run targeted tests to verify RED**

Run the smallest relevant `vitest` selectors before changing production code.
Expected: FAIL for behavior tests; for pure syntax/narrow E2E assertion cleanup, verify the targeted test file currently contains the stale pattern before editing.

**Status:** Complete

### Task 5: Implement Frontend, Workflow, Package, And Doc Fixes

**Files:**
- Modify: `apps/packages/ui/src/components/Layouts/header-shortcut-items.ts`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/ExportDialog.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/SearchBar.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/SourceCard.tsx`
- Modify: `apps/packages/ui/src/components/Option/Collections/Templates/TemplatePreview.tsx`
- Modify: `apps/extension/tests/e2e/watchlists.spec.ts`
- Modify: `.github/workflows/frontend-required.yml`
- Modify: `.github/workflows/sbom.yml`
- Modify: `apps/packages/ui/package.json`
- Modify: `Dockerfiles/docker-compose.host-storage.yml`
- Modify: `CHANGELOG.md`
- Modify: other current-head files only if a verified adjacent issue requires it

**Step 1: Implement the minimal frontend fixes**

Keep changes localized to the reviewed components and settings helpers.

**Step 2: Apply low-risk workflow/package/doc hardening**

Pin mutable actions, bound peer dependency majors, and tighten docs/comments where the review is still correct.

**Step 3: Re-run targeted frontend verification**

Run the touched `vitest` selectors and any narrow Playwright command needed for watchlists/family guardrails.
Expected: PASS

**Status:** Complete

### Task 6: Security Verification And Review-Thread Inventory

**Files:**
- Modify: all touched files above

**Step 1: Run Bandit on touched Python paths**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/API_Deps/DB_Deps.py tldw_Server_API/app/core/AuthNZ/repos/users_repo.py tldw_Server_API/app/api/v1/endpoints/agent_orchestration.py -f json -o /tmp/bandit_pr916_review_hardening.json`
Expected: JSON report written with no new actionable findings in touched code

**Step 2: Re-run the targeted test set**

Run the final `pytest`/`vitest` commands that cover all touched code.
Expected: PASS

**Step 3: Prepare GitHub thread responses**

Classify review comments as:
- fixed in branch
- already obsolete in current head
- intentionally not changed with technical justification

**Status:** In Progress
