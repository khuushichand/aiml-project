# Persona And Companion Connection UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the remaining boolean online entry gates in persona and companion with accurate auth/setup/unreachable connection UX while preserving each surface’s existing layout.

**Architecture:** Use `useConnectionUxState()` locally inside `sidepanel-persona` and `CompanionPage` rather than forcing `WorkspaceConnectionGate` into shells that have different chrome and navigation requirements.

**Tech Stack:** React, Vitest, React Router, shared connection store hooks, Ant Design

---

### Task 1: Add Failing Persona Connection UX Tests

**Files:**
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`

**Step 1: Write the failing test**

Add tests for:
- auth-required persona state shows targeted credentials guidance
- setup-required persona state shows setup guidance
- unreachable persona state still shows connectivity guidance

Mock `useConnectionUxState()` explicitly instead of only `useServerOnline()`.

**Step 2: Run test to verify it fails**

Run: `bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx --reporter=verbose`

Expected: FAIL because persona currently only distinguishes online vs offline.

**Step 3: Write minimal implementation**

In `sidepanel-persona.tsx`:
- replace the top-level `if (!isOnline)` branch with local `useConnectionUxState()` handling
- preserve the existing route header and `persona-route-root` shell
- keep capability and live-session logic after connection handling

**Step 4: Run test to verify it passes**

Run: `bunx vitest run src/routes/__tests__/sidepanel-persona.test.tsx --reporter=verbose`

Expected: PASS.

### Task 2: Add Failing Companion Connection UX Tests

**Files:**
- Create or modify: `apps/packages/ui/src/components/Option/Companion/__tests__/CompanionPage.connection.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/Companion/CompanionPage.tsx`

**Step 1: Write the failing test**

Add focused tests for:
- auth-required state renders credentials guidance
- setup-required state renders setup guidance
- unreachable state renders connectivity guidance
- connected state still reaches the feature capability flow

Use a narrow harness so the tests exercise only the top-level gating behavior.

**Step 2: Run test to verify it fails**

Run: `bunx vitest run src/components/Option/Companion/__tests__/CompanionPage.connection.test.tsx --reporter=verbose`

Expected: FAIL because companion currently only checks `useServerOnline()`.

**Step 3: Write minimal implementation**

In `CompanionPage.tsx`:
- introduce local `useConnectionUxState()` handling ahead of the current offline return
- preserve both `options` and `sidepanel` surface framing
- leave `hasPersonalization` unavailable behavior unchanged after connection passes

**Step 4: Run test to verify it passes**

Run: `bunx vitest run src/components/Option/Companion/__tests__/CompanionPage.connection.test.tsx --reporter=verbose`

Expected: PASS.

### Task 3: Re-verify Existing Persona Route Guard Coverage

**Files:**
- Modify if needed: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.blocker.test.tsx`

**Step 1: Run adjacent tests**

Run: `bunx vitest run src/routes/__tests__/sidepanel-persona.blocker.test.tsx --reporter=verbose`

Expected: PASS. If it fails due to connection-state harness changes, patch only the mock setup.

**Step 2: Make minimal test-harness fixes if needed**

Only update shared mocks required by the new top-level connection hook usage.

**Step 3: Re-run to verify**

Run the same blocker suite again and confirm it passes.

### Task 4: Verify The Touched Slice

**Files:**
- Verify all files touched in Tasks 1-3

**Step 1: Run targeted tests**

Run from `apps/packages/ui`:

```bash
bunx vitest run \
  src/routes/__tests__/sidepanel-persona.test.tsx \
  src/routes/__tests__/sidepanel-persona.blocker.test.tsx \
  src/components/Option/Companion/__tests__/CompanionPage.connection.test.tsx \
  --reporter=verbose
```

Expected: all targeted tests pass.

**Step 2: Run whitespace sanity check**

Run from repo root:

```bash
git diff --check
```

Expected: no whitespace errors.

**Step 3: Run Bandit on touched scope**

Run from repo root with project venv:

```bash
source .venv/bin/activate && python -m bandit -r \
  apps/packages/ui/src/routes \
  apps/packages/ui/src/components/Option/Companion \
  -f json -o /tmp/bandit_persona_companion_connection_ux.json
```

Expected: 0 findings in the touched scope.
