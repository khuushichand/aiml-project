# Implementation Plan: Characters - Creation and Editing Experience

## Scope

Components: `apps/packages/ui/src/components/Option/Characters/Manager.tsx`, `apps/packages/ui/src/components/Option/Characters/GenerateFieldButton.tsx`, `apps/packages/ui/src/components/Option/Characters/GenerateCharacterPanel.tsx`
Finding IDs: `C-13` through `C-15`

## Finding Coverage

- Alternate greeting editor is mismatched to multi-line message use case: `C-13`
- System prompt input lacks high-quality example guidance: `C-14`
- Create/edit form duplication risks behavioral drift and defects: `C-15`

## Stage 1: Replace Alternate Greetings Tag Input with Structured Message List
**Goal**: Make alternate greetings easy to author, edit, and reorder.
**Success Criteria**:
- Alternate greetings use dynamic `Input.TextArea` rows with add/remove controls.
- Drag-and-drop or keyboard move actions support explicit ordering.
- Data normalization still emits clean string array payloads.
**Tests**:
- Component tests for add/remove/reorder behaviors.
- Unit tests for normalization/parsing from UI model to API payload.
- Integration tests confirming create/edit/save round-trip preserves order.
**Status**: Not Started

## Stage 2: Upgrade System Prompt Guidance
**Goal**: Help users author effective system prompts without leaving the form.
**Success Criteria**:
- System prompt field includes a stronger multi-line placeholder and optional example insert action.
- Example can be inserted without overwriting existing user text unless confirmed.
- Guidance is consistent with prompt preset behavior.
**Tests**:
- Component tests for show/hide example interactions.
- Integration test for insert behavior and undo/cancel path.
- i18n tests for new helper copy.
**Status**: Not Started

## Stage 3: Extract Shared `CharacterForm` Component
**Goal**: Eliminate create/edit divergence risk and reduce maintenance cost.
**Success Criteria**:
- Shared `CharacterForm` encapsulates common field rendering and validation.
- `Manager.tsx` create/edit modals use shared component with mode-specific props.
- Validation rules, helper text, and generation helpers are consistent across modes.
**Tests**:
- Snapshot/component tests for create and edit mode parity.
- Integration tests for create flow and edit flow after extraction.
- Regression tests for form-draft persistence with shared component.
**Status**: Not Started

## Stage 4: Hardening and Migration Cleanup
**Goal**: Ship form refactor with low regression risk.
**Success Criteria**:
- Removed duplicate form blocks and dead helper code from `Manager.tsx`.
- Existing shortcuts and AI field-generation affordances still function.
- Rollout note documents field-level parity checklist completion.
**Tests**:
- E2E tests for create/edit/import/export critical paths.
- Manual QA checklist for advanced fields parity across modes.
**Status**: Not Started

## Dependencies

- Stage 3 should be coordinated with Category 2 advanced-field sectioning changes.
- Alternate greeting model updates should remain compatible with backend schema expectations.
