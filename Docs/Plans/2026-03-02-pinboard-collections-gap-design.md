# Pinboard Tour vs Collections Gap Analysis Design

## Context

This design captures approved direction after comparing [Pinboard Tour](https://pinboard.in/tour/) capabilities with the existing Collections module in `tldw_server`.

Current Collections strengths already exceed Pinboard in several areas (highlights, digest scheduling, template-driven outputs, summarize/TTS), but there are specific Pinboard-inspired utility improvements worth adding.

This design uses a strict boundary model with the existing Notes module:

- Notes remains the source of truth for standalone rich notes.
- Collections remains the source of truth for URL/content-item workflows.
- Collections `notes` fields stay lightweight annotations, not a second notes system.

## Goal

Improve Collections with high-value Pinboard-like features while preserving local-first privacy model and avoiding duplication with Notes.

## Non-Goals

- Public sharing, profiles, social discovery, or network features.
- Replacing Notes CRUD/search/export with Collections.
- New crawler classes unrelated to capture/archive reliability.

## Existing Overlap and Boundary Decision

### Existing overlap areas

- Both Notes and Collections can store text.
- Collections items already have `notes` fields for per-item annotation.
- Notes has full notebook capabilities (`/api/v1/notes`) including richer CRUD/search/export/attachments/keyword-linking.

### Boundary model (approved)

1. Standalone text notes belong in Notes (`/api/v1/notes`).
2. Collections annotations remain attached to content items.
3. Collections can link to Notes records but does not own standalone note entities.

## Proposed Improvements (Approach 2, strict boundary)

1. Auto-archive on save (default + per-request override).
2. Saved searches in Reading list (`name + filters + sort`).
3. Fast capture surfaces (bookmarklet/deep-link + extension quick-save path).
4. Dead-link resilience UX (archive availability + last fetch error).
5. Note linking from Collections to Notes (create/link/unlink), not notes-only content items in Collections.

## Architecture

The design extends existing Collections APIs and DB adapter surfaces with small additive models:

- `saved_searches` for reusable reading filters.
- `content_item_note_links` for cross-module associations to Notes IDs.
- Optional collections preference for default archive behavior.

Archive generation reuses existing reading archive/output artifact flows. Notes integration reuses `/api/v1/notes` for creation and content ownership, with Collections storing only link references.

## Data Model Design

### `saved_searches` (Collections DB)

Fields:

- `id`
- `name`
- `query_json` (normalized allowlisted reading filters)
- `sort`
- `created_at`
- `updated_at`
- `last_used_at`

Notes:

- User-scoped via per-user DB.
- `query_json` should include only supported keys: `q`, `status`, `tags`, `favorite`, `domain`, `date_from`, `date_to`.

### `content_item_note_links` (Collections DB)

Fields:

- `content_item_id` (int)
- `note_id` (string UUID from Notes)
- `link_kind` (default `annotation`)
- `created_at`

Notes:

- No cross-DB FK due separate DB systems (Collections DB vs ChaChaNotes DB).
- App-level validation and stale-link handling required.

### Preferences

Add or reuse user preference storage for:

- `auto_archive_on_save` (bool)

## API Design

### Reading saved searches

- `POST /api/v1/reading/saved-searches`
- `GET /api/v1/reading/saved-searches`
- `PATCH /api/v1/reading/saved-searches/{id}`
- `DELETE /api/v1/reading/saved-searches/{id}`

### Reading save with archive policy override

Extend:

- `POST /api/v1/reading/save`

Add request field:

- `archive_mode: use_default | always | never`

Response should include archive status hints, including `archive_output_id` when created.

### Collections-to-Notes links

- `POST /api/v1/reading/items/{item_id}/links/note` (payload: `note_id`)
- `GET /api/v1/reading/items/{item_id}/links`
- `DELETE /api/v1/reading/items/{item_id}/links/note/{note_id}`

### Reading detail resilience fields

Expose derived fields in reading detail response:

- `has_archive_copy`
- `last_fetch_error`

## UX Design

### Reading list toolbar

- Add `Saved Searches` menu:
  - Save current filters
  - Run a saved search
  - Rename/delete saved searches

### Add URL modal

- Add archive behavior control (default from preference; optional per-save override).

### Reading item detail

- Archive status badge (`available`, `not available`, `failed last fetch`).
- `Create Note` action (calls Notes API then links result).
- `Link Existing Note` action.
- Linked Notes list with open/unlink.

### Notes integration behavior

- `Create Note` pre-fills title/content snippet + source URL backlink context.
- User can remain in Collections after create or choose to open note page.

## Data Flow

### Save URL

1. Save/update reading item.
2. Resolve archive policy via request override and default preference.
3. If archive enabled, start archive creation without blocking base save.
4. Return save success plus archive status metadata.

### Save current filters

1. Normalize + validate filter payload.
2. Persist as saved search row.
3. Running saved search hydrates standard list query params.

### Create linked note

1. Call Notes `POST /api/v1/notes/`.
2. Persist item-note link in Collections.
3. Return combined result.

### Link existing note

1. Select note via Notes list/search.
2. Persist mapping only in Collections.

## Error Handling

1. Archive failures must not fail reading save.
2. Two-step note create/link must report partial success clearly:
   - Note created but link failed -> explicit retry link action.
3. Deleted notes referenced by links should display stale markers and cleanup actions.
4. Saved search payload validation failures return `422` with clear messages.

## Testing Plan

### Unit tests

- Saved search normalization and allowlist validation.
- Archive mode resolution precedence (`use_default|always|never`).
- Link lifecycle handling and stale-link detection.

### API integration tests

- Reading save behavior under each archive mode.
- Saved search CRUD and malformed payloads.
- Item-note link endpoints for valid/invalid/deleted notes.
- Reading detail resilience fields.

### UI tests

- Save/run/manage saved searches.
- Add URL archive override.
- Linked Notes panel create/link/unlink/open flows.
- Partial-failure messaging and retry.

### Regression tests

- Existing reading filters/sorting behavior unchanged.
- Notes module CRUD/search/export unaffected.
- Outputs/digests unaffected by link metadata additions.

## Rollout Plan

1. DB migration for `saved_searches` and `content_item_note_links`.
2. Backend feature flags:
   - `COLLECTIONS_SAVED_SEARCHES_ENABLED`
   - `COLLECTIONS_NOTE_LINKS_ENABLED`
   - `COLLECTIONS_AUTO_ARCHIVE_ENABLED`
3. Enable UI after backend validation.
4. Observe for one release window; then promote defaults.

## Success Criteria

1. Reading save remains high reliability even with archive failures.
2. Saved searches have meaningful adoption.
3. Item-note linking succeeds with low error rate; partial failures are recoverable.
4. No Notes module regression in error rate/latency.
5. No schema/domain collisions between Collections and Notes ownership boundaries.
