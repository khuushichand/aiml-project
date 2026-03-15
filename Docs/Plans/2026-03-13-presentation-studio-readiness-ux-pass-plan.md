## Stage 1: Define the focused UX pass
**Goal**: Limit this pass to richer slide readiness detail and publish-prep explanations.
**Success Criteria**: The scope stays within UI/helper changes for issue reasons, duration visibility, and clearer deck readiness status.
**Tests**: N/A
**Status**: Complete

## Stage 2: Add regression coverage for readiness explanations
**Goal**: Add tests for duration formatting, issue summaries, and richer current-slide/deck-readiness content.
**Success Criteria**: Tests fail before implementation and cover both helper logic and visible UI copy.
**Tests**: Vitest unit/component tests for readiness helpers and media rail text.
**Status**: Complete

## Stage 3: Implement readiness detail and publish-prep improvements
**Goal**: Add explicit missing/stale/failed reasons, narration duration visibility, and clearer deck-level status summaries.
**Success Criteria**: Users can tell why a slide is blocked and whether narration timing is known without inferring from raw status badges.
**Tests**: Existing and new Vitest tests.
**Status**: Complete

## Stage 4: Verify with targeted tests and Playwright audit
**Goal**: Confirm the new readiness copy does not regress the working create/load and responsive flows.
**Success Criteria**: Targeted Vitest suite passes and the Presentation Studio Playwright audit passes.
**Tests**: `bunx vitest run ...`, `bunx playwright test e2e/ux-audit/presentation-studio.spec.ts --project=chromium --reporter=line`
**Status**: Complete
