# World Book Entry Move API Contract (Draft)

**Date**: 2026-02-18  
**Status**: Draft for backend implementation  
**Related plan**: `IMPLEMENTATION_PLAN_world_books_04_bulk_operations_2026_02_18.md` (Stage 3)

## Goal

Support moving or copying entry sets between world books with conflict handling and explicit result accounting.

## Proposed Endpoint

`POST /api/v1/characters/world-books/entries/move`

## Request

```json
{
  "entry_ids": [12, 13, 14],
  "destination_world_book_id": 42,
  "mode": "move",
  "conflict_strategy": "skip_existing"
}
```

### Fields

- `entry_ids`: required list of source entry IDs.
- `destination_world_book_id`: required destination world book.
- `mode`: `move` or `copy`.
- `conflict_strategy`:
  - `skip_existing` (default): skip entries already present in destination (keyword+content match).
  - `allow_duplicates`: copy regardless of existing content.
  - `replace_existing` (optional future mode): replace matching destination entries.

## Response

```json
{
  "success": true,
  "requested_count": 3,
  "copied_count": 2,
  "moved_count": 2,
  "skipped_count": 1,
  "failed_ids": [],
  "skipped_ids": [12],
  "message": "Moved 2 entries, skipped 1 duplicate"
}
```

## UI Mapping

- Display concise summary toast from `moved_count`, `skipped_count`, and `failed_ids`.
- Keep per-entry metadata preserved on copy/move:
  - `priority`, `enabled`, `case_sensitive`, `regex_match`, `whole_word_match`, `appendable`, `metadata`.

## Current Implementation Note

Until this endpoint exists, frontend currently performs move via:
1. Read destination entries.
2. Copy selected entries with client-side conflict filtering.
3. Bulk-delete successfully copied source entries.
