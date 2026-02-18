# Implementation Plan: Knowledge QA - Performance and Perceived Speed

## Scope

Components: `apps/packages/ui/src/components/Option/KnowledgeQA/index.tsx`, `AnswerPanel.tsx`, `SourceList.tsx`, `HistorySidebar.tsx`, `KnowledgeQAProvider.tsx`
Finding IDs: `9.1` through `9.7`

## Finding Coverage

- Preserve existing fast/smooth patterns: `9.3`, `9.5`, `9.6`
- Improve perceived speed cues for long searches: `9.1`, `9.2`
- Scale result rendering and reduce empty-feeling thread switches: `9.4`, `9.7`

## Stage 1: Perceived-Latency Communication Improvements
**Goal**: Reduce uncertainty during long-running searches.
**Success Criteria**:
- Results-area reveal includes transition strategy that avoids abrupt layout perception (`9.1`).
- Loading state shows preset-aware expectation and elapsed time/stage after threshold (`9.2`).
- Existing spinner behavior remains as fallback for short operations.
**Tests**:
- Component tests for layout transition class/state behavior.
- Integration tests for elapsed-time/status messaging thresholds.
- UX regression snapshots for centered-to-results transition.
**Status**: Complete (2026-02-18)

## Stage 2: Source Rendering Scalability Strategy
**Goal**: Keep UI responsive for high `top_k` result counts.
**Success Criteria**:
- Result rendering uses threshold strategy (full render under threshold, paginate/virtualize over threshold) (`9.4`).
- Scroll behavior and keyboard interactions remain stable with scaled rendering.
- Total/visible counts are communicated to users.
**Tests**:
- Performance benchmark test for 10/25/50 result render paths.
- Integration tests for virtualization/pagination state transitions.
- Keyboard navigation tests under large result sets.
**Status**: Complete (2026-02-18)

## Stage 3: Thread-Switch Hydration for Immediate Context
**Goal**: Remove blank/empty perception when restoring prior threads.
**Success Criteria**:
- Thread switch restores latest answer/results immediately from persisted context (`9.7`).
- Fallback re-query strategy only triggers when persisted context is absent.
- Restored content and query remain consistent with selected thread metadata.
**Tests**:
- Provider integration tests for thread restore hydration branches.
- E2E test for switching between threads with immediate content display.
- State consistency tests between `messages`, `answer`, and `results`.
**Status**: Complete (2026-02-18)

## Stage 4: Regression Protection for Existing Performance Strengths
**Goal**: Keep already-good performance affordances intact.
**Success Criteria**:
- History skeleton timing behavior remains stable (`9.3`).
- Settings drawer animation speed remains unchanged (`9.5`).
- Citation scroll behavior remains smooth and browser-native (`9.6`).
**Tests**:
- Snapshot/integration tests for history skeleton duration gate.
- UI animation timing assertions for settings drawer classes.
- Interaction test for citation smooth scroll call signature.
**Status**: Complete (2026-02-18)

## Dependencies

- Thread hydration changes should be shared with History restoration plan (`5.5`).

## Implementation Notes (2026-02-18)

- Added preset-aware loading expectation copy in the answer loading state (`fast`, `balanced`, `thorough`, `custom`) while preserving staged spinner and elapsed-time feedback.
- Added explicit results-area fade-in transition strategy for results reveal while keeping the existing centered-to-top search-shell transition.
- Preserved and validated threshold rendering scalability strategy through source pagination and visible-vs-total count communication.
- Confirmed immediate thread-switch hydration path restores query, answer, sources, and citations from persisted context; stale state is cleared when context is absent.
- Added regression guards for history skeleton timing gate, settings drawer animation class contract, and native smooth citation scroll call signature.

## Verification (2026-02-18)

- `bunx vitest run src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx src/components/Option/KnowledgeQA/__tests__/HistorySidebar.responsive.test.tsx src/components/Option/KnowledgeQA/__tests__/SettingsPanel.behavior.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.focus-lifecycle.test.tsx`
- `bunx vitest run src/components/Option/KnowledgeQA/__tests__`
