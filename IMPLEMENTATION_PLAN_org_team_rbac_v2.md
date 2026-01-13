## Stage 1: Discovery + alignment
**Goal**: Inventory current RBAC/org/team flows and identify integration points for scoped permissions.
**Success Criteria**: Target files, data-model gaps, and compatibility risks documented.
**Tests**: N/A
**Status**: Complete

## Stage 2: Design doc
**Goal**: Publish a v2 design in `/Docs/Design/` covering data model, permission resolution, API changes, and migration strategy.
**Success Criteria**: Design doc reviewed with explicit decisions on scope selection and enforcement mode.
**Tests**: N/A
**Status**: In Progress

## Stage 3: Core implementation
**Goal**: Implement scoped RBAC propagation (schema + permission resolution + settings) behind a feature flag.
**Success Criteria**: Scoped permissions computed for active org/team, defaulting to legacy behavior when disabled.
**Tests**: Unit tests for resolution logic + migration coverage.
**Status**: Not Started

## Stage 4: Endpoint wiring + tests
**Goal**: Wire scoped permission checks into auth dependencies/endpoints where required and add integration tests.
**Success Criteria**: Key endpoints honor org/team permissions without regressing single-user mode.
**Tests**: Integration tests for org/team scoped access; update auth/privileges tests.
**Status**: Not Started

## Stage 5: Docs + rollout
**Goal**: Update PRD/README and add migration/rollout guidance.
**Success Criteria**: Docs cover feature flag behavior, defaults, and upgrade notes.
**Tests**: N/A
**Status**: Not Started
