# Knowledge Source Card Header Density Implementation Plan

## Stage 1: Lock the target behavior
**Goal**: Add regression coverage for a lower-density header treatment in the evidence rail cards.
**Success Criteria**: Tests describe the compact header hierarchy and fail before implementation.
**Tests**: `bunx vitest run src/components/Option/KnowledgeQA/__tests__/SourceCard.behavior.test.tsx`
**Status**: Complete

## Stage 2: Reduce metadata competition in the compact header
**Goal**: Rework the compact source-card header so the title leads, secondary metadata is collapsed, and badges have a clearer priority order.
**Success Criteria**: Compact cards show a shorter, more structured metadata header without removing useful provenance signals.
**Tests**: `bunx vitest run src/components/Option/KnowledgeQA/__tests__/SourceCard.behavior.test.tsx src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx`
**Status**: Complete

## Stage 3: Verify in the live knowledge page
**Goal**: Confirm the rendered rail is easier to scan on `127.0.0.1:3000/knowledge` and run the touched verification suite.
**Success Criteria**: Live page shows lighter header density; targeted tests and Bandit pass.
**Tests**: `bunx vitest run src/components/Option/KnowledgeQA/__tests__/SourceList.behavior.test.tsx src/components/Option/KnowledgeQA/__tests__/SourceList.accessibility.test.tsx src/components/Option/KnowledgeQA/__tests__/SourceCard.behavior.test.tsx src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx src/components/Option/KnowledgeQA/__tests__/ConversationThread.test.tsx src/components/Option/KnowledgeQA/__tests__/FollowUpInput.accessibility.test.tsx src/components/Option/KnowledgeQA/__tests__/AnswerWorkspace.a11y.test.tsx`
**Status**: Complete
