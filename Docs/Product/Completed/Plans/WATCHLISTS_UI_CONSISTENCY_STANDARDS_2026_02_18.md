# Watchlists UI Consistency Standards

## Purpose

Define cross-tab interaction and layout standards for `/watchlists` so Sources, Monitors, Activity, Articles, Reports, Templates, and Settings follow predictable patterns.

## Standards

### 1. Table Action Placement

- Primary row actions live in the rightmost `Actions` column.
- Action-column width target: `140px` for Sources/Monitors/Activity/Reports/Templates.
- Bulk actions live above the table in a dedicated batch bar, never mixed into row-level action groups.

### 2. Icon and Label Usage

- Icon-only buttons require both:
  - `aria-label` with explicit action intent.
  - Tooltip text matching the action label.
- Destructive actions use explicit text labels in confirmations (`Delete`, `Delete anyway`) and never icon-only affordances without a confirm step.
- Disabled controls must include rationale text or tooltip when the disabled state is not self-explanatory.

### 3. Empty-State Pattern

- Empty states must include:
  - One concise reason line ("No feeds yet", "No runs found", etc.).
  - One or two contextual CTAs (create/import/open related tab).
- Empty-state wording uses user vocabulary from H2 (`Feeds`, `Monitors`, `Activity`, `Articles`, `Reports`).

### 4. Layout Pattern Matrix

- Table-centric tabs:
  - `Sources`, `Jobs`, `Runs`, `Outputs`, `Templates`
  - Optional secondary panel allowed only for scoped navigation (example: group tree in Sources).
- Reader-centric tab:
  - `Items` keeps 3-pane layout because the primary task is list triage + detail reading.

### 5. Shared Utility Adoption Plan

- Continue using shared watchlists components where available:
  - `StatusTag`
  - `CronDisplay`
  - `WatchlistsHelpTooltip`
- New dense tab work should add shared wrappers before adding one-off patterns:
  - candidate: shared action-cell wrapper for icon+label+tooltip parity
  - candidate: shared empty-state helper for CTA/description consistency

## Implementation Notes

- Existing consistency pass already aligned:
  - action column widths to `140px` across primary table tabs.
  - icon-button tooltip/aria parity on key controls.
  - disabled Forum source-type rationale and Run Now disabled rationale.
- Remaining iterations should treat this doc as baseline acceptance criteria.
