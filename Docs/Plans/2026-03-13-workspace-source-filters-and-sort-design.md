Date: 2026-03-13
Owner: Codex collaboration session
Status: Approved

# Workspace Playground Source Filters And Sort Design

## Context

`/workspace-playground` already supports:

- source search by title
- direct and folder-derived source selection
- bulk removal of selected sources
- nested source folders for organization
- manual source ordering via drag/drop and move up/down controls

The remaining gap is source discovery once a workspace becomes large. Users need richer ways to narrow the list and temporarily reorder it without changing the workspace's saved manual order.

## Goals

1. Add richer source filtering controls to the Sources pane.
2. Add temporary, view-only sort controls to the Sources pane.
3. Keep the pane compact by hiding advanced controls behind a disclosure.
4. Preserve the current workspace source order as the canonical saved order.
5. Avoid changes to workspace persistence, import/export, and cross-tab sync for transient UI preferences.
6. Preserve existing search, folder focus, selection, bulk actions, preview, and virtualization behavior.

## Non-Goals

1. Persisting filter or sort preferences in workspace snapshots.
2. Replacing the existing folder tree with a second folder filter UI.
3. Full-text source-content filtering in v1.
4. Server-backed query/filter APIs.
5. Changing grounded chat scope semantics beyond clarifying how selection behaves under filtered views.

## Existing Constraints

The current source model already exposes enough metadata for a practical v1:

- `type`
- `status`
- `addedAt`
- `sourceCreatedAt`
- `url`
- `fileSize`
- `duration`
- `pageCount`

The current source pane already applies this pipeline:

1. base source list in manual workspace order
2. optional folder focus narrowing
3. text search narrowing
4. virtualization and row rendering

The design should extend that pipeline rather than replace it.

## Design Decision

Add a compact `Advanced` disclosure inside the Sources pane. When collapsed, it shows a short summary of active filters and sort. When expanded, it reveals richer filter and sort controls.

Filtering and sorting remain non-persisted, session-local view state. The canonical saved source order remains the existing manual order in the workspace store.

## UX Model

### Placement

Add the disclosure directly below the existing source search box and above the existing select-all / selected-actions area.

### Collapsed state

When collapsed, show:

- an `Advanced` toggle
- a short summary of active filters and sort, if any
- a `Clear filters` action when advanced filters are active

Example summary:

- `Filters: Type=PDF, Status=Ready · Sort: Added date (newest)`

### Expanded state

When expanded, show:

- filter groups
- sort controls
- a note that sorts are view-only and do not change manual source order

The controls should stay inline in the pane rather than opening a modal or popover, to reduce repeated interaction cost.

## State And Data Flow

### State placement

Do not persist advanced filter/sort state in the workspace store.

However, do not keep it only in the `SourcesPane` component instance either, because `SourcesPane` can remount when switching between desktop/mobile layouts or drawer/tab variants.

Use a small page-level view-state owner instead:

- either in `WorkspacePlaygroundBody`
- or in a dedicated non-persisted hook owned by `WorkspacePlaygroundBody`

This keeps the state session-local and non-persisted while surviving pane remounts inside the page.

### Derivation pipeline

Visible sources should be derived in this order:

1. start with the base source list in manual workspace order
2. apply active folder focus
3. apply text search
4. apply advanced filters
5. apply temporary view-only sort
6. pass the resulting list into virtualization and rendering

Switching sort back to `Manual order` must restore the underlying saved source order exactly.

## Filter Set For V1

Keep the v1 set intentionally narrow and grounded in existing metadata.

### Core filters

- `Type`
  - multi-select
  - values: `pdf`, `video`, `audio`, `website`, `document`, `text`
- `Status`
  - multi-select
  - values: `ready`, `processing`, `error`
- `Date field`
  - single-select
  - values: `Added date`, `Source date`
- `Date range`
  - optional `from` and `to`
- `Has URL`
  - yes/no toggle

### Metadata presence filters

- `Has page count`
- `Has duration`
- `Has file size`

### Numeric range filters

- `File size`
- `Duration`
- `Page count`

### Conditional control visibility

To avoid clutter, metadata-specific controls should only appear when at least one source in the current workspace has the relevant field:

- show file-size controls only if any source has `fileSize`
- show duration controls only if any source has `duration`
- show page-count controls only if any source has `pageCount`

