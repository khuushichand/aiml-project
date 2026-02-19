# Decision Record: Notes List Scalability (Stage 5)

## Context

Plan: `IMPLEMENTATION_PLAN_notes_page_01_notes_list_navigation_2026_02_18.md`  
Stage: 5 (Scalable List Rendering Option)  
Audit findings: `1.10` (infinite scroll / virtualization consideration), `1.11` (page-size configurability)

The notes list now supports sort controls and user-configurable page size. The remaining Stage 5 decision is whether to replace pagination with virtualization/load-more for larger datasets.

## Decision

For the current remediation cycle, keep **server-side pagination** as the primary rendering strategy and **defer virtualization/load-more** implementation.

## Rationale

- Existing list interactions (selection, bulk actions, filters, sort) are stable with paginated fetches and avoid introducing complex state synchronization risks.
- Pagination behavior is explicit and predictable for accessibility and keyboard workflows in the current sidebar layout.
- The latest stage work already raised practical list capacity via page sizes `20/50/100`, which addresses medium collections while keeping API load bounded.

## Trigger Threshold for Revisit

Revisit virtualization or load-more when either condition is observed:

1. Regular user flows involve **> 100 visible notes per page** and render/perceived latency is unacceptable.
2. Instrumented profiling shows notes-list render or interaction delays (selection, filter application, row navigation) consistently breaching acceptable UX budgets.

## Implementation Notes

- A large-list hint is surfaced in the notes sidebar when `total >= 100` to make the current mode explicit.
- Regression coverage was added using 500+ mock notes to ensure pagination fallback and bulk-selection controls remain functional under large data volumes.
