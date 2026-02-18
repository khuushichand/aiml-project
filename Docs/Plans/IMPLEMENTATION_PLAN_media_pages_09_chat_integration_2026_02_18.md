# Implementation Plan: Media Pages - Chat Integration

## Scope

Pages/components: media-to-chat actions in `ContentViewer.tsx` and multi-selection chat entry points in `MediaReviewPage.tsx`
Finding IDs: `9.1` through `9.3`

## Finding Coverage

- Preserve working media-chat integration path: `9.1`
- Improve action clarity for users: `9.2`
- Add multi-item RAG chat from selection: `9.3`

## Stage 1: Clarify Existing Chat Action Semantics
**Goal**: Remove ambiguity between "chat with media" and "chat about media".
**Success Criteria**:
- Tooltips/help text explain context differences for both actions.
- Labels remain concise and understandable in compact layouts.
- Analytics/telemetry (if present) can distinguish action usage.
**Tests**:
- Component tests for tooltip content and accessibility attributes.
- Regression tests ensuring both callbacks still dispatch correctly.
- UX copy snapshot test to avoid accidental wording drift.
**Status**: Not Started

## Stage 2: Multi-Item "Chat About Selection"
**Goal**: Let users launch RAG chat across selected items in `/media-multi`.
**Success Criteria**:
- New action appears when one or more items are selected, with clear selected-count context.
- Selected media IDs/context are passed into chat initialization event/payload.
- Error handling covers invalid or stale selections.
**Tests**:
- Integration tests for selection -> chat launch payload.
- Component tests for action enable/disable states.
- Regression tests for single-item chat entry points.
**Status**: Not Started

## Stage 3: Stability and Backward Compatibility
**Goal**: Ensure new chat entry paths do not regress existing chat behavior.
**Success Criteria**:
- Existing `tldw:discuss-media` event flow remains functional.
- Single-item "chat with" and "chat about" flows remain unchanged.
- Multi-item payload handling is backward compatible when chat consumer only expects one ID.
**Tests**:
- Event contract tests for media chat events.
- Integration tests for both single-item and multi-item launch paths.
- Error-state tests for chat target initialization failure.
**Status**: Not Started

## Dependencies

- Multi-item launch semantics should align with search/filter context behavior in Category 7.
