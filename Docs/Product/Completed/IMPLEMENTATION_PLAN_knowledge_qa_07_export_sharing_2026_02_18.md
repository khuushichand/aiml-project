# Implementation Plan: Knowledge QA - Export and Sharing

## Scope

Components: `apps/packages/ui/src/components/Option/KnowledgeQA/ExportDialog.tsx`, export format generators, chatbook export API integration, answer-panel save/share hooks
Finding IDs: `7.1` through `7.10`

## Finding Coverage

- Preserve strong format selection and defaults: `7.1`, `7.4`, `7.5`, `7.10`
- Resolve critical modal accessibility gap: `7.2`
- Improve citation expectations and export reliability: `7.3`, `7.6`, `7.7`
- Add workflow features: `7.8`, `7.9`

## Stage 1: Export Dialog Accessibility and Keyboard Containment
**Goal**: Bring export modal to parity with SettingsPanel accessibility behavior.
**Success Criteria**:
- Export dialog uses `role="dialog"`, `aria-modal="true"`, and heading association (`7.2`).
- Focus trap and focus restoration are implemented consistently (`7.2`).
- Keyboard escape and backdrop interactions remain predictable.
**Tests**:
- Accessibility tests for modal ARIA semantics and heading reference.
- Integration tests for tab-cycle focus trap and close-on-escape behavior.
- Regression tests for open/close focus restoration.
**Status**: Complete

## Stage 2: Export Reliability, Error Feedback, and Citation Transparency
**Goal**: Reduce silent failures and set correct user expectations.
**Success Criteria**:
- Chatbook export failures surface user-visible toasts with actionable guidance (`7.7`).
- Export failure handling covers network/server/thread errors with differentiated messages (`7.7`, `7.10`).
- Citation-style output includes explicit note that formatting is simplified with limited metadata (`7.3`).
- PDF path messaging remains explicit when using browser print fallback and roadmap for direct-PDF path is documented (`7.6`).
**Tests**:
- Integration tests for chatbook export success/failure branches.
- Unit tests for export error mapper and toast copy selection.
- Snapshot tests for citation disclaimer visibility.
**Status**: Complete

## Stage 3: Save/Share Extensions
**Goal**: Add high-value downstream workflows from Knowledge QA output.
**Success Criteria**:
- "Save to Notes" action creates note payload with query, answer, and citations (`7.9`).
- Shareable-thread URL copy action is enabled for server-backed threads and resolves via `/knowledge/thread/:threadId`; local-only threads remain disabled (`7.8`).
- New actions do not regress existing export format flow.
**Tests**:
- Integration tests for note creation and success/error notifications.
- Routing tests for thread permalink generation/resolve behavior.
- E2E coverage for export + save-to-notes sequence.
**Status**: Complete

## Stage 4: Regression Safety for Existing Strengths
**Goal**: Lock in existing polished behaviors while adding capability.
**Success Criteria**:
- Three-format selector card UX remains clear and keyboard accessible (`7.1`).
- Include-source and settings-snapshot default toggles remain unchanged (`7.4`).
- Preview truncation and copy-feedback behavior persist (`7.5`, `7.10`).
**Tests**:
- Component snapshot tests for format selector/default toggles.
- Integration tests for preview truncation and copy feedback timing.
**Status**: Complete

## Dependencies

- Save-to-notes action should align with notes schema and permissions used elsewhere in the app.
