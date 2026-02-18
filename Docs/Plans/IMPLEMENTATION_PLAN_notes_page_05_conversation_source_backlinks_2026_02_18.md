# Implementation Plan: Notes Page - Conversation & Source Backlinks

## Scope

Components/pages: note list/backlink rendering, editor header metadata, chat-navigation bridge, source relationship display.
Finding IDs: `5.1` through `5.6`

## Finding Coverage

- Human-readable backlink labels and scan-friendly indicators: `5.1`, `5.4`
- Preserve working navigation behavior with optional enhancements: `5.2`
- Source relationship visibility gaps: `5.5`
- In-product discoverability of chat-to-note flow: `5.6`
- Preserve strong quick-save behavior: `5.3`

## Stage 1: Conversation Label Enrichment
**Goal**: Replace opaque backlink identifiers with useful context.
**Success Criteria**:
- Resolve conversation UUIDs to title/topic labels in list and header surfaces.
- Show compact link icon badges for backlink notes in list rows.
- Keep full UUID available in tooltip/debug affordance.
**Tests**:
- Integration tests for UUID-to-title fallback chain when title missing.
- Component tests for icon/text rendering states.
- Error-path tests for unavailable conversation metadata.
**Status**: Not Started

## Stage 2: Source Relationship Surfacing
**Goal**: Expose note-to-source graph relationships inside notes UX.
**Success Criteria**:
- Add editor header subsection for connected media/sources.
- Read source membership from graph-service-backed endpoint.
- Provide click-through from source chips to corresponding source pages.
**Tests**:
- API integration tests for source relationship retrieval.
- Component tests for multi-source rendering and overflow handling.
- Navigation tests for source link routing behavior.
**Status**: Not Started

## Stage 3: Workflow Discoverability and Navigation Options
**Goal**: Make capture and revisit paths explicit for end users.
**Success Criteria**:
- Add empty-state/help hint explaining chat-message quick-save flow.
- Evaluate optional `open in new tab` behavior for linked-conversation navigation.
- Keep current same-tab behavior as default unless product decision changes.
**Tests**:
- UX copy tests for empty-state hint visibility.
- Integration tests for navigation mode selection if option is introduced.
- Regression tests preserving current chat-state hydration path.
**Status**: Not Started

## Dependencies

- Graph relationship data should be coordinated with Plan 06 models and endpoints.
- List badge/icon treatment should align with list-level metadata from Plan 01.
