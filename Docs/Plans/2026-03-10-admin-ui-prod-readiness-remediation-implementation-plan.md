# Admin UI Production Readiness Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the remaining `admin-ui` production-readiness gaps so the app has truthful quality gates, credible privileged-flow verification, and a release process that matches the current control-plane risk.

**Architecture:** Remediate in layers. First restore trustworthy local and CI signals by fixing the current lint/build blockers and clearing strict TypeScript failures. Then harden release confidence with browser smoke coverage and CI wiring. Finally reduce regression pressure in the largest modules after the production gate is restored.

**Tech Stack:** Next.js 15 App Router, React 19, TypeScript 5, Vitest, React Testing Library, Bun, GitHub Actions, Playwright using existing repo patterns from `apps/tldw-frontend/`.

---

## Stage 1: Restore Truthful Quality Gates
**Goal:** Make `lint`, `build`, and the main plan-gated flows reflect the actual code quality instead of failing early on known issues or hiding type debt.
**Success Criteria:** `bun run lint` passes, `bun run build` no longer fails on current ESLint issues, and the billing gate continues to behave correctly.
**Tests:** `bunx vitest run components/__tests__/PlanGuard.test.tsx app/onboarding/__tests__/page.test.tsx app/plans/__tests__/page.test.tsx`, `bun run lint`, `bun run build`
**Status:** Not Started

### Task 1: Fix the current lint and build blockers

**Files:**
- Modify: `admin-ui/components/PlanGuard.tsx`
- Modify: `admin-ui/components/__tests__/PlanGuard.test.tsx`
- Modify: `admin-ui/app/onboarding/page.tsx`
- Modify: `admin-ui/app/onboarding/__tests__/page.test.tsx`
- Modify: `admin-ui/app/plans/page.tsx`

**Step 1: Write the failing test**

Add a regression case in `admin-ui/components/__tests__/PlanGuard.test.tsx` that proves the guard renders children immediately when billing is disabled and does not fetch an org subscription.

```tsx
it('renders children immediately when billing is disabled', async () => {
  vi.mocked(isBillingEnabled).mockReturnValue(false);
  const getOrgSubscription = vi.spyOn(api, 'getOrgSubscription');

  render(<PlanGuard requiredPlan="pro"><div>Allowed</div></PlanGuard>);

  expect(await screen.findByText('Allowed')).toBeInTheDocument();
  expect(getOrgSubscription).not.toHaveBeenCalled();
});
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run components/__tests__/PlanGuard.test.tsx -t "renders children immediately when billing is disabled"`

Expected: FAIL if the current guard still depends on synchronous `setState` inside the effect.

**Step 3: Write minimal implementation**

Refactor `admin-ui/components/PlanGuard.tsx` so the non-billing path is derived before the effect, and keep the effect only for the async subscription fetch path.

```tsx
const billingEnabled = isBillingEnabled();
const [allowed, setAllowed] = useState<boolean | null>(billingEnabled ? null : true);

useEffect(() => {
  if (!billingEnabled) return;
  if (orgLoading || !selectedOrg) return;
  // existing async subscription fetch
}, [billingEnabled, orgLoading, requiredPlan, selectedOrg]);
```

Then remove the unused local bindings that currently fail ESLint:

- `handleSubmit` in `admin-ui/app/onboarding/page.tsx`
- `mockedCreateOnboardingSession` in `admin-ui/app/onboarding/__tests__/page.test.tsx`
- `PlanTier` import in `admin-ui/app/plans/page.tsx`

**Step 4: Run tests to verify behavior and lint**

Run: `bunx vitest run components/__tests__/PlanGuard.test.tsx app/onboarding/__tests__/page.test.tsx app/plans/__tests__/page.test.tsx`

Expected: PASS

Run: `bun run lint`

Expected: PASS with no `react-hooks/set-state-in-effect` or `no-unused-vars` failures.

**Step 5: Run the build to verify the lint failure is gone**

Run: `bun run build`

Expected: BUILD proceeds past linting; any remaining failures should now be TypeScript or config-related only.

