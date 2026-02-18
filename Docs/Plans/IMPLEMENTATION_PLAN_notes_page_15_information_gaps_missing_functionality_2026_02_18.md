# Implementation Plan: Notes Page - Information Gaps & Missing Functionality

## Scope

Components/pages: major net-new notes capabilities not covered by core reliability plans, including organization models and power-user extensions.
Finding IDs: `15.1` through `15.10`

## Finding Coverage

- High-impact near-term productivity additions: `15.1`, `15.3`, `15.4`, `15.6`
- Organizational model expansions: `15.2`, `15.9`
- Content-structure/authoring enhancements: `15.7`, `15.8`
- Offline and resilience extensions: `15.10`
- Trash functionality dependency tracked in Plan 10 for `15.5`

## Stage 1: Quick Productivity Extensions
**Goal**: Add low-complexity, high-frequency authoring improvements.
**Success Criteria**:
- Add note templates for common research workflows.
- Add pin/favorite toggle for top-of-list prioritization.
- Add duplicate-note action.
- Add keyboard shortcuts help overlay trigger (`?`).
**Tests**:
- Integration tests for template application and duplicate flow.
- Component tests for pinned ordering persistence.
- Keyboard tests for help overlay toggle and dismiss behavior.
**Status**: Not Started

## Stage 2: Organization Model Enhancements
**Goal**: Improve large-collection navigability beyond flat keywording.
**Success Criteria**:
- Define and implement notebooks/collections grouping model.
- Add timeline/calendar view prototype for date-based browsing.
- Ensure grouping model interoperates with existing keywords and search.
**Tests**:
- API tests for notebook membership create/update/delete.
- Integration tests for moving notes across collections.
- Search regression tests across notebook-filtered scopes.
**Status**: Not Started

## Stage 3: Advanced Editing Modes and Navigation Aids
**Goal**: Offer alternatives for different writing preferences and long notes.
**Success Criteria**:
- Evaluate and implement optional WYSIWYG mode alongside markdown source.
- Add generated table of contents for notes with heading thresholds.
- Preserve markdown fidelity when switching between editing modes.
**Tests**:
- Conversion fidelity tests between markdown and WYSIWYG representations.
- Component tests for TOC generation and anchor navigation.
- Regression tests for edit/preview parity with mixed markdown constructs.
**Status**: Not Started

## Stage 4: Offline Drafting and Sync Strategy
**Goal**: Reduce dependence on constant connectivity for authoring continuity.
**Success Criteria**:
- Add local draft persistence when offline.
- Implement reconnect sync flow with conflict-safe merge rules.
- Provide explicit offline/queued-sync status indicators.
**Tests**:
- Integration tests for offline edit and reconnect sync lifecycle.
- Conflict tests for offline edits against newer server versions.
- Recovery tests for interrupted sync sessions.
**Status**: Not Started

## Dependencies

- Trash/recovery UI for `15.5` is owned by Plan 10 and should be treated as prerequisite.
- WYSIWYG/editor mode decisions should align with Plan 02 editor architecture.
- Notebook/filter/search interactions should align with Plans 01 and 04.
