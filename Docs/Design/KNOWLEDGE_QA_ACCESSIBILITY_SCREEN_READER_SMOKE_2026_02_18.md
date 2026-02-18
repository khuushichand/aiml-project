# Knowledge QA Accessibility Manual Smoke Checklist (Stage 4)

## Date

2026-02-18

## Scope

Manual verification checklist for release readiness of Knowledge QA accessibility semantics after Stage 1-3 remediations.

## Screen Reader Flow Checklist

1. Landmarks and skip navigation
- Confirm page exposes `main` and `aside` regions.
- Activate "Skip to search" and verify focus lands in search input.

2. Search and follow-up fields
- Verify search input announces a clear accessible name.
- Verify follow-up input announces "Ask a follow-up question".
- Verify queued follow-up state is announced while search is active.

3. Answer and citations
- Verify answer region announces guidance that citations are inline button controls.
- Navigate citation buttons with Tab and activate jump to source.

4. Settings and export dialogs
- Confirm settings modal announces dialog title and traps focus.
- Confirm export modal announces dialog title and traps focus.
- Verify Escape closes each modal and returns focus to prior control.

5. History and sources
- Confirm active history item announces current state (`aria-current`).
- Confirm source collection announces list semantics (`role=list` / `role=listitem`).

## Automated Coverage Mapping

- `SearchBar.behavior.test.tsx`: search labeling and keyboard shortcuts.
- `FollowUpInput.accessibility.test.tsx`: follow-up naming + helper guidance.
- `AnswerPanel.states.test.tsx`: citation guidance + button semantics.
- `ExportDialog.a11y.test.tsx`: dialog semantics + focus behavior.
- `HistorySidebar.responsive.test.tsx`: active thread and keyboard discoverability.
- `SourceList.accessibility.test.tsx`: list semantics for source grid/cards.
- `contrastTokens.test.ts`: token-level contrast regression guard.
