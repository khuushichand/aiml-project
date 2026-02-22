# Implementation Plan: Workspace Playground - Cross-Pane Interaction and Information Flow

## Scope

Components: interactions spanning `SourcesPane`, `ChatPane`, `StudioPane`, `QuickNotesSection`
Finding IDs: `6.1` through `6.7`

## Finding Coverage

- Source/chat traceability: `6.3`, `6.6`
- Output/chat/notes interoperability: `6.2`, `6.4`
- Advanced interaction and navigation: `6.1`, `6.5`, `6.7`

## Stage 1: Core Cross-Pane Actions
**Goal**: Connect evidence, outputs, and notes into one continuous workflow.
**Success Criteria**:
- Citation click scrolls/highlights matching source row in Sources pane.
- Artifacts support `Discuss in chat` and inject structured context message.
- Artifacts support `Save to notes` without copy/paste.
**Tests**:
- Integration tests for citation -> source focus/highlight.
- Integration tests for discuss action preserving source context.
- Integration tests for artifact-to-note save behavior.
**Status**: Complete

## Stage 2: Source-to-Chat Direct Manipulation
**Goal**: Reduce friction for source-specific questioning.
**Success Criteria**:
- Sources are draggable to chat drop zone.
- Drop action temporarily scopes selected source(s) and seeds prompt template.
- Deselecting sources mid-thread shows warning that prior answers may reference removed context.
**Tests**:
- Component tests for drag handles and drop target states.
- Integration tests for drop payload and selection scoping.
- Component test for context-change warning notification.
**Status**: Complete

## Stage 3: Global Navigation and Context Transition Cues
**Goal**: Improve navigation across all workspace artifacts and contexts.
**Success Criteria**:
- Global search (`Cmd/Ctrl+K`) returns unified results for sources/chat/notes.
- Selecting a result focuses relevant pane and target item.
- Workspace switch applies brief transition/progress cue to avoid abrupt context swap.
**Tests**:
- Integration tests for keyboard shortcut open/close behavior.
- Search index tests for mixed-domain ranking and filtering.
- Visual/integration test for workspace switch transition.
**Status**: Complete

## Dependencies

- Relies on workspace snapshot integrity from Category 5.
- Citation and discuss actions should reuse contracts defined in Categories 2 and 3.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Citation click -> source focus/highlight is wired from chat citations into source pane focus actions.
  - Studio artifacts support `Discuss in chat` via workspace event contract and message injection.
  - Studio artifacts support `Save to notes` append/replace actions (integrated with workspace note capture flow).
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`

- Stage 2 completed:
  - Added drag payload contract for sources (`application/x-tldw-workspace-source`).
  - Made source rows draggable and serialized source context on drag start.
  - Added chat drop zone that scopes selection to dropped source and seeds a source-specific prompt template.
  - Added contextual warning toast when selected sources are removed mid-conversation.
- Files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/drag-source.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx`
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage4.test.tsx src/store/__tests__/workspace.test.ts`

- Stage 3 completed:
  - Added workspace-global search index utility with unified result ranking across Sources, Chat messages, and current Quick Note (`Cmd/Ctrl+K`/`Ctrl+K` shortcut support).
  - Added workspace-level global search modal in `WorkspacePlayground` with keyboard open/close, arrow-key navigation, and domain-filter prefixes (`source:`, `chat:`, `note:`).
  - Wired focus routing:
    - Source result -> opens Sources pane/drawer/tab and focuses/highlights source row.
    - Chat result -> routes to chat message target and highlights message.
    - Note result -> opens Studio pane/drawer/tab, expands notes section, and focuses title/content editor target.
  - Added workspace switch transition cue overlay to reduce abrupt context swap perception.
  - Added cross-pane transient focus targets to workspace store (`chatFocusTarget`, `noteFocusTarget`) with clear/focus actions.
- Files updated:
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/workspace-global-search.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/QuickNotesSection.tsx`
  - `apps/packages/ui/src/store/workspace.ts`
  - `apps/packages/ui/src/store/__tests__/workspace.test.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/workspace-global-search.test.ts`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage2.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage3.test.tsx`
  - `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage4.test.tsx`
- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/workspace-global-search.test.ts src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx --reporter=verbose`
  - `cd apps/packages/ui && bunx vitest run src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.desktop-layout.test.tsx src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/workspace-global-search.test.ts src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage1.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage2.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage3.test.tsx src/components/Option/WorkspacePlayground/__tests__/QuickNotesSection.stage4.test.tsx src/components/Option/WorkspacePlayground/__tests__/source-location-copy.test.ts src/components/Option/WorkspacePlayground/__tests__/workspace-header.utils.test.ts src/store/__tests__/workspace.test.ts`
