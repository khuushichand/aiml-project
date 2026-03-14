## Stage 1: Define the focused UX pass
**Goal**: Limit this pass to sequence editing controls and clearer slide-level publish readiness cues.
**Success Criteria**: The scope stays within store/UI changes for slide movement and progress visibility.
**Tests**: N/A
**Status**: Complete

## Stage 2: Add regression coverage for sequence editing and progress cues
**Goal**: Add tests for reordering slides and surfacing ready-versus-needs-attention states in the rail.
**Success Criteria**: Tests fail before implementation and cover both the store transition and visible UI cues.
**Tests**: Vitest store/component tests for move-up/down behavior and progress labels.
**Status**: Complete

## Stage 3: Implement sequence editing and slide progress improvements
**Goal**: Add move earlier/later controls, update slide ordering, and show explicit ready/attention cues in the rail.
**Success Criteria**: Users can reorder slides without drag/drop, selected-slide controls respect boundaries, and the rail shows which slides are render-ready.
**Tests**: Existing and new Vitest tests.
**Status**: Complete

## Stage 4: Verify with targeted tests and Playwright audit
**Goal**: Confirm the next UX pass preserves the working create/load flow and improved responsive layout.
**Success Criteria**: Targeted Vitest suite passes and the Presentation Studio Playwright audit passes.
**Tests**: `bunx vitest run ...`, `bunx playwright test e2e/ux-audit/presentation-studio.spec.ts --project=chromium --reporter=line`
**Status**: Complete
