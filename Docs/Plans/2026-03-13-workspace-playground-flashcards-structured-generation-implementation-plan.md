## Stage 1: Lock the flashcard contract in tests
**Goal**: Prove the workspace flashcard generator uses structured source-content generation instead of raw RAG parsing.
**Success Criteria**: Stage-2 tests fail until the production path calls the flashcard generation service with selected-source content and model fallback.
**Tests**:
- `bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`
**Status**: Complete

## Stage 2: Switch workspace flashcards to the structured endpoint
**Goal**: Replace the flashcard RAG-text path with the existing `/api/v1/flashcards/generate` UI service while preserving deck persistence and artifact formatting.
**Success Criteria**: Flashcard generation no longer depends on `parseFlashcards()` for backend output and the existing edit/download behaviors still work.
**Tests**:
- `bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`
- `bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`
**Status**: Complete

## Stage 3: Verify end to end on the live workspace page
**Goal**: Confirm the real browser flow now completes flashcard generation along with the rest of the studio outputs.
**Success Criteria**: The live Playwright output-matrix probe passes without flashcard parse failures.
**Tests**:
- `TLDW_WEB_URL=http://localhost:3000 TLDW_SERVER_URL=http://127.0.0.1:8002 TLDW_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY TLDW_WEB_AUTOSTART=false bunx playwright test e2e/workflows/workspace-playground.output-matrix.probe.spec.ts --reporter=line --workers=1`
- `source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx -f json -o /tmp/bandit_workspace_flashcards_structured_generation.json`
**Status**: Complete
