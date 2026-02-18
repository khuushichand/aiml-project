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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Relies on workspace snapshot integrity from Category 5.
- Citation and discuss actions should reuse contracts defined in Categories 2 and 3.
