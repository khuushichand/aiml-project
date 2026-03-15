# Workspace Playground WebUI + Extension Parity Design

Date: 2026-03-04
Owner: Codex collaboration session
Status: Approved (design)

## Context and Problem

The repository already has substantial Workspace Playground coverage, but it is uneven across clients:

- WebUI (`apps/tldw-frontend`) has dedicated Playwright workflow specs for `/workspace-playground`, including a real-backend variant.
- Extension (`apps/extension`) has route-level and tutorial-level checks touching `/workspace-playground`, but no dedicated end-to-end functional suite for the page itself.

This creates parity risk between WebUI and extension behavior for one of the highest-value routes.

## Goals

1. Establish a scalable, maintainable parity test strategy for `/workspace-playground` across WebUI and extension.
2. Add CI-friendly PR gates that are stable and high-signal.
3. Preserve deeper integration confidence through nightly real-backend runs.

## Non-Goals

1. Rewriting existing component/unit test coverage in `apps/packages/ui`.
2. Making every Workspace Playground flow PR-blocking.
3. Introducing a new test framework or replacing Playwright.

## Existing Coverage Summary

### WebUI

- Dedicated E2E specs already exist:
  - `apps/tldw-frontend/e2e/workflows/workspace-playground.spec.ts`
  - `apps/tldw-frontend/e2e/workflows/workspace-playground.real-backend.spec.ts`
- Existing smoke gates include `/workspace-playground`, but smoke is broad and not deep feature workflow validation.

### Extension

- No dedicated `/workspace-playground` functional E2E spec found.
- Route appears in inventories/tutorial checks and broad workflow harnesses, but not with targeted pane/studio lifecycle assertions comparable to WebUI.

## Design Decision

Use a shared cross-platform contract plus layered execution:

1. Shared contract tests for `/workspace-playground` run in both WebUI and extension contexts.
2. PR gate uses deterministic baseline+studio checks only.
3. Nightly runs execute deeper real-backend workspace workflows.

This combines maintainability (single source of truth) with operational stability (fast deterministic PR gates).

## Architecture

### 1) Shared Test Contract Layer

Create shared workspace parity modules under `apps/test-utils`:

- `workspace-playground.contract.ts`
  - Cross-platform assertions and flow orchestration.
- `workspace-playground.page.ts`
  - Shared page object abstraction and selectors.
- `workspace-playground.fixtures.ts`
  - Deterministic seed payloads and helper generators.

Design rule: app-specific runtime differences must stay in driver/page-object adapters, not in contract logic.

### 2) Thin App Wrappers

- WebUI wrapper spec:
  - `apps/tldw-frontend/e2e/workflows/workspace-playground.parity.spec.ts`
- Extension wrapper spec:
  - `apps/extension/tests/e2e/workspace-playground.parity.spec.ts`

Each wrapper only:
- boots the correct client runtime,
- provides route navigation/auth/connection hooks,
- calls the same shared contract suite.

### 3) Reuse Existing Infrastructure

- Reuse existing auth seed and diagnostics helpers in WebUI tests.
- Reuse extension launch helpers (`launchWithBuiltExtension*` / real-server helpers) for extension tests.
- Reuse existing console/network critical-issue classifiers where available.

## PR-Blocking Gate Scope (Approved)

PR gate for `/workspace-playground` parity includes:

1. Baseline health
- Route boot succeeds.
- Core panes visible (sources/chat/studio).
- No critical console/request failures.

2. Studio critical deterministic flows
- Open output controls.
- Trigger stable output generation (start with summary path).
- Verify generated artifact appears.
- Verify primary actions (`View`, `Download`) are available.
- Verify secondary actions (`Regenerate options`, `Discuss in chat`, `Delete`) are available and at least one state transition is validated.

3. Cross-app parity
- Same core assertions executed in WebUI and extension via shared contract.

### PR Explicit Exclusions

The following are not PR-blocking and move to nightly:

- Heavy/non-deterministic media output validations (e.g., audio/slides end-state quality).
- Full backend-content quality checks.
- Large export/import payload and long-running workflows.

## Nightly Deep Coverage Scope

Nightly workspace parity/deep suite includes:

1. Real-backend resilience
- No route stubbing.
- Validate bootstrap endpoints and reachability behavior.

2. Extended studio matrix
- Validate multiple output types (`summary`, `quiz/flashcards`, `audio_overview`, optional `slides`).
- Validate create/view/edit/discuss/save/delete lifecycle where feature supports it.

3. Persistence and reload
- Verify artifact/pane/workspace continuity after reload.

4. Failure-path behavior
- Controlled server error/timeout scenarios to validate graceful degradation.

5. Evidence
- Keep traces/screenshots/videos and optional compact JSON evidence outputs for trend/debugging.

## CI Strategy

Layered model:

1. PR required check
- Fast deterministic workspace parity gate (WebUI + extension wrappers on shared contract).

2. Nightly scheduled check (and optional manual dispatch)
- Deep real-backend workspace matrix.

3. Change scoping
- Route/workspace/ui-store/shared-component path changes should trigger parity gate.

## Risks and Mitigations

1. Flakiness from async UI hydration
- Mitigation: explicit page ready criteria and stable polling with bounded timeouts.

2. Selector drift
- Mitigation: keep selectors centralized in shared page object and prefer semantic role/test-id selectors already present.

3. Divergence between wrappers
- Mitigation: keep wrappers minimal and enforce shared contract ownership for assertions.

4. PR runtime inflation
- Mitigation: strict deterministic PR scope; move deep checks to nightly.

## Success Criteria

1. A single shared workspace contract executes in both WebUI and extension.
2. PR check blocks regressions in baseline+studio critical flows for `/workspace-playground`.
3. Nightly detects deeper integration regressions not suitable for PR gate.
4. Test maintenance overhead decreases versus duplicating equivalent spec logic per client.

## Proposed Deliverables

1. Shared workspace parity contract modules under `apps/test-utils`.
2. WebUI wrapper parity spec.
3. Extension wrapper parity spec.
4. CI workflow updates for layered gating.
5. Test docs update describing run commands and gate intent.
