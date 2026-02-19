# Implementation Plan: Knowledge QA - RAG Settings and Configuration

## Scope

Components: `apps/packages/ui/src/components/Option/KnowledgeQA/SettingsPanel/index.tsx`, Basic/Expert settings controls, preset selection copy
Finding IDs: `6.1` through `6.10`

## Finding Coverage

- Preserve high-quality existing accessibility and interaction foundations: `6.1`, `6.3`, `6.4`, `6.8`, `6.10`
- Improve non-technical clarity and settings-scope messaging: `6.2`, `6.6`, `6.7`, `6.9`
- Fix expert accordion accessibility gap: `6.5`

## Stage 1: Critical Expert Accordion Accessibility Remediation
**Goal**: Ensure section open/closed state is fully announced to assistive tech.
**Success Criteria**:
- Accordion triggers expose `aria-expanded` and `aria-controls` (`6.5`).
- Section content panels have stable IDs matching `aria-controls` references (`6.5`).
- Keyboard behavior remains unchanged after ARIA updates.
**Tests**:
- Component tests asserting `aria-expanded` toggles with click/keyboard.
- Accessibility tests validating trigger/content relationship.
- Keyboard integration test over full expert sections list.
**Status**: Complete

## Stage 2: Preset and Settings Copy Clarity Improvements
**Goal**: Make configuration language understandable to non-technical users.
**Success Criteria**:
- Preset descriptions avoid jargon and explain trade-offs in plain language (`6.2`).
- Expert source labels use same friendly terminology as basic mode (`6.9`).
- Reset action naming clearly reflects Balanced-default behavior (`6.7`).
**Tests**:
- Component tests for updated preset/reset copy rendering.
- i18n coverage checks for new strings/keys where applicable.
- UX smoke tests for basic/expert label parity.
**Status**: Complete

## Stage 3: Settings Scope Communication and Regression Protection
**Goal**: Clarify when changes apply while preserving existing strong interactions.
**Success Criteria**:
- Panel includes note that changes apply to future searches, not prior answers (`6.6`).
- Existing best-in-class patterns remain untouched and covered by tests: preset radiogroup (`6.1`), curated basic controls (`6.3`), expert onboarding (`6.4`), drawer layout (`6.8`), focus trap (`6.10`).
**Tests**:
- Integration test for settings note visibility and persistence across open/close.
- Regression tests covering radiogroup keyboard navigation and focus trap behavior.
- Responsive test for drawer width/backdrop behavior.
**Status**: Complete

## Dependencies

- Copy changes should stay aligned with global terminology used in Search and Source filter plans.
