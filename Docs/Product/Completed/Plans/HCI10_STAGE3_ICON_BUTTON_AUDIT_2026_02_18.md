# HCI Plan 10 Stage 3: Icon Button Audit (2026-02-18)

## Scope

- Audited sources: `admin-ui/app/**/*.{ts,tsx}`, `admin-ui/components/**/*.{ts,tsx}` (excluding tests).
- Goal: detect icon-only `Button` usages missing accessible labeling.

## Automated Audit Gate

- Command: `cd admin-ui && bunx vitest run app/__tests__/icon-button-audit.test.ts`
- Rule: icon-only `<Button>` blocks must include `aria-label` or `aria-labelledby`.

## Findings and Fixes

- Unlabeled icon-only action buttons found in team member row actions and fixed:
  - `admin-ui/app/teams/[id]/page.tsx`
  - Added `aria-label` for:
    - View user action.
    - Remove member action.

## Current Status

- Audit test now passes with no remaining unlabeled icon-only `Button` matches under the current heuristic scan.
- Existing explicit `AccessibleIconButton` usage remains in place for major icon-action surfaces.
