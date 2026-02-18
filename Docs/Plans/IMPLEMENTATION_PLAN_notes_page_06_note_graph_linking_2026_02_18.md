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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Editor insertion behavior should align with Plan 02 toolbar/cursor handling.
- Backlink/source metadata surfaces should integrate with Plan 05.
