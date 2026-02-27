# Notes Moodboards

Moodboards let users collect notes into visual boards (Pinterest-style) and open a note in the existing Notes detail panel with related/backlinks/sources context.

## API Summary

Base route: `/api/v1/notes/moodboards`

- `POST /moodboards` - create moodboard
- `GET /moodboards` - list moodboards
- `GET /moodboards/{moodboard_id}` - get moodboard
- `PATCH /moodboards/{moodboard_id}` - update moodboard (`expected-version` header required)
- `DELETE /moodboards/{moodboard_id}` - soft delete moodboard (`expected-version` header required)
- `POST /moodboards/{moodboard_id}/notes/{note_id}` - pin note to moodboard
- `DELETE /moodboards/{moodboard_id}/notes/{note_id}` - unpin note from moodboard
- `GET /moodboards/{moodboard_id}/notes` - list notes shown on moodboard

Trailing-slash variants are supported for list/create routes for compatibility.

## Data Model

- `moodboards` table:
  - `id`, `name`, `description`, `smart_rule_json`, `created_at`, `last_modified`, `deleted`, `client_id`, `version`
- `moodboard_notes` table:
  - `moodboard_id`, `note_id`, `created_at`
  - unique pair via primary key (`moodboard_id`, `note_id`)

Schema migration version: `v29`.

## Note Membership Semantics

`GET /moodboards/{id}/notes` returns a merged set of:

- Manual pins (`moodboard_notes`)
- Smart-rule matches (`smart_rule_json`)

Each returned note includes `membership_source`:

- `manual`
- `smart`
- `both`

## Smart Rule Payload

`smart_rule_json` stores a JSON object. Supported keys in current implementation:

- `query`: text search against note content/title
- `keyword_tokens`: keyword token filters
- `sources`: source filters
- `updated`, `updated_after`, `updated_before`: updated-time filters

If both manual and smart membership include the same note, the note is returned once with `membership_source="both"`.

## WebUI Behavior

Notes page now includes a third list mode: `Moodboard`.

- Sidebar controls: select/create/rename/delete moodboards
- Main panel: moodboard tile grid
- Tile click: opens note in existing Notes detail view
- Detail context strip reuses current compact Related/Backlinks/Sources behavior
