# Characters Recovery QA Checklist (2026-02-18)

Use this checklist after changes to delete/undo/restore flows in the Characters workspace.

## Policy and messaging checks

- [ ] Single delete confirm copy states soft-delete + 10-second undo.
- [ ] Bulk delete confirm copy states soft-delete + 10-second undo.
- [ ] Single delete toast shows undo action and expires after 10 seconds.
- [ ] Bulk delete toast shows undo action and expires after 10 seconds.
- [ ] `Recently deleted` scope is visible and clearly labeled as deleted-state content.

## Recovery behavior checks

- [ ] Restoring from `Recently deleted` returns the character to Active list.
- [ ] Restore updates list state without full page reload.
- [ ] Restore failure shows actionable error text and server-log hint.
- [ ] Version mismatch restore failure can be resolved by refresh + retry.
- [ ] Deleted scope hides destructive bulk toolbar/inline edit affordances.

## API and data checks

- [ ] `GET /api/v1/characters/query?deleted_only=true` returns only soft-deleted records.
- [ ] Restore endpoint rejects stale `expected_version` with `409`.
- [ ] Recovery event telemetry emits `tldw:characters-recovery` actions for delete/undo/restore and failure paths.
