# PR 916 CI Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore PR #916 to a passing GitHub Actions state by reproducing and fixing the currently failing CI gates on the PR head.

**Architecture:** Work from an isolated worktree based on the PR head, reproduce each failing gate with the same commands CI uses, fix the smallest root causes first, and re-run the affected local checks before pushing. Prefer fixes that remove shared causes across multiple failing jobs.

**Tech Stack:** GitHub Actions, Python 3.12, pytest, compileall, pre-commit, Bun, Next.js, Playwright

---

## Stage 1: Reproduce Current Failures
**Goal**: Map every currently failing PR #916 check to a concrete local command and reproduce the backend and frontend failures.
**Success Criteria**: A short failure inventory exists, and the local worktree reproduces the actionable compile, lint, guard, or test failures.
**Tests**:
- `source .venv/bin/activate && python -m compileall tldw_Server_API/app`
- `source .venv/bin/activate && python Helper_Scripts/checks/guard_http_client_patching.py`
- `cd apps/tldw-frontend && bun run lint`
**Status**: Complete

## Stage 2: Fix Shared Root Causes
**Goal**: Correct the smallest set of source issues causing the failing gates, starting with failures that cascade into backend health and e2e jobs.
**Success Criteria**: The reproduced local failures from Stage 1 pass after targeted code changes and any needed regression tests are added first.
**Tests**:
- Re-run the exact failing commands from Stage 1
- Add focused regression tests for any bugfix that changes behavior
**Status**: Complete

## Stage 3: Verify CI-Parity Commands
**Goal**: Run the affected local verification commands with CI-like settings to reduce the risk of another red run after push.
**Success Criteria**: Compile, lint, guard, and targeted pytest/playwright commands pass locally in the isolated worktree.
**Tests**:
- `source .venv/bin/activate && python -m compileall tldw_Server_API/app`
- `source .venv/bin/activate && python -m pytest -q --maxfail=1 --disable-warnings -p pytest_cov -p pytest_asyncio.plugin tldw_Server_API/tests/wizard --cov=tldw_Server_API/cli/wizard --cov-report=term-missing --cov-fail-under=70`
- `cd apps/tldw-frontend && bun run lint`
**Status**: Complete

## Stage 4: Security, Diff Hygiene, and Push
**Goal**: Run touched-scope security and diff hygiene checks, commit the fixes, push the branch, and re-check the live PR status.
**Success Criteria**: Bandit is clean on touched Python paths, `git diff --check` passes, the fixes are committed and pushed, and the live PR check set is re-polled.
**Tests**:
- `source .venv/bin/activate && python -m bandit -r <touched_python_paths> -f json -o /tmp/bandit_pr916_ci_fixes.json`
- `git diff --check`
- Live GitHub API check-run poll for PR #916
**Status**: In Progress
