# Knowledge Workspace Beta Readiness Audit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Audit and harden live E2E coverage for `/knowledge` and `/workspace-playground`, fix confirmed regressions, and define a small live-backend beta gate for both routes.

**Architecture:** Work from outside in. First capture a route-level coverage matrix from the existing Playwright suite, then add failing live Playwright checks for every high-risk missing workflow, and only then patch the UI or backend code required to make those tests pass. Keep mocked or intercepted tests explicitly non-gating and use them only for edge states that cannot be reproduced reliably against the real backend.

**Tech Stack:** Playwright, Bun, Next.js, React, `@tldw/ui`, Vitest, FastAPI (only if a confirmed bug requires backend changes), Bandit for touched Python scope.

**Execution Mode Note:** When executing this plan with subagent-driven development, insert spec-compliance review and code-quality review after every task before committing and before moving to the next task.

---

## Stage 0: Isolate the Work
**Goal:** Move implementation into a dedicated worktree before touching tests or product code.
**Success Criteria:** A clean worktree exists on a `codex/` branch with only the new plan/design docs carried forward.
**Tests:** `git -C <worktree> status --short` shows a clean tree before implementation begins.
**Status:** Not Started

### Task 0: Create the implementation worktree

**Files:**
- Modify: `Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-design.md`
- Modify: `Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-implementation-plan.md`
- Test: repository git state only

**Step 1: Create the worktree and branch**

Run:

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2 worktree add /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/knowledge-workspace-beta-audit -b codex/knowledge-workspace-beta-audit
```

Expected: a new clean worktree is created on `codex/knowledge-workspace-beta-audit`.

**Step 2: Verify the worktree is clean**

Run:

```bash
git -C /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/knowledge-workspace-beta-audit status --short
```

Expected: no unrelated modifications are present.

**Step 3: Confirm the planning docs are available in the worktree**

Run:

```bash
ls /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/knowledge-workspace-beta-audit/Docs/Plans | rg 'knowledge-workspace-beta-readiness-audit'
```

Expected: both planning documents are present.

**Step 4: Commit the worktree setup only if any new bootstrap file is required**

```bash
git add <only-if-needed>
git commit -m "chore: bootstrap knowledge/workspace beta audit worktree"
```

### Task 0B: Verify live-backend preflight and data hygiene

**Files:**
- Modify: `Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-implementation-plan.md`
- Test: live backend reachability only

**Step 1: Confirm the environment variables that govern the live suite**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && printf "TLDW_SERVER_URL=%s\nTLDW_API_KEY=%s\nTLDW_WEB_URL=%s\nTLDW_WEB_AUTOSTART=%s\n" "${TLDW_SERVER_URL:-http://127.0.0.1:8000}" "${TLDW_API_KEY:-THIS-IS-A-SECURE-KEY-123-FAKE-KEY}" "${TLDW_WEB_URL:-http://localhost:8080}" "${TLDW_WEB_AUTOSTART:-true}"
```

Expected: the exact values driving the live suite are visible before any failures are interpreted.

**Step 2: Preflight the backend endpoint used by the real-backend workspace suite**

Run:

```bash
curl -sS -H "x-api-key: ${TLDW_API_KEY:-THIS-IS-A-SECURE-KEY-123-FAKE-KEY}" "${TLDW_SERVER_URL:-http://127.0.0.1:8000}/api/v1/chats/?limit=1&offset=0&ordering=-updated_at"
```

Expected: a successful JSON response or an explicit backend availability problem that must be fixed before continuing.

**Step 3: Define the test-data namespace before creating any live records**

Use the prefix:

```text
e2e-knowledge-workspace-<timestamp-or-generateTestId>
```

Expected: every live document, thread, or artifact created by the audit is uniquely namespaced and traceable.

**Step 4: Record the cleanup mode**

If a reliable delete/cleanup path is available, use it after each live test group. If no delete path exists, record created IDs and titles in the bug log for later cleanup.

## Stage 1: Baseline Audit and Coverage Matrix
**Goal:** Replace vague assumptions with an explicit live/mock/misleading/missing matrix for both routes.
**Success Criteria:** A matrix doc exists, current workflow specs are mapped to features, and misleading tests are called out by name.
**Tests:** Existing Playwright workflow suites run and the matrix records whether each test is truly live-backed.
**Status:** Not Started

### Task 1: Create the audit matrix and baseline test inventory

**Files:**
- Create: `Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md`
- Test: `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`
- Test: `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts`
- Test: `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts`

