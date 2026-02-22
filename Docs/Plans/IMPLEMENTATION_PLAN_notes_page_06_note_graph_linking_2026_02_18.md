# Implementation Plan: Notes Page - Note Graph & Linking

## Scope

Components/pages: related-notes discovery, graph visualizations, manual link lifecycle UI, wikilink authoring/preview behavior.
Finding IDs: `6.1` through `6.4`

## Finding Coverage

- Backend graph capability exposure gap: `6.1`
- Wikilink authoring and navigation gaps: `6.2`
- Backlinks visibility for current note: `6.3`
- Full-map browsing and traversal UX: `6.4`

## Stage 1: Related Notes and Backlinks Panels
**Goal**: Surface immediate graph value without requiring full-map view.
**Success Criteria**:
- Add `Related Notes` panel driven by `/notes/{id}/neighbors`.
- Add `Backlinks` panel listing notes linking to the current note.
- Support click-to-open note navigation from both panels.
**Tests**:
- Integration tests for neighbor/backlink fetch and panel rendering.
- Component tests for empty/error/loading states.
- Navigation tests for note-switch and unsaved-change guard interplay.
**Status**: Complete

## Stage 2: Full Graph Visualization View
**Goal**: Enable whole-graph exploration as knowledge map.
**Success Criteria**:
- Add dedicated graph view (route or modal) using Cytoscape-formatted endpoint.
- Support zoom, pan, node selection, and click-to-open note.
- Provide controls for radius and node count within safe performance defaults.
**Tests**:
- Integration tests for graph fetch parameters and rendering lifecycle.
- Interaction tests for zoom/pan/select/open flows.
- Performance tests for configured node-cap thresholds.
**Status**: Complete

## Stage 3: Manual Link Creation and Deletion UX
**Goal**: Let users curate explicit relationships between notes.
**Success Criteria**:
- Add UI to create manual links from current note to selected targets.
- Add UI to remove existing manual links with confirmation.
- Reflect link changes in related/backlink panels and graph view without full reload.
**Tests**:
- API integration tests for POST/DELETE link operations.
- Component tests for optimistic updates and rollback on failure.
- Regression tests for duplicate-link prevention and edge-type integrity.
**Status**: Complete

## Stage 4: Wikilink Authoring and Preview Navigation
**Goal**: Make `[[wikilink]]` a first-class writing workflow.
**Success Criteria**:
- Add `[[` autocomplete for note title suggestions in editor.
- Render wikilinks as clickable references in preview and split modes.
- Resolve ambiguous titles with deterministic fallback/selection behavior.
**Tests**:
- Unit tests for wikilink parsing/tokenization.
- Integration tests for autocomplete selection and insertion behavior.
- Preview tests ensuring wikilink click routes to the correct note.
**Status**: Complete

## Dependencies

- Editor insertion behavior should align with Plan 02 toolbar/cursor handling.
- Backlink/source metadata surfaces should integrate with Plan 05.

## Progress Notes (2026-02-18)

- Implemented Stage 1 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added graph-neighbor query using `/api/v1/notes/{id}/neighbors?edge_types=manual,wikilink,backlink`.
  - Added `Related notes` panel and `Backlinks` panel with click-to-open note actions.
  - Routed panel navigation through existing `handleSelectNote` flow so dirty-note discard confirmations apply consistently.
  - Added loading, empty, and error states for both panels.
- Added Stage 1 test coverage in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage5.graph-panels.test.tsx`:
  - Verifies neighbor/backlink panel rendering and navigation from related note chips.
  - Verifies unsaved-change guard blocks navigation when discard is canceled.
  - Verifies loading, empty, and error states for neighbor fetches.
- Implemented Stage 2 in `/apps/packages/ui/src/components/Notes/NotesGraphModal.tsx` and `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`:
  - Added dedicated graph modal view driven by `/api/v1/notes/graph` with Cytoscape rendering and Dagre layout.
  - Added radius and max-node controls with safe caps (radius 1 -> 300, radius 2 -> 200) and bounded edge scaling.
  - Added graph interaction controls for zoom-in, zoom-out, fit-to-view, and note selection.
  - Added selected-note open action from graph modal and integrated it with existing note selection/discard-guard flow.
- Added Stage 2 test coverage in `/apps/packages/ui/src/components/Notes/__tests__/NotesGraphModal.stage2.graph-view.test.tsx`:
  - Verifies graph fetch parameterization and radius-2 node-cap clamping behavior.
  - Verifies loading-to-canvas rendering lifecycle and zoom/fit interactions.
  - Verifies node-selection/open workflow and error-state rendering.
- Implemented Stage 3 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx` and `/apps/packages/ui/src/components/Notes/NotesGraphModal.tsx`:
  - Added manual-link create/remove controls in the related-notes panel.
  - Wired create flow to `POST /api/v1/notes/{id}/links` with duplicate-link conflict handling.
  - Wired remove flow to `DELETE /api/v1/notes/links/{edgeId}` with confirmation.
  - Added relation/graph refresh token wiring so link mutations update panel chips and graph modal without full page reload.
- Added Stage 3 test coverage in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage6.manual-links.test.tsx`:
  - Verifies create/remove manual-link workflows and refresh behavior.
  - Verifies duplicate-link conflict warning path.
- Updated Stage 1 panel tests in `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage5.graph-panels.test.tsx`:
  - Scoped related/backlink queries using dedicated list test IDs to avoid collisions with manual-link chips.
- Implemented Stage 4 in `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx` and `/apps/packages/ui/src/components/Notes/wikilinks.ts`:
  - Added `[[` trigger autocomplete in editor/split textareas with keyboard navigation and insertion.
  - Added deterministic wikilink parsing/resolution utilities and preview markdown transformation to `note://` anchors.
  - Added delegated preview/split link click handling to open linked notes via existing selection/discard flow.
- Added Stage 4 test coverage in:
  - `/apps/packages/ui/src/components/Notes/__tests__/wikilinks.test.ts`
  - `/apps/packages/ui/src/components/Notes/__tests__/NotesManagerPage.stage7.wikilinks.test.tsx`
  - Covers parsing/tokenization, deterministic ambiguous-title resolution, autocomplete insertion, and preview/split wikilink navigation.