**Step 6: Commit**

```bash
git add admin-ui/components/PlanGuard.tsx admin-ui/components/__tests__/PlanGuard.test.tsx admin-ui/app/onboarding/page.tsx admin-ui/app/onboarding/__tests__/page.test.tsx admin-ui/app/plans/page.tsx
git commit -m "fix(admin-ui): clear plan guard lint blockers"
```

## Stage 2: Remove Hidden Type Debt And Re-enable Type Safety
**Goal:** Make `bunx tsc --noEmit` and `next build` trustworthy by fixing the current strict-type failures and removing `ignoreBuildErrors`.
**Success Criteria:** `bunx tsc --noEmit` passes, `next.config.js` no longer suppresses build type errors, and `bun run build` passes without skipping type validation.
**Tests:** `bunx tsc --noEmit`, targeted Vitest suites for touched files, `bun run build`
**Status:** Not Started

### Task 2: Restore test matcher typing and Next page-module compatibility

**Files:**
- Modify: `admin-ui/tsconfig.json`
- Create: `admin-ui/vitest.d.ts`
- Modify: `admin-ui/app/monitoring/page.tsx`
- Create: `admin-ui/app/monitoring/status-utils.ts`
- Test: `admin-ui/app/monitoring/__tests__/page.test.tsx`

**Step 1: Add the failing type gate**

Run: `bunx tsc --noEmit`

Expected: FAIL with matcher typing errors such as `toBeInTheDocument` and the `.next/types/app/monitoring/page.ts` export error for `normalizeHealthStatus`.

**Step 2: Add the missing test matcher declaration**

Create `admin-ui/vitest.d.ts` with the matcher imports used by the test suite.

```ts
/// <reference types="vitest/globals" />
import '@testing-library/jest-dom/vitest';
```

Update `admin-ui/tsconfig.json` so the declaration file is included in typecheck.

**Step 3: Move the exported page helper out of the App Router page module**

Extract the exported status-normalization helper from `admin-ui/app/monitoring/page.tsx` into `admin-ui/app/monitoring/status-utils.ts`, then import it back into the page and tests.

```ts
export function normalizeHealthStatus(status?: string): SystemHealthStatus {
  // existing normalization logic
}
```

This keeps the App Router page module contract clean for Next-generated `.next/types`.

**Step 4: Re-run the focused suite and typecheck**

Run: `bunx vitest run admin-ui/app/monitoring/__tests__/page.test.tsx`

Expected: PASS

Run: `bunx tsc --noEmit`

Expected: FAIL, but the matcher-type errors and `app/monitoring/page` export error should be gone.

**Step 5: Commit**

```bash
git add admin-ui/tsconfig.json admin-ui/vitest.d.ts admin-ui/app/monitoring/page.tsx admin-ui/app/monitoring/status-utils.ts admin-ui/app/monitoring/__tests__/page.test.tsx
git commit -m "fix(admin-ui): restore test and page-module typings"
```

### Task 3: Burn down the remaining strict TypeScript runtime errors

**Files:**
- Modify: `admin-ui/components/PermissionGuard.tsx`
- Create: `admin-ui/components/__tests__/PermissionGuard.test.tsx`
- Modify: `admin-ui/components/ErrorBoundary.tsx`
- Create: `admin-ui/components/__tests__/ErrorBoundary.test.tsx`
- Modify: `admin-ui/components/users/ApiKeyCreateForm.tsx`
- Modify: `admin-ui/components/data-ops/MaintenanceSection.tsx`
- Modify: `admin-ui/app/dependencies/page.tsx`
- Modify: `admin-ui/lib/export.ts`
- Modify: `admin-ui/lib/use-user-api-keys.ts`
- Modify: `admin-ui/middleware.ts`

**Step 1: Add focused regression tests around shared auth and error components**

Create tests for the currently untested shared components:

`admin-ui/components/__tests__/PermissionGuard.test.tsx`

