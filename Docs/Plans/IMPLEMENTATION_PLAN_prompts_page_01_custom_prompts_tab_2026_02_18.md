# Implementation Plan: Prompts Page - Custom Prompts Tab

## Scope

Components: `apps/packages/ui/src/components/Option/Prompt/index.tsx`, `apps/packages/ui/src/services/prompt-sync.ts`, `tldw_Server_API/app/api/v1/endpoints/prompts.py`
Finding IDs: `1.1` through `1.10`

## Finding Coverage

- Search and scaling: `1.1`, `1.2`
- Table information architecture: `1.3`, `1.4`, `1.5`, `1.10`
- Import/export and bulk workflows: `1.6`, `1.7`, `1.8`
- Preserve existing strong interaction: `1.9`

## Stage 1: Server-Backed Search and Pagination
**Goal**: Replace client-only filtering with backend search while preserving offline behavior.
**Success Criteria**:
- Search input calls `POST /prompts/search` with 300ms debounce when online.
- Query payload supports field-level filtering, page, and `results_per_page`.
- Offline mode falls back to current client-side filter path.
- Pagination controls added and wired to backend/page state.
- Tag filtering exposes match mode toggle (`any` OR / `all` AND) and applies correctly.
**Tests**:
- Unit tests for search query builder and OR/AND tag filter translation.
- Component tests for debounce, loading state, and pagination state changes.
- Integration tests for online search path and offline fallback path.
**Status**: Not Started

## Stage 2: Table Usability and Metadata Visibility
**Goal**: Improve discoverability and comparison in the prompt table.
**Success Criteria**:
- Columns add sorters for title, type, and date.
- Default ordering remains favorites-first, but user sort override persists per session.
- `Modified` column added with relative time and sortable backing value.
- Content preview supports in-row expand/collapse or equivalent show-more affordance.
**Tests**:
- Component tests for sorter behavior and default/fallback ordering.
- Unit tests for modified-date renderer and relative time formatting.
- Interaction test for content expand/collapse behavior.
**Status**: Not Started

## Stage 3: Export, Import Feedback, and Bulk Operations
**Goal**: Enable high-volume prompt management workflows.
**Success Criteria**:
- Export control supports JSON (local), CSV (server), and Markdown (server).
- Import success notifications include imported/skipped/failed counts.
- Bulk action bar adds: assign keyword(s), push to server, and favorite toggle.
- Bulk actions handle partial failures without aborting remaining items.
**Tests**:
- Integration tests for CSV/Markdown export request/response handling.
- Unit tests for import result aggregation and notification formatting.
- Integration tests for each new bulk action including partial-failure summaries.
**Status**: Not Started

## Stage 4: Regression Safety and Interaction Preservation
**Goal**: Ship improvements without regressing proven strengths.
**Success Criteria**:
- Existing "Use in Chat" modal flow remains unchanged in behavior and emphasis.
- Large dataset performance stays acceptable after pagination/search refactor.
- Deep-link and selected-row behavior still work with paged data.
**Tests**:
- Snapshot/interaction regression tests for "Use in Chat" modal.
- Performance smoke test with large prompt fixture (search + pagination + sort).
- E2E scenario covering select, use, and navigation to chat.
**Status**: Not Started

## Dependencies

- Backend search/export contracts from `tldw_Server_API/app/api/v1/endpoints/prompts.py`.
- Sync/bulk workflows should align with conflict and batch-sync work in Category 3 plan.
