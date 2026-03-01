# Watchlists Help Drift Audit Plan (2026-02-18)

## Objective

Detect and correct drift between Watchlists UI language/flows and in-product help content before release.

## Inputs

- UI sources:
  - `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx`
  - `apps/packages/ui/src/components/Option/Watchlists/shared/help-docs.ts`
  - `apps/packages/ui/src/assets/locale/en/watchlists.json`
  - `apps/packages/ui/src/public/_locales/en/watchlists.json`
- Policy/checklist:
  - `Docs/Monitoring/WATCHLISTS_HELP_MAINTENANCE_POLICY_2026_02_18.md`
  - `Docs/Product/Completed/Plans/WATCHLISTS_HELP_RELEASE_CHECKLIST_2026_02_18.md`

## Cadence

- Run on every release candidate touching `/watchlists`.
- Run on any PR that changes watchlists tab labels, setup flow wording, or help links.

## Audit Procedure

1. Verify all docs links are valid HTTPS and route/tab mappings remain intact:
   - `bun run test:watchlists:help` (in `apps/packages/ui`)
2. Compare active tab labels (`overview`, `sources`, `jobs`, `runs`, `items`, `outputs`, `templates`, `settings`) to:
   - guided tour step copy in `WatchlistsPlaygroundPage`
   - contextual help labels in locale files
3. Confirm beta banner docs/report actions still exist and remain dismissible.
4. Confirm guided tour state transitions (`not_started`, `in_progress`, `completed`) still match visible CTAs.
5. Record drift findings and disposition:
   - fix immediately if user-facing mismatch
   - defer only with explicit rationale and tracking issue

## Pass/Fail Criteria

- Pass:
  - All Watchlists help tests pass.
  - No mismatches between tab names and help/tour copy.
  - All help/report links resolve to intended destinations.
- Fail:
  - Any broken/missing help link.
  - Any user-visible label mismatch across tab labels, tour steps, and help text.
  - Missing beta support/reporting entry points.

## Evidence to Attach

- Test output from `test:watchlists:help`.
- Screenshot(s) of:
  - header docs links
  - beta docs/report links
  - guided-tour completion state.
