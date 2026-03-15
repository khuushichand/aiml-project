# Companion Consent Gating Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Require explicit user opt-in before any companion workspace read or write, while keeping the feature discoverable and clearly explaining what enabling it stores.

**Architecture:** Reuse the existing personalization profile and opt-in endpoints as the single consent source of truth. Gate companion backend endpoints on `profile.enabled`, then update the option and sidepanel companion flows to show a consent-required state and route users through explicit enablement before storing or loading companion data.

**Tech Stack:** FastAPI, Pydantic, PersonalizationDB, React, Vitest, Testing Library

**Status:** Complete

---

### Task 1: Backend opt-in enforcement

**Status:** Complete

**Files:**
- Modify: `tldw_Server_API/tests/Personalization/test_companion_api.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/companion.py`

**Step 1: Write the failing tests**

Add tests asserting companion `GET /activity`, `POST /activity`, `POST /check-ins`, and `GET /knowledge` reject when the personalization profile exists but `enabled` is false.

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Personalization/test_companion_api.py -k "opt_in_required"`
Expected: FAIL because the endpoints currently allow access.

**Step 3: Write minimal implementation**

Add a helper in `companion.py` that loads the current user profile and raises a consistent HTTP error when `enabled` is false, then call it from all companion endpoints.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Personalization/test_companion_api.py -k "opt_in_required"`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Personalization/test_companion_api.py tldw_Server_API/app/api/v1/endpoints/companion.py
git commit -m "fix: require consent for companion endpoints"
```

### Task 2: Companion workspace opt-in UX

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/services/companion.ts`
- Modify: `apps/packages/ui/src/components/Option/Companion/CompanionPage.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/option-companion.test.tsx`

**Step 1: Write the failing tests**

Add tests for a consent-required state when personalization capability exists but the user profile is disabled, and a test for enabling personalization then loading the workspace.

**Step 2: Run test to verify it fails**

Run: `bunx vitest run --config vitest.config.ts src/routes/__tests__/option-companion.test.tsx`
Expected: FAIL because the route currently loads the workspace immediately.

**Step 3: Write minimal implementation**

Add profile fetch and opt-in helpers to the companion service, then update `CompanionPage` to render an explicit enablement screen until consent is granted.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run --config vitest.config.ts src/routes/__tests__/option-companion.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/companion.ts apps/packages/ui/src/components/Option/Companion/CompanionPage.tsx apps/packages/ui/src/routes/__tests__/option-companion.test.tsx
git commit -m "feat: add companion consent onboarding"
```

### Task 3: Sidepanel and extension consent handling

**Status:** Complete

**Files:**
- Modify: `apps/packages/ui/src/routes/sidepanel-companion.tsx`
- Modify: `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-companion.test.tsx`
- Modify: `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx`

**Step 1: Write the failing tests**

Add tests asserting pending extension captures show a consent-required banner on companion opt-in failure, and persona draft save-to-companion surfaces the same requirement.

**Step 2: Run test to verify it fails**

Run: `bunx vitest run --config vitest.config.ts src/routes/__tests__/sidepanel-companion.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx`
Expected: FAIL because these routes currently report generic errors.

**Step 3: Write minimal implementation**

Map the backend consent-required response into explicit UI messaging and avoid clearing pending captures until the user enables personalization.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run --config vitest.config.ts src/routes/__tests__/sidepanel-companion.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/packages/ui/src/routes/sidepanel-companion.tsx apps/packages/ui/src/routes/sidepanel-persona.tsx apps/packages/ui/src/routes/__tests__/sidepanel-companion.test.tsx apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx
git commit -m "fix: surface companion consent requirements"
```

### Task 4: Verification and PR update

**Status:** Complete

**Files:**
- Modify: `docs/plans/2026-03-10-companion-consent-gating-implementation-plan.md`

**Step 1: Run targeted backend and frontend verification**

Run:
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Personalization/test_companion_api.py`
- `bunx vitest run --config vitest.config.ts src/routes/__tests__/option-companion.test.tsx src/routes/__tests__/sidepanel-companion.test.tsx src/routes/__tests__/sidepanel-persona.test.tsx`

Expected: PASS

**Step 2: Run security and diff hygiene checks**

Run:
- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/companion.py -f json -o /tmp/bandit_companion_consent.json`
- `git diff --check`

Expected: no new Bandit findings, clean diff formatting

**Step 3: Update plan status**

Mark completed tasks in this plan file.

**Step 4: Commit**

```bash
git add docs/plans/2026-03-10-companion-consent-gating-implementation-plan.md
git commit -m "docs: record companion consent gating verification"
```
