# Implementation Plan: Prompts Page - Accessibility

## Scope

Components: Prompts page controls and Studio sub-tab controls in `index.tsx`, `PromptActionsMenu.tsx`, `Studio/StudioTabContainer.tsx`
Finding IDs: `7.1` through `7.9`

## Finding Coverage

- Preserve implemented strengths: `7.1`, `7.2`, `7.3`, `7.4`, `7.5`
- Control-level a11y gaps: `7.6`, `7.7`, `7.8`
- Shortcut discoverability: `7.9`

## Stage 1: Accessibility Baseline Lock-In
**Goal**: Prevent regressions in already strong accessibility foundations.
**Success Criteria**:
- Existing live region, keyboard row activation, action labels, favorite toggle semantics, and type-group labels are covered by explicit tests.
- Accessibility checklist entry added for Prompts page critical controls.
**Tests**:
- Component tests validating `aria-live`, keyboard activation, and `aria-pressed`.
- Accessibility integration test for row focus and keyboard flow.
**Status**: Not Started

## Stage 2: Critical Control and Labeling Remediation
**Goal**: Fix important screen-reader and touch/keyboard gaps.
**Success Criteria**:
- Copilot edit control receives visible focus styles and larger target size.
- Disabled Studio tabs expose accessible explanation of unmet prerequisites.
- Mobile icon-only Studio tab controls retain accessible labels.
**Tests**:
- Component tests for focus-visible classes and minimum target sizing.
- Accessibility tests confirming labels/disabled explanations across breakpoints.
**Status**: Not Started

## Stage 3: Keyboard Shortcut Discoverability
**Goal**: Make existing keyboard support discoverable to all users.
**Success Criteria**:
- Prompts page includes shortcut help entry point (`?` key and/or button).
- Help panel lists current shortcuts with scoped context.
- Shortcut help is keyboard navigable and screen-reader accessible.
**Tests**:
- Interaction tests for opening/closing shortcut help panel.
- Accessibility tests for modal semantics, focus trap, and labels.
**Status**: Not Started

## Dependencies

- Mobile icon-labeling overlaps with Studio tab plan and should ship together.
