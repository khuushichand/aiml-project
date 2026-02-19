# Implementation Plan: Knowledge QA - History and Thread Management

## Scope

Components: `apps/packages/ui/src/components/Option/KnowledgeQA/HistorySidebar.tsx`, `apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx`, history persistence and restore helpers
Finding IDs: `5.1` through `5.12`

## Finding Coverage

- Preserve strong mobile grouping and safety patterns: `5.2`, `5.3`, `5.6`, `5.11`
- Improve discoverability and accessibility affordances: `5.1`, `5.7`, `5.12`
- Restore richer thread context and recognition: `5.4`, `5.5`
- Add retrieval/organization power tools: `5.8`, `5.9`, `5.10`

## Stage 1: Accessibility and Discoverability Corrections
**Goal**: Make sidebar controls visible and understandable across mouse, keyboard, and touch.
**Success Criteria**:
- Collapsed desktop affordance includes tooltip/first-use cue for expansion (`5.1`).
- Delete control is visible on keyboard focus and accessible on touch interaction (`5.7`).
- Active history item exposes visual selected state and `aria-current` semantics (`5.12`).
**Tests**:
- Component tests for tooltip and collapsed-state affordance visibility.
- Accessibility tests for focus-visible/group-focus-within delete button behavior.
- Integration test asserting single active item marker and `aria-current` on selection.
**Status**: Complete

## Stage 2: Richer History Item Context and True Thread Restoration
**Goal**: Make history useful for recognition and immediate resumption.
**Success Criteria**:
- History rows include short answer preview when available (`5.4`).
- Restoring a thread hydrates query, answer, sources, citations, and preset (not only query text) (`5.5`).
- Restored state handles missing/partial server payloads gracefully.
**Tests**:
- Component tests for answer preview rendering/truncation.
- Provider integration tests for `restoreFromHistory` full-state hydration.
- E2E thread-switch test confirming immediate content visibility after click.
**Status**: Complete

## Stage 3: Search, Pinning, and Bulk Export Capabilities
**Goal**: Improve high-volume history management workflows.
**Success Criteria**:
- Sidebar supports history text filtering by query and optional answer preview (`5.8`).
- Threads can be pinned/favorited and grouped above chronological sections (`5.9`).
- Sidebar exposes export-all action with clear output format and status messaging (`5.10`).
**Tests**:
- Unit tests for filter matcher and pinned grouping logic.
- Integration tests for pin/unpin ordering and persistence.
- Export-all integration tests for success and failure states.
**Status**: Complete

## Stage 4: Regression Safeguards for Existing Strengths
**Goal**: Preserve currently effective behaviors while expanding capability.
**Success Criteria**:
- Mobile overlay interactions remain unchanged (`5.2`).
- Date-group labeling behavior remains stable (`5.3`).
- Two-click delete confirmation behavior remains intact (`5.6`).
- Preset shortcut button keeps opening settings panel (`5.11`).
**Tests**:
- Existing responsive tests retained and expanded for new controls.
- Grouping snapshot tests with fixed time fixtures.
- Interaction tests for delete confirm timeout/reset logic.
**Status**: Complete

## Dependencies

- Full thread restoration should share model logic with Performance (`9.7`) and Follow-Up conversation rendering (`4.4`).
