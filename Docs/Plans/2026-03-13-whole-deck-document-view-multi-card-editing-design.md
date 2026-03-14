# Whole-Deck Document View And Multi-Card Editing Design

Date: 2026-03-13  
Status: Approved

## Summary

This design adds a third presentation mode to Flashcards `Manage`: a whole-deck document view for continuous-scroll maintenance and inline multi-card editing.

The feature is intentionally scoped as a maintenance surface, not a new workspace. It reuses existing `Manage` filters, selection, bulk actions, and detailed edit drawer while adding a faster way to inspect and update large filtered card sets.

## Goals

- Let users review large filtered card sets in one continuous document-style surface.
- Support inline editing for the most important maintenance fields:
  - `front`
  - `back`
  - `deck`
  - `tags`
  - `notes`
  - `template/model_type`
- Save row edits immediately without forcing a full-page refresh after every change.
- Preserve optimistic-locking safety and give row-local recovery for conflicts and validation errors.
- Keep advanced edit and preview workflows in the existing drawer.

## Non-Goals

- Build a separate flashcard editor outside `Manage`
- Add spreadsheet-style formulas, drag-fill, or desktop-sheet behavior
- Replace existing bulk move/tag/delete flows
- Add image support, image occlusion, or scheduler upgrades in this feature
- Guarantee literal rendering of an entire unlimited dataset in memory at once

## Current Baseline

The current `Manage` tab already owns the state that should remain authoritative for this feature:

- deck, tag, search, due-state, and sort filters
- selection and select-all-across-results
- bulk move, bulk tag, export, delete
- detailed drawer editing and delete/reset actions
- optimistic-lock-aware single-card updates

Relevant code anchors:

