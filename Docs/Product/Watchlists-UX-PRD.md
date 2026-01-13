# PRD: Watchlists UX Enhancements (Content Collections UX Backlog)

Version: 0.1
Owner: Core Maintainers (Server/API + WebUI)
Status: Draft
Updated: 2026-01-12

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
- Rewriting the existing Next.js pages or API contracts.

## 4. UX Scope and Flows

### 4.1 Pocket/Instapaper Import/Export
- Import modal: drag/drop and file picker, file type validation, source override (auto/pocket/instapaper), merge-tags toggle.
- Import results: show imported/updated/skipped counts and top errors (if any).
- Export panel: format selection (jsonl/zip), filter options (status/tags/favorite/domain), and clear filename hints.

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

- Use existing endpoints: `/api/v1/reading/import`, `/api/v1/reading/export`, `/api/v1/reading/items`,
  `/api/v1/outputs/templates`, `/api/v1/outputs/templates/{id}/preview`, `/api/v1/outputs`.
- Import UX must surface invalid file errors (400) and size limit errors (413) clearly.
- Export UX must preserve filters used in list views by default.
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

- Do we need background jobs for very large imports, or is the current sync flow acceptable?
- Should exports include highlights and notes by default or behind a toggle?

