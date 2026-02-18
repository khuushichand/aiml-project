# Implementation Plan: Characters - First-Use Onboarding

## Scope

Components: `apps/packages/ui/src/components/Option/Characters/Manager.tsx`, `apps/packages/ui/src/components/Common/FeatureEmptyState.tsx`, character template data in `apps/packages/ui/src/data/character-templates.ts`
Finding IDs: `C-01` through `C-03`

## Finding Coverage

- Empty-state guidance gaps (icon, examples, secondary action): `C-01`
- Template discoverability before modal deep-dive: `C-02`
- Clarify character-to-chat relationship for new users: `C-03`

## Stage 1: Enrich Empty-State Onboarding
**Goal**: Make the zero-state actionable and self-explanatory for first-time users.
**Success Criteria**:
- Empty state adds icon, 2-3 concrete examples, and an import secondary CTA.
- Secondary CTA opens the existing character import flow directly.
- New copy includes one-line orientation about reusable personas and separate chat history.
**Tests**:
- Component test for `FeatureEmptyState` props rendering (icon/examples/secondary action).
- Integration test validating `Import character` action opens import modal/flow.
- i18n key coverage test for newly introduced onboarding strings.
**Status**: Not Started

## Stage 2: Surface Templates Earlier in the Journey
**Goal**: Remove hidden discoverability of starter templates.
**Success Criteria**:
- Empty state shows a visible template strip/grid (at least 3 starter templates).
- Create modal defaults to template chooser expanded on first visit.
- First-visit expansion state persists and does not re-expand after dismissal.
**Tests**:
- Component test for template cards rendering inside empty state.
- Integration test for first-visit expanded template chooser behavior.
- Unit test for persisted "template chooser seen" local-storage key handling.
**Status**: Not Started

## Stage 3: Validate First-Run Flow End-to-End
**Goal**: Ensure users can create/import and immediately understand next action.
**Success Criteria**:
- New user can complete one guided path: select template -> create character -> start chat.
- Empty-state CTAs and copy have no dead ends or contradictory labels.
- Analytics/telemetry hook (if enabled) captures empty-state CTA usage for follow-up tuning.
**Tests**:
- E2E test for empty state -> template create -> chat launch path.
- E2E test for empty state -> import path.
- QA checklist for copy clarity and route transitions.
**Status**: Not Started

## Dependencies

- Reuses existing template catalog and import handlers in `Manager.tsx`.
- Telemetry capture (if added) should align with current UI event tracking conventions.
