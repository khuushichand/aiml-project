# Quiz E2E Critical Flows Split Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split quiz E2E coverage into focused critical-path tests and harden assertions so edit/create/take failures are no longer masked.

**Architecture:** Keep the existing broad quiz UX test as smoke-oriented coverage while splitting focused critical tests into dedicated spec files. Reuse shared setup/seeding helpers from a helper module to reduce flake, then replace warning-only branches in critical flows with hard assertions and deterministic waits.

**Tech Stack:** Playwright, TypeScript, extension options page UI (Ant Design), direct quiz API fetch calls.

---

### Task 1: Add Focused Critical Quiz E2E Tests
**Status:** Complete

**Files:**
- Create: `apps/extension/tests/e2e/quiz-critical-edit.spec.ts`
- Create: `apps/extension/tests/e2e/quiz-critical-create.spec.ts`
- Create: `apps/extension/tests/e2e/quiz-critical-take-results.spec.ts`
- Create: `apps/extension/tests/e2e/utils/quiz-critical-helpers.ts`

**Step 1: Write failing tests for each critical flow**
- Add three tests:
  - `strictly edits quiz metadata and question set`
  - `strictly creates a manual quiz from create tab`
  - `strictly starts, submits, and verifies take/results flow`
- Use strict assertions (no warning-only fallback for required behavior).

**Step 2: Run only new specs and verify RED**
- Run: `TLDW_E2E_SERVER_URL=127.0.0.1:8000 TLDW_E2E_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY node_modules/.bin/playwright test tests/e2e/quiz-critical-*.spec.ts --reporter=line`
- Expected: At least one failure initially due selector/flow timing assumptions.

**Step 3: Implement robust selectors + flow helpers to pass**
- Add helper methods for:
  - preflight/config launch
  - quiz fixture seeding and cleanup
  - opening quiz workspace and panel selection
  - API validation for persisted metadata and question CRUD
- Use deterministic selectors/test IDs where available.

**Step 4: Run split specs and verify GREEN**
- Re-run command above.
- Expected: all tests pass.

**Step 5: Commit checkpoint (deferred until full batch passes)**
- Stage after Tasks 1-3 complete.

### Task 2: Scope Unsaved-Changes Dialog Handling to Expected Prompt
**Status:** Complete

**Files:**
- Modify: `apps/extension/tests/e2e/utils/quiz-critical-helpers.ts`
- Modify: `apps/extension/tests/e2e/quiz-critical-create.spec.ts`

**Step 1: Add failing assertion for dialog message filtering**
- Require dialog text to match unsaved-create prompt before accept.
- Fail test on unexpected dialogs.

**Step 2: Run target test and verify RED if generic handler exists**
- Run create-flow test only using `-g "strictly enforces unsaved-create navigation confirm copy"`.

**Step 3: Implement scoped dialog helper**
- Add helper that accepts only expected message regex:
  - `/You have unsaved quiz changes\. Leave Create tab\?/i`

**Step 4: Re-run target test and verify GREEN**
- Expected: dialog is accepted only when message matches expected unsaved prompt.

### Task 3: Ensure Missing Question List Is a Hard Failure with Debug Artifacts
**Status:** Complete

**Files:**
- Modify: `apps/extension/tests/e2e/utils/quiz-critical-helpers.ts`
- Modify: `apps/extension/tests/e2e/quiz-critical-take-results.spec.ts`

**Step 1: Write failing assertion path for missing rendered questions**
- Replace any early return on missing question list with explicit failure.

**Step 2: Implement artifact capture before failure**
- Capture full-page screenshot to Playwright output dir with deterministic filename.
- Throw explicit error message referencing screenshot path.

**Step 3: Run take-flow test and verify behavior**
- If flow passes, no artifact expected.
- If it fails in future runs, failure is explicit and includes screenshot trace path.

### Task 4: Verify, Document, and Clean Plan Status
**Status:** Complete (strict spec + backend integration; quiz-ux smoke left unchanged by design)

**Files:**
- Modify: `docs/plans/2026-03-04-quiz-e2e-critical-split.md`

**Step 1: Run focused verification commands**
- `TLDW_E2E_SERVER_URL=127.0.0.1:8000 TLDW_E2E_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY node_modules/.bin/playwright test tests/e2e/quiz-critical-*.spec.ts --reporter=line`
- `TLDW_E2E_SERVER_URL=127.0.0.1:8000 TLDW_E2E_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY node_modules/.bin/playwright test tests/e2e/quiz-ux.spec.ts --reporter=line`

Verification notes (2026-03-03/04):
- `python -m pytest -q tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py` -> `8 passed`
- `bunx playwright test tests/e2e/quiz-critical-*.spec.ts --reporter=line` (with local server) -> `4 passed`
- `python -m bandit -r tldw_Server_API/app/api/v1/endpoints/quizzes.py ...` -> `0 findings`

**Step 2: Update task statuses**
- Mark each task complete/incomplete with notes.

**Step 3: Leave plan file in place for traceability**
- Keep file unless user explicitly asks for cleanup/removal.
