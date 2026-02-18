# Implementation Plan: Phase A Follow-up - Resource Governor Form, Loading Sweep, Bun Gates

## Stage 1: Baseline Audit
**Goal**: Confirm remaining gaps for Stage 1 criteria and quality-gate command consistency.
**Success Criteria**:
- Resource governor form gap documented (field-level validation and accessibility wiring).
- Remaining mutation button candidates identified.
- Plan files with legacy non-Bun quality-gate commands identified.
**Tests**:
- N/A (analysis stage).
**Status**: Complete

## Stage 2: Resource Governor Form Refactor
**Goal**: Refactor policy create/edit form to use structured form validation with accessible error announcements.
**Success Criteria**:
- Policy form uses `react-hook-form` + `zod`.
- Required field and conditional scope-id validation implemented.
- Field errors are linked with `aria-invalid`, `aria-describedby`, and `role="alert"` via shared form components.
- Existing create/edit behavior remains functional.
**Tests**:
- Add/extend unit/integration tests for policy form validation behavior.
**Status**: Complete

## Stage 3: Mutation Button Loading Sweep
**Goal**: Standardize mutation actions on the shared `Button` loading API.
**Success Criteria**:
- Remaining high-value mutation buttons migrated to `loading`/`loadingText`.
- Existing guard conditions (`disabled` for invalid forms etc.) preserved where needed.
**Tests**:
- Update affected tests if expectations change.
**Status**: Complete

## Stage 4: Bun Quality Gate Command Update
**Goal**: Align HCI phase quality-gate commands with workspace toolchain.
**Success Criteria**:
- Legacy lint quality-gate command updated to `bun run lint`.
- Legacy Vitest quality-gate command updated to `bunx vitest run`.
- Legacy Next build quality-gate command updated to `bun run build`.
- No stale non-Bun `cd admin-ui && ...` quality-gate commands remain in HCI plan files.
**Tests**:
- Validate by grep scan for stale command strings.
**Status**: Complete
