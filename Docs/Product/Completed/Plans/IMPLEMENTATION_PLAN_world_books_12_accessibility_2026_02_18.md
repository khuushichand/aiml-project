# Implementation Plan: World Books - Accessibility

## Scope

Components: World-books table actions, drawer/modals focus behavior, disclosure controls, conflict indicators, switch semantics, matrix keyboard model, color contrast and form error announcements.
Finding IDs: `12.1` through `12.8`

## Finding Coverage

- Icon/action labeling and semantic control issues: `12.1`, `12.3`, `12.5`
- Focus and keyboard navigation risks: `12.2`, `12.6`
- Non-visual conflict and validation communication: `12.4`, `12.8`
- Color contrast compliance risk: `12.7`

## Stage 1: Baseline A11y Audit and Test Harness
**Goal**: Establish repeatable checks before implementing targeted fixes.
**Success Criteria**:
- Add world-books accessibility checklist for keyboard, screen reader, and contrast scenarios.
- Add automated a11y test coverage for key pages/components where feasible.
- Capture baseline defects with finding ID traceability.
**Tests**:
- Automated checks (axe/lint) in component or E2E tests.
- Manual audit checklist execution for screen reader and keyboard flows.
- Contrast audit report for light and dark theme variants.
**Status**: Complete

## Stage 2: Strengthen Semantics for Controls and Disclosures
**Goal**: Ensure controls convey meaning and state to assistive technologies.
**Success Criteria**:
- Confirm all icon-only buttons have explicit `aria-label`s.
- Replace or harden `<details>/<summary>` disclosures with robust ARIA state reporting.
- Add clearer switch semantics (`checkedChildren` / `unCheckedChildren` or equivalent labeling).
**Tests**:
- Component tests for accessible name presence on icon-only controls.
- Accessibility tests for disclosure expanded/collapsed announcements.
- Screen reader smoke test for switch state/meaning announcements.
**Status**: Complete

## Stage 3: Fix Focus Management and Matrix Keyboard Navigation
**Goal**: Ensure keyboard-only users can complete end-to-end workflows.
**Success Criteria**:
- Validate and enforce focus trap and focus return behavior in drawer/modals.
- Introduce grid keyboard navigation model or equivalent shortcuts for attachment matrix.
- Keep nested modal/drawer flows predictable under Tab and arrow-key navigation.
**Tests**:
- E2E keyboard navigation tests for drawer open/close focus behavior.
- Keyboard tests for matrix navigation and activation.
- Regression tests for nested modal focus handoff.
**Status**: Complete

## Stage 4: Improve Non-Visual Alerts, Validation Wiring, and Contrast
**Goal**: Make critical state and errors perceivable beyond color-only cues.
**Success Criteria**:
- Add conflict announcements (`aria-label` and/or live summary) for keyword conflict indicators.
- Verify and enforce `aria-describedby` linkage for field-level validation errors.
- Remediate `text-text-muted` and other low-contrast tokens to meet WCAG AA targets.
**Tests**:
- Component tests for conflict aria text generation.
- Form validation tests ensuring errors are announced on focus.
- Contrast tests validating minimum ratios across themes.
**Status**: Complete

## Dependencies

- Matrix keyboard model may require structural changes to current table implementation.
- Contrast fixes should be coordinated with shared design token definitions to avoid cross-page regressions.
