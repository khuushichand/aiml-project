# Shared Banner And Admin Settings Connection UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update the shared connection banner and warning-only admin/settings surfaces so auth/setup/unreachable states show actionable guidance instead of generic offline messaging.

**Architecture:** Keep the shared change localized to `ConnectFeatureBanner`, then patch `KnowledgeQA`, `ModerationPlaygroundShell`, `GuardianSettings`, and `evaluations.tsx` with small state-aware branches. Add focused failing tests first, verify red, then make the minimal render-layer changes without refactoring lower-level hooks.

**Tech Stack:** React, TypeScript, React Testing Library, Vitest, React Router, Ant Design

---

### Task 1: Add focused failing connection-state tests

**Files:**
- Create: `apps/packages/ui/src/components/Common/__tests__/ConnectFeatureBanner.connection.test.tsx`
- Create: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.connection.test.tsx`
- Create: `apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlaygroundShell.connection.test.tsx`
- Create: `apps/packages/ui/src/components/Option/Settings/__tests__/GuardianSettings.connection.test.tsx`
- Create: `apps/packages/ui/src/components/Option/Settings/__tests__/evaluations.connection.test.tsx`

**Step 1: Write the failing tests**

Cover:

- `ConnectFeatureBanner` auth/setup/unreachable actions and `testing` suppression
- `KnowledgeQA` auth/setup guidance and unreachable retry preservation
- `ModerationPlaygroundShell` warning copy for auth/setup/unreachable and `testing` suppression
- `GuardianSettings` warning copy for auth/setup/unreachable and `testing` suppression
- `EvaluationsSettings` warning copy for auth/setup/unreachable and `testing` suppression

Reuse the lightest existing harnesses where possible:

- `GuardianSettings.test.tsx`
- `ModerationPlaygroundShell.test.tsx`
- `KnowledgeQA.golden-layout.test.tsx`

**Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Common/__tests__/ConnectFeatureBanner.connection.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.connection.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlaygroundShell.connection.test.tsx src/components/Option/Settings/__tests__/GuardianSettings.connection.test.tsx src/components/Option/Settings/__tests__/evaluations.connection.test.tsx
```

Expected: FAIL because the banner and warning surfaces still render generic offline/setup copy.

### Task 2: Implement the minimal render-layer changes

**Files:**
- Modify: `apps/packages/ui/src/components/Common/ConnectFeatureBanner.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/index.tsx`
- Modify: `apps/packages/ui/src/components/Option/ModerationPlayground/ModerationPlaygroundShell.tsx`
- Modify: `apps/packages/ui/src/components/Option/Settings/GuardianSettings.tsx`
- Modify: `apps/packages/ui/src/components/Option/Settings/evaluations.tsx`

**Step 1: Write minimal implementation**

Update `ConnectFeatureBanner` to:

- import `useServerOnline()` and `useConnectionUxState()`
- render built-in auth/setup/unreachable copy and actions
- render nothing during `testing`
- preserve current caller-driven fallback behavior otherwise

Update the local pages to:

- branch on `uxState` only at the render layer
- keep existing layout and capability behavior
- keep KnowledgeQA retry/countdown behavior for unreachable/generic offline
- suppress warning-only pages during `testing`

**Step 2: Run the new tests to verify they pass**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Common/__tests__/ConnectFeatureBanner.connection.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.connection.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlaygroundShell.connection.test.tsx src/components/Option/Settings/__tests__/GuardianSettings.connection.test.tsx src/components/Option/Settings/__tests__/evaluations.connection.test.tsx
```

Expected: PASS.

### Task 3: Run targeted verification

**Files:**
- Modify: none

**Step 1: Run focused and nearby tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Common/__tests__/ConnectFeatureBanner.connection.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.connection.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlaygroundShell.connection.test.tsx src/components/Option/Settings/__tests__/GuardianSettings.connection.test.tsx src/components/Option/Settings/__tests__/evaluations.connection.test.tsx src/components/Option/Settings/__tests__/GuardianSettings.test.tsx src/components/Option/ModerationPlayground/__tests__/ModerationPlaygroundShell.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx
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
source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Common apps/packages/ui/src/components/Option/KnowledgeQA apps/packages/ui/src/components/Option/ModerationPlayground apps/packages/ui/src/components/Option/Settings -f json -o /tmp/bandit_shared_banner_admin_connection.json
```

Expected: 0 findings. If Bandit parse limitations appear, note them explicitly.

**Step 4: Commit**

If the user wants a commit and the index is clean enough for a selective commit:

```bash
git add Docs/Plans/2026-03-13-shared-banner-admin-settings-connection-ux-design.md Docs/Plans/2026-03-13-shared-banner-admin-settings-connection-ux-implementation-plan.md apps/packages/ui/src/components/Common/ConnectFeatureBanner.tsx apps/packages/ui/src/components/Option/KnowledgeQA/index.tsx apps/packages/ui/src/components/Option/ModerationPlayground/ModerationPlaygroundShell.tsx apps/packages/ui/src/components/Option/Settings/GuardianSettings.tsx apps/packages/ui/src/components/Option/Settings/evaluations.tsx apps/packages/ui/src/components/Common/__tests__/ConnectFeatureBanner.connection.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.connection.test.tsx apps/packages/ui/src/components/Option/ModerationPlayground/__tests__/ModerationPlaygroundShell.connection.test.tsx apps/packages/ui/src/components/Option/Settings/__tests__/GuardianSettings.connection.test.tsx apps/packages/ui/src/components/Option/Settings/__tests__/evaluations.connection.test.tsx
git commit -m "fix(ui): improve admin connection guidance"
```

If unrelated staged work is present, skip committing and report that explicitly.
