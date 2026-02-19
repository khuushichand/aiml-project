# Implementation Plan: Knowledge QA - Search Experience

## Scope

Components: `apps/packages/ui/src/components/Option/KnowledgeQA/SearchBar.tsx`, `apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx`, keyboard shortcut hooks/state for `/knowledge`
Finding IDs: `1.1` through `1.10`

## Finding Coverage

- Preserve strong current behavior: `1.1`, `1.10`
- Improve input guidance and loading communication: `1.2`, `1.3`, `1.4`, `1.5`, `1.6`
- Add control safety and state clarity: `1.7`, `1.8`, `1.9`

## Stage 1: Baseline Preservation and Discovery Improvements
**Goal**: Keep the current first-load strengths while improving query discoverability.
**Success Criteria**:
- Centered-first-load to top-on-results transition remains unchanged and tested (`1.1`).
- Example query rotator includes broader research intents and still pauses on focus (`1.2`).
- Keyboard hint treatment supports first-visit emphasis without permanent visual noise (`1.3`).
- Subtitle/description is programmatically associated with the search input (`1.10`).
**Tests**:
- Component regression test for pre/post-results layout classes.
- Unit test for placeholder rotation count, pause-on-focus, and expanded examples.
- Accessibility test asserting `aria-describedby` linkage for helper/subtitle content.
**Status**: Complete

## Stage 2: Loading-State Communication and Fallback Clarity
**Goal**: Make in-progress search states explicit and understandable.
**Success Criteria**:
- Submit button uses explicit loading copy/icon (not `...`) while preserving disabled behavior (`1.4`).
- Web fallback toggle includes clear explanatory tooltip text for activation behavior (`1.5`).
- Search-in-progress indicator is visually prominent beyond icon swap (progress/pulse/inline status) (`1.6`).
**Tests**:
- Component tests for loading button label/icon states.
- Tooltip rendering test with keyboard and pointer triggers.
- Visual/state test confirming prominent searching indicator appears while `isSearching=true`.
**Status**: Complete

## Stage 3: Search Cancellation and Safer Clearing Semantics
**Goal**: Prevent lock-in during long searches and avoid destructive accidental clears.
**Success Criteria**:
- In-flight search can be aborted from UI with a stop/cancel action and cancellation feedback (`1.7`).
- Query clear action no longer wipes thread/results by default (`1.8`).
- Separate explicit action exists for resetting results/thread state (`1.8`).
- Input enforces max length and surfaces count feedback near limits (`1.9`).
**Tests**:
- Integration test with mocked delayed request + AbortController cancellation.
- Reducer/provider tests for split behaviors: clear query vs clear full session.
- Input constraint test for `maxLength` and near-limit helper state.
- E2E test for canceling a long-running search and continuing with a new query.
**Status**: Complete

## Stage 4: Instrumentation and UX Guardrails
**Goal**: Ensure search changes are measurable and regression-safe.
**Success Criteria**:
- Telemetry distinguishes submit, cancel, and clear-full actions.
- Search error/cancel outcomes have deterministic user-visible status.
- Keyboard shortcuts remain functional after UI updates.
**Tests**:
- Event emission/unit tests for action analytics payloads.
- Integration tests for shortcut `/` focus and `Cmd+K` reset behavior.
**Status**: Complete

## Dependencies

- Cancellation plumbing should align with loading/error-state work in Answer Display and Error Handling plans.
