# Implementation Plan: Characters - Search, Filtering, and Scalability

## Scope

Components: `apps/packages/ui/src/components/Option/Characters/Manager.tsx`, `apps/packages/ui/src/components/Option/Characters/search-utils.ts`, `apps/packages/ui/src/services/tldw/TldwApiClient.ts`, `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`
Finding IDs: `C-08` through `C-12`

## Finding Coverage

- Missing sort dimensions (created/updated/last-used): `C-08`
- Missing filters (creator, has-conversations, date range): `C-09`
- Fixed page size with no user control: `C-10`
- Client-side all-record filtering risks large-list performance: `C-11`
- Tag management lacks rename/merge/delete tools: `C-12`

## Stage 1: Deliver Frontend Quick Wins for Sorting and Pagination Control
**Goal**: Improve list ergonomics quickly without backend contract changes.
**Success Criteria**:
- Page-size selector supports 10/25/50/100 and persists via local storage.
- UI exposes sort options for currently available fields and prepared hooks for timestamp fields.
- Filter UI scaffold includes has-conversations and creator filters where data is already present.
**Tests**:
- Unit tests for persisted page-size read/write behavior.
- Component tests for sort/filter controls and reset behavior.
- Integration tests for pagination correctness with changed page size.
**Status**: Not Started

## Stage 2: Add Server-Side Search/Filter/Sort/Pagination Contract
**Goal**: Remove client-side scaling bottlenecks and support advanced query dimensions.
**Success Criteria**:
- Characters list endpoint supports query params for page, page size, sort key/order, creator, has-conversations, created/updated date ranges.
- API returns lightweight listing payload (optionally excluding large avatar data).
- Frontend switches from list-all + local filtering to server-driven query model.
**Tests**:
- Backend unit/integration tests for new query params and default ordering.
- API contract tests for pagination metadata and stable sorting.
- Frontend integration tests verifying query-state-to-request mapping.
**Status**: Not Started

## Stage 3: Introduce Tag Management Operations
**Goal**: Make tags maintainable at scale for power users.
**Success Criteria**:
- "Manage tags" modal/popover lists tags with usage counts.
- Rename, merge, and delete operations are available with confirmation on destructive actions.
- Tag operations update visible character lists without hard refresh.
**Tests**:
- Backend tests for rename/merge/delete semantics and conflict handling.
- Component tests for tag manager interaction and validation states.
- Integration tests for list refresh after tag mutation.
**Status**: Not Started

## Stage 4: Performance Hardening and Rollout Safety
**Goal**: Validate scalability improvements under realistic large datasets.
**Success Criteria**:
- List interactions remain responsive at 200+ characters.
- Avatar rendering is lazy or deferred to prevent initial payload bloat.
- Feature rollout supports fallback to current behavior behind a feature flag if regressions appear.
**Tests**:
- Performance benchmark test for 200+ list rendering and interaction latency.
- E2E test for server-driven pagination/filtering flow.
- Monitoring checklist for API response size and query latency.
**Status**: Not Started

## Dependencies

- Stage 2 depends on backend endpoint extensions and frontend API client updates.
- Stage 3 may require tag-level service methods not currently exposed by the characters endpoint.
