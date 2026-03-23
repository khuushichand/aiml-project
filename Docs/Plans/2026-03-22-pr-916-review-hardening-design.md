# PR 916 Review Hardening Design

**Goal:** Close the remaining valid PR `#916` review findings and adjacent issues without widening the branch into an unrelated refactor.

## Verified Scope

This branch needs three kinds of remediation:

1. Backend correctness and security fixes that still appear valid in the current tree:
   - `DB_Deps` owner media DB lifecycle and shared-backend `:memory:` propagation
   - `users_repo` role-removal commit handling
   - `agent_orchestration` path handling flagged by code scanning
2. Frontend state-management and UX correctness fixes that still appear valid in the current tree:
   - hosted header shortcut filtering and duplicate shortcut IDs
   - Knowledge QA export dialog session isolation and reset behavior
   - stale Enter-submit handling, rerun scope hydration, copy teardown races
   - `TemplatePreview` memoized sanitization
   - watchlists keyboard E2E nullish fallback cleanup
3. Workflow/package/docs hardening that is still justified:
   - immutable action pinning in `sbom.yml`
   - bounded peer dependency ranges in `apps/packages/ui/package.json`
   - changelog/backfill wording cleanup
   - compose warnings for default credentials

## Non-Goals

- No attempt to rewrite the entire PR diff or normalize all pre-existing plan/docs churn in the branch.
- No changes to review comments that are already obsolete in current code beyond replying in GitHub later.
- No speculative product behavior changes outside the files already implicated by review findings or tightly adjacent defects.

## Approach

### Backend

Keep the backend changes explicit and test-backed:

- Add regression coverage around media DB owner access and shared-backend RAG wiring before changing implementation.
- Remove silent failure handling where role-removal commits can be lost.
- Prefer narrow fixes over new abstractions, except where a context manager is the simplest way to guarantee media DB cleanup.
- Inspect the path-handling code scanner finding directly and harden the path join/validation only if the current code still trusts user-controlled path segments.

### Frontend

Treat the current comments as bug reports and verify each against the live code:

- Add or extend targeted Vitest coverage before behavior changes.
- Fix hosted header shortcut visibility and persistence collisions with the smallest settings-compatible change.
- Make dialog/request session keys unique per open lifecycle so stale async completions cannot mutate a reopened dialog.
- Reset thread-bound export state when the active thread changes while the dialog remains open.
- Ensure async clipboard flows cannot update unmounted components.
- Prevent stale suggestion Enter presses from falling through to form submit.
- Memoize expensive sanitization work that currently reruns on unrelated state changes.

### Workflows, Packages, and Docs

Apply only changes that are clearly net-positive and low-risk:

- Pin mutable action references when the repo already uses immutable SHA pinning elsewhere.
- Cap peer dependency major ranges where the review correctly identified open-ended upgrade risk.
- Keep changelog and compose/doc updates narrow and explanatory.

## Verification

- Targeted `pytest` for backend paths touched by DB and orchestration fixes
- Targeted `vitest` and Playwright test execution for touched frontend paths
- `bandit` on the touched Python files before claiming completion
- Manual inventory of PR review comments afterward so GitHub replies distinguish fixed issues from obsolete threads
