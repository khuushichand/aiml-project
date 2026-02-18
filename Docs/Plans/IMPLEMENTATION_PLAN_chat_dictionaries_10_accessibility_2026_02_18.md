# Implementation Plan: Chat Dictionaries - Accessibility

## Scope

Components: dictionary table/list controls, entry manager interactions, collapse/region semantics, modal and confirmation dialog behavior in `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`
Finding IDs: `10.1` through `10.9`

## Finding Coverage

- Preserve existing strong accessible labeling patterns: `10.1`, `10.2`, `10.5`, `10.9`
- Keyboard-accessible active-state control gap: `10.3`
- Expand/collapse semantics and region exposure: `10.4`
- Contrast and non-color communication verification: `10.6`, `10.7`
- Nested modal focus-trap behavior verification: `10.8`

## Stage 1: Keyboard and Semantic Control Remediation
**Goal**: Ensure core dictionary actions are fully operable and understandable without a mouse.
**Success Criteria**:
- Active status is keyboard-actionable from list via semantic switch control.
- Expandable panels expose accurate `aria-expanded` and region associations.
- Collapsible validation/preview sections announce state changes clearly.
- All newly introduced controls include accessible names and focus styles.
**Tests**:
- Component tests for switch keyboard toggling (`Space`/`Enter`).
- Accessibility tests asserting `aria-expanded`/`aria-controls` pairs.
- Keyboard navigation integration tests across primary dictionaries workflows.
**Status**: Not Started

## Stage 2: Focus Management and Modal Interaction Integrity
**Goal**: Guarantee predictable focus behavior in complex overlay workflows.
**Success Criteria**:
- Nested modal cases are removed or validated so outer content is inert.
- Focus trap and return-focus behavior work in entry edit and confirm dialogs.
- Screen-reader announcement order is stable during modal transitions.
- No focus loss occurs on async mutation success/failure states.
**Tests**:
- Integration tests for focus trap and restoration after close.
- Screen-reader-focused manual test checklist for modal transitions.
- E2E keyboard-only path tests for create/edit/delete flows.
**Status**: Not Started

## Stage 3: Contrast Compliance and A11y Regression Gates
**Goal**: Keep status/validation visuals compliant across supported themes.
**Success Criteria**:
- Status icon/text color combinations meet WCAG 2.1 AA contrast thresholds.
- Non-color cues remain present for key state indicators.
- Automated a11y checks are added for dictionaries workspace regressions.
- Existing positive accessible behaviors are locked with regression tests.
**Tests**:
- Contrast audit checklist with measured ratios for light/dark themes.
- Axe-based component/integration tests for dictionaries pages.
- Regression tests for existing aria-label and context-aware label text.
**Status**: Not Started

## Dependencies

- Stage 1 active-toggle implementation shares code path with Category 1 Stage 2.
- Responsive/mobile adaptations from Category 9 must not degrade keyboard accessibility.
