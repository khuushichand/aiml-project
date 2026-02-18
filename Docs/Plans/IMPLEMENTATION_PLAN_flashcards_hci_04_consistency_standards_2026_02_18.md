# Implementation Plan: Flashcards H4 - Consistency and Standards

## Scope

Route/components: `FlashcardsManager.tsx`, `tabs/ReviewTab.tsx`, `tabs/ManageTab.tsx`, drawer components under flashcards UI package  
Finding IDs: `H4-1` through `H4-3`

## Finding Coverage

- Tab-level interaction model differs from adjacent app patterns: `H4-1`
- Card creation entry points are fragmented across contexts: `H4-2`
- Drawer sizing and visual rhythm differ between related workflows: `H4-3`

## Stage 1: Interaction Model Alignment
**Goal**: Make flashcards navigation and action placement predictable relative to the rest of the app.
**Success Criteria**:
- Tab labels and descriptions clarify workflow separation (Study, Manage, Transfer) with consistent naming.
- Primary creation entry point is defined and reused across tabs; secondary triggers route to it.
- Empty-state CTAs and top-level CTA copy use a single canonical label.
**Tests**:
- Component tests for tab labels, aria attributes, and active state behavior.
- UX regression tests for CTA routing from Review, Cards, and empty states.
- Snapshot tests for cross-breakpoint layout consistency.
**Status**: Not Started

## Stage 2: Shared Drawer and Action Standards
**Goal**: Normalize panel dimensions and action affordances across create/edit/move flows.
**Success Criteria**:
- Shared drawer sizing tokens are introduced and used by Create/Edit/Move drawers.
- Footer action ordering (cancel, secondary, primary) is consistent for all flashcard drawers.
- Form spacing and section headers follow shared UI conventions.
**Tests**:
- Component tests asserting shared size tokens and consistent footer controls.
- Visual regression tests across desktop/mobile widths.
- Accessibility tests for focus order and escape/close interactions.
**Status**: Not Started

## Stage 3: Flashcards Pattern Documentation
**Goal**: Prevent reintroduction of inconsistencies via lightweight internal standards.
**Success Criteria**:
- Flashcards UI conventions documented in a short design note linked from feature docs.
- New PR checklist items include CTA placement, naming consistency, and drawer standards.
- At least one lint/test guard exists for core pattern invariants (labels, action keys, token usage).
**Tests**:
- Docs link checks and CI validation for updated references.
- Unit test or static rule enforcing shared drawer token usage.
- Regression tests covering primary CTA visibility rules.
**Status**: Not Started

## Dependencies

- Stage 1 decisions should coordinate with product naming in existing route navigation.
- Stage 2 relies on shared UI token availability in the frontend package.
- Stage 3 should reflect outcomes from H8 visual simplification work.
