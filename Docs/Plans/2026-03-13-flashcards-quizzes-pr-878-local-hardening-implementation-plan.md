# Flashcards And Quizzes PR 878 Local Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Run a broad local hardening pass for PR `#878`, fix real regressions immediately, and leave the branch with stronger baseline confidence across flashcards and quizzes.

**Architecture:** Use a risk-based verification matrix. Start with backend and frontend regression suites that cover both legacy and new paths, then run docs/link checks, and finally perform slower Playwright/manual UI verification on the highest-risk journeys. If any tier fails, fix the regression immediately, prove the fix with the smallest targeted rerun, and then rerun the containing tier.

**Tech Stack:** FastAPI, Pydantic, SQLite-backed ChaChaNotes DB, pytest, Bandit, React 19, TypeScript, Vitest, Playwright, Next.js/extension route shells, markdown docs.

---

### Task 1: Capture The Hardening Baseline

**Files:**
- Read: `Docs/Plans/2026-03-13-flashcards-quizzes-pr-878-local-hardening-design.md`
- Read: `Docs/Plans/2026-03-13-flashcards-quizzes-pr-878-local-hardening-implementation-plan.md`
- Test: `git status`, `git log`, `git diff --stat`

**Step 1: Record the current branch state**

Run:

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import status --short
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import log --oneline -n 15
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import diff --stat dev...HEAD
```

Expected: clean worktree, recent flashcards/quizzes commits visible, large diff summary available for risk review.

**Step 2: Note the verification tiers you will execute**

Document in execution notes:

- backend regression
- frontend regression
- docs/link checks
- slower UI verification

**Step 3: Confirm docs are already landed and continue**

Treat the hardening docs as baseline input for execution. Do not create a second docs-only commit unless the review pass itself changes the plan/design again.

Expected: no-op for already committed planning docs.

### Task 2: Run Backend Baseline Regression

**Files:**
- Test: `tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py`
- Test: `tldw_Server_API/tests/Flashcards/test_apkg_exporter.py`
- Test: `tldw_Server_API/tests/Flashcards/test_apkg_importer.py`
- Test: `tldw_Server_API/tests/Flashcards/test_flashcards_db_assets.py`
- Test: `tldw_Server_API/tests/Flashcards/test_flashcards_scheduler_schema.py`
- Test: `tldw_Server_API/tests/Flashcards/test_structured_qa_import.py`
- Test: `tldw_Server_API/tests/Flashcards/test_study_assistant_db.py`
- Test: `tldw_Server_API/tests/Flashcards/test_study_assistant_service.py`
- Test: `tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py`
- Test: `tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py`

**Step 1: Run the backend matrix**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py \
  tldw_Server_API/tests/Flashcards/test_apkg_exporter.py \
  tldw_Server_API/tests/Flashcards/test_apkg_importer.py \
  tldw_Server_API/tests/Flashcards/test_flashcards_db_assets.py \
  tldw_Server_API/tests/Flashcards/test_flashcards_scheduler_schema.py \
  tldw_Server_API/tests/Flashcards/test_structured_qa_import.py \
  tldw_Server_API/tests/Flashcards/test_study_assistant_db.py \
  tldw_Server_API/tests/Flashcards/test_study_assistant_service.py \
  tldw_Server_API/tests/Quizzes/test_quiz_source_resolver.py \
  tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py -q
```

Expected: all tests pass.

**Step 2: If a test fails, isolate before fixing**

Run the smallest failing target, for example:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Flashcards/test_flashcards_endpoint_integration.py::test_name -q
```

Expected: one reproducible failing test.

**Step 3: Write the minimal fix**

Modify only the touched backend file(s), for example:

- `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- `tldw_Server_API/app/api/v1/endpoints/quizzes.py`
- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- `tldw_Server_API/app/core/Flashcards/*.py`
- `tldw_Server_API/app/services/quiz_*.py`

Keep fixes narrow and behavior-driven.

**Step 4: Prove the fix and rerun the tier**

Run the smallest failing test first, then rerun the whole backend matrix command from Step 1.

Expected: isolated failure fixed, full backend tier green.

