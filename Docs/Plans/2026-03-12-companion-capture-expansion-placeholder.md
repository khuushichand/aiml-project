Date: 2026-03-12
Status: Activated And Planned

# Companion Capture Expansion Placeholder

## Purpose

Reserve the next companion breadth-oriented slice and record that it has now been upgraded into a reviewed design plus implementation plan.

## Current State

This placeholder is no longer just a deferred reminder.

It is now backed by:

- `Docs/Plans/2026-03-12-companion-capture-expansion-design.md`
- `Docs/Plans/2026-03-12-companion-capture-expansion-implementation-plan.md`

## Activated Scope

This activated slice is intentionally narrow and lower risk:

- `notes/import`
- `notes/bulk`
- `watchlists/sources/import`
- `watchlists/sources/bulk`

Rules locked in by design review:

- per-item explicit companion capture only
- only rows that actually changed state are eligible
- reuse existing event families
- import/bulk origin is represented through provenance and surface metadata
- skips, duplicates, and row-level errors stay out of the companion ledger

## Deferred Items That Still Remain Deferred

Not part of this slice:

- `chatbooks/import`
- restore semantics beyond current endpoint behavior
- new import-specific companion event families
- broader extension or adjacent-system capture families outside these four routes

## Deliverable Expectation

The next time this area is executed, it should follow the reviewed implementation plan rather than reopening scope from scratch.
