# Decision Record: Watchlists Layout Model (Stage 1)

## Context

Watchlists tabs mixed table-first and pane-first layouts, creating inconsistency concerns (`H4.1`, `H4.2`). We needed a clear rule for when a 3-pane layout is acceptable versus when table layouts are required.

## Decision

Use a **task-shape rule**:

- Use **table-first layouts** for management tasks:
  - creating, editing, deleting, scheduling, monitoring status, and exporting.
- Use **3-pane reader layout** only for high-volume content triage where users repeatedly switch between list and full content detail.

Applied outcome:

- Keep `Items` as 3-pane.
- Keep `Sources`, `Jobs`, `Runs`, `Outputs`, `Templates` table-first.
- Allow narrow contextual sidebars only when they act as filters/navigation (example: Sources group tree), not as second full-detail panes.

## Rationale

- Preserves speed for operational actions (table tabs).
- Preserves deep-reading efficiency where it matters (Items).
- Reduces cognitive switching by keeping one dominant interaction model per task class.

## Consequences

- New tabs/features should default to table-first unless they satisfy reader-centric criteria.
- Any future 3-pane proposal outside `Items` requires explicit UX rationale in plan notes.
