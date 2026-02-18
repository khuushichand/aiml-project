# Implementation Plan: Flashcards H6 - Recognition Rather Than Recall

## Scope

Route/components: `tabs/ManageTab.tsx`, `tabs/ReviewTab.tsx`, flashcard source metadata surfaces, shortcuts/help modal components  
Finding IDs: `H6-1` through `H6-2`

## Finding Coverage

- Card origin (`source_ref_type`, `source_ref_id`) is stored but not surfaced: `H6-1`
- Shortcut discovery depends on hidden/help-modal recall: `H6-2`

## Stage 1: Source Attribution Visibility
**Goal**: Let users recognize card provenance instantly without searching manually.
**Success Criteria**:
- Cards display source badges for non-manual origins (`media`, `message`, `note`) in list and edit/review contexts.
- Source badges deep-link to originating content when target exists and user has access.
- Missing/archived sources degrade gracefully with explicit "source unavailable" state.
**Tests**:
- Component tests for source badge rendering by source type.
- Integration tests for deep-link routing and permission-gated visibility.
- Regression tests for manual cards ensuring no empty source chrome appears.
**Status**: Not Started

## Stage 2: Inline Shortcut Discovery
**Goal**: Move key shortcut hints into task context so users do not need memorization.
**Success Criteria**:
- Review and Cards surfaces show persistent, low-noise shortcut chips near primary actions.
- Tooltip hints expose shortcut keys on hover/focus for action buttons.
- Shortcut help modal remains available but is no longer required for basic productivity.
**Tests**:
- Component tests for shortcut chip visibility and responsive behavior.
- Accessibility tests for tooltip keyboard focus and screen-reader labels.
- E2E tests for keyboard-only review and cards-management loops.
**Status**: Not Started

## Stage 3: Progressive Hinting and Preference Memory
**Goal**: Balance discoverability for new users and low-noise operation for experienced users.
**Success Criteria**:
- First-use sessions show expanded shortcut and source hints; experienced users can collapse/disable hints.
- User preference for hint density persists across sessions.
- Hint system does not regress performance or visual clutter on mobile.
**Tests**:
- Preference persistence tests for hint toggle state.
- Visual regression tests for dense vs minimal hint modes.
- Analytics instrumentation test for hint exposure and dismissal events.
**Status**: Not Started

## Dependencies

- Stage 1 depends on source metadata being included in list/review API payloads.
- Stage 2 hint placement should align with H8 minimalism constraints.
- Stage 3 preference model should integrate with existing user settings persistence patterns.
