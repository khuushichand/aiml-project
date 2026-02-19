# Implementation Plan: Prompts Page - Prompt Drawer (Create/Edit)

## Scope

Components: `apps/packages/ui/src/components/Option/Prompt/PromptDrawer.tsx`, shared draft hooks, Studio version history integration
Finding IDs: `2.1` through `2.7`

## Finding Coverage

- Prompt length visibility: `2.1`
- Template variable UX and validation: `2.2`
- Few-shot and versioning workflow continuity: `2.3`, `2.4`
- Draft integrity, responsive behavior, and close safety: `2.5`, `2.6`, `2.7`

## Stage 1: Prompt Length and Budget Signals
**Goal**: Provide immediate prompt-size visibility for editing decisions.
**Success Criteria**:
- System and user textareas display live character counts.
- Estimated token count appears alongside character count using shared utility.
- Warning state appears at configurable token thresholds.
**Tests**:
- Unit tests for token estimate utility and threshold state logic.
- Component tests for live counter updates and warning rendering.
**Status**: Complete

## Stage 2: Template Variable Parsing, Highlighting, and Validation
**Goal**: Make template variables first-class in the drawer workflow.
**Success Criteria**:
- `{{variable}}` patterns are visually highlighted in editor fields.
- Extracted variables render as chips below relevant fields.
- Validation errors surface missing/invalid variable references before save.
- Parsing behavior matches backend extraction semantics.
**Tests**:
- Unit tests for extraction/normalization parity with backend regex behavior.
- Component tests for highlighting and variable-chip rendering.
- Form validation tests for missing variable references.
**Status**: Complete

## Stage 3: Few-Shot and Version History In-Context Editing
**Goal**: Remove avoidable context switches to Studio for common edit tasks.
**Success Criteria**:
- Drawer includes collapsible editor for few-shot example add/remove/reorder.
- Version section adds `View history` action for synced prompts.
- Version action opens shared history UI or navigates with selected prompt context.
**Tests**:
- Component tests for few-shot CRUD and reorder state handling.
- Integration test validating history action availability only for synced prompts.
**Status**: Complete

## Stage 4: Draft Isolation, Responsive Drawer, and Unsaved-Change Confirmation
**Goal**: Prevent accidental data crossover and accidental-close loss.
**Success Criteria**:
- Draft storage key includes unique prompt ID (not prompt name) and mode.
- Drawer width is responsive and full-width on narrow/mobile viewports.
- Close action performs dirty-check and shows save/discard/cancel confirmation.
- Auto-save and explicit save paths do not conflict.
**Tests**:
- Unit tests for draft key construction and retrieval isolation.
- Responsive component tests for drawer width by breakpoint.
- Interaction tests for dirty-close confirmation decision paths.
**Status**: Complete

## Dependencies

- Shared drawer behavior should align with prompt creation/edit flows in Custom tab plan.
- Version history integration depends on existing Studio history components.
