# Characters Test Harness

This document defines the canonical character harness commands and setup contract.

## Canonical Commands

- Frontend context: `cd apps/tldw-frontend && bun run test:characters-harness`
- UI package context: `cd apps/packages/ui && bun run test:characters-harness`

Both commands must pass when changing character manager behavior, shared character utilities, or Vitest setup.

## Setup Contract

- Baseline shared test setup lives in `apps/packages/ui/vitest.setup.ts`.
- Frontend setup (`apps/tldw-frontend/vitest.setup.ts`) must import and preserve that baseline contract.
- Drift guard coverage lives in `apps/tldw-frontend/__tests__/vitest.setup-contract.test.ts`.

## When Adding Shared Test Polyfills

1. Add the baseline behavior in `apps/packages/ui/vitest.setup.ts`.
2. Add frontend-only compatibility shims in `apps/tldw-frontend/vitest.setup.ts` only when required.
3. Update `apps/tldw-frontend/__tests__/vitest.setup-contract.test.ts` with any new required invariants.
4. Run both canonical harness commands before submitting.

## CI

- Workflow: `.github/workflows/ui-characters-harness-tests.yml`
- CI runs the canonical harness command in both contexts to prevent setup drift.
