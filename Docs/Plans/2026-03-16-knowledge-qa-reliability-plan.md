# Knowledge QA Reliability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the Knowledge QA reliability issues around shortcut scope, thread-load failure recovery, route hydration retries, and source-list storage resilience.

**Architecture:** Keep the changes narrow and behavioral. Add failing tests around the existing Knowledge QA surface first, then patch the smallest number of runtime paths: `SearchBar` for shortcut scoping, `KnowledgeQAProvider` for transactional thread loading, `index.tsx` for retry-aware route hydration, and `SourceList` for guarded storage access.

**Tech Stack:** React, Vitest, Testing Library, Playwright-adjacent UI patterns already used in `apps/packages/ui`.

---

### Task 1: Shortcut Scope Regression Test

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/SearchBar.behavior.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/SearchBar.tsx`

**Step 1: Write the failing test**

Add a test proving `Cmd/Ctrl+K` does not clear Knowledge QA state when focus is inside another editable control.

**Step 2: Run test to verify it fails**

Run:
```bash
bunx vitest run src/components/Option/KnowledgeQA/__tests__/SearchBar.behavior.test.tsx --config vitest.config.ts
```

**Step 3: Write minimal implementation**

Update `SearchBar.tsx` so global shortcuts ignore editable and dialog-contained targets.

**Step 4: Run test to verify it passes**

Run the same command and confirm the suite is green.

### Task 2: Thread Failure Recovery Test

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.history.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx`

**Step 1: Write the failing test**

Add a provider test showing a failed `selectThread()` call preserves the existing visible query/results state and sets an error instead of blanking the page.

**Step 2: Run test to verify it fails**

Run:
```bash
bunx vitest run src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.history.test.tsx --config vitest.config.ts
```

**Step 3: Write minimal implementation**

Make thread loading transactional and surface a recoverable error on failure.

**Step 4: Run test to verify it passes**

Run the same command and confirm the suite is green.

### Task 3: Route Hydration Retry Tests

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/index.tsx`

**Step 1: Write the failing tests**

Add tests showing `/knowledge/thread/:id` and `/knowledge/shared/:token` can retry hydration after an initial failure on the same route.

**Step 2: Run test to verify it fails**

Run:
```bash
bunx vitest run src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx --config vitest.config.ts
```

**Step 3: Write minimal implementation**

Adjust route hydration bookkeeping so success and failure are tracked separately and same-route retries remain possible.

**Step 4: Run test to verify it passes**

Run the same command and confirm the suite is green.

### Task 4: SourceList Storage Resilience Test

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/SourceList.tsx`

**Step 1: Write the failing test**

Add a test that simulates `localStorage` get/set failures and verifies `SourceList` still renders and remains usable.

**Step 2: Run test to verify it fails**

Run:
```bash
bunx vitest run src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx --config vitest.config.ts
```

**Step 3: Write minimal implementation**

Wrap filter storage hydration and persistence in safe helpers with fallbacks.

**Step 4: Run test to verify it passes**

Run the same command and confirm the suite is green.

### Task 5: Focused Verification

**Files:**
- Verify only; no intentional code changes

**Step 1: Run focused Knowledge QA suites**

Run:
```bash
bunx vitest run \
  src/components/Option/KnowledgeQA/__tests__/SearchBar.behavior.test.tsx \
  src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.history.test.tsx \
  src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx \
  src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.branch-share.test.tsx \
  src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx \
  --config vitest.config.ts
```

**Step 2: Run Bandit on touched scope**

Run:
```bash
source .venv/bin/activate && python -m bandit -r \
  apps/packages/ui/src/components/Option/KnowledgeQA \
  -f json -o /tmp/bandit_knowledge_qa_reliability.json
```

**Step 3: Confirm outputs**

Expected:
- focused Vitest suites pass
- Bandit returns zero results
