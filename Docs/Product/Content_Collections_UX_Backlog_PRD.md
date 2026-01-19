# PRD: Content Collections UX Backlog Execution

Version: 0.1
Owner: Core Maintainers (Server/API + WebUI)
Status: In Progress
Updated: 2026-01-15

Related: Docs/Product/Completed/Content_Collections_PRD.md, Docs/Product/Watchlists-UX-PRD.md

---

## 1. Summary

This PRD tracks the remaining UX delivery work for Content Collections. It rolls up the Watchlists-UX-PRD backlog into concrete, implementable tasks and maps each item to the existing API and module surfaces. The goal is to finish UX parity for Reading, Watchlists, and Items while keeping the existing backend contracts stable.

## 2. Goals

- Ship self-service Pocket/Instapaper import/export UX with clear validation and results feedback.
- Deliver a reader-centric highlights experience (selection, review, edit, stale badges).
- Provide an output template editor with preview and default assignment inside job settings.
- Enable bulk item actions (tags, status, favorite, delete, output generation).
- Prevent notes loss with autosave and a small, consistent dirty indicator.

## 3. Non-Goals

- New ingestion or scraping capabilities.
- New import formats beyond Pocket JSON and Instapaper CSV.
- Rewriting existing backend contracts unless needed for UX reliability.

## 4. UX Tasks (Concrete)

### 4.1 Import/Export UX
- Import modal with drag/drop and file picker, file type validation, source override (auto/pocket/instapaper), merge-tags toggle.
- Import results: show imported/updated/skipped counts, plus top errors if provided by API.
- Export panel: format selection (jsonl/zip), filter controls (status/tags/favorite/domain), and filename hints.
- Error handling: surface 400 and 413 responses with human-readable messaging.

### 4.2 Reader Highlights and Notes UX
- Reader detail view for a single item with selectable text.
- Highlight selection with quick actions (color, note, delete).
- Highlights list with search and filter by color; stale highlight badge when content changes.
- Notes autosave and a subtle dirty indicator; confirm before navigation if unsaved.

### 4.3 Output Template Editor
- Template list (type, description, updated timestamp).
- Create/edit with syntax assistance, variable hints, and preview.
- Assign default template in job output preferences without leaving the job editor.

### 4.4 Bulk Item Actions
- Multi-select list UI for Items and Reading list views.
- Bulk actions: add/remove tags, set status, toggle favorite, delete, generate outputs via `/api/v1/outputs` using selected `item_ids`.
- Progress + partial failure reporting; reversible actions where feasible.

## 5. Backend/API Tasks (Remaining)

- Use `/api/v1/outputs/templates` (DB-backed) as the canonical template editor surface.
- Watchlists outputs resolve DB templates by name and fall back to legacy file-based watchlists templates when needed.
- Bulk update/delete endpoints are already available:
  - `POST /api/v1/items/bulk` with `action` + `item_ids` + payload (tags, status, favorite, delete).
  - `POST /api/v1/reading/items/bulk` as a thin wrapper alias.
- Bulk output generation should call `POST /api/v1/outputs` with `template_id` + `item_ids` (no new bulk endpoint required).

## 6. Dependencies and Constraints

- Existing endpoints:
  - Reading: `/api/v1/reading/import`, `/api/v1/reading/export`, `/api/v1/reading/items`, `/api/v1/reading/items/{id}`, `/api/v1/reading/items/{id}/highlight`, `/api/v1/reading/items/bulk`.
  - Highlights: `/api/v1/reading/items/{id}/highlights`, `/api/v1/reading/highlights/{id}`.
  - Items: `/api/v1/items`, `/api/v1/items/bulk`.
  - Outputs: `/api/v1/outputs` (requires `template_id` + `item_ids`), `/api/v1/outputs/templates`, `/api/v1/outputs/templates/{id}/preview`.
  - Watchlists templates (legacy fallback): `/api/v1/watchlists/templates`.
- Collections DB is stored inside per-user `Media_DB_v2.db`.
- Tests should use UTC for scheduling/time-freezing.

## 7. Acceptance Criteria

- Import UX surfaces validation errors and shows summary results with error details.
- Export UX preserves filters used in the list view and produces correct filenames.
- Highlight selection creates a highlight without manual quote copy/paste.
- Highlights list supports search and color filter; stale highlights are visible.
- Notes autosave prevents data loss on navigation.
- Bulk actions show progress and per-item results; errors are visible.
- Bulk output generation prompts for template selection and returns a generated output artifact or a clear failure state.
- Template editor supports preview and default assignment in job settings.

## 8. Test Plan

- Import: Pocket JSON and Instapaper CSV fixtures; invalid file; oversized file.
- Export: jsonl and zip downloads; filter retention; large lists.
- Highlights: create/edit/delete; stale highlight state; persistence on reload.
- Bulk actions: mixed-success scenarios; undo flow when supported.
- Bulk output generation: template selection, output creation success, output creation failures.
- Notes: dirty indicator and autosave behavior across navigation.

## 9. Open Questions

- Should export include highlights and notes by default or behind a toggle?
- Do large imports need background jobs, or is the current sync flow sufficient?
