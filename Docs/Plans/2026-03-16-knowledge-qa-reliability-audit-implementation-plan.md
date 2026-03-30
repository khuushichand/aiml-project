## Stage 1: Thread And History Reliability
**Goal**: Remove one-shot hydration failures and stale thread lifecycle state.
**Success Criteria**: Thread/share routes retry after transient failures; failed thread restores do not blank the active session; local/server history hydration is resilient.
**Tests**: `KnowledgeQAProvider.history.test.tsx`, `KnowledgeQA.golden-layout.test.tsx`, `KnowledgeQAProvider.persistence.test.tsx`
**Status**: Complete

## Stage 2: Export, Copy, And Timer Cleanup
**Goal**: Make export/share/copy feedback state follow the latest user action and clean up on close or unmount.
**Success Criteria**: Repeated copy actions keep the latest confirmation active for its full duration; delayed print/copy actions do not survive close/unmount; export dialog state reopens cleanly.
**Tests**: `ExportDialog.a11y.test.tsx`, `SourceCard.behavior.test.tsx`, `AnswerPanel.states.test.tsx`, `SettingsPanel.behavior.test.tsx`
**Status**: Complete

## Stage 3: Remaining Settings And Interaction Guardrails
**Goal**: Audit the remaining Knowledge QA UI state transitions that users hit frequently.
**Success Criteria**: Settings and history/sidebar interactions recover cleanly from rapid toggles, blocked storage, and repeated actions.
**Tests**: Focused Knowledge QA Vitest suite plus Bandit on touched paths
**Status**: In Progress