```tsx
it('keeps the user in the permission context after a successful refresh', async () => {
  vi.mocked(api.getCurrentUser).mockResolvedValue(mockUser);
  vi.mocked(api.getUserEffectivePermissions).mockResolvedValue({ permissions: ['read:users'] });
  render(<PermissionProvider><ProtectedChild /></PermissionProvider>);
  expect(await screen.findByText('Protected')).toBeInTheDocument();
});
```

`admin-ui/components/__tests__/ErrorBoundary.test.tsx`

```tsx
it('resets cleanly before retry exhaustion', async () => {
  render(<ErrorBoundary><ThrowOnce /></ErrorBoundary>);
  await user.click(screen.getByRole('button', { name: /try again/i }));
  expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument();
});
```

**Step 2: Run tests to verify they fail**

Run: `bunx vitest run components/__tests__/PermissionGuard.test.tsx components/__tests__/ErrorBoundary.test.tsx`

Expected: FAIL until the type-safe implementations and tests are in place.

**Step 3: Fix each current strict-type error without loosening compiler settings**

Apply narrow, boring fixes only:

- `admin-ui/components/PermissionGuard.tsx`
  - Narrow `api.getCurrentUser()` and `api.getUserEffectivePermissions()` responses before writing them into state.
- `admin-ui/components/ErrorBoundary.tsx`
  - Return a fully populated `ErrorBoundaryState` shape from the functional `setState`.
- `admin-ui/components/users/ApiKeyCreateForm.tsx`
  - Align the `Resolver` and submit callback generic types with the actual form schema.
- `admin-ui/components/data-ops/MaintenanceSection.tsx`
  - Reconcile the `RotationStatus` union with the UI state that can legitimately be `"running"`.
- `admin-ui/app/dependencies/page.tsx`
  - Guard `Object.entries()` calls with a record-type check before iterating unknown API payloads.
- `admin-ui/lib/export.ts`
  - Add the correct `Record<string, unknown>` generic constraints and narrow date inputs before constructing `Date`.
- `admin-ui/lib/use-user-api-keys.ts`
  - Narrow the hook response before writing state.
- `admin-ui/middleware.ts`
  - Use an `ArrayBuffer`-compatible `BufferSource` input when verifying HMAC signatures.

**Step 4: Re-run the relevant suites and the full typecheck**

Run: `bunx vitest run components/__tests__/PermissionGuard.test.tsx components/__tests__/ErrorBoundary.test.tsx components/data-ops/MaintenanceSection.test.tsx app/dependencies/__tests__/page.test.tsx`

Expected: PASS

Run: `bunx tsc --noEmit`

Expected: PASS

**Step 5: Remove the build type bypass**

Modify `admin-ui/next.config.js` to remove:

```js
typescript: {
  ignoreBuildErrors: true,
}
```

Then run:

`bun run build`

Expected: PASS without `Skipping validation of types`.

**Step 6: Commit**

```bash
git add admin-ui/components/PermissionGuard.tsx admin-ui/components/__tests__/PermissionGuard.test.tsx admin-ui/components/ErrorBoundary.tsx admin-ui/components/__tests__/ErrorBoundary.test.tsx admin-ui/components/users/ApiKeyCreateForm.tsx admin-ui/components/data-ops/MaintenanceSection.tsx admin-ui/app/dependencies/page.tsx admin-ui/lib/export.ts admin-ui/lib/use-user-api-keys.ts admin-ui/middleware.ts admin-ui/next.config.js
git commit -m "fix(admin-ui): restore truthful type-safe build gates"
```

## Stage 3: Increase Production Confidence Beyond Unit Tests
**Goal:** Add the missing browser-level and CI/release checks for the privileged admin paths that matter most in production.
**Success Criteria:** Critical login and privileged user-management flows have browser smoke coverage, and the required frontend gate runs the same checks the release checklist requires.
**Tests:** Playwright smoke specs, `bun run test:a11y`, updated frontend-required workflow green
**Status:** Not Started

### Task 4: Add browser smoke coverage for critical admin flows

