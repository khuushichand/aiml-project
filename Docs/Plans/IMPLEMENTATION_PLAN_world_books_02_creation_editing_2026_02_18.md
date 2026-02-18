# Implementation Plan: World Books - Creation and Editing

## Scope

Components: Create/Edit world-book modals in `Manager.tsx`, form validation, shared form extraction, create/update mutation UX.
Finding IDs: `2.1` through `2.7`

## Finding Coverage

- Field clarity and default correctness: `2.1`, `2.2`, `2.3`
- Authoring acceleration features: `2.4`, `2.5`
- Maintainability and consistency: `2.6`
- Validation and conflict feedback: `2.7`

## Stage 1: Correct Defaults and Improve Field Semantics
**Goal**: Eliminate misleading defaults and clarify required vs optional inputs.
**Success Criteria**:
- Update UI defaults/placeholder text to match backend defaults (`scan_depth=3`, `token_budget=500`).
- Prefer explicit initial form values over placeholder-only defaults for advanced settings.
- Label `Description` as optional and keep required indicators explicit on required fields.
- Increase help icon target size and keep tooltip hit area keyboard accessible.
**Tests**:
- Unit test asserting frontend default constants match backend schema defaults.
- Component test verifying optional label text and advanced-setting default rendering.
- Accessibility test for help icon size/focusability and tooltip activation.
**Status**: In Progress

## Stage 2: Unify Create/Edit Form Implementation
**Goal**: Prevent behavior drift between create and edit experiences.
**Success Criteria**:
- Extract a shared `WorldBookForm` component used by both Create and Edit modals.
- Ensure all fields, tooltips, and validation rules are identical between modes.
- Centralize transform logic between form values and API payloads.
**Tests**:
- Component tests for `WorldBookForm` in both create and edit modes.
- Regression test ensuring create and edit submit identical payload shapes for same input.
- Mutation tests covering success and error states for both flows.
**Status**: In Progress

## Stage 3: Improve Conflict and Validation Messaging
**Goal**: Provide actionable feedback for duplicate and invalid submissions.
**Success Criteria**:
- Add client-side duplicate-name validation against loaded world-book names.
- Surface server 409 conflict messages verbatim when available.
- Show contextual inline errors instead of generic toast-only failures.
**Tests**:
- Unit tests for duplicate-name validator (case sensitivity and trimming behavior).
- Integration tests for create/edit 409 response handling and message rendering.
- Component test for inline error presentation and focus management.
**Status**: In Progress

## Stage 4: Add Duplication and Template Bootstrap
**Goal**: Reduce time-to-first-usable world book for repeat workflows.
**Success Criteria**:
- Add `Duplicate` row action to clone metadata and entries into `Copy of {name}`.
- Introduce lightweight starter templates in Create modal (at least 2 presets).
- Track template selection to prefill entries/settings while allowing immediate edits.
**Tests**:
- Integration test for duplicate workflow end-to-end with copied entries.
- Component tests for template selection and correct field prefill.
- Validation test confirming cloned/template names still pass uniqueness checks.
**Status**: Not Started

## Dependencies

- Duplicate behavior may require backend clone endpoint or client-side create+entry-copy orchestration.
- Template content should be versioned in a dedicated constants module for safe evolution.

## Progress Notes (2026-02-18)

- Implemented backend-aligned frontend defaults (`scan_depth=3`, `token_budget=500`) via shared defaults/constants.
- Replaced duplicated create/edit modal markup with a shared `WorldBookForm` component in `Manager.tsx`.
- Added client-side duplicate-name validation (case-insensitive, trims whitespace, ignores current record in edit mode).
- Improved conflict handling for 409 responses with clearer user-facing messages.
- Added utility tests in `apps/packages/ui/src/components/Option/WorldBooks/__tests__/worldBookFormUtils.test.ts`.
