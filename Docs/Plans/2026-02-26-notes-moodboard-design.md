# Notes Moodboard Design (Hybrid Boards)

Date: 2026-02-26
Status: Approved (brainstorming)
Author: Codex + user

## 1. Problem Statement

Add moodboard support to Notes so users can build Pinterest-like collections of notes shown as image-first cards, click a card to open the note, and immediately see associated items (related/backlinks/sources).

## 2. User-Approved Product Decisions

- Moodboard model: Hybrid boards (manual pins + smart rule results in one board).
- Card cover source: First image attachment on the note, fallback to text-only card.
- Surface location: Inside existing Notes workspace as a third view mode.
- Note open behavior: Reuse existing Notes detail view plus compact associated strip.
- Membership model: Many-to-many (a note can belong to multiple moodboards).
- Board behavior: Mixed board mode in V1 (manual + smart union).
- Default layout: Masonry wall, newest-first.

## 3. Approaches Considered

### Approach A: UI-Only Moodboards

Store moodboards client-side and derive cards from existing note APIs.

Pros:
- Fastest implementation.
- Lowest backend risk.

Cons:
- No durable server sync.
- Weak fit for multi-user/JWT mode.
- Harder to query/audit server-side.

### Approach B: First-Class Backend Moodboards (Recommended, selected)

Add dedicated moodboard entities to ChaChaNotes and expose Notes moodboard APIs.

Pros:
- Durable and multi-user safe.
- Natural fit for many-to-many membership.
- Clean support for mixed manual + smart boards.
- Better long-term maintainability.

Cons:
- Requires schema + API + tests.

### Approach C: Reuse Keyword Collections as Moodboards

Model boards on top of keyword collections.

Pros:
- Less initial schema work.

Cons:
- Confuses semantics.
- Manual pinning and mixed rules become awkward.
- Higher long-term debt.

## 4. Architecture

Moodboards are a first-class Notes domain and are rendered from Notes page view modes:
- `list`
- `timeline`
- `moodboard`

Effective board content is computed as:
- `manual note pins UNION smart rule matches`
- Deduped by `note_id`

Clicking a moodboard card reuses current note selection/detail paths so existing note edit/save/graph features keep working.

## 5. Data Model Design

## 5.1 New tables

### `moodboards`

Fields:
- `id` INTEGER PRIMARY KEY
- `name` TEXT NOT NULL
- `description` TEXT NULL
- `smart_rule_json` TEXT/JSON NULL
- `created_at` DATETIME NOT NULL
- `last_modified` DATETIME NOT NULL
- `client_id` TEXT NOT NULL
- `version` INTEGER NOT NULL DEFAULT 1
- `deleted` BOOLEAN NOT NULL DEFAULT 0

### `moodboard_note_links`

Fields:
- `moodboard_id` INTEGER NOT NULL FK -> `moodboards.id`
- `note_id` TEXT NOT NULL FK -> `notes.id`
- `created_at` DATETIME NOT NULL

Constraints/indexes:
- UNIQUE(`moodboard_id`, `note_id`) for idempotent manual pinning.
- Index on `moodboard_id` and `note_id`.

## 5.2 Smart rule payload (V1)

`smart_rule_json` shape:
- `query`: string | null
- `keyword_tokens`: string[]
- `notebook_collection_ids`: number[]
- `sources`: string[]
- `updated_after`: ISO datetime | null
- `updated_before`: ISO datetime | null

## 6. API Design

Namespace: `/api/v1/notes/moodboards`

CRUD:
- `POST /api/v1/notes/moodboards`
- `GET /api/v1/notes/moodboards`
- `GET /api/v1/notes/moodboards/{id}`
- `PATCH /api/v1/notes/moodboards/{id}`
- `DELETE /api/v1/notes/moodboards/{id}` (soft delete)

Membership:
- `POST /api/v1/notes/moodboards/{id}/notes/{note_id}`
- `DELETE /api/v1/notes/moodboards/{id}/notes/{note_id}`

Board content:
- `GET /api/v1/notes/moodboards/{id}/notes?limit=&offset=`

Board content response should include card-ready fields:
- `note_id`, `title`, `content_preview`, `updated_at`, `keywords`
- `cover_image_url` (first image attachment if available)
- `membership_source` in `{manual, smart, both}`

No new note-detail endpoint is required; existing note fetch and relation panel flows are reused.

## 7. Frontend UX Design

Within `NotesManagerPage`:
- Add a third view mode button: `Moodboard`.
- In moodboard mode, sidebar includes:
- Board selector + create/edit/delete actions.
- Board filters/settings summary.
- Main pane renders masonry card wall.

Card behavior:
- Show cover image when present.
- Fallback to text card when absent or image unavailable.
- Click card opens selected note in existing detail/editor panel.

Associated items behavior:
- Keep current compact strip approach (Related / Backlinks / Sources).
- No expanded tab redesign in V1.

## 8. Data Flow

On moodboard select:
1. Fetch board metadata (`GET /moodboards/{id}`).
2. Fetch board cards (`GET /moodboards/{id}/notes`).
3. Render masonry wall.

On card click:
1. Reuse existing note selection handler.
2. Existing note detail and relation data load as today.

On board rule/manual changes:
1. Persist mutation.
2. Refetch board cards.

## 9. Error Handling

- Invalid smart rule JSON/validation:
- Return 400 with clear field errors.
- UI shows inline warning and preserves editable draft.

- Missing or inaccessible cover image:
- Non-fatal; render text-only fallback card.

- Version conflicts on board updates:
- Follow existing optimistic-lock pattern used in Notes/Keywords.

- Offline/unavailable server:
- Reuse current Notes connection banner behavior.
- Disable board mutations while preserving local view state.

## 10. Testing Strategy

## 10.1 Backend tests

- Moodboard CRUD integration tests.
- Manual pin/unpin idempotency tests.
- Smart-rule filtering tests.
- Mixed union/dedupe correctness tests.
- Soft-delete and optimistic-lock conflict tests.
- RBAC/rate-limit parity tests.

## 10.2 Frontend tests

- View toggle to moodboard mode.
- Masonry rendering with image covers.
- Fallback rendering with no image.
- Card click opens existing note detail.
- Compact associated strip visible and functional.
- Create/edit/delete board flows.
- Conflict/offline UI behavior.
- Regression coverage for existing list/timeline behavior.

## 11. Non-Goals (V1)

- Drag-and-drop manual card ordering.
- Board collaboration/sharing permissions UI.
- AI-generated board themes or auto-clustering visuals.

## 12. Rollout Notes

- Keep feature behind existing Notes capability checks.
- Default existing users to current list view; moodboard is opt-in via toggle.
- No migration of current notebooks into moodboards in V1.

## 13. Open Questions Deferred to Implementation Plan

- Whether to include board-specific sort overrides in V1 API.
- Whether smart rules should support AND/OR groups beyond current filter primitives.
- Whether to precompute `cover_image_url` for large boards vs. resolve at query time.
