# Implementation Plan: Chat Dictionaries - Error Handling and Edge Cases

## Scope

Components: dictionary workspace states in `apps/packages/ui/src/components/Option/Dictionaries/DictionariesWorkspace.tsx` and `Manager.tsx`, import and mutation error flows, optimistic locking/version handling
Finding IDs: `8.1` through `8.8`

## Finding Coverage

- Empty-state and no-data guidance: `8.1`, `8.2`
- Preserve existing solid behaviors: `8.3`, `8.5`
- Actionable failure messaging and malformed-import handling: `8.4`, `8.7`
- Recovery patterns and concurrent edit safety: `8.6`, `8.8`

## Stage 1: Empty and Error State Clarity
**Goal**: Ensure users always see actionable next steps when data is absent or unavailable.
**Success Criteria**:
- Dictionary list empty state uses `FeatureEmptyState` with create/import CTAs and example use cases.
- Entry manager empty state explains entry purpose with example pattern/replacement.
- Query `error` state renders explicit failure UI with retry action.
- Existing regex error clarity and soft-delete safety behavior are preserved.
**Tests**:
- Component tests for dictionary and entry empty-state rendering.
- Integration test for server-offline/query-error retry flow.
- Entry-manager query-error retry rendering test.
- Manual regression check: regex validation alert and dictionary delete confirmation path unchanged.
**Status**: Complete

## Stage 2: Failure Recovery and Undo for Destructive Actions
**Goal**: Make destructive and import actions recoverable where practical.
**Success Criteria**:
- Entry delete shows toast with short-lived undo action.
- Undo restores deleted entry state without full-page reload.
- Import malformed-file handling includes client-side structural error details.
- Error copy consistently includes remediation hints.
**Tests**:
- Component tests for delete -> undo -> restore lifecycle.
- Unit tests for client-side import schema validation helper.
- Component test for malformed import rendering client-side structural errors and blocking request dispatch.
**Status**: Complete

## Stage 3: Optimistic Concurrency and Version Conflict Handling
**Goal**: Prevent silent overwrite when multiple sessions edit the same dictionary.
**Success Criteria**:
- Update requests include dictionary `version` for optimistic locking.
- 409 conflict responses surface explicit reload/review prompt.
- UI can refresh latest dictionary state without data loss in active forms.
- Conflict copy differentiates from name-collision conflicts in import flows.
**Tests**:
- API tests for version mismatch conflict behavior.
- Component tests for inline active-toggle conflict dialog and reload action.
- Manual check: edit modal conflict reload preserves in-progress edits while refreshing version.
**Status**: Complete

## Dependencies

- Undo patterns should align with global destructive-action patterns used in other option managers.
- Conflict handling should share language and mechanics with Category 5 import conflicts.
