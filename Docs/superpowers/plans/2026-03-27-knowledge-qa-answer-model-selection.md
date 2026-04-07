# Knowledge QA Answer Model Selection Plan

## Stage 1: Red Test
**Goal**: Add a focused component test proving QA quick settings exposes provider/model controls and writes through callbacks.
**Success Criteria**: The new test fails before implementation for the missing controls or callbacks.
**Tests**: `bunx vitest run src/components/Knowledge/QASearchTab/__tests__/QAQuickSettings.test.tsx`
**Status**: Complete

## Stage 2: Quick Settings Wiring
**Goal**: Surface provider/model controls in the QA page and wire them to existing `generation_provider` / `generation_model` settings.
**Success Criteria**: The QA page exposes a provider select and model autocomplete/input that stay in sync with shared settings.
**Tests**: `bunx vitest run src/components/Knowledge/QASearchTab/__tests__/QAQuickSettings.test.tsx`
**Status**: Complete

## Stage 3: Verification
**Goal**: Confirm the focused UI behavior and existing request-building path still pass after the change.
**Success Criteria**: QA quick settings tests and unified RAG request builder tests pass.
**Tests**: `bunx vitest run src/components/Knowledge/QASearchTab/__tests__/QAQuickSettings.test.tsx src/services/__tests__/unified-rag.test.ts`
**Status**: Complete
