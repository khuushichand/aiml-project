# Implementation Plan: Knowledge QA - Accessibility

## Scope

Components: `SearchBar.tsx`, `AnswerPanel.tsx`, `HistorySidebar.tsx`, `SourceList.tsx`, `SourceCard.tsx`, `FollowUpInput.tsx`, `ExportDialog.tsx`, `SettingsPanel/index.tsx`, page shell layout in `index.tsx`
Finding IDs: `12.1` through `12.16`

## Finding Coverage

- Preserve exemplary existing patterns: `12.1`, `12.3`, `12.5`, `12.6`, `12.12`, `12.13`, `12.16`
- Resolve critical semantic/control visibility gaps: `12.4`, `12.7`, `12.8`, `12.11`
- Add active-state and structural semantics: `12.9`, `12.10`, `12.15`
- Improve reading flow and contrast assurance: `12.2`, `12.14`

## Stage 1: Critical Modal/Accordion/Control Label Fixes
**Goal**: Close the highest-impact blockers for keyboard and screen-reader users.
**Success Criteria**:
- Export dialog includes modal ARIA semantics and keyboard focus trap (`12.4`).
- Settings accordion triggers expose open/closed state and controlled-region mapping (`12.7`).
- History delete controls are visibly focusable, not hover-only (`12.8`).
- Follow-up input includes explicit accessible name (`12.11`).
**Tests**:
- Accessibility integration tests for export dialog focus trap and ARIA roles.
- Component tests for accordion `aria-expanded` and `aria-controls` toggling.
- Keyboard navigation tests for history item + delete control visibility.
- Component test for follow-up input accessible name.
**Status**: Complete

## Stage 2: Landmark, List, and Active-State Semantics
**Goal**: Improve navigability and orientation within complex page layout.
**Success Criteria**:
- Active history item exposes `aria-current` and visual selected state (`12.9`).
- Source grid/cards expose list/article semantics for assistive tech (`12.10`).
- Page shell uses landmark roles (`main`, `aside`, optional `nav`) and includes skip link (`12.15`).
**Tests**:
- Accessibility tests for landmark presence and skip-link focus target.
- Component tests for `aria-current` behavior tied to selected thread.
- Screen-reader smoke checklist for source list semantics.
**Status**: Complete

## Stage 3: Reading-Flow Guidance and Contrast Compliance
**Goal**: Reduce assistive-tech friction and ensure visual token compliance.
**Success Criteria**:
- Answer container includes guidance for inline citation-button navigation (`12.2`).
- Design token audit confirms citation and muted text color combinations meet WCAG AA (`12.14`).
- Remediation applied for any failing token combinations.
**Tests**:
- Automated axe checks integrated for Knowledge QA route.
- Contrast test script/manual audit log with measured ratios.
- Regression tests for citation button ARIA and announced context copy.
**Status**: Complete

## Stage 4: Regression Gates for Existing Accessibility Strengths
**Goal**: Protect already-strong accessible implementations while changes land.
**Success Criteria**:
- Existing compliant controls remain intact for findings `12.1`, `12.3`, `12.5`, `12.6`, `12.12`, `12.13`, `12.16`.
- New accessibility checks are wired into CI for Knowledge QA components.
- Manual screen-reader smoke pass is documented for release criteria.
**Tests**:
- Regression suite covering search input labeling and settings dialog behavior.
- Component tests for switch/radiogroup semantics.
- CI axe test targeting Knowledge QA page.
**Status**: Complete

## Dependencies

- This plan intentionally overlaps with category-specific fixes (History, Settings, Export) and should run as a cross-cutting release gate.