**Files:**
- Create: `admin-ui/playwright.config.ts`
- Create: `admin-ui/tests/e2e/login-and-mfa.spec.ts`
- Create: `admin-ui/tests/e2e/user-privileged-actions.spec.ts`
- Modify: `admin-ui/package.json`
- Reference: `apps/tldw-frontend/playwright.config.ts`

**Step 1: Write the first failing smoke spec**

Create a login smoke test that covers the hardened auth model:

```ts
test('supports password login and MFA challenge completion', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel(/username or email/i).fill('admin');
  await page.getByLabel(/password/i).fill('AdminPass123!');
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page.getByLabel(/verification code/i)).toBeVisible();
});
```

Create a privileged-action smoke test:

```ts
test('requires reason and reauthentication before reset password', async ({ page }) => {
  await page.goto('/users/42');
  await page.getByRole('button', { name: /reset password/i }).click();
  await expect(page.getByLabel(/reason/i)).toBeVisible();
  await expect(page.getByLabel(/current password/i)).toBeVisible();
});
```

**Step 2: Run the new smoke tests to verify they fail**

Run: `bunx playwright test tests/e2e/login-and-mfa.spec.ts tests/e2e/user-privileged-actions.spec.ts`

Expected: FAIL until the harness, fixtures, and routes are correctly wired.

**Step 3: Implement the minimal harness using existing repo conventions**

- Reuse the shape of `apps/tldw-frontend/playwright.config.ts`.
- Point the smoke suite at the local `admin-ui` dev or preview server.
- Keep the suite intentionally small: auth, MFA, users detail, privileged action modal.
- Add package scripts:

```json
"test:smoke": "playwright test"
```

**Step 4: Run smoke and accessibility checks**

Run: `bunx playwright test tests/e2e/login-and-mfa.spec.ts tests/e2e/user-privileged-actions.spec.ts`

Expected: PASS

Run: `bun run test:a11y`

Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/playwright.config.ts admin-ui/tests/e2e/login-and-mfa.spec.ts admin-ui/tests/e2e/user-privileged-actions.spec.ts admin-ui/package.json
git commit -m "test(admin-ui): add browser smoke coverage for privileged flows"
```

### Task 5: Align CI and release docs with the real production gate

**Files:**
- Modify: `.github/workflows/frontend-required.yml`
- Modify: `admin-ui/package.json`
- Modify: `admin-ui/README.md`
- Modify: `admin-ui/Release_Checklist.md`
- Modify: `admin-ui/next.config.js`

**Step 1: Add the failing gate locally**

Add explicit scripts if they do not already exist:

```json
"typecheck": "tsc --noEmit",
"test:smoke": "playwright test"
```

Then run:

- `bun run typecheck`
- `bun run build`

Expected: PASS locally before CI is updated.

**Step 2: Update the required workflow**

Extend `.github/workflows/frontend-required.yml` so `admin-ui_changed == true` runs:

1. `bun run lint`
2. `bun run typecheck`
3. `bun run test`
4. `bun run build`

Keep browser smoke in the release checklist unless runtime fixtures are made CI-stable in the same PR.

**Step 3: Update the operator-facing docs**

Document the real production gate in:

- `admin-ui/README.md`
- `admin-ui/Release_Checklist.md`

Required checklist items:

- `bun run lint`
- `bun run typecheck`
- `bun run test`
- `bun run test:a11y`
- `bun run build`
- `bun run test:smoke`

Also set `outputFileTracingRoot` in `admin-ui/next.config.js` so Next resolves the workspace root deterministically instead of guessing from stray lockfiles.

```js
const path = require('path');

