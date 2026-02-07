## Stage 1: Audit Playground Search & Context RAG Surface
**Goal**: Map the fullscreen chat playground Search & Context modal UX and identify RAG option gaps versus Knowledge QA.
**Success Criteria**: Clear list of missing controls, weak constraints, and test coverage gaps.
**Tests**: Review existing e2e coverage for playground knowledge panel and settings tabs.
**Status**: Complete

## Stage 2: Implement RAG Option Parity in Search & Context Modal
**Goal**: Add complete key-level RAG option access in the playground modal and fix incorrect bounds on exposed controls.
**Success Criteria**: Users can reach all RAG keys from modal settings; known invalid ranges no longer produce avoidable 422s.
**Tests**: Targeted UI assertions for settings tab and all-options editor behavior.
**Status**: Complete

## Stage 3: Add/Update E2E Coverage for Fullscreen Chat Modal
**Goal**: Validate Search & Context modal UX in fullscreen chat playground and ensure RAG settings UI is reachable and functional.
**Success Criteria**: New/updated Playwright spec passes locally and confirms key flows.
**Tests**: `apps/extension/tests/e2e/knowledge-rag-ux.spec.ts` and focused playground RAG checks.
**Status**: Complete

## Stage 4: Live Verification Against Local Server
**Goal**: Run live UX checks against `127.0.0.1:8000` to validate no regressions in real-server behavior.
**Success Criteria**: Live suite passes with deterministic outcomes and useful diagnostics artifacts.
**Tests**: `apps/extension/tests/e2e/live-ux-review.spec.ts` targeted run.
**Status**: Not Started
