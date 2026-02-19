# Decision Record: Notes Editor Stage 4 (Revision + Attachments)

Date: 2026-02-18
Scope: `/notes` editor Stage 4 groundwork

## Context

The notes editor already supports optimistic locking (`version`) and unsaved change tracking. It does not yet provide full revision history UI or attachment upload endpoints.

Stage 4 required:
- A short-term revision decision for safe editing.
- Attachment insertion groundwork without introducing broken server behavior.
- Visible `version` and `last saved` metadata in the editor.

## Decision

1. Revision strategy (short term):
- Keep native browser undo/redo behavior.
- Keep optimistic locking as the conflict authority.
- Surface `version` and `last saved` metadata in the editor footer.
- Defer full revision history UI/diff tooling to a later phase.

2. Attachment strategy (short term):
- Add an editor toolbar action that inserts attachment markdown placeholders.
- Require the note to be saved first so placeholders can reference a stable note ID.
- Use placeholder link format:
  - Image: `![filename](/api/v1/notes/{id}/attachments/{filename})`
  - File: `[filename](/api/v1/notes/{id}/attachments/{filename})`
- Show a user-facing info message that upload wiring is staged.

## Deferred API Contract (Attachment Upload Phase)

Planned endpoint contract for later implementation:
- `POST /api/v1/notes/{id}/attachments`
  - Multipart body: one or more files
  - Returns canonical attachment URLs and metadata
- `GET /api/v1/notes/{id}/attachments/{attachment_id_or_name}`
  - Streams or downloads attachment bytes
- Optional metadata persistence:
  - `metadata.attachments[]` with `name`, `mime`, `size`, `url`, `created_at`

## Acceptance Criteria For Revision History Phase

Phase is complete when all are true:
- Users can list prior revisions for a note.
- Users can open a specific revision snapshot.
- Users can compare current vs selected revision (diff view).
- Users can restore a previous revision as a new head version.
- Revisions include timestamp + actor/version metadata.

