# Implementation Plan: Quiz Page - Manage Quiz Tab

## Scope

Components: `ManageTab`, quiz list cards/table actions, edit modal, soft-delete undo lifecycle
Finding IDs: `4.1` through `4.8`

## Finding Coverage

- Safe deletion and undo reliability: `4.1`, `4.8`
- Edit modal scalability and ordering controls: `4.2`, `4.3`
- Operational productivity features: `4.4`, `4.5`, `4.6`
- Source traceability metadata: `4.7`

## Stage 1: Deletion UX Hardening
**Goal**: Make destructive actions recoverable and visible regardless of navigation changes.
**Success Criteria**:
- Replace ephemeral undo toast with persistent, keyboard-focusable notification/banner.
- Pending delete state survives tab switches within undo grace window.
- Commit/undo outcomes are explicit and auditable in UI state.
**Tests**:
- Integration tests for undo availability after tab switch/navigation.
- Accessibility tests for keyboard focusability of undo control.
- Mutation tests for delete commit timing and cancellation behavior.
**Status**: Not Started

## Stage 2: Edit Modal Usability at Scale
**Goal**: Reduce complexity when editing quizzes with many questions.
**Success Criteria**:
- Edit modal supports question reorder controls matching Create tab behavior.
- Replace nested question pagination with virtualized scrolling or full-screen edit layout.
- Form state remains stable while scrolling/reordering long question sets.
**Tests**:
- Component tests for reorder actions and persisted order.
- Integration tests for long-list edit interactions without pagination confusion.
- Performance smoke tests for modal behavior with large question counts.
**Status**: Not Started

## Stage 3: Bulk and Clone Operations
**Goal**: Improve operational throughput for power users.
**Success Criteria**:
- Add `Duplicate` action to clone quiz metadata and questions.
- Add row selection + bulk operations for delete/export.
- Bulk actions provide clear confirmation and partial failure messaging.
**Tests**:
- Integration tests for duplicate creating independent editable copy.
- Component tests for selection model and bulk toolbar state.
- Mutation tests for mixed success/failure bulk action reporting.
**Status**: Not Started

## Stage 4: Export and Source Context Visibility
**Goal**: Improve portability and source traceability.
**Success Criteria**:
- Add per-quiz export options (JSON minimum, PDF optional path).
- Show source media name/link on quiz cards when `media_id` exists.
- Export payload includes metadata required for future import compatibility.
**Tests**:
- API/UI contract tests for export schema stability.
- Component tests for source link rendering and navigation.
- Regression tests validating export compatibility with planned import flow.
**Status**: Not Started

## Dependencies

- Reorder implementation should share contracts with `IMPLEMENTATION_PLAN_quiz_page_03_create_quiz_tab_2026_02_18.md`.
- Export format should align with import roadmap in `IMPLEMENTATION_PLAN_quiz_page_12_information_gaps_missing_functionality_2026_02_18.md`.
