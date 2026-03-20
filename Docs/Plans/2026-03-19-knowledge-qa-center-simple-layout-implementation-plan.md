# Knowledge QA Simple Layout Centering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Center the Knowledge QA simple-mode content lane inside the `/knowledge` workspace without widening the content or altering research-mode side-panel behavior.

**Architecture:** Keep the route-level shell unchanged and adjust the simple-mode lane inside `KnowledgeQALayout.tsx`, because that component owns the hero, recent searches, composer, and results column. Use a focused golden-layout test to pin the class contract for the modified wrapper, then implement the smallest change that satisfies the test and preserves research mode.

**Tech Stack:** React, TypeScript, Tailwind utility classes, Vitest, Testing Library

---

## Stage 1: Guardrail Test
**Goal**: Capture the expected centered-lane class contract before changing production code.
**Success Criteria**: The target test fails before implementation and describes the missing centering behavior.
**Tests**: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`
**Status**: Not Started

### Task 1: Strengthen the simple-mode layout test

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`

**Step 1: Write the failing test**

Add or update the existing simple-mode empty-state assertions so the test checks the exact search shell or inner lane class contract that should guarantee centered layout in simple mode.

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate && bunx vitest run apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
```

Expected: FAIL because the current class contract does not include the new centering rule.

**Step 3: Do not touch production code yet**

Stop once the test fails for the expected reason.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
git commit -m "test: pin knowledge qa simple layout centering"
```

## Stage 2: Minimal Layout Change
**Goal**: Implement the smallest simple-mode layout adjustment that centers the content lane.
**Success Criteria**: Empty state and simple results state use the same centered lane; research mode remains unchanged.
**Tests**: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`
**Status**: Not Started

### Task 2: Update the simple-mode lane in `KnowledgeQALayout`

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx`

**Step 1: Write minimal implementation**

Adjust the container that owns the simple-mode search shell and, if needed, the simple-mode results lane so:

- the content lane remains `max-w-3xl`
- the lane is explicitly centered within the available workspace width
- research-mode wrappers remain unchanged

**Step 2: Run focused test to verify it passes**

Run:

```bash
source .venv/bin/activate && bunx vitest run apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
```

Expected: PASS

**Step 3: Sanity-check affected code paths**

Read the updated layout and confirm:

- no class changes were applied to research-mode wrappers
- evidence rail and history pane conditions are untouched
- the simple-mode results shell still uses the same max width

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
git commit -m "fix: center knowledge qa simple layout"
```

## Stage 3: Verification
**Goal**: Validate the change with automated tests, a security pass on touched scope, and a visual sanity check.
**Success Criteria**: Focused tests pass, Bandit reports no new issues in touched scope, and the `/knowledge` page appears centered locally.
**Tests**:
- `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`
- visual check of `/knowledge`
**Status**: Not Started

### Task 3: Run verification commands

**Files:**
- Modify: none

**Step 1: Run the focused frontend test suite**

Run:

```bash
source .venv/bin/activate && bunx vitest run apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
```

Expected: PASS

**Step 2: Run Bandit on touched scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/KnowledgeQA -f json -o /tmp/bandit_knowledge_qa_centering.json
```

Expected: JSON report generated with no new findings in touched code.

**Step 3: Perform a browser sanity check**

Verify on `/knowledge`:

- simple empty state is visually centered
- content width looks unchanged
- research mode still renders as before if toggled

**Step 4: Commit**

```bash
git add docs/plans/2026-03-19-knowledge-qa-center-simple-layout-design.md docs/plans/2026-03-19-knowledge-qa-center-simple-layout-implementation-plan.md
git commit -m "docs: add knowledge qa centering design and plan"
```
