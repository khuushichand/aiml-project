# Decision Record: World Book Entry Reordering

**Date**: 2026-02-18  
**Scope**: World Books Entry Management (`Manager.tsx`, entries drawer UX)  
**Related finding**: `3.12` (No drag-and-drop reordering)

## Context

World book entry ordering is currently driven by numeric `priority` (0-100), which is also the backend selection mechanism used when token budgets constrain injected content. A drag-and-drop UI was requested as a potential improvement.

## Options Considered

1. Implement drag-and-drop ordering now.
2. Keep priority-only ordering and improve explanatory UX copy.

## Decision

Choose option 2 for this phase.

## Rationale

- Priority already maps directly to backend injection semantics.
- Drag-and-drop would introduce an additional ordering model that can conflict with priority rules unless backend schema and ranking logic are expanded.
- Current roadmap priority is higher-impact authoring/debugging throughput improvements.

## Consequence

- Entry ordering remains priority-driven.
- UI now explicitly communicates that higher-priority entries are evaluated first.
- Drag-and-drop remains backlog work for a future schema/UX revision.