- `apps/packages/ui/src/components/Flashcards/tabs/ManageTab.tsx`
- `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
- `apps/packages/ui/src/components/Flashcards/components/FlashcardEditDrawer.tsx`
- `apps/packages/ui/src/services/flashcards.ts`
- `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`

## Key Constraints

### Query And Sort Constraints

Current `Manage` behavior mixes server-backed and client-backed sorting:

- Stable server-backed order today:
  - `due`
  - `created`
- Client-side order today:
  - `ease`
  - `last_reviewed`
  - `front_alpha`

Current multi-tag filtering also uses capped client-side scanning.

That means document mode cannot safely promise stable continuous scrolling for every existing sort/filter shape without either reworking the API or explicitly narrowing scope.

### Mutation Constraints

Current card editing is single-card and uses optimistic locking through `expected_version`.

Immediate inline saves introduce two risks if left unspecified:

- overlapping saves on the same row can create client-generated version conflicts
- membership-changing edits can make naive cache patching wrong

The design therefore adds per-row save serialization and a conditional cache policy.

## Approved Product Decisions

- Add `document` as a third presentation mode inside `Manage`.
- Keep `cards` and `trash` as the top-level `Manage` modes.
- Keep the existing drawer as the advanced edit surface.
- Add a new bulk-update API for document-mode saves.
- Use mixed-result row updates, not all-or-nothing transactions.
- Keep document-mode v1 sorts limited to stable server-orderable sorts.

## UX Design

### Presentation Model

`Manage` will support:

- `cards`
- `trash`

Within active cards, the presentation toggle will support:

- `compact`
- `expanded`
- `document`

`document` is a maintenance-oriented layout, not a study layout. It should feel like a readable deck sheet that becomes editable on focus.

### Document Rows

Each row shows:

- selection affordance
- `front`
- `back`
- `deck`
- `tags`
- `notes`
- `template/model_type`
- row actions to open the full edit drawer

Rows default to read mode. Editing is activated when the user focuses a field. This avoids mounting heavy interactive controls for every visible cell at once.

### Editing Behavior

Save behavior by field type:

- Single-line text fields: save on blur or `Enter`
- Multi-line fields: save on explicit action or `Cmd/Ctrl+Enter`
- Tags and deck: save after inline selector confirmation
- Template changes: normalize `model_type`, `reverse`, and `is_cloze` before save using the same logic as the drawer

Each row has explicit local state:

- `clean`
- `dirty`
- `saving`
- `saved`
- `conflict`
- `validation_error`
- `stale`

Saved state should be brief and low-noise. Errors stay row-local and never block successful updates on other rows.

### Drawer Relationship

The existing edit drawer remains the place for:

- Markdown preview and richer inspection
- delete
- scheduling reset
- detailed metadata review
- any future advanced fields not exposed inline

Document mode is the fast-edit surface, not a replacement for the drawer.

### Bulk Actions

Selection, bulk move, bulk add/remove tag, export, and delete remain shared `Manage` actions.

Document mode reuses the current bulk-action bar. It does not create a second bulk-action model.

If the active document query is known to be truncated by a scan cap, `select all across results` must be disabled for that query shape and the UI must say why.

## Data And API Design

### New Endpoint

Add a bulk-update endpoint:

- `PATCH /api/v1/flashcards/bulk`

Request body: a list of row-scoped card updates, each including:

- `uuid`
- changed editable fields
- `expected_version`

Response body: per-item results, not one global success/failure.

Each result includes:

- `uuid`
- `status`
  - `updated`
  - `conflict`
  - `validation_error`
  - `not_found`
- `flashcard` when update succeeds
- structured error details when it fails

### Transaction Model

The endpoint is mixed-result by design.

One row failing validation or optimistic locking must not roll back successful updates for other rows in the same request. The DB helper should isolate row updates and collect results rather than treating the whole request as one atomic mutation.

### Validation Rules

Bulk update must preserve current single-card rules:

- deck existence and deleted-deck rejection
- template normalization
- cloze validation
- optimistic locking with `expected_version`

Document mode and drawer editing must share normalization rules so identical edits cannot behave differently depending on surface.

## Frontend Data Flow

### Query Model

Add a dedicated infinite-query hook for document mode keyed by the same filter state as `Manage`.

Document mode uses continuous incremental page fetches rather than traditional pagination controls.

V1 supported document-mode sorts:

- `due`
- `created`

V1 excluded document-mode sorts:

- `ease`
- `last_reviewed`
- `front_alpha`

Those remain available in card-list mode only.

### Truncation Rules

For multi-tag queries or other capped scan paths, document mode must surface truncation explicitly when a query hits its configured limit.

When truncation is active:

- show a visible results-truncated banner
- disable `select all across results`
- keep inline editing available for loaded rows

### Cache Update Policy

Successful row saves do not always invalidate everything.

Use this rule:

- Patch the updated row directly into the active document query cache only when the row still belongs in the active result set and its ordering remains valid.
- If the update can change membership or order, invalidate only the active document query and refetch around the current viewport.

Examples that should trigger query refresh rather than blind patching:

- `deck_id`
- `tags`
- `front` when sort/filter depends on it
- any edit that changes whether the row belongs in the filtered set

Bulk move/delete can retain broader invalidation behavior.

## Row Save Orchestration

Each row gets its own save queue.

Rules:

- only one save request per row can be in flight at a time
- if more edits happen while a save is in flight, coalesce them into the next queued patch
- after success, replace local row state with the returned server row, including new `version`
- then send any queued patch against that fresh version

This prevents the client from creating its own version-conflict churn when blur/commit events happen close together.

## Error Handling And Recovery

### Validation Errors

- Stay on the row and field that failed
- Do not invalidate the whole document
- Allow immediate correction and retry

### Version Conflicts

Conflicts stay row-local and offer:

- `Reload row`
- `Reapply my edit`

The user’s attempted edit should not be silently discarded until they explicitly reload or cancel it.

### Not Found Or Stale Rows

If a row disappears or is deleted elsewhere:

- mark it as `stale`
- collapse editing affordances
- offer refresh/reload messaging

### Undo

Inline row edits should support row-local undo after successful save, using the same previous-row snapshot pattern already used by drawer edits.

Undo should restore the previous row state through the same optimistic-lock-aware mutation path.

## Keyboard And Accessibility

Document mode must not accidentally regress from list mode.

V1 should define keyboard support for:

- moving row focus
- entering edit mode
- saving
- canceling
- toggling selection
- opening the detailed edit drawer

Screen-reader-visible row states should expose saving/error/conflict feedback without relying only on color.

## Testing Strategy

### Backend

- bulk update returns mixed results
- one row conflict does not roll back successful siblings
- deck validation works in bulk updates
- cloze/template normalization works in bulk updates
- not-found rows return explicit per-item failure results

### Frontend

- document mode toggle renders and preserves shared filters
- document mode limits sort options to `due` and `created`
- incremental loading appends rows correctly
- truncation banner appears for capped scan paths
- select-all-across-results is disabled when truncation is active
- row save success updates local row state
- row save queue coalesces overlapping edits
- conflict flow supports reload and reapply
- membership-changing edits trigger targeted refetch
- row undo works
- existing drawer flow still works from document mode

## Success Criteria

This design is successful if:

- users can inspect and edit large filtered card sets without leaving `Manage`
- document mode feels faster than one-card-at-a-time drawer editing
- per-row saves remain safe under optimistic locking
- filter/order correctness is preserved after edits
- existing `Manage` capabilities stay shared rather than duplicated

## Next Step

Create an implementation plan for:

`Whole-deck document view plus multi-card editing in Flashcards Manage`