**Step 5: Commit backend fixes if needed**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add <touched_backend_files>
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "fix(flashcards): harden backend regressions"
```

### Task 3: Run Frontend Baseline Regression

**Files:**
- Test: `apps/packages/ui/src/components/Flashcards/**/*test*`
- Test: `apps/packages/ui/src/components/Quiz/**/*test*`
- Test: `apps/packages/ui/src/services/__tests__/flashcard-assets.test.ts`
- Test: `apps/packages/ui/src/services/__tests__/flashcards-structured-import.test.ts`
- Test: `apps/packages/ui/src/services/__tests__/quizzes.test.ts`
- Test: `apps/packages/ui/src/services/__tests__/quiz-flashcards-handoff.test.ts`

**Step 1: Run the high-value frontend matrix**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run \
  src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.image-insert.test.tsx \
  src/components/Flashcards/components/__tests__/FlashcardDocumentRow.image-insert.test.tsx \
  src/components/Flashcards/components/__tests__/FlashcardDocumentRow.test.tsx \
  src/components/Flashcards/components/__tests__/FlashcardEditDrawer.image-insert.test.tsx \
  src/components/Flashcards/hooks/__tests__/useFlashcardAssistantQueries.test.tsx \
  src/components/Flashcards/hooks/__tests__/useFlashcardDocumentQuery.test.ts \
  src/components/Flashcards/hooks/__tests__/useFlashcardQueries.review-next.test.tsx \
  src/components/Flashcards/tabs/__tests__/ImageOcclusionPanel.test.tsx \
  src/components/Flashcards/tabs/__tests__/ImageOcclusionTransferPanel.test.tsx \
  src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx \
  src/components/Flashcards/tabs/__tests__/ManageTab.document-editing.test.tsx \
  src/components/Flashcards/tabs/__tests__/ManageTab.document-mode.test.tsx \
  src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx \
  src/components/Flashcards/tabs/__tests__/ReviewTab.assistant.test.tsx \
  src/components/Flashcards/tabs/__tests__/ReviewTab.cram-mode.test.tsx \
  src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx \
  src/components/Flashcards/tabs/__tests__/ReviewTab.edit-in-review.test.tsx \
  src/components/Quiz/tabs/__tests__/CreateTab.draft-safety.test.tsx \
  src/components/Quiz/tabs/__tests__/CreateTab.flexible-composition.test.tsx \
  src/components/Quiz/tabs/__tests__/CreateTab.preview.test.tsx \
  src/components/Quiz/tabs/__tests__/CreateTab.save-progress.test.tsx \
  src/components/Quiz/tabs/__tests__/CreateTab.validation-accessibility.test.tsx \
  src/components/Quiz/tabs/__tests__/GenerateTab.media-selection.test.tsx \
  src/components/Quiz/tabs/__tests__/ManageTab.bulk-duplicate.test.tsx \
  src/components/Quiz/tabs/__tests__/ManageTab.edit-modal-scale.test.tsx \
  src/components/Quiz/tabs/__tests__/ManageTab.undo-accessibility.test.tsx \
  src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx \
  src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx \
  src/components/Quiz/tabs/__tests__/TakeQuizTab.navigation-guardrails.test.tsx \
  src/components/Quiz/tabs/__tests__/TakeQuizTab.start-flow.test.tsx \
  src/components/Quiz/tabs/__tests__/TakeQuizTab.study-modes.test.tsx \
  src/components/Quiz/tabs/__tests__/TakeQuizTab.submission-retry.test.tsx \
  src/components/Quiz/hooks/__tests__/useQuizRemediationQueries.test.tsx \
  src/components/Quiz/tabs/__tests__/ResultsTab.details.test.tsx \
  src/components/Quiz/tabs/__tests__/ResultsTab.export.test.tsx \
  src/components/Quiz/tabs/__tests__/ResultsTab.filters-retake.test.tsx \
  src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx \
  src/services/__tests__/flashcard-assets.test.ts \
  src/services/__tests__/flashcards-structured-import.test.ts \
  src/services/__tests__/quizzes.test.ts \
  src/services/__tests__/quiz-flashcards-handoff.test.ts
```

Expected: all selected suites pass.

This command must run from the UI package root so the package-local `vitest.config.ts` and path aliases are applied.

**Step 2: If a test fails, isolate before fixing**

Run the smallest failing test file or test name:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run src/components/Quiz/tabs/__tests__/ResultsTab.remediation.test.tsx
```

Expected: one clear failing behavior.

**Step 3: Write the minimal frontend fix**

Likely files:

- `apps/packages/ui/src/components/Flashcards/**/*`
- `apps/packages/ui/src/components/Quiz/**/*`
- `apps/packages/ui/src/services/flashcards.ts`
- `apps/packages/ui/src/services/quizzes.ts`

Prefer behavior-preserving fixes over refactors.

**Step 4: Prove the fix and rerun the tier**

Run the smallest failing slice first, then rerun the matrix command from Step 1.

Expected: isolated failure fixed, full frontend tier green.

**Step 5: Commit frontend fixes if needed**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add <touched_frontend_files>
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "fix(ui): harden flashcards quiz regressions"
```

### Task 4: Run Docs And Link Hygiene Checks

**Files:**
- Test: `apps/packages/ui/src/components/Flashcards/constants/__tests__/help-links.test.ts`
- Create: `tldw_Server_API/tests/Docs/test_flashcards_guide_discoverability.py`
- Modify: `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md`
- Modify: `apps/packages/ui/src/components/Flashcards/constants/help-links.ts`

**Step 1: Ensure a flashcards-specific discoverability guard exists**

Inspect `tldw_Server_API/tests/Docs`.

If there is no flashcards-specific guide/index test, add:

- `tldw_Server_API/tests/Docs/test_flashcards_guide_discoverability.py`

It should assert:

- `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md` exists
- `Docs/User_Guides/index.md` links to the flashcards guide

