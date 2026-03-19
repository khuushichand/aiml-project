## Stage 1: Finish Full UI Typecheck Cleanup
**Goal**: Remove the remaining full-package `tsc` failures introduced by stale fixtures, MCP Hub path typing drift, and Presentation Studio metadata typing.
**Success Criteria**: `bunx tsc --noEmit -p tsconfig.json` completes successfully from `apps/packages/ui`.
**Tests**: Full UI typecheck plus targeted Vitest suites for touched areas.
**Status**: Complete

## Stage 2: Reverify Touched UI Areas
**Goal**: Prove the cleanup did not regress the touched flows in Presentation Studio, Workspace Playground, MCP Hub, PersonaGarden, Flashcards, and Knowledge QA.
**Success Criteria**: Targeted Vitest suites covering the touched files pass.
**Tests**: Focused `vitest run` commands for affected components and stores.
**Status**: Complete

## Stage 3: Polish Custom Style Authoring UI
**Goal**: Replace the current raw custom-style authoring experience with a more guided editor while preserving advanced controls.
**Success Criteria**: Common visual-style fields are form-driven, advanced JSON is isolated, and style CRUD behavior remains covered by tests.
**Tests**: Presentation Studio visual-style CRUD tests and any new UI tests for the guided editor.
**Status**: Complete
