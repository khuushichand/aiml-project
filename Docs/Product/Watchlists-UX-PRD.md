# PRD: Watchlists UX Enhancements (Content Collections UX Backlog)

Version: 0.2
Owner: Core Maintainers (Server/API + WebUI)
Status: Draft
Updated: 2026-02-07

Related: Docs/Product/Content_Collections_PRD.md

---

## 1. Summary

This PRD captures the remaining UX work for Content Collections after the core APIs shipped. It focuses on Watchlists and Reading List UX gaps: output template editing, bulk item actions, Pocket/Instapaper import/export UI, reader highlights, and clearer notes save affordances.

## 2. Goals

- Add a first-class output template editor with preview, defaults, and guardrails.
- Make Pocket/Instapaper import/export self-service with clear feedback.
- Provide reader highlights UI with a clean review and edit flow.
- Enable bulk actions in Items/Reading list views without brittle workflows.
- Show unsaved note edits with a small, consistent "dirty" indicator.

## 3. Non-Goals

- New backend ingestion or scraping capabilities.
- New import formats beyond Pocket JSON and Instapaper CSV.
- Broad API rewrites unrelated to UX-driven contract alignment.

## 4. UX Scope and Flows

### 4.1 Pocket/Instapaper Import/Export
- Import modal: drag/drop and file picker, file type validation, source override (auto/pocket/instapaper), merge-tags toggle.
- Import results: async job status (queued/processing/completed/failed/cancelled/quarantined) with imported/updated/skipped counts and top errors (if any).
- Export panel: format selection (jsonl/zip), filter options (status/tags/favorite/domain/date), include toggles (`include_notes`, `include_highlights`), and clear filename hints.

### 4.2 Reader Highlights and Notes UX
- Highlight selection in reader view with quick actions (color, note, delete).
- Highlights list with search and filter by color; stale highlight badge when content changed.
- Notes editor with autosave and a subtle dirty indicator while edits are pending.

### 4.3 Output Template Editor (Watchlists)
- Template list with type, description, and last updated.
- Create/edit with syntax assistance, variable hints, and preview.
- Assign template defaults in job output preferences without leaving the job editor.

### 4.4 Bulk Item Actions
- Multi-select list with bulk tag add/remove, status update, favorite toggle, delete, and output generation.
- Progress and error reporting for partial failures; reversible actions where possible.

## 5. Requirements

- Use endpoints: `/api/v1/reading/import`, `/api/v1/reading/import/jobs`, `/api/v1/reading/import/jobs/{job_id}`,
  `/api/v1/reading/export`, `/api/v1/reading/items`, `/api/v1/outputs/templates`,
  `/api/v1/outputs/templates/{template_id}/preview`, `/api/v1/outputs`.
- Import UX must surface invalid file errors (400) and size limit errors (413) clearly.
- Import request supports `merge_tags`; import status polling must use job endpoints.
- Export UX must preserve filters used in list views by default.
- Export request supports `include_notes` and `include_highlights` toggles.
- Bulk actions must provide a clear completion summary and error details.
- Notes edits must not be lost on navigation; prompt to save or auto-save before leaving.

## 6. Dependencies and Constraints

- Output template editor depends on the output templates API already shipped.
- Bulk actions can batch per-item calls; add a bulk endpoint only if latency or rate limits become problematic.
- Reader highlights UI depends on highlight endpoints once shipped.

## 7. Success Metrics

- Import completion rate and time-to-first-successful-import.
- Reduction in manual per-item actions for status/tags.
- Template preview success rate and template adoption.
- Highlight usage rate per saved item.

## 8. Test Plan

- Import: Pocket JSON and Instapaper CSV fixtures; invalid file; oversized file.
- Export: jsonl and zip downloads; filter retention; large lists.
- Highlights: create/edit/delete; stale highlight state; persistence on reload.
- Bulk actions: mixed-success scenarios; undo flow when supported.
- Notes: dirty indicator and autosave behavior across navigation.

## 9. Open Questions

- Resolved: Import uses async job lifecycle with `/reading/import/jobs` polling.
- Resolved: Exports keep notes/highlights as explicit toggles (defaults: notes on, highlights off).
- Open: Should date-range filtered ZIP export gain backend support, or remain JSONL-only fallback?

## 10. Implementation Plan (Phase 3)

## Stage 1: UX Audit and Contract Alignment
**Goal**: Confirm current Reading/Watchlists UI coverage against Watchlists-UX-PRD and validate required API contracts.
**Success Criteria**: Phase 3 backlog is finalized with scoped UI changes, confirmed endpoints, and any required API additions explicitly listed.
**Tests**: None (documentation and scope validation only).
**Status**: Complete

## Stage 2: Import/Export UX (Pocket/Instapaper)
**Goal**: Implement the import/export UX refinements described in the PRD (drag/drop, validation errors, results summary, export filters).
**Success Criteria**: Import modal validates file type/size, supports source override + merge tags toggle, starts async import jobs, polls status, and surfaces API/job error details; export panel preserves list filters, wires `include_notes`/`include_highlights`, and delivers JSONL/ZIP with clear filename hints.
**Tests**: Targeted frontend client tests for import/export contract wiring; manual QA with Pocket JSON and Instapaper CSV fixtures.
**Status**: Complete

## Stage 3: Reader Highlights and Notes UX
**Goal**: Provide selection-based highlight creation, highlight list filtering, stale badges, and stronger notes autosave/dirty indicators.
**Success Criteria**: Users can select text to create highlights, edit/delete highlights in-place, filter highlights by color/search, and see stale badges; notes show dirty state and do not lose edits on navigation.
**Tests**: UI tests for highlight CRUD state changes and notes autosave/dirty indicator; manual QA for text selection flows.
**Status**: In Progress

## Stage 4: Output Template Editor and Bulk Item Actions
**Goal**: Add a template editor with preview and integrate bulk actions in Items/Reading views.
**Success Criteria**: Templates list/create/edit/preview flows work end-to-end; job editor can assign default templates; bulk actions support tag add/remove, status update, favorite toggle, delete, and output generation with progress/error summaries.
**Tests**: UI tests for template preview rendering and bulk action summaries; manual QA for mixed-success scenarios.
**Status**: Not Started
