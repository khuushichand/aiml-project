## Stage 1: Cover Lifecycle Regressions
**Goal**: Add failing tests for fresh-topic reset and active-thread deletion recovery.
**Success Criteria**: New tests fail against the current behavior for the intended reasons.
**Tests**:
- `bunx vitest run src/components/Option/KnowledgeQA/__tests__/FollowUpInput.accessibility.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.persistence.test.tsx --config vitest.config.ts`
**Status**: Complete

## Stage 2: Centralize Provider Lifecycle Actions
**Goal**: Implement provider-owned thread lifecycle actions and rewire the follow-up UI.
**Success Criteria**:
- `New Topic` resets visible state and creates a new thread.
- Deleting the active thread clears stale active-session state.
- Existing restore/resume behavior remains intact.
**Tests**:
- `bunx vitest run src/components/Option/KnowledgeQA/__tests__/FollowUpInput.accessibility.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.persistence.test.tsx --config vitest.config.ts`
**Status**: Complete

## Stage 3: Focused Verification
**Goal**: Re-run the relevant Knowledge QA suites and security check.
**Success Criteria**: Focused tests are green and Bandit reports no findings for touched Knowledge QA files.
**Tests**:
- `bunx vitest run src/components/Option/KnowledgeQA/__tests__/FollowUpInput.accessibility.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.persistence.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.history.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.branch-share.test.tsx --config vitest.config.ts`
- `source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/KnowledgeQA -f json -o /tmp/bandit_knowledge_qa_thread_lifecycle.json`
**Status**: Complete
