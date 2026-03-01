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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

## Dependencies

- Virtualization approach must remain compatible with bulk selection and inline actions.
- Batch add throughput improvements should align with backend rate-limit expectations.

## Progress Notes (2026-02-18)

- Implemented Stage 1 in `apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - kept drawer responsive sizing with `size={screens.md ? "60vw" : "100%"}` (Ant Design v6 in this repo accepts responsive CSS values on `size`; `width` is deprecated in this version).
  - enabled entry-table virtualization with fixed scroll window (`virtual`, `pagination={false}`, `scroll={{ y: 420, x: 900 }}`) to avoid full DOM render for large lorebooks.
  - preserved existing row-selection and row-action flows under virtualization.
- Added Stage 1 integration coverage:
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.entryStage1.test.tsx`
  - validates responsive drawer sizing behavior across desktop/mobile breakpoints.
  - validates 200+ entry rendering behavior and selection/edit interactions with virtualized table.
- Implemented Stage 2 in `apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - replaced comma-string keyword inputs with tag-based `Select mode="tags"` in both add and edit forms.
  - enabled keyword preview parity in both add and edit flows.
  - added content stats (`chars` + approximate token estimate) below add/edit content fields.
  - added priority-band rendering in entry table (`x/100` with low/medium/high visual bands).
  - added contextual `Appendable` help text via `LabelWithHelp`.
  - persisted matching-options disclosure state in `sessionStorage` for add/edit forms.
  - added client-side regex syntax validation for keyword lists before submit when regex mode is enabled.
- Added Stage 2 utilities and tests:
  - `apps/packages/ui/src/components/Option/WorldBooks/worldBookEntryUtils.ts`
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/worldBookEntryUtils.test.ts`
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.entryStage2.test.tsx`
- Implemented Stage 3 in `apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - added entry-level search (`keyword` + `content` substring matching).
  - added entry enabled-state filter (`All`, `Enabled`, `Disabled`).
  - wired filtered data source into the entry table with explicit filtered empty-state copy.
  - promoted keyword-index visibility with conflict-count text in the summary (`Keyword Index (N conflicts)`).
  - added screen-reader summary announcement via `aria-label` on the keyword-index summary.
- Added Stage 3 integration coverage:
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.entryStage3.test.tsx`
  - validates combined search + status filters.
  - validates conflict count visibility, filtered empty-state messaging, and filter control labels.
- Implemented Stage 4 in `apps/packages/ui/src/components/Option/WorldBooks/Manager.tsx`:
  - added explicit "Supported formats" guidance for all parser separators (`=>`, `->`, `|`, tab) in bulk mode UI.
  - replaced sequential bulk-add loop with bounded-concurrency execution via `runBulkAddEntries(...)`.
  - added live progress indicator (`Bulk progress: completed/total`) and completion status details.
  - added per-entry failure summary with source line, keyword context, and error message.
- Added Stage 4 supporting utility:
  - `apps/packages/ui/src/components/Option/WorldBooks/worldBookBulkUtils.ts`
  - provides bounded-concurrency execution and progress/failure aggregation.
- Added Stage 4 test coverage:
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/entryParsers.test.ts`
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.entryStage4.test.tsx`
  - validates separator parsing examples, malformed-line diagnostics, bounded concurrency, progress updates, and mixed success/failure summary behavior.
- Implemented Stage 5 decision and UX clarity:
  - documented explicit defer decision in `Docs/Product/Completed/Plans/IMPLEMENTATION_PLAN_world_books_03_entry_management_2026_02_18.md`.
  - added in-drawer explanatory copy clarifying that priority drives entry ordering.
- Added Stage 5 regression coverage:
  - `apps/packages/ui/src/components/Option/WorldBooks/__tests__/WorldBooksManager.entryStage5.test.tsx`
  - validates priority-ordering explanatory copy is visible in entry management UI.