**Step 2: Run targeted docs-related tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run src/components/Flashcards/constants/__tests__/help-links.test.ts
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Docs/test_flashcards_guide_discoverability.py -q
```

Expected: link hygiene and docs discoverability tests pass.

**Step 3: Read the flashcards guide directly**

Inspect:

- `Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md`

Confirm it still matches:

- structured Q&A import
- document mode
- image-backed cards
- image occlusion
- scheduler behavior
- study assistant and remediation

**Step 4: Fix any drift**

Update only:

- guide content
- help-link constants/tests
- flashcards-specific discoverability test if it needed to be added or updated

Do not widen this to the entire `tldw_Server_API/tests/Docs` directory unless the flashcards-specific check points to a shared docs helper that actually needs broader confirmation.

**Step 5: Rerun the targeted docs checks**

Run the commands from Step 2 again.

Expected: docs tier green.

**Step 6: Commit docs fixes if needed**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add Docs/User_Guides/WebUI_Extension/Flashcards_Study_Guide.md apps/packages/ui/src/components/Flashcards/constants/help-links.ts apps/packages/ui/src/components/Flashcards/constants/__tests__/help-links.test.ts tldw_Server_API/tests/Docs/test_flashcards_guide_discoverability.py
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "docs(flashcards): harden guide and help links"
```

### Task 5: Run Slower UI Verification

**Files:**
- Read: `apps/extension/tests/e2e/quiz-ux.spec.ts`
- Read: `apps/extension/playwright.config.ts`
- Read: `apps/extension/tests/e2e/ux-design-audit.spec.ts`
- Read: `apps/extension/tests/e2e/ux-review-complete.spec.ts`
- Read: `apps/tldw-frontend/e2e/smoke/stage5-release-gate.spec.ts`

**Step 1: Confirm which local harnesses are actually runnable**

Before running any slow check, confirm:

- Next.js web smoke can autostart or connect to the local WebUI
- extension Playwright can reach a real local server and API key
- the extension host-permission prompt is acceptable for this run

Record which of these two automated harnesses are runnable:

- `apps/tldw-frontend` smoke gate for shared `/flashcards`
- `apps/extension` quiz UX spec for quiz workspace coverage

**Step 2: Run the shared `/flashcards` route smoke when the web harness is available**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend
bunx playwright test e2e/smoke/stage5-release-gate.spec.ts --grep "Flashcards" --reporter=line
```

This uses the local Playwright config to autostart the WebUI unless `TLDW_WEB_AUTOSTART=false` is already set.

If the web harness is unavailable, document the exact reason and verify the `/flashcards` route manually instead.

**Step 3: Run the extension quiz workspace flow when real-server config is available**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/extension
TLDW_E2E_SERVER_URL=<local_server_host:port> TLDW_E2E_API_KEY=<local_api_key> bunx playwright test tests/e2e/quiz-ux.spec.ts --reporter=line
```

This relies on the extension Playwright config to build the extension if needed. It also expects real-server reachability and may require granting host permission for the local origin during the run.

If real-server config, build prerequisites, or host permission make this path unavailable, document the exact blocker and switch only quiz workspace verification to manual coverage instead of forcing a brittle E2E run.

**Step 4: Run manual walkthroughs for the remaining gaps**

Verify these flows manually in the local app or extension surface that owns them:

1. WebUI `/flashcards`: structured Q&A preview import and save
2. WebUI `/flashcards`: document mode edit/save on multiple rows
3. WebUI `/flashcards`: image-backed card create/edit/review
4. WebUI `/flashcards`: image occlusion authoring save path
5. WebUI `/flashcards`: scheduler-backed review next-card loop plus assistant quick actions and follow-up
6. Quiz workspace surface: quiz results remediation explain/quiz/flashcard/study handoff

Record for each:

- setup
- route
- action
- expected result
- actual result

If a flow is covered by one of the automated slow checks above, capture the command and result instead of duplicating it manually.

**Step 5: Fix any real regression immediately**

Modify only the smallest required files, then rerun:

- the affected Playwright/manual step
- the smallest relevant Vitest/Pytest suite

**Step 6: Commit slower-verification fixes if needed**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import add <touched_files>
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import commit -m "fix(flashcards): resolve hardening verification findings"
```

### Task 6: Run Final Security And Closeout Verification

**Files:**
- Test: touched Python files under `tldw_Server_API/app`

**Step 1: Run Bandit on the touched Python scope**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/tldw_Server_API/app/api/v1/endpoints/flashcards.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/tldw_Server_API/app/api/v1/endpoints/quizzes.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/tldw_Server_API/app/core/Flashcards \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/tldw_Server_API/app/services/quiz_generator.py \
  /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/tldw_Server_API/app/services/quiz_source_resolver.py \
  -f json -o /tmp/bandit_pr878_hardening.json
cat /tmp/bandit_pr878_hardening.json
```

Expected: no new findings in changed code. If pre-existing findings remain, identify them clearly.

**Step 2: Confirm branch cleanliness**

Run:

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import status --short
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import rev-parse HEAD
```

Expected: clean worktree and final commit SHA recorded.

**Step 3: Push if new commits were created**

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import push
```

Expected: branch updated on PR `#878`.

**Step 4: Summarize findings and residual risk**

Report:

- suites run
- slower UI checks run
- regressions found and fixed
- any residual risk or unverified path
