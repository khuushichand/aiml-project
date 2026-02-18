# Implementation Plan: Chat Dictionaries - Dictionary List and Overview

## Scope

Components: `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`, `apps/packages/ui/src/components/Option/Dictionaries/DictionariesWorkspace.tsx`, dictionary list APIs and related E2E coverage
Finding IDs: `1.1` through `1.9`

## Finding Coverage

- Sorting and discoverability basics: `1.1`, `1.2`, `1.8`
- Inline list actions and metadata visibility: `1.3`, `1.4`, `1.5`, `1.7`
- Chat relationship and operational safety: `1.6`
- CTA polish and visual hierarchy refinement: `1.9`

## Stage 1: Table Discoverability and Navigation
**Goal**: Make large dictionary lists quickly navigable and scannable.
**Success Criteria**:
- Name, entry-count, and active columns support deterministic sorting.
- Header-level search filters by name and description without full-page reload.
- Active-state filter exists and composes with text search.
- Pagination is explicitly configured (default 20 rows) and verified in UI tests.
**Tests**:
- Component tests for sort comparators and active-filter behavior.
- Integration tests for combined search + filter + pagination state.
- E2E test covering list navigation with 50+ dictionaries.
**Status**: In Progress

## Stage 2: High-Frequency Actions and Context Signals
**Goal**: Reduce clicks for common operations and improve list-level context.
**Success Criteria**:
- Active column replaces read-only tag with inline `Switch` update flow.
- Updated timestamp is shown in human-readable relative format with absolute tooltip.
- Entry count includes regex/literal breakdown text or badge.
- Actions column includes duplicate operation creating `"(copy)"` suffix naming.
**Tests**:
- Component test for inline active toggle success and error rollback.
- Unit test for timestamp formatting helper.
- Integration test for duplicate action and name-collision handling.
**Status**: In Progress

## Stage 3: Chat Relationship Visibility and Safe Deactivation
**Goal**: Connect dictionaries to real chat usage so activation decisions are safe.
**Success Criteria**:
- List surfaces dictionary-to-chat usage (`Used by`) via column or tooltip.
- Deactivation flow warns when linked chats are currently active.
- Warning content includes impacted chat count and safe confirmation copy.
- Data fetch strategy avoids N+1 queries for usage metadata.
**Tests**:
- API integration test for usage metadata inclusion.
- Component test for conditional deactivation warning dialog.
- E2E test validating warning appears when deactivating in-use dictionaries.
**Status**: Not Started

## Stage 4: CTA Hierarchy and UX Polish
**Goal**: Preserve current good CTA placement while improving action clarity.
**Success Criteria**:
- Primary CTA (`New Dictionary`) is visually distinct from import action.
- CTA iconography and spacing are consistent with option workspace patterns.
- No regression in keyboard and screen-reader discoverability for top actions.
**Tests**:
- Visual regression snapshot for header action area.
- Accessibility test for CTA keyboard tab order and accessible names.
**Status**: In Progress

## Dependencies

- Stage 3 depends on chat-to-dictionary association data source from the Character Chat domain.
- Deactivation confirmation messaging should align with Category 7 and Category 8 plans.
