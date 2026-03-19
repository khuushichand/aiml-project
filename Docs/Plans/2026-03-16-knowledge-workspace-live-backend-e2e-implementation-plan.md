# Knowledge QA and Workspace Live-Backend E2E Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `/knowledge` and `/workspace-playground` e2e coverage prove real live-backend feature behavior instead of passing through permissive selectors and weak assertions.

**Architecture:** Tighten the Knowledge QA page object around the current UI contract, convert weak Knowledge QA tests into explicit live-backend assertions, and extend Workspace Playground real-backend coverage for source-scoped chat and studio behavior. Keep existing parity/smoke coverage, but rely on live backend flows for feature truth.

**Tech Stack:** Playwright, Next.js WebUI, Zustand-backed UI state, live FastAPI backend, Bandit

---

### Task 1: Harden Knowledge QA selectors around the current layout contract

**Files:**
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/KnowledgeQAPage.ts`
- Reference: `apps/packages/ui/src/components/Option/KnowledgeQA/SearchBar.tsx`
- Reference: `apps/packages/ui/src/components/Option/KnowledgeQA/SettingsPanel/index.tsx`
- Reference: `apps/packages/ui/src/components/Option/KnowledgeQA/HistorySidebar.tsx`

**Step 1: Write the failing test expectation targets**

Document the selectors the page object must support:

- search input: `#knowledge-search-input`
- settings button: `button[aria-label="Open settings"]`
- settings dialog: `role="dialog"` with name `RAG Settings`
- history expand affordances:
  - desktop collapsed: `button[aria-label="Expand history sidebar"]`
  - mobile open: `[data-testid="knowledge-history-mobile-open"]`
- answer shell: `AI Answer`, `data-knowledge-citation-index`, `complementary[aria-label="Evidence panel"]`

**Step 2: Run the failing suite to verify current selectors are insufficient**

Run:

```bash
cd apps/tldw-frontend
TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://localhost:3000 bunx playwright test e2e/workflows/knowledge-qa.spec.ts --reporter=line
```

Expected: current failures in settings/history and delayed-loading assertions remain visible.

**Step 3: Update the page object to use exact selectors first**

Implement helpers for:

- `getSearchInput()` using `#knowledge-search-input`
- `openSettings()` using `getByRole("button", { name: "Open settings" })`
- `getSettingsDialog()`
- `openHistorySidebar()` choosing current visible affordance
- `getEvidencePanel()`
- `getCitationButtons()`

**Step 4: Run the focused suite again**

Run:

```bash
cd apps/tldw-frontend
TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://localhost:3000 bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "Settings|Search History|delayed" --reporter=line
```

Expected: selector failures improve or become feature-contract failures instead of timeouts from wrong locators.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/utils/page-objects/KnowledgeQAPage.ts
git commit -m "test: align knowledge qa page object with current ui contract"
```

### Task 2: Replace weak Knowledge QA assertions with live-backend contracts

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`
- Reference: `apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx`
- Reference: `apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx`

**Step 1: Write the failing test changes first**

Convert these weak patterns:

- broad `try/catch` blocks that swallow missing UI
- tautologies such as `|| true`
- text assertions that ignore structured citation markup

Into explicit contracts:

- delayed-loading test must observe staged copy and then a visible answer panel with at least one citation button
- settings test must open `RAG Settings`
- preset test must visibly toggle radio state
- expert mode test must flip the switch state and reveal expert controls
- history test must visibly expand the history container

**Step 2: Run the targeted failing tests and confirm red**

Run:

```bash
cd apps/tldw-frontend
TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://localhost:3000 bunx playwright test e2e/workflows/knowledge-qa.spec.ts --grep "progressive loading|open settings panel|switch between presets|toggle expert mode|apply settings to search request|open history sidebar" --reporter=line
```

Expected: failures are specific to missing assertions or request-shape mismatches.

**Step 3: Implement minimal test updates**

Update the suite to assert:

- search request payload changes when settings are changed
- citation/evidence controls exist when an answer is rendered
- history restore behavior uses a prior live search rather than checking generic visibility only
- no-results/error tests assert a real recovery or error contract, not a tautology

**Step 4: Run the Knowledge QA suite**

Run:

```bash
cd apps/tldw-frontend
TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://localhost:3000 bunx playwright test e2e/workflows/knowledge-qa.spec.ts --reporter=line
```

Expected: Knowledge QA passes or exposes only real backend product issues.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts
git commit -m "test: strengthen knowledge qa live backend e2e coverage"
```

### Task 3: Expand Workspace Playground live-backend feature coverage

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/WorkspacePlaygroundPage.ts`
- Reference: `apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
- Reference: `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
- Reference: `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx`

**Step 1: Write the failing test scenarios**

Add live-backend scenarios for:

- selected sources are surfaced in chat context
- sending one chat turn produces an assistant response in workspace chat
- one studio output uses selected sources and reaches a completed state
- one workspace search or retrieval affordance returns actionable results

**Step 2: Run the workspace real-backend suite and verify new tests fail**

Run:

```bash
cd apps/tldw-frontend
TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://localhost:3000 bunx playwright test e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line
```

Expected: new tests fail until missing page-object helpers and assertions are implemented.

**Step 3: Add the minimal page-object helpers and test assertions**

Implement helpers for:

- chat input/send and awaiting assistant response
- asserting selected-source context badges
- opening workspace search and interacting with one result
- locating a completed studio artifact from a real generation action

**Step 4: Run the workspace suites**

Run:

```bash
cd apps/tldw-frontend
TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://localhost:3000 bunx playwright test e2e/workflows/workspace-playground.spec.ts e2e/workflows/workspace-playground.parity.spec.ts e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line
```

Expected: all workspace-targeted suites remain green with stronger live-backend feature coverage.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts apps/tldw-frontend/e2e/utils/page-objects/WorkspacePlaygroundPage.ts
git commit -m "test: add live backend workspace feature coverage"
```

### Task 4: Final verification and security check

**Files:**
- Modify: touched files from Tasks 1-3 only
- Output: `/tmp/bandit_knowledge_workspace_e2e.json`

**Step 1: Run the targeted combined Playwright verification**

Run:

```bash
cd apps/tldw-frontend
TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://localhost:3000 bunx playwright test e2e/workflows/knowledge-qa.spec.ts e2e/workflows/workspace-playground.spec.ts e2e/workflows/workspace-playground.parity.spec.ts e2e/workflows/workspace-playground.real-backend.spec.ts --reporter=line
```

Expected: targeted route suites pass.

**Step 2: Run Bandit on the touched frontend test scope**

Run:

```bash
source .venv/bin/activate
python -m bandit -r apps/tldw-frontend/e2e -f json -o /tmp/bandit_knowledge_workspace_e2e.json
```

Expected: no new actionable findings in changed paths.

**Step 3: Self-review**

Check:

- no `|| true` assertions remain in the touched suites
- no blanket `try/catch` hides missing UI contracts
- request assertions only rely on stable, real contracts

**Step 4: Final clean run**

Re-run the targeted Playwright command if the Bandit or self-review changes anything.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e Docs/Plans/2026-03-16-knowledge-workspace-live-backend-e2e-design.md Docs/Plans/2026-03-16-knowledge-workspace-live-backend-e2e-implementation-plan.md
git commit -m "test: harden knowledge and workspace live backend e2e coverage"
```
