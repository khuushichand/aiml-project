# Implementation Plan: Watchlists H10 - Help and Documentation

## Scope

Route/components: `WatchlistsPlaygroundPage`, first-run and contextual help surfaces, docs/reporting links  
Finding IDs: `H10.1` through `H10.3`

## Finding Coverage

- No first-time guidance or guided tour: `H10.1`
- Missing direct documentation entry points in UI: `H10.2`
- Beta messaging lacks support/reporting route: `H10.3`

## Stage 1: Inline Documentation Entry Points
**Goal**: Ensure every major watchlists surface has discoverable help.
**Success Criteria**:
- Top-level route includes persistent docs/help link.
- Each major tab includes contextual "Learn more" access to focused documentation.
- Beta banner includes links for docs and issue reporting.
**Tests**:
- Component tests for help-link visibility across tabs.
- Link validation tests for docs and issue-report URLs.
- Regression tests confirming banners remain dismissible and stateful.
**Status**: Complete

### Stage 1 Implementation Notes (2026-02-18)
- Added persistent route-level docs entry points in `WatchlistsPlaygroundPage`:
  - Top-level `Watchlists docs` link.
  - Contextual `Learn more: <tab>` link mapped to the active tab’s focused docs destination.
- Added beta support/reporting links:
  - `DismissibleBetaAlert` description now includes:
    - docs link
    - `Report an issue` link
  - Maintains existing dismissible + localStorage persistence behavior.
- Expanded help-doc registry:
  - Added route-level docs URL, issue-report URL, and per-tab docs map in `shared/help-docs.ts`.
- Verification coverage:
  - `WatchlistsPlaygroundPage.help-links.test.tsx` validates docs/report links and beta banner dismissal persistence.
  - `shared/help-docs.test.ts` now validates main docs URL, issue-report URL, and per-tab docs mapping.
  - `apps/extension/tests/e2e/watchlists.spec.ts` includes `watchlists help links and guided-tour resume are discoverable` for route-level docs/report entry points in runtime flow.

## Stage 2: Guided First-Run Experience
**Goal**: Make first successful pipeline run self-service.
**Success Criteria**:
- Guided tour or wizard introduces Sources -> Jobs -> Runs -> Items -> Outputs flow.
- Tour supports skip/resume and does not block returning users.
- First-run completion card confirms what to do next and where to monitor status.
**Tests**:
- E2E test for first-time user completing setup via guide.
- Component tests for guide state persistence and resume behavior.
- Accessibility tests for guided overlays/modals.
**Status**: Complete

### Stage 2 Implementation Notes (2026-02-18)
- Added first-run guided tour scaffolding in `WatchlistsPlaygroundPage`:
  - Guided sequence covers `Sources -> Jobs -> Runs -> Items -> Outputs`.
  - Includes `Start`, `Skip`, `Back`, `Next`, `Finish`, and `Resume` controls.
- Added skip/resume persistence:
  - Tour state persisted in localStorage (`watchlists:guided-tour:v1`).
  - Returning users are not blocked; in-progress users get a `Resume guided tour` affordance.
- Added completion confirmation card:
  - On finishing the tour, users see a success notice with direct actions to `Open Activity` and `Open Articles`.
- Verification coverage:
  - `WatchlistsPlaygroundPage.help-links.test.tsx` now covers guided-tour start/resume persistence and completion-state behavior.
  - `apps/extension/tests/e2e/watchlists.spec.ts` validates persisted guided-tour resume (`step 3 of 5`) and contextual docs-link updates while navigating tabs.

## Stage 3: Operational Help Maintenance
**Goal**: Keep in-product help accurate as watchlists features evolve.
**Success Criteria**:
- Documentation ownership and update trigger policy defined (when UI/API changes ship).
- Help content includes examples for cron presets, templates, filters, and delivery modes.
- Release checklist includes verification of docs/help links and onboarding flow.
**Tests**:
- CI doc-link checker against watchlists help references.
- Manual QA checklist integrated into release workflow.
- Drift audit test plan comparing current UI labels vs help glossary.
**Status**: Complete

### Stage 3 Implementation Notes (2026-02-18)
- Added operational ownership/update-trigger policy:
  - `Docs/Monitoring/WATCHLISTS_HELP_MAINTENANCE_POLICY_2026_02_18.md`
- Added release QA checklist for help surfaces and guided-tour behavior:
  - `Docs/Plans/WATCHLISTS_HELP_RELEASE_CHECKLIST_2026_02_18.md`
- Added drift-audit procedure and evidence requirements:
  - `Docs/Plans/WATCHLISTS_HELP_DRIFT_AUDIT_PLAN_2026_02_18.md`
- Added CI gate for help-link integrity and contextual-help regression:
  - `.github/workflows/ui-watchlists-help-tests.yml`
  - `apps/packages/ui/package.json` script: `test:watchlists:help`

## Dependencies

- Help copy should share terminology contract with H2 and H4.
- Guided flows should reuse quick-create/onboarding mechanics from H7 where possible.
