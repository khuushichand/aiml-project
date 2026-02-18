# Implementation Plan: World Books - Entry Management Drawer

## Scope

Components: Entries drawer, entry add/edit forms, entry table rendering, keyword tooling, bulk-add parser UX in `Manager.tsx` and `entryParsers.ts`.
Finding IDs: `3.1` through `3.13`

## Finding Coverage

- Core layout and performance fixes: `3.1`, `3.2`
- Entry authoring usability and validation: `3.3`, `3.4`, `3.5`, `3.6`, `3.9`, `3.10`
- Discovery and diagnostics in large entry sets: `3.7`, `3.11`
- Bulk-add clarity and throughput: `3.8`, `3.13`
- Prioritized backlog item: `3.12`

## Stage 1: Fix Drawer Sizing Contract and Render Performance
**Goal**: Stabilize drawer behavior and prevent performance collapse on large lorebooks.
**Success Criteria**:
- Replace invalid `size` usage with `width={screens.md ? "60vw" : "100%"}`.
- Introduce table virtualization (`virtual` or equivalent) with verified behavior on 200+ entries.
- Preserve selection/edit interactions and sticky controls under virtualization.
**Tests**:
- Component test for responsive drawer width on mobile and desktop breakpoints.
- Performance test rendering 200+ entries with acceptable frame/interaction budget.
- Regression test for row selection/edit actions under virtualized rendering.
**Status**: Not Started

## Stage 2: Upgrade Entry Authoring Controls
**Goal**: Make keyword/content authoring accurate, inspectable, and low-friction.
**Success Criteria**:
- Replace comma-input keywords with tag-based input (`Select mode="tags"` or equivalent).
- Show keyword preview in both Add and Edit flows.
- Add content character and estimated token count using shared estimator logic.
- Add visual priority scale treatment and appendable tooltip help text.
- Persist matching-options panel open/closed state per session.
- Add client-side regex validation when regex mode is enabled.
**Tests**:
- Component tests for keyword add/remove, preview sync, and edit-mode parity.
- Unit tests for token estimator formatting and priority-band mapping.
- Validation tests for regex success/failure states and blocked submit behavior.
**Status**: Not Started

## Stage 3: Add Entry Search/Filter and Promote Keyword Index Visibility
**Goal**: Improve findability and conflict debugging in large entry sets.
**Success Criteria**:
- Add search filtering by keyword and content substring.
- Add enabled-state filter (`All`, `Enabled`, `Disabled`).
- Promote keyword index with conflict-count badge visibility when conflicts exist.
**Tests**:
- Component tests for combined search + status filtering.
- Component tests for conflict badge count and empty-state behavior.
- Accessibility tests for filter controls and keyword index summary announcement.
**Status**: Not Started

## Stage 4: Harden Bulk Add Workflow and Throughput
**Goal**: Make bulk entry import fast and self-explanatory.
**Success Criteria**:
- Document all supported separators (`=>`, `->`, `|`, tab) in UI help.
- Replace fully sequential add loop with bounded concurrency batch strategy.
- Add progress indicator and per-entry failure summary for bulk-add runs.
**Tests**:
- Unit tests for parser format examples and invalid line diagnostics.
- Integration test for bounded concurrency batch behavior with mixed success/failure entries.
- UI test verifying progress updates and terminal summary messaging.
**Status**: Not Started

## Stage 5: Reordering Roadmap Decision
**Goal**: Resolve drag-and-drop reorder request with explicit product decision.
**Success Criteria**:
- Capture decision record: keep priority-only ordering for now or implement drag-and-drop.
- If deferred, add UX copy clarifying priority controls determine order.
- If implemented, ensure persisted ordering semantics do not conflict with priority scoring.
**Tests**:
- Decision artifact added and linked in plan/docs.
- If implemented: integration tests for reorder persistence.
- If deferred: component test for priority-ordering explanatory copy.
**Status**: Not Started

## Dependencies

- Virtualization approach must remain compatible with bulk selection and inline actions.
- Batch add throughput improvements should align with backend rate-limit expectations.
