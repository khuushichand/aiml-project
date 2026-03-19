## Stage 1: Reproduce the Mount Wipe
**Goal**: Add a failing test that proves persisted local history is lost during initial mount.
**Success Criteria**: The new test fails for the expected mount-order reason.
**Tests**:
- `bunx vitest run src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.history.test.tsx --config vitest.config.ts`
**Status**: Complete

## Stage 2: Defer Persistence Until Hydration
**Goal**: Gate history persistence until `loadSearchHistory()` has completed.
**Success Criteria**:
- Mount-time local history survives hydration.
- Existing history persistence and trimming behavior remain intact.
**Tests**:
- `bunx vitest run src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.history.test.tsx src/components/Option/KnowledgeQA/__tests__/historyStorage.test.ts --config vitest.config.ts`
**Status**: Complete

## Stage 3: Focused Verification
**Goal**: Re-run the touched Knowledge QA suites and Bandit.
**Success Criteria**: Focused tests are green and Bandit reports no findings.
**Tests**:
- `bunx vitest run src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.history.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.persistence.test.tsx src/components/Option/KnowledgeQA/__tests__/historyStorage.test.ts --config vitest.config.ts`
- `source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/KnowledgeQA -f json -o /tmp/bandit_knowledge_qa_history_hydration.json`
**Status**: Complete