## Sort Set For V1

Support:

- `Manual order`
- `Name A-Z`
- `Name Z-A`
- `Added date newest`
- `Added date oldest`
- `Source date newest`
- `Source date oldest`
- `File size largest`
- `File size smallest`
- `Duration longest`
- `Duration shortest`
- `Page count highest`
- `Page count lowest`

### Sort rules

1. Non-manual sorts are view-only.
2. Missing values sort to the end for metadata/date sorts.
3. Ties should fall back to stable manual order.
4. Returning to `Manual order` restores the exact saved source order.

## Interaction Rules

### Search and filters

Text search remains independent and continues to work as quick narrowing.

Advanced filters apply on top of the current search result set.

### Folder behavior

Do not add folder filtering to the advanced controls. The existing folder tree already handles:

- focus/filtering
- folder-derived grounded selection

Keeping folders out of the advanced disclosure avoids duplicating two different folder-filter models.

### Selection semantics under filtered views

This is the highest-risk interaction area and must be explicit.

Rules:

1. `Select all` becomes `Select visible` whenever search, folder focus, or advanced filters narrow the current list.
2. Selected-count messaging should distinguish visible selected sources from total effective selected sources when they differ.
3. Bulk remove confirmation must explicitly say whether hidden selected sources are included.
4. `Clear filters` resets only advanced filters.
5. `Clear filters` does not clear:
   - text search
   - folder focus
   - direct source selection
   - folder-derived selection

Recommended confirmation language when hidden selections exist:

- `Remove 8 selected sources? 3 are hidden by current filters.`

### Reorder behavior while sorted

Manual reorder controls are incompatible with non-manual view sorting.

Rules:

1. Disable drag/drop when sort is not `Manual order`.
2. Disable move up/down controls when sort is not `Manual order`.
3. Show a short hint explaining that reorder is available only in `Manual order`.

This prevents users from thinking they are reordering the currently sorted view.

## Implementation Shape

Keep the change mostly local to the Sources pane area.

### Recommended structure

- add a small `SourceAdvancedControls` component for the disclosure UI
- add pure helpers for:
  - filtering sources
  - sorting sources
  - summarizing active filters
- keep row rendering, preview, folder membership, bulk actions, and virtualization largely intact

### Store impact

No persisted store changes are required for v1 filter/sort state.

At most, add small typed helper utilities if they reduce duplication around filterable source metadata, but do not add transient filter/sort state to workspace persistence.

## Error Handling And Edge Cases

1. Incomplete numeric or date ranges should be treated as open-ended.
2. Invalid numeric input should not crash filtering.
3. Sources missing a filtered field should be excluded only when that filter is active.
4. Sources missing a sortable field should remain visible and sort to the end.
5. If filters remove all results, reuse the existing empty-state region with `No matching sources`.
6. The `No sources yet` empty state remains reserved for truly empty workspaces.

## Testing Strategy

### Pure logic tests

Add tests for:

- each filter type
- combined filters
- missing metadata behavior
- each sort mode
- stable fallback to manual order on ties

### Component tests

Add `SourcesPane` tests for:

- disclosure open/close
- collapsed summary text
- clear-filters behavior
- interaction with existing text search
- interaction with folder focus
- conditional visibility of metadata-specific controls
- `Select visible` behavior
- bulk-remove confirmation when hidden selections exist
- disabled reorder controls under non-manual sort

### Regression tests

Preserve coverage for:

- bulk selection
- preview and annotations
- source removal
- folder-derived selection
- virtualization behavior

Add a specific regression asserting:

- switching from a non-manual sort back to `Manual order` restores the original saved order exactly

## Recommended Rollout

Implement as a single local-first UI enhancement with no migration requirements.

The safest sequence is:

1. pure filter/sort helpers and tests
2. advanced-controls UI
3. integration with existing visible-source pipeline
4. selection and bulk-action clarifications
5. reorder-disable behavior under non-manual sort

## Open Questions Resolved

1. Advanced controls should live behind a disclosure to keep the pane compact.
2. Sorts should be temporary and view-only.
3. The current metadata fields are sufficient for v1 filtering and sorting.
4. Improvements were added to avoid remount-state loss, reorder confusion, duplicated folder UI, and hidden-selection surprises.
