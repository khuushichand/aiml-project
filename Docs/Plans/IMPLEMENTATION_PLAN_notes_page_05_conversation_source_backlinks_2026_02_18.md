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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

## Dependencies

- Graph relationship data should be coordinated with Plan 06 models and endpoints.
- List badge/icon treatment should align with list-level metadata from Plan 01.

## Progress Notes (2026-02-18)

- Completed Stage 1 conversation label enrichment in:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
    - Added cached conversation-label resolution from `tldwClient.getChat` using a title/topic fallback chain.
    - Wired resolved labels into both notes list and editor header backlink surfaces.
    - Preserved raw UUIDs in tooltips for debugging while showing human-readable labels by default.
  - `/apps/packages/ui/src/components/Notes/NotesListPanel.tsx`
    - Added conversation-label map support and backlink tooltip with full conversation UUID.
  - `/apps/packages/ui/src/components/Notes/NotesEditorHeader.tsx`
    - Added conversation label prop and debug tooltip for raw conversation UUID.
- Added Stage 1 verification in:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage26.backlink-labels.test.tsx`
    - Verifies title-label rendering, topic-label fallback when title is empty, and raw-ID fallback on metadata errors.
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesListPanel.stage15.metadata-badges.test.tsx`
    - Confirms backlink badge/icon rendering remains intact for scan-friendly list rows.

### Stage 2 completion (2026-02-18)

- Surfaced source memberships in the notes editor header by extending neighbor parsing for `source_membership` edges in:
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
  - `/apps/packages/ui/src/components/Notes/NotesEditorHeader.tsx`
- Added source chip routing behavior:
  - URL-like source references open in a new tab.
  - Media permalink-like references navigate to `/media?id=...`.
- Added Stage 2 tests:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage27.source-links.test.tsx`
    - Verifies sorted source-chip rendering and route/open behavior by source type.

### Stage 3 completion (2026-02-18)

- Added in-product discoverability hint for chat-to-note quick save in the active empty state:
  - `/apps/packages/ui/src/components/Notes/NotesListPanel.tsx`
- Preserved and regression-tested same-tab linked-conversation navigation (no forced new-tab behavior by default):
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage26.backlink-labels.test.tsx`
- Added Stage 3 discoverability test:
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesListPanel.stage19.quick-save-hint.test.tsx`
