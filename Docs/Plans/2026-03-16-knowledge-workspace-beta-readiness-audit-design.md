# Knowledge Workspace Beta Readiness Audit Design

**Date:** 2026-03-16

## Goal

Define a live-backend-heavy audit for `/knowledge` and `/workspace-playground` that finds real user-facing bugs, identifies misleading E2E coverage, and produces a credible beta release gate for both surfaces.

## Scope

In scope:
- `/knowledge` (`KnowledgeQA`)
- `/workspace-playground` (`WorkspacePlayground`)
- Existing Playwright workflow coverage for both routes
- Related component tests and docs only as supporting context

Out of scope:
- `/researchers` and other marketing or landing pages
- Unrelated product areas outside the two target routes
- Broad CI cleanup unrelated to these two surfaces

## Route Mapping

- "ResearchQA" maps to `/knowledge`
- "Research workspace" maps to `/workspace-playground`
- `apps/tldw-frontend/e2e/workflows/tier-5-specialized/researchers.spec.ts` is not a real coverage artifact for this effort because it only validates a placeholder route expectation

## Recommended Approach

Use a live-backend-heavy broad feature sweep.

Why this approach:
- The goal is pre-beta defect reduction, not just increasing test count
- These two routes have significant backend-coupled behavior that mocked tests can hide
- Existing coverage is uneven: `/knowledge` has broad workflow coverage, while `/workspace-playground` has stronger live checks for a smaller subset of features

Mocks and route interception are still allowed for states that cannot be reproduced reliably on demand, but those tests should remain explicitly non-gating.

## Audit Model

The audit should build a feature matrix for each route and classify each feature as one of:

- `Live-covered`: validated against the real backend with meaningful assertions
- `Mock-only`: covered only with interception, store seeding, or synthetic state
- `Misleading`: a green test exists but does not actually prove the feature works
- `Missing`: no credible E2E proof exists

The matrix is a bug-finding tool, not a documentation vanity metric.

## Feature Matrix

### `/knowledge`

Audit these areas:
- Search initiation, request shape, and loading lifecycle
- Answer rendering, citations, and evidence/source coherence
- Trust and verification metadata
- No-answer, no-results, timeout, offline, and failure states
- Follow-up flow and thread continuity
- History restore and thread reload behavior
- Settings, presets, and expert mode behavior
- Export, share, and branch/thread surfaces
- Responsive/mobile behavior where user flow meaningfully changes
- Workspace handoff into `/workspace-playground`

### `/workspace-playground`

Audit these areas:
- Boot, hydration, and backend reachability
- Source intake, add-source flows, source list controls, and selection state
- Chat grounding and source scoping
- Global search and cross-pane navigation
- Notes and workspace affordances that affect user workflow
- Studio actions, artifact generation, and result rendering
- Cancellation, retry, recovery, and reload persistence
- Trust/status/telemetry surfaces that materially affect UX
- Responsive behavior only where it changes workflow correctness

## Execution Workflow

### Pass 1: Reality Check

Map current E2E tests for both routes to the feature matrix and classify them as live-covered, mock-only, misleading, or missing.

Primary output:
- a current-state coverage matrix
- a list of weak assertions and misleading tests

### Pass 2: Live Bug Hunt

Exercise both routes against the real backend and attempt to break the actual product behavior.

Key stress cases:
- cold boot
- reload and rehydration
- empty states
- slow responses
- failed responses
- follow-up continuity
- source scope changes
- workspace handoff
- artifact generation
- cancellation and recovery

Primary output:
- a prioritized bug list with concrete reproduction evidence

### Pass 3: Coverage Repair

After the live pass, tighten, replace, or remove misleading tests and add new tests for missing coverage.

Rules:
- Prefer live backend assertions wherever the state is reproducible
- Reserve mocked coverage for rare or nondeterministic edge states
- Do not count store-seeded shortcuts as full feature coverage unless they prove a unique behavior

Primary output:
- repaired E2E coverage with explicit live vs mock boundaries

### Pass 4: Beta Gate

Define a small must-pass live suite for the most user-critical workflows on both routes, and keep the broader feature sweep as non-gating regression coverage.

Primary output:
- a defensible live-backend beta gate for `/knowledge` and `/workspace-playground`

## Verification Rules

- A test only counts as `Live-covered` if it proves meaningful backend-coupled behavior
- Superficial render checks do not count as release confidence
- Store seeding, direct localStorage injection, and route interception are suspect by default
- Features that cannot be tested live deterministically should be marked non-gating rather than overstated
- Every gate test must correspond to a real user-critical workflow
- New audit tests should use explicit route-specific tags from their first draft so reruns stay deterministic as the suite grows

## High-Risk Integration Points

### `/knowledge`

- RAG request shape and settings propagation
- citation and evidence coherence
- follow-up thread continuity
- history restore correctness
- workspace handoff payload and route transition

### `/workspace-playground`

- source scoping and grounding correctness
- chat requests tied to selected sources
- studio generation correctness and completion
- cancellation and recovery behavior
- reload persistence and backend health handling

## Deliverables

- Coverage matrix for `/knowledge`
- Coverage matrix for `/workspace-playground`
- Prioritized live bug log with reproduction evidence
- Prioritized bug list with evidence
- List of misleading or insufficient existing E2E tests
- Proposed live-backend beta gate for both routes

## Working Constraints

- The current repository is dirty; planning artifacts should avoid touching unrelated work
- The approved implementation should execute in an isolated worktree
- New E2E coverage should favor accuracy over test-count inflation
- Live execution requires an explicit environment preflight for `TLDW_SERVER_URL`, `TLDW_API_KEY`, `TLDW_WEB_URL`, and Playwright web autostart behavior
- Seeded test data must be uniquely namespaced and either cleaned up or explicitly recorded to avoid polluting the shared backend state over repeated runs

## Success Criteria

This audit is successful when:
- the real feature surface for both routes is mapped to credible test coverage
- misleading tests are identified instead of trusted blindly
- concrete bugs are found and prioritized before beta exposure
- a small live-backend release gate exists for the most important workflows
- remaining risk is explicit rather than hidden behind green checks
