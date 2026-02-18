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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Help copy should share terminology contract with H2 and H4.
- Guided flows should reuse quick-create/onboarding mechanics from H7 where possible.