**Step 1: Write the matrix scaffold**

```md
| Route | Feature | Existing Test(s) | Classification | Evidence | Follow-up |
| --- | --- | --- | --- | --- | --- |
| /knowledge | Workspace handoff | AnswerPanel.workspace-handoff.test.tsx | Mock-only | Component test only | Add live Playwright |
```

**Step 2: Run the current route-level suites**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && bunx playwright test e2e/workflows/knowledge-qa.spec.ts e2e/workflows/workspace-playground.spec.ts e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line
```

Expected: current pass/fail/skip behavior is captured and copied into the matrix with notes.

**Step 3: Mark every current check as `Live-covered`, `Mock-only`, `Misleading`, or `Missing`**

Expected: obvious weak cases are named explicitly, including store-seeded shortcuts and placeholder assertions that do not prove real user workflows.

**Step 4: Commit the matrix baseline**

```bash
git add Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md
git commit -m "docs: add knowledge/workspace beta audit matrix baseline"
```

## Stage 2: Record the Baseline Live Bug Log
**Goal:** Capture confirmed live failures and flaky behaviors before changing tests or product code.
**Success Criteria:** A bug log exists with prioritized, reproducible issues taken from the baseline live runs and route exploration.
**Tests:** Baseline real-backend behavior is documented before coverage repair begins.
**Status:** Not Started

### Task 2: Create the prioritized bug log from baseline live behavior

**Files:**
- Create: `Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-bug-log.md`
- Modify: `Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md`
- Test: `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`
- Test: `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts`

**Step 1: Write the bug log scaffold**

```md
## P1
- Route:
- Feature:
- Reproduction:
- Evidence:
- Suspected layer:
```

**Step 2: Re-run the baseline live suites and capture failures as bugs first**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && bunx playwright test e2e/workflows/knowledge-qa.spec.ts e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line --workers=1
```

Expected: every confirmed failure, flaky behavior, or suspicious pass is written to the bug log before coverage work begins.

**Step 3: Update the matrix with links to each confirmed bug**

Expected: high-risk missing or misleading rows point to the bug log entry that justified the next coverage task.

**Step 4: Commit the bug log baseline**

```bash
git add Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-bug-log.md Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md
git commit -m "docs: add baseline bug log for knowledge/workspace audit"
```

## Stage 3: Close KnowledgeQA Live Coverage Gaps
**Goal:** Convert the highest-risk `/knowledge` workflows from component-only or partial coverage into credible live E2E checks.
**Success Criteria:** High-risk flows are covered live or explicitly downgraded to non-gating with evidence.
**Tests:** New and existing `/knowledge` Playwright checks pass against the real backend; targeted Vitest checks pass for any touched UI components.
**Status:** Not Started

### Task 3: Add failing live tests for workspace handoff, history reload, and citation/evidence coherence

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/KnowledgeQAPage.ts`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.workspace-handoff.test.tsx`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.history.test.tsx`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx`

**Step 1: Write the failing live Playwright checks**

Add tests with titles similar to:

```ts
test("@kw-audit-live @beta-broad opens workspace with grounded prefill from a live answer", async () => {})
test("@kw-audit-live @beta-broad restores the prior thread after reload and accepts a follow-up", async () => {})
test("@kw-audit-live @beta-broad keeps citation clicks and evidence details aligned to the same source", async () => {})
```

**Step 2: Run the targeted `/knowledge` tests and capture the first real failure**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "@kw-audit-live" --reporter=line
```

Expected: at least one new test fails until the missing selector, state restore path, or source/evidence behavior is fixed. If a new test passes immediately, keep it and upgrade that matrix row to `Live-covered`.

**Step 3: Implement the minimal fix required by the failing test**

Likely touch one or more of:
- `apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx`
- `apps/packages/ui/src/components/Option/KnowledgeQA/HistorySidebar.tsx`
- `apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx`
- `apps/packages/ui/src/components/Option/KnowledgeQA/ConversationThread.tsx`
- `apps/packages/ui/src/components/Option/KnowledgeQA/evidence/EvidenceRail.tsx`
- `apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx`

**Step 4: Re-run the targeted E2E and component tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "@kw-audit-live" --reporter=line
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui && bunx vitest run src/components/Option/KnowledgeQA/__tests__/AnswerPanel.workspace-handoff.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.history.test.tsx src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx
```

Expected: the new live checks pass and the touched component tests stay green.

**Step 5: Commit the KnowledgeQA live-flow closure**

