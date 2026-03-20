# Demo Workspaces Connection UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Quiz, Flashcards, and Media preserve demo preview while surfacing real auth/setup/unreachable states, and make their non-demo offline states connection-aware.

**Architecture:** Keep the change local to each workspace. Use `useConnectionUxState()` in each page, preserve demo precedence visually, and add focused tests per surface instead of introducing a new shared abstraction.

**Tech Stack:** React, TypeScript, React Testing Library, Vitest, React Router

---

### Task 1: Extend Quiz connection-state tests

**Files:**
- Modify: `apps/packages/ui/src/components/Quiz/__tests__/QuizWorkspace.connection-state.test.tsx`
- Modify: none yet in production code
- Test: `apps/packages/ui/src/components/Quiz/__tests__/QuizWorkspace.connection-state.test.tsx`

**Step 1: Write the failing test**

Extend the existing Quiz harness to also mock `useConnectionUxState()` while preserving the current `useConnectionActions()` mock.

Add tests for:
- demo preview remains visible in auth-required state
- demo preview remains visible in unreachable state
- non-demo setup/auth guidance shows actionable copy

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Quiz/__tests__/QuizWorkspace.connection-state.test.tsx
```

Expected: FAIL because Quiz still uses only `isOnline` and `demoEnabled`.

### Task 2: Add Flashcards connection-state tests

**Files:**
- Create: `apps/packages/ui/src/components/Flashcards/__tests__/FlashcardsWorkspace.connection-state.test.tsx`
- Test: `apps/packages/ui/src/components/Flashcards/__tests__/FlashcardsWorkspace.connection-state.test.tsx`

**Step 1: Write the failing test**

Create a focused Flashcards harness with mocks for:
- `useServerOnline`
- `useConnectionUxState`
- `useDemoMode`
- `useServerCapabilities`
- `useScrollToServerCard`
- `useConnectionActions`

Add tests for:
- demo preview plus auth warning
- demo preview plus unreachable warning
- non-demo setup/auth guidance

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Flashcards/__tests__/FlashcardsWorkspace.connection-state.test.tsx
```

Expected: FAIL because Flashcards still renders generic offline/demo branches.

### Task 3: Add Media connection-state tests

**Files:**
- Create: `apps/packages/ui/src/routes/__tests__/option-media-multi.connection-state.test.tsx`
- Test: `apps/packages/ui/src/routes/__tests__/option-media-multi.connection-state.test.tsx`

**Step 1: Write the failing test**

Create a dedicated Media connection-state harness rather than changing the route-wrapper test.

Mock:
- `useServerOnline`
- `useConnectionUxState`
- `useDemoMode`
- `useServerCapabilities`
- `useNavigate`

Add tests for:
- demo preview plus auth warning
- non-demo setup/auth guidance
- non-demo unreachable guidance with diagnostics navigation

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/routes/__tests__/option-media-multi.connection-state.test.tsx
```

Expected: FAIL because Media still uses only `isOnline` and `demoEnabled`.

### Task 4: Implement minimal workspace changes

**Files:**
- Modify: `apps/packages/ui/src/components/Quiz/QuizWorkspace.tsx`
- Modify: `apps/packages/ui/src/components/Flashcards/FlashcardsWorkspace.tsx`
- Modify: `apps/packages/ui/src/routes/option-media-multi.tsx`
- Test:
  - `apps/packages/ui/src/components/Quiz/__tests__/QuizWorkspace.connection-state.test.tsx`
  - `apps/packages/ui/src/components/Flashcards/__tests__/FlashcardsWorkspace.connection-state.test.tsx`
  - `apps/packages/ui/src/routes/__tests__/option-media-multi.connection-state.test.tsx`

**Step 1: Write minimal implementation**

For each page:
- import `useConnectionUxState`
- derive local warning/guidance copy from `uxState`
- keep demo preview intact when `demoEnabled` is true
- use small inline warning UI in demo mode
- replace only the non-demo offline branch with state-aware guidance
- treat `testing` as neutral: no demo warning, no auth/setup/unreachable guidance

**Step 2: Run tests to verify they pass**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Quiz/__tests__/QuizWorkspace.connection-state.test.tsx src/components/Flashcards/__tests__/FlashcardsWorkspace.connection-state.test.tsx src/routes/__tests__/option-media-multi.connection-state.test.tsx
```

Expected: PASS.

### Task 5: Targeted verification

**Files:**
- Modify: none
- Test:
  - `apps/packages/ui/src/components/Quiz/__tests__/QuizWorkspace.connection-state.test.tsx`
  - `apps/packages/ui/src/components/Flashcards/__tests__/FlashcardsWorkspace.connection-state.test.tsx`
  - `apps/packages/ui/src/routes/__tests__/option-media-multi.connection-state.test.tsx`
  - `apps/packages/ui/src/routes/__tests__/option-media-route-guards.test.tsx`

**Step 1: Run focused tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Quiz/__tests__/QuizWorkspace.connection-state.test.tsx src/components/Flashcards/__tests__/FlashcardsWorkspace.connection-state.test.tsx src/routes/__tests__/option-media-multi.connection-state.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx
```

Expected: PASS.

**Step 2: Check patch cleanliness**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2
git diff --check
```

Expected: no output.

**Step 3: Run Bandit on the touched scope**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2
source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Quiz apps/packages/ui/src/components/Flashcards apps/packages/ui/src/routes/option-media-multi.tsx apps/packages/ui/src/routes/__tests__/option-media-multi.connection-state.test.tsx -f json -o /tmp/bandit_demo_workspaces_connection.json
```

Expected: 0 findings. If Bandit reports TypeScript parse limitations, note that explicitly.

**Step 4: Commit**

Only commit if the user asks and the staged scope is isolated:

```bash
git add Docs/Plans/2026-03-13-demo-workspaces-connection-ux-design.md Docs/Plans/2026-03-13-demo-workspaces-connection-ux-implementation-plan.md apps/packages/ui/src/components/Quiz/QuizWorkspace.tsx apps/packages/ui/src/components/Quiz/__tests__/QuizWorkspace.connection-state.test.tsx apps/packages/ui/src/components/Flashcards/FlashcardsWorkspace.tsx apps/packages/ui/src/components/Flashcards/__tests__/FlashcardsWorkspace.connection-state.test.tsx apps/packages/ui/src/routes/option-media-multi.tsx apps/packages/ui/src/routes/__tests__/option-media-multi.connection-state.test.tsx
git commit -m "fix(ui): surface connection state in demo workspaces"
```
