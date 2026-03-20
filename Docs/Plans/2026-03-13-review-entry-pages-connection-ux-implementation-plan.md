# Review Entry Pages Connection UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update the current Review entry pages so auth/setup/unreachable states render actionable guidance instead of generic offline messaging.

**Architecture:** Keep the changes local to `ViewMediaPage`, `MediaTrashPage`, and `ReviewPage`. Add focused connection-state tests first, verify they fail, then patch only the top-level render gates using `useConnectionUxState()` while preserving capability checks, demo behavior, and the `forceOffline` escape hatch.

**Tech Stack:** React, TypeScript, React Testing Library, Vitest, React Router

---

### Task 1: Add focused failing connection-state tests

**Files:**
- Create: `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.connection.test.tsx`
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaTrashPage.connection.test.tsx`
- Create: `apps/packages/ui/src/components/Review/__tests__/ReviewPage.connection.test.tsx`
- Test:
  - `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.connection.test.tsx`
  - `apps/packages/ui/src/components/Review/__tests__/MediaTrashPage.connection.test.tsx`
  - `apps/packages/ui/src/components/Review/__tests__/ReviewPage.connection.test.tsx`

**Step 1: Write the failing tests**

Add small harnesses that:
- mock `useServerOnline`
- mock `useConnectionUxState`
- mock `useServerCapabilities`
- mock `useDemoMode`
- mock `useNavigate`
- mock `useConnectionActions` where retry buttons are asserted

Cover:
- `ViewMediaPage` auth/setup/unreachable messaging and actions
- `MediaTrashPage` auth/setup/unreachable messaging and actions
- `ReviewPage` demo-mode auth warning
- `ReviewPage` non-demo setup guidance
- `ReviewPage forceOffline` preserving the generic offline branch

**Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Review/__tests__/ViewMediaPage.connection.test.tsx src/components/Review/__tests__/MediaTrashPage.connection.test.tsx src/components/Review/__tests__/ReviewPage.connection.test.tsx
```

Expected: FAIL because the pages still render generic offline states.

**Step 3: Commit**

Do not commit yet. Keep the tests red until the gate changes land.

### Task 2: Implement the minimal top-level gate changes

**Files:**
- Modify: `apps/packages/ui/src/components/Review/ViewMediaPage.tsx`
- Modify: `apps/packages/ui/src/components/Review/MediaTrashPage.tsx`
- Modify: `apps/packages/ui/src/components/Review/ReviewPage.tsx`
- Test:
  - `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.connection.test.tsx`
  - `apps/packages/ui/src/components/Review/__tests__/MediaTrashPage.connection.test.tsx`
  - `apps/packages/ui/src/components/Review/__tests__/ReviewPage.connection.test.tsx`

**Step 1: Write minimal implementation**

Update the three pages to:
- import `useConnectionUxState()`
- branch on `uxState` ahead of the generic offline fallback
- preserve capability and demo behavior
- keep `ReviewPage forceOffline` on the generic offline path
- add retry handling for unreachable `ViewMediaPage` and `MediaTrashPage`

Do not refactor downstream hooks or query `enabled` flags.

**Step 2: Run tests to verify they pass**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Review/__tests__/ViewMediaPage.connection.test.tsx src/components/Review/__tests__/MediaTrashPage.connection.test.tsx src/components/Review/__tests__/ReviewPage.connection.test.tsx
```

Expected: PASS.

**Step 3: Commit**

Do not commit yet. Finish targeted verification first.

### Task 3: Run targeted verification

**Files:**
- Modify: none
- Test:
  - `apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.connection.test.tsx`
  - `apps/packages/ui/src/components/Review/__tests__/MediaTrashPage.connection.test.tsx`
  - `apps/packages/ui/src/components/Review/__tests__/ReviewPage.connection.test.tsx`
  - `apps/packages/ui/src/routes/__tests__/option-media-route-guards.test.tsx`

**Step 1: Run focused tests**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/apps/packages/ui
bunx vitest run src/components/Review/__tests__/ViewMediaPage.connection.test.tsx src/components/Review/__tests__/MediaTrashPage.connection.test.tsx src/components/Review/__tests__/ReviewPage.connection.test.tsx src/routes/__tests__/option-media-route-guards.test.tsx
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
source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Review -f json -o /tmp/bandit_review_connection_ux.json
```

Expected: 0 findings. If Bandit reports TypeScript parse limitations, note that explicitly in the handoff.

**Step 4: Commit**

If the user wants a commit and the index is clean enough for a selective commit:

```bash
git add Docs/Plans/2026-03-13-review-entry-pages-connection-ux-design.md Docs/Plans/2026-03-13-review-entry-pages-connection-ux-implementation-plan.md apps/packages/ui/src/components/Review/ViewMediaPage.tsx apps/packages/ui/src/components/Review/MediaTrashPage.tsx apps/packages/ui/src/components/Review/ReviewPage.tsx apps/packages/ui/src/components/Review/__tests__/ViewMediaPage.connection.test.tsx apps/packages/ui/src/components/Review/__tests__/MediaTrashPage.connection.test.tsx apps/packages/ui/src/components/Review/__tests__/ReviewPage.connection.test.tsx
git commit -m "fix(ui): improve review connection guidance"
```

If unrelated staged work is present, skip committing and report that explicitly.
