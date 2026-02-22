# Watchlists Help Maintenance Policy (2026-02-18)

## Purpose

Keep Watchlists in-product help accurate as UI labels, routes, and workflow behavior evolve.

## Ownership

- Primary owner: Watchlists frontend maintainers.
- Secondary owner: Docs/API maintainers for `Docs/API-related/Watchlists_API.md`.
- QA owner: Release QA for Watchlists route smoke checks.

## Update Triggers

Update help copy and link maps when any of the following ship:

1. Tab labels, route labels, or major action labels change.
2. Setup flow changes (sources/jobs/runs/items/outputs path).
3. API behavior changes that affect user remediation guidance.
4. Beta/reporting links or documentation destinations move.

## Required Update Artifacts

1. In-product copy:
   - `apps/packages/ui/src/assets/locale/en/watchlists.json`
   - `apps/packages/ui/src/public/_locales/en/watchlists.json`
2. Link registry:
   - `apps/packages/ui/src/components/Option/Watchlists/shared/help-docs.ts`
3. Tests:
   - `shared/__tests__/help-docs.test.ts`
   - `__tests__/WatchlistsPlaygroundPage.help-links.test.tsx`

## Content Minimums

Help surfaces must include examples for:

1. Cron preset use cases and cadence expectations.
2. Filter behavior (include/exclude/flag outcomes).
3. Template/output workflow.
4. Delivery and reporting verification flow (runs -> items -> outputs).

## Enforcement

- CI gate: run Watchlists help/link tests in frontend test pack.
- Release gate: execute Watchlists help release checklist before final QA sign-off.
