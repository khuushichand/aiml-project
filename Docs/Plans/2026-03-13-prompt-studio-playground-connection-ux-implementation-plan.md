# Prompt Studio Playground Connection UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update `PromptStudioPlaygroundPage` so auth/setup/unreachable states render actionable guidance instead of the generic offline warning.

**Architecture:** Keep the change local to `PromptStudioPlaygroundPage`. Add a focused React Query test harness, write failing connection-state tests first, then patch the top-level render gate using `useConnectionUxState()` and options-only navigation actions.

**Tech Stack:** React, TypeScript, React Query, React Testing Library, Vitest, React Router

---

### Task 1: Add focused failing connection-state tests

**Files:**
- Create: `apps/packages/ui/src/components/Option/PromptStudio/__tests__/PromptStudioPlaygroundPage.connection.test.tsx`
- Modify: none
- Test: `apps/packages/ui/src/components/Option/PromptStudio/__tests__/PromptStudioPlaygroundPage.connection.test.tsx`

**Step 1: Write the failing test**

Create a small test harness that:
- wraps the component in `QueryClientProvider`
- mocks `useServerOnline`
- mocks `useConnectionUxState`
- mocks `useNavigate`
- mocks Prompt Studio services with stable resolved values

Add tests for:
- auth guidance and `/settings/tldw`
- setup guidance and `/`
- unreachable guidance and `/settings/health`
- `testing` falling through to the existing loading state

**Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Option/PromptStudio/__tests__/PromptStudioPlaygroundPage.connection.test.tsx
```

Expected: FAIL because the page still renders the generic offline `Alert`.

**Step 3: Commit**

Do not commit yet. Keep the test red until the implementation lands.

### Task 2: Implement the minimal connection-state gate

**Files:**
- Modify: `apps/packages/ui/src/components/Option/PromptStudio/PromptStudioPlaygroundPage.tsx`
- Test: `apps/packages/ui/src/components/Option/PromptStudio/__tests__/PromptStudioPlaygroundPage.connection.test.tsx`

**Step 1: Write minimal implementation**

Update the page to:
- import `useNavigate`
- import `useConnectionUxState`
- add options-only navigation handlers
- branch on `uxState` before the generic `!online` alert
- preserve the existing `testing` and loading flow

Use Ant Design `Alert` actions/buttons rather than introducing a new shared gate.

**Step 2: Run test to verify it passes**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Option/PromptStudio/__tests__/PromptStudioPlaygroundPage.connection.test.tsx
```

Expected: PASS.

**Step 3: Commit**

Do not commit yet. Finish verification first because the worktree is already dirty.

### Task 3: Run targeted verification

**Files:**
- Modify: none
- Test:
  - `apps/packages/ui/src/components/Option/PromptStudio/__tests__/PromptStudioPlaygroundPage.connection.test.tsx`
  - `apps/packages/ui/src/components/Option/Prompt/__tests__/StudioTabContainer.stage6-navigation.test.tsx` only if the local change unexpectedly affects shared Prompt Studio assumptions

**Step 1: Run focused tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Option/PromptStudio/__tests__/PromptStudioPlaygroundPage.connection.test.tsx
```

If shared behavior looks affected, also run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Option/Prompt/__tests__/StudioTabContainer.stage6-navigation.test.tsx
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
source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/PromptStudio -f json -o /tmp/bandit_prompt_studio_playground_connection.json
```

Expected: 0 findings. If Bandit reports TypeScript AST parse errors, note that limitation explicitly in the handoff.

**Step 4: Commit**

If the user wants a commit and the index is clean enough for a selective commit:

```bash
git add Docs/Plans/2026-03-13-prompt-studio-playground-connection-ux-design.md Docs/Plans/2026-03-13-prompt-studio-playground-connection-ux-implementation-plan.md apps/packages/ui/src/components/Option/PromptStudio/PromptStudioPlaygroundPage.tsx apps/packages/ui/src/components/Option/PromptStudio/__tests__/PromptStudioPlaygroundPage.connection.test.tsx
git commit -m "fix(ui): improve prompt studio connection guidance"
```

If unrelated staged work is present, skip committing and report that explicitly.
