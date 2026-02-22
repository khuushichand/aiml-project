# Implementation Plan: Characters - Information Architecture and Discoverability

## Scope

Components: `apps/packages/ui/src/components/Option/Characters/Manager.tsx`, `apps/packages/ui/src/components/Option/Characters/CharacterGalleryCard.tsx`
Finding IDs: `C-04` through `C-07`

## Finding Coverage

- Advanced fields are over-collapsed and hard to navigate: `C-04`
- Overlapping field intent is unclear (`personality`/`description`/`system_prompt`): `C-05`
- Gallery cards lack differentiating metadata: `C-06`
- Mood image capability mismatch between docs/model and UI: `C-07`

## Stage 1: Restructure Advanced Fields into Named Sections
**Goal**: Reduce cognitive load by grouping advanced controls by intent.
**Success Criteria**:
- Advanced area is split into named sections: Prompt Control, Generation Settings, Metadata.
- `prompt_preset` is promoted into main form area under `system_prompt`.
- Section expand/collapse state is independently controllable.
**Tests**:
- Component tests asserting section headers and grouped field locations.
- Regression test ensuring create/edit forms both render identical section structure.
- Integration test verifying form submit payload still maps all advanced fields correctly.
**Status**: Complete

## Stage 2: Add Inline Field Guidance for Overlapping Concepts
**Goal**: Clarify role boundaries between key text fields without requiring docs lookup.
**Success Criteria**:
- `personality`, `description`, and `system_prompt` each include concise help text or tooltip.
- Help text language is distinct and non-overlapping.
- Help text is available in both create and edit modes.
**Tests**:
- Component tests for help text/tooltips presence and accessible names.
- i18n coverage test for all new helper copy keys.
- UX QA checklist confirming examples align with backend prompt assembly behavior.
**Status**: Complete

## Stage 3: Increase Gallery Card Information Density
**Goal**: Make gallery scanning viable without opening each character.
**Success Criteria**:
- Gallery cards render 1-2 lines of description and up to 3 tags.
- Overflow behavior is stable (ellipsis/truncation) on narrow widths.
- Existing click actions and selection behavior remain unchanged.
**Tests**:
- Component tests for description/tag rendering and truncation.
- Visual regression snapshots for desktop and mobile breakpoints.
- Interaction tests for click/select actions after layout change.
**Status**: Complete

## Stage 4: Resolve Mood Image Expectation Gap
**Goal**: Remove ambiguity around mood-image support status.
**Success Criteria**:
- Either add "Mood images (coming soon)" placeholder in advanced section or remove unsupported docs claims.
- UI copy accurately reflects current implementation status.
- No broken controls are exposed for unsupported mood image flows.
**Tests**:
- Doc/UI consistency checklist for character feature matrix.
- Component test ensuring placeholder visibility when selected implementation path is UI placeholder.
**Status**: Complete

## Dependencies

- Stage 1 should align with Category 4 form extraction plan to avoid duplicate layout logic.
- Stage 4 requires coordination with documentation owners if docs-first remediation is selected.
