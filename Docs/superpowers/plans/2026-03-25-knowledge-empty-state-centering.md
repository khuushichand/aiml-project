# Knowledge Empty State Centering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `/knowledge` simple-mode empty-state stack upward as a single unit so the hero, recent sessions, and composer no longer sit too low in the viewport.

**Architecture:** Keep the existing `KnowledgeQALayout` structure and adjust only the empty-state shell classes that control vertical alignment. Guard the behavior with a layout-focused test so results mode and research mode remain unchanged.

**Tech Stack:** React, Tailwind utility classes, Vitest, Testing Library

---

### Task 1: Guard The Empty-State Shell Layout

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/layout/KnowledgeQALayout.tsx`
- Test: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`

- [x] **Step 1: Write the failing test**

Update the empty-state layout assertion so it expects a top-biased shell instead of true vertical centering.

- [x] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && bunx vitest run apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`

Expected: FAIL because `knowledge-search-shell` still uses centered alignment classes.

- [x] **Step 3: Write minimal implementation**

Change the simple empty-state shell classes in `KnowledgeQALayout.tsx` so the full stack remains horizontally centered but is vertically biased upward with top padding and start alignment.

- [x] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && bunx vitest run apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx`

Expected: PASS

- [x] **Step 5: Run focused verification**

Run:
- `source .venv/bin/activate && bunx vitest run apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQALayout.behavior.test.tsx`
- `source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/KnowledgeQA -f json -o /tmp/bandit_knowledge_empty_state_centering.json`

Expected: PASS and no new actionable findings in the touched scope.