```bash
git add apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts apps/tldw-frontend/e2e/utils/page-objects/KnowledgeQAPage.ts apps/packages/ui/src/components/Option/KnowledgeQA
git commit -m "test: add live knowledge qa coverage for handoff and history"
```

### Task 4: Cover share/export/branch behavior live where possible, or mark it non-gating with proof

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/KnowledgeQAPage.ts`
- Modify: `Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/ExportDialog.a11y.test.tsx`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.branch-share.test.tsx`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/ConversationThread.test.tsx`

**Step 1: Add the smallest live checks the product can support today**

Use titles like:

```ts
test("@kw-audit-live @beta-broad exposes a shareable thread route after a live search", async () => {})
test("@kw-audit-live @beta-broad exports the current answer or clearly surfaces why export is unavailable", async () => {})
```

**Step 2: Run just those checks**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "@kw-audit-live" --reporter=line
```

Expected: either the live behavior works and the feature becomes `Live-covered`, or the check fails and exposes a real bug, or the route cannot support the flow and the matrix is updated to `Mock-only` or `Missing`.

**Step 3: Fix only the confirmed product gap**

Likely touch one or more of:
- `apps/packages/ui/src/components/Option/KnowledgeQA/ExportDialog.tsx`
- `apps/packages/ui/src/components/Option/KnowledgeQA/ConversationThread.tsx`
- `apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx`

**Step 4: Re-run the targeted checks and update the matrix classification**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "@kw-audit-live" --reporter=line
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui && bunx vitest run src/components/Option/KnowledgeQA/__tests__/ExportDialog.a11y.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.branch-share.test.tsx src/components/Option/KnowledgeQA/__tests__/ConversationThread.test.tsx
```

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts apps/tldw-frontend/e2e/utils/page-objects/KnowledgeQAPage.ts apps/packages/ui/src/components/Option/KnowledgeQA Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md
git commit -m "test: classify and harden knowledge qa share flows"
```

## Stage 4: Close Workspace Playground Live Coverage Gaps
**Goal:** Replace store-seeded and partial workspace checks with live coverage for the most failure-prone flows.
**Success Criteria:** Source intake, grounding, studio, persistence, and recovery have live proof or an explicit non-gating classification.
**Tests:** New and existing workspace Playwright checks pass against the real backend; targeted workspace Vitest checks pass for any touched UI components.
**Status:** Not Started

### Task 5: Add failing live tests for real add-source ingestion and source-list state

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/WorkspacePlaygroundPage.ts`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.ingestion.test.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage4.filters-and-sort.test.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage12.source-list-view-state.test.tsx`

**Step 1: Write the failing live E2E checks**

Add tests with titles similar to:

```ts
test("@wp-audit-live @beta-broad ingests a live document through Add Sources and selects it from the real list", async () => {})
test("@wp-audit-live @beta-broad preserves source filters or list state across a reload", async () => {})
```

**Step 2: Run the targeted workspace real-backend checks**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && bunx playwright test e2e/workflows/workspace-playground.real-backend.spec.ts --grep "@wp-audit-live" --reporter=line
```

Expected: at least one check fails until the real ingestion or state wiring is fixed.

**Step 3: Implement the minimal fix**

Likely touch one or more of:
- `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/AddSourceModal.tsx`
- `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx`
- `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/source-ingestion-utils.ts`
- `apps/packages/ui/src/components/Option/WorkspacePlayground/source-list-view.ts`
- `apps/packages/ui/src/components/Option/WorkspacePlayground/use-source-list-view-state.ts`
- `apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx`

**Step 4: Re-run the targeted E2E and component tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && bunx playwright test e2e/workflows/workspace-playground.real-backend.spec.ts --grep "@wp-audit-live" --reporter=line
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.ingestion.test.tsx src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage4.filters-and-sort.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage12.source-list-view-state.test.tsx
```

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts apps/tldw-frontend/e2e/utils/page-objects/WorkspacePlaygroundPage.ts apps/packages/ui/src/components/Option/WorkspacePlayground
git commit -m "test: add live workspace ingestion coverage"
```

### Task 6: Add failing live tests for studio cancellation, recovery, and status/trust surfaces

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/WorkspacePlaygroundPage.ts`
- Modify: `Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/undo-manager.test.ts`

**Step 1: Write the failing live checks**

Add tests with titles similar to:

```ts
test("@wp-audit-live @beta-broad cancels a long-running studio action without leaving a stuck state", async () => {})
test("@wp-audit-live @beta-broad reloads after interruption and surfaces a recoverable artifact status", async () => {})
test("@wp-audit-live @beta-broad shows backend health or status changes without blocking the workspace", async () => {})
```

