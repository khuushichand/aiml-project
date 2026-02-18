# Implementation Plan: Workspace Playground - RAG-Powered Chat

## Scope

Components: `ChatPane`, `PlaygroundMessage`, chat input, message state/store integration
Finding IDs: `2.1` through `2.11`

## Finding Coverage

- Control and resilience: `2.5`, `2.6`, `2.7`, `2.11`
- Traceability and context clarity: `2.1`, `2.2`, `2.8`
- User control over retrieval behavior: `2.3`, `2.4`, `2.9`, `2.10`

## Stage 1: Chat Session Reliability and User Control
**Goal**: Ensure chat sessions are cancellable, recoverable, and workspace-scoped.
**Success Criteria**:
- Stop-generation button aborts in-flight streaming requests via `AbortController`.
- Chat history persists per `workspaceId` and restores on workspace switch/load.
- Clear chat action exists in header with confirmation when messages exist.
- Connection status banner appears on failures with retry action.
**Tests**:
- Unit test for abort controller wiring and cleanup.
- Integration test for workspace switch preserving independent message histories.
- Component test for clear-chat confirm and reset.
- Integration test for offline/server-failure banner and retry.
**Status**: Not Started

## Stage 2: Citation Traceability and Retrieval Transparency
**Goal**: Make RAG grounding inspectable and navigable.
**Success Criteria**:
- Citation clicks trigger `onSourceClick(mediaId)` and highlight/scroll target source.
- Source context tags show collapsed summary (`+N more`) when overflowed.
- Responses optionally expose retrieval diagnostics (chunk count, source count, relevance summary).
**Tests**:
- Component test for citation click callback payload.
- Integration test for citation -> source highlight behavior across panes.
- Snapshot/component tests for tag overflow summary logic.
- Unit test for retrieval diagnostics rendering with missing/partial metadata.
**Status**: Not Started

## Stage 3: Adaptive Prompting and Mode Controls
**Goal**: Improve intent alignment for mixed RAG/general use.
**Success Criteria**:
- Empty-state suggestions vary by selected source types.
- User can explicitly toggle `RAG` vs `General chat` regardless of source selection.
- Advanced RAG settings panel exposes `top_k`, similarity threshold, rerank toggle.
- Input helper text documents `Enter` and `Shift+Enter` behavior.
**Tests**:
- Component tests for source-type-aware suggestions.
- Integration tests for mode toggle precedence over auto mode behavior.
- Unit tests for settings value validation/bounds.
- Accessibility test for helper text discoverability.
**Status**: Not Started

## Dependencies

- Citation navigation depends on shared cross-pane navigation action from Category 6.
- Workspace-scoped chat persistence should align with workspace snapshot model in Category 5.
