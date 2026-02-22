# Implementation Plan: Characters Gap 07 - Test Harness Unification (2026-02-19)

## Issue Summary

Character-related frontend tests behave differently depending on execution context (`apps/tldw-frontend` vs `apps/packages/ui`) due to setup/polyfill divergence.

## Stage 1: Baseline and Drift Inventory
**Goal**: Inventory setup differences and capture failing/passing matrix for key suites.
**Success Criteria**:
- Vitest configs and setup files are diffed and documented.
- Failure matrix exists for target character suites across both contexts.
- Required browser/runtime polyfills are identified.
**Tests**:
- Run target suites from both package entry points and record results.
- Snapshot setup import order where relevant.
**Status**: Complete
**Update (2026-02-19)**:
- Captured baseline matrix for `Manager.first-use`, `CharacterGalleryCard`, and `search-utils` in both contexts.
- Confirmed initial frontend-context failures were driven by missing browser primitives (`matchMedia`, `ResizeObserver`).
- Identified additional runtime drift for import-preview tests tied to jsdom capability differences (`File.text`/`Blob.text` absent in jsdom `27.x`).

## Stage 2: Unify Shared Setup Contract
**Goal**: Implement common setup path so character suites run consistently in both contexts.
**Success Criteria**:
- Shared setup contains required polyfills and test utilities.
- Both contexts import same baseline setup or deterministic equivalent.
- Character suites pass from both contexts.
**Tests**:
- Run `Manager.first-use`, `CharacterGalleryCard`, and `search-utils` from both roots.
- Add smoke target that executes under both contexts.
**Status**: Complete
**Update (2026-02-19)**:
- Frontend setup now imports shared baseline setup from `apps/packages/ui/vitest.setup.ts`.
- Added jsdom-compatibility polyfill for `Blob.text()` / `File.text()` in `apps/tldw-frontend/vitest.setup.ts`.
- Added explicit smoke scripts:
  - `apps/tldw-frontend/package.json` -> `test:characters-harness`
  - `apps/packages/ui/package.json` -> `test:characters-harness`
- Verified target suites pass in both contexts (`83/83` in frontend context and `83/83` in ui context).

## Stage 3: CI Standardization and Regression Guardrails
**Goal**: Standardize CI command path and protect against future setup drift.
**Success Criteria**:
- CI job references one documented canonical command flow.
- Drift check fails when setup contracts diverge unexpectedly.
- Contributor docs explain where to add new shared setup behavior.
**Tests**:
- CI validation run using standardized command path.
- Drift-guard test proving mismatch detection.
**Status**: Complete
**Update (2026-02-19)**:
- Canonical local smoke commands have been established in both package scripts.
- Added drift guard test `apps/tldw-frontend/__tests__/vitest.setup-contract.test.ts` to enforce baseline setup import and required browser API availability.
- Added CI workflow `.github/workflows/ui-characters-harness-tests.yml` to run `test:characters-harness` in both `apps/tldw-frontend` and `apps/packages/ui`.
- Added contributor-facing harness contract documentation in `Docs/Development/Characters_Test_Harness.md`.
