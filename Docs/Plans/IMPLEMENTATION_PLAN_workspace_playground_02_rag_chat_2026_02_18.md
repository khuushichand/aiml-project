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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

## Dependencies

- Citation navigation depends on shared cross-pane navigation action from Category 6.
- Workspace-scoped chat persistence should align with workspace snapshot model in Category 5.

## Progress Notes (2026-02-18)

- Stage 1 implemented in `ChatPane`:
  - Added stop-generation control in the composer while streaming, wired to `stopStreamingRequest`.
  - Added clear-chat icon control with confirmation and full local message/session reset.
  - Added connection failure banner with retry action backed by `useConnectionStore().checkOnce`.
  - Added workspace-aware chat session save/restore behavior on workspace switches.
- Workspace store enhancements:
  - Added persisted `workspaceChatSessions` map keyed by workspace ID.
  - Added actions: `saveWorkspaceChatSession`, `getWorkspaceChatSession`, `clearWorkspaceChatSession`.
  - Wired chat-session cleanup into workspace delete flow and rehydration defaults.
- Files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
  - `apps/packages/ui/src/store/workspace.ts`
  - `apps/packages/ui/src/store/__tests__/workspace.test.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx src/store/__tests__/workspace.test.ts`
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx src/store/__tests__/workspace.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx src/components/Option/WorkspacePlayground/__tests__/workspace-header.utils.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts`

## Progress Notes (2026-02-18 - Stage 2)

- Citation traceability:
  - Added workspace store actions for cross-pane source focus (`focusSourceByMediaId`, `focusSourceById`, `clearSourceFocusTarget`) with transient focus token support.
  - Wired `ChatPane` citation clicks (`PlaygroundMessage.onSourceClick`) to resolve source targets via media ID first, then title/url fallback matching.
  - Updated `SourcesPane` to react to focus targets by scrolling to the source, clearing active filters when needed, and applying a transient visual highlight.
- Context clarity:
  - Updated `ChatContextIndicator` to show a collapsed source chip list with `+N more` and a `Show less` expansion control.
- Retrieval transparency:
  - Added per-response retrieval diagnostics panel under assistant messages with chunk count, source count, and average relevance score.
  - Diagnostics gracefully infer values from partial source metadata when generation-level retrieval metrics are missing.
- Files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx`
  - `apps/packages/ui/src/store/workspace.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx`
  - `apps/packages/ui/src/store/__tests__/workspace.test.ts`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/store/__tests__/workspace.test.ts`

## Progress Notes (2026-02-18 - Stage 3)

- Adaptive prompting:
  - Updated empty-state examples to adapt to selected source types (video/audio/document/website), with source-aware prompts and generic fallback prompts.
- Mode controls:
  - Added explicit chat mode toggle (`General chat` vs `RAG mode`) in the composer area.
  - Mode selection now drives effective retrieval behavior by synchronizing `ragMediaIds`, `chatMode`, and `fileRetrievalEnabled`.
  - Added contextual warning when sources are selected but General mode is active.
- Advanced RAG settings:
  - Added expandable settings panel with controls for `top_k`, `min_score` (similarity threshold), and `enable_reranking`.
  - Settings update existing RAG store fields (`setRagTopK`, `setRagAdvancedOptions`) with safe bounds handling.
- Input affordance:
  - Added keyboard helper text under chat composer: `Enter to send, Shift+Enter for new line`.
- Files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/store/__tests__/workspace.test.ts`