**Step 2: Run the targeted real-backend checks**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && bunx playwright test e2e/workflows/workspace-playground.real-backend.spec.ts --grep "@wp-audit-live" --reporter=line
```

Expected: a real failure or gap is exposed before any product code changes are made.

**Step 3: Fix only the behavior proven broken**

Likely touch one or more of:
- `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
- `apps/packages/ui/src/components/Option/WorkspacePlayground/WorkspaceHeader.tsx`
- `apps/packages/ui/src/components/Option/WorkspacePlayground/WorkspaceStatusBar.tsx`
- `apps/packages/ui/src/components/Option/WorkspacePlayground/undo-manager.ts`
- `apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx`

**Step 4: Re-run the targeted E2E and component tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && bunx playwright test e2e/workflows/workspace-playground.real-backend.spec.ts --grep "@wp-audit-live" --reporter=line
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx src/components/Option/WorkspacePlayground/__tests__/undo-manager.test.ts
```

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts apps/tldw-frontend/e2e/utils/page-objects/WorkspacePlaygroundPage.ts apps/packages/ui/src/components/Option/WorkspacePlayground Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md
git commit -m "test: harden workspace studio recovery flows"
```

## Stage 5: Establish the Beta Gate and Final Verification
**Goal:** Finish with a small, defensible live-backend gate plus a broader non-gating sweep and explicit residual risk.
**Success Criteria:** A named beta-gate command exists, the gate is justified by the matrix, and final verification evidence is captured.
**Tests:** Gate suite passes; supporting broad suite passes or has explicitly documented non-gating failures.
**Status:** Not Started

### Task 7: Tag the must-pass live tests and add a dedicated gate command

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`
- Modify: `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts`
- Modify: `apps/tldw-frontend/package.json`
- Modify: `Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md`

**Step 1: Mark the final must-pass live tests with a shared tag**

Use test names that include `@beta-gate` only for workflows that map directly to critical user value:
- live KnowledgeQA search + answer/evidence coherence
- live KnowledgeQA follow-up/history continuity or workspace handoff
- live workspace source grounding
- live workspace studio generation or cancellation/recovery

**Step 2: Add a single runner command**

Add a script similar to:

```json
"e2e:beta:knowledge-workspace:live": "playwright test e2e/workflows/knowledge-qa.spec.ts e2e/workflows/workspace-playground.real-backend.spec.ts --grep @beta-gate --reporter=line --workers=1"
```

**Step 3: Run the beta gate**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && bun run e2e:beta:knowledge-workspace:live
```

Expected: the must-pass live workflows succeed cleanly.

**Step 4: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts apps/tldw-frontend/package.json Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md
git commit -m "test: add live beta gate for knowledge and workspace"
```

### Task 8: Run the final verification sweep and capture residual risk

**Files:**
- Modify: `Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md`
- Test: `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`
- Test: `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts`
- Test: `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts`

**Step 1: Run the full route-focused Playwright sweep**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/tldw-frontend && bunx playwright test e2e/workflows/knowledge-qa.spec.ts e2e/workflows/workspace-playground.spec.ts e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line --workers=1
```

Expected: all intended route-focused checks pass, or any remaining failures are explicitly documented as non-gating.

**Step 2: Run the most relevant component suites**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui && bunx vitest run src/components/Option/KnowledgeQA/__tests__/AnswerPanel.workspace-handoff.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.history.test.tsx src/components/Option/KnowledgeQA/__tests__/ExportDialog.a11y.test.tsx src/components/Option/WorkspacePlayground/__tests__/AddSourceModal.stage1.ingestion.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx
```

Expected: touched supporting component suites pass.

**Step 3: If any backend or Python files were touched, run Python verification and Bandit**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest -v <touched_python_tests>
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r <touched_python_paths> -f json -o /tmp/bandit_knowledge_workspace_beta_audit.json
```

Expected: Python regressions are caught before completion and new security findings in touched Python scope are fixed immediately.

**Step 4: Update the matrix with final classifications and residual risk**

Record:
- which features are now `Live-covered`
- which remain `Mock-only`
- which were intentionally left non-gating
- which bugs were fixed vs deferred

**Step 5: Commit the final verification artifacts**

```bash
git add Docs/Plans/2026-03-16-knowledge-workspace-beta-readiness-audit-matrix.md
git commit -m "docs: finalize knowledge/workspace beta audit results"
```
