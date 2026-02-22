# Decision Record: Notes Export Print/PDF Path (Stage 3)

## Context

Plan: `IMPLEMENTATION_PLAN_notes_page_07_export_sharing_2026_02_18.md`  
Stage: 3 (Bulk export feedback and print/PDF path)  
Audit findings: `7.6`, `7.8`

The notes page already includes chunked export progress feedback and large-export preflight confirmation. The remaining decision is how to deliver PDF export ergonomics without introducing backend rendering complexity too early.

## Decision

Use a **client print-first path** for single-note PDF export:

1. Add a `Print / Save as PDF` option in the single-note export actions.
2. Generate a print-friendly HTML document in a new window, with dedicated `@media print` styles.
3. Rely on native browser print dialogs for PDF generation.

Defer server-side PDF generation to a later phase.

## Rationale

- Fastest path to usable PDF output with minimal backend scope and zero new server infrastructure.
- Preserves markdown readability with print-safe typography and page-break rules.
- Keeps failures user-actionable (e.g., blocked pop-ups) in the existing UI notification flow.
- Avoids introducing dependency-heavy headless rendering and queueing concerns during this remediation cycle.

## Deferred Work

Revisit server-side PDF generation when one or more triggers are true:

1. Users need background/batch PDF generation for large note sets.
2. Output fidelity/branding requirements exceed browser print capabilities.
3. Operational requirements call for deterministic PDFs independent of client browser behavior.

## Implementation Notes

- Print HTML builder and stylesheet are centralized in:
  - `/apps/packages/ui/src/components/Notes/export-utils.ts`
- Print action is exposed in:
  - `/apps/packages/ui/src/components/Notes/NotesEditorHeader.tsx`
  - `/apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`
- Regression coverage includes:
  - print stylesheet snapshot + html sanitization checks
  - print action success/failure integration tests
  - existing preflight/progress integration tests for bulk export
