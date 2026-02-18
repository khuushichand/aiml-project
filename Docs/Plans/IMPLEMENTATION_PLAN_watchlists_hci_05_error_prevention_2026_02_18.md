# Implementation Plan: Watchlists H5 - Error Prevention

## Scope

Route/components: `SourceFormModal`, `SourcesTab`, `SchedulePicker`, `GroupsTree`, `JobFormModal`  
Finding IDs: `H5.1` through `H5.5`

## Finding Coverage

- No pre-save source reachability validation: `H5.1`
- Missing dependency warnings before source deletion: `H5.2`
- Unsafe schedule and hierarchy configuration paths: `H5.3`, `H5.4`
- Missing field-level recipient validation: `H5.5`

## Stage 1: Form-Level Preflight Validation
**Goal**: Catch invalid input before submission.
**Success Criteria**:
- Source create/edit flow includes optional/inline "Test Source" preflight.
- Email recipient chips enforce basic email format with clear inline errors.
- Schedule picker warns or blocks high-frequency schedules beyond configured threshold.
**Tests**:
- Unit tests for email and schedule validation helpers.
- Component tests for source test action states (idle/running/success/failure).
- Integration tests for blocked invalid submissions.
**Status**: Not Started

## Stage 2: Structural and Dependency Guardrails
**Goal**: Prevent operations that silently break running jobs or group trees.
**Success Criteria**:
- Deleting a source referenced by active jobs prompts with impacted job list.
- Group move/edit flow blocks circular parent relationships.
- Bulk delete path includes dependency summary count before execution.
**Tests**:
- Integration tests for source delete dependency warnings.
- Unit tests for group cycle detection algorithm.
- E2E test for dependency-gated destructive action confirmation.
**Status**: Not Started

## Stage 3: Policy and Observability for Prevented Errors
**Goal**: Make prevention behavior transparent and supportable.
**Success Criteria**:
- Validation failures return specific, localized reasons with remediation guidance.
- Prevention events are captured in client telemetry/logging for UX quality tracking.
- Documentation of thresholds (frequency limits, validation rules) is published.
**Tests**:
- Contract tests for structured validation error payloads.
- Logging/telemetry tests for prevention event emission.
- Regression tests for localized message rendering.
**Status**: Not Started

## Dependencies

- Source testing uses existing API endpoint (`POST /sources/{id}/test`) or equivalent pre-create probe.
- Dependency checks should share impact query utilities with H3 undo safety prompts.