module.exports = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, '..'),
};
```

**Step 4: Re-run the production gate**

Run:

- `bun run lint`
- `bun run typecheck`
- `bun run test`
- `bun run build`

Expected: PASS

**Step 5: Commit**

```bash
git add .github/workflows/frontend-required.yml admin-ui/package.json admin-ui/README.md admin-ui/Release_Checklist.md admin-ui/next.config.js
git commit -m "ci(admin-ui): align frontend gate with production checks"
```

## Stage 4: Reduce Regression Surface In Oversized Modules
**Goal:** Lower the probability that future production changes regress critical admin flows by extracting the highest-risk monoliths into smaller typed units.
**Success Criteria:** The largest user-management pages and their helper state are split into section components or hooks with no behavior change.
**Tests:** Existing page suites remain green; new extracted helpers have focused unit tests
**Status:** Not Started

### Task 6: Decompose the highest-risk user-management modules after the gate is green

**Files:**
- Modify: `admin-ui/app/users/[id]/page.tsx`
- Create: `admin-ui/app/users/[id]/components/UserProfileCard.tsx`
- Create: `admin-ui/app/users/[id]/components/UserSecurityCard.tsx`
- Create: `admin-ui/app/users/[id]/components/UserMembershipDialogs.tsx`
- Create: `admin-ui/app/users/[id]/hooks/use-user-security.ts`
- Modify: `admin-ui/app/users/[id]/__tests__/page.test.tsx`
- Modify: `admin-ui/app/users/page.tsx`
- Create: `admin-ui/app/users/components/UserBulkActions.tsx`
- Create: `admin-ui/app/users/hooks/use-user-filters.ts`
- Modify: `admin-ui/app/users/__tests__/page.test.tsx`

**Step 1: Write a no-behavior-change extraction test**

Add assertions in the existing users page suites that anchor the highest-risk behaviors before extraction:

- reset password still requires privileged confirmation
- revoke-all sessions still works
- saved views still round-trip correctly

**Step 2: Run the targeted suites to freeze current behavior**

Run: `bunx vitest run app/users/[id]/__tests__/page.test.tsx app/users/__tests__/page.test.tsx`

Expected: PASS

**Step 3: Extract by concern, not by visual fragment**

Start with the detail page security flows:

- `UserSecurityCard.tsx`
- `use-user-security.ts`

Then extract the membership dialogs and bulk-action logic. Keep API calls in one place and pass typed props down instead of duplicating fetch logic.

**Step 4: Re-run the suites after each extraction slice**

Run after each slice:

`bunx vitest run app/users/[id]/__tests__/page.test.tsx app/users/__tests__/page.test.tsx`

Expected: PASS after every extraction.

**Step 5: Commit**

```bash
git add admin-ui/app/users/[id]/page.tsx admin-ui/app/users/[id]/components admin-ui/app/users/[id]/hooks admin-ui/app/users/[id]/__tests__/page.test.tsx admin-ui/app/users/page.tsx admin-ui/app/users/components admin-ui/app/users/hooks admin-ui/app/users/__tests__/page.test.tsx
git commit -m "refactor(admin-ui): split user management monoliths"
```

## Verification Checklist For The Full Remediation Series

Run from `admin-ui/` unless noted otherwise:

1. `bun run lint`
2. `bun run typecheck`
3. `bun run test`
4. `bun run test:a11y`
5. `bun run build`
6. `bun run test:smoke`
7. From repo root: `python -m bandit -r admin-ui -f json -o /tmp/bandit_admin_ui.json` if the final change set adds Python-touching automation or backend helpers adjacent to `admin-ui`; otherwise skip and document why it is not applicable.

## Recommended Commit Sequence

1. `fix(admin-ui): clear plan guard lint blockers`
2. `fix(admin-ui): restore test and page-module typings`
3. `fix(admin-ui): restore truthful type-safe build gates`
4. `test(admin-ui): add browser smoke coverage for privileged flows`
5. `ci(admin-ui): align frontend gate with production checks`
6. `refactor(admin-ui): split user management monoliths`

## Notes For The Implementer

- Do not widen TypeScript types or disable rules to make the gate green.
- Keep `admin-ui` on Bun as the canonical package manager.
- Reuse repo Playwright patterns instead of creating a second browser-test style.
- Treat the Stage 4 refactor as post-gate work; do not mix it into the same PR as the gate restoration unless the branch stays small and reviewable.
