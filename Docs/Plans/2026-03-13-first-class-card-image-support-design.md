# First-Class Card Image Support Design

Date: 2026-03-13  
Status: Approved

## Summary

This design adds first-class flashcard image support without turning flashcard text fields into binary transport containers.

Images will be stored as managed flashcard assets and referenced inline from `front`, `back`, `extra`, and `notes` using internal asset references. The WebUI will resolve those references through authenticated fetches and object URLs, while APKG import/export will translate between app-native references and Anki media packaging.

## Goals

- Add durable image support for flashcards across create, edit, manage, review, and document-mode editing.
- Keep the authoring model inline-first so inserted images live where the user places them in the field body.
- Preserve APKG import/export round-trip for image-backed cards in the same slice.
- Avoid storing base64 image payloads inside flashcard text fields.
- Keep flashcard search/index performance stable as image usage grows.

## Non-Goals

- Image occlusion authoring
- Drag-and-drop reordering galleries
- Rich resize/crop/caption tooling
- Clipboard image paste unless it falls out cheaply from the upload helper
- Public asset URLs or unauthenticated image delivery

## Current Constraints

- Flashcards are still persisted as text-first records in `CharactersRAGDB`, with `front`, `back`, `notes`, and `extra` driving the user experience.
- The current markdown renderer emits plain `<img src=...>` tags, which cannot attach authenticated API headers on their own.
- APKG export currently only extracts media from raw HTML `<img>` / `<audio>` tags and only touches `front`, `back`, and `extra`.
- APKG import currently maps only the visible Anki fields by position and does not yet rewrite packaged media into app-native references.
- Flashcard FTS currently indexes `front`, `back`, and `notes` directly, so any reference format stored there affects search quality unless sanitized.

## Core Decisions

### 1. Persist Internal Asset References, Not API URLs

Saved flashcard fields will store inline markdown using a managed internal reference format:

```md
![Histology slide](flashcard-asset://<asset_uuid>)
```

We will not persist raw API URLs such as `/api/v1/flashcards/assets/<uuid>`.

Why:

- Plain `<img src="/api/...">` rendering does not reliably work with the current authenticated request model.
- Absolute API URLs would be treated like external images by the shared markdown policy in some contexts.
- Internal references keep persisted content stable even if delivery endpoints change later.

### 2. Resolve Managed Images Through an Authenticated Client Cache

The shared markdown renderer will gain a flashcard-asset-aware image component.

When `src` matches `flashcard-asset://<uuid>`:

- fetch asset bytes through authenticated request helpers
- create an object URL
- render the image from that object URL
- reuse cached object URLs for repeated cards
- revoke object URLs when cache entries are evicted

This makes image rendering work in single-user and multi-user auth modes without weakening the existing image security defaults.

### 3. Store Image Bytes in a Dedicated Flashcard Asset Table

Add a new `flashcard_assets` table in the notes DB.

Recommended fields:

- `id`
- `uuid`
- `card_id` nullable
- `mime_type`
- `original_filename`
- `byte_size`
- `sha256`
- `image_data`
- `width`
- `height`
- `created_at`
- `last_modified`
- `deleted`
- `client_id`
- `version`

Notes:

- Assets are immutable for v1. Replacing an image means uploading a new asset and updating the inline reference.
- `card_id IS NULL` represents a draft/unattached asset.
- Save/update reconciliation attaches referenced assets to the card and detaches assets no longer referenced by that card.

### 4. Keep Text Limits; Add Asset Limits

The current `8192` text-field guardrail stays in place for flashcard text.

Image support will not rely on increasing those text caps because:

- base64 blobs would bloat flashcard payloads
- `flashcards_fts` would index binary-like payload text
- document mode and optimistic updates would become significantly heavier
- import safeguards would weaken for all flashcard text, not just image-backed cards

Instead, add dedicated asset/media limits such as:

- per-image bytes cap
- allowed raster MIME types
- APKG total media bytes cap
- stale draft asset TTL for cleanup

## Architecture

### Backend

Add a flashcard asset subsystem inside the existing flashcards API and DB layer.

New backend responsibilities:

- upload and validate flashcard image assets
- serve image bytes for authenticated clients
- parse internal flashcard asset references from text fields
- reconcile references to asset attachments during create/update/bulk update
- translate app-native references to Anki media during APKG export
- translate Anki media-bearing fields back to app-native references during APKG import

Recommended helper modules:

- `tldw_Server_API/app/core/Flashcards/asset_refs.py`
  - parse internal refs
  - build markdown snippets
  - sanitize text for search indexing
  - translate between markdown refs and HTML `<img>` tags for APKG
- flashcard DB helpers in `ChaChaNotes_DB.py`
  - create asset
  - fetch asset content
  - list referenced asset UUIDs for a card payload
  - attach/detach referenced assets
  - clean stale unattached assets

### Frontend

Keep the UX inline-first.

New frontend responsibilities:

- upload selected image files to the flashcard asset endpoint
- insert the returned markdown snippet at the cursor position
- resolve `flashcard-asset://` references to authenticated blob/object URLs in markdown
- reuse the same helper in create drawer, edit drawer, and document-mode row editing

## API Design

### Upload

Add a new endpoint:

- `POST /api/v1/flashcards/assets`

Request:

- `multipart/form-data`
- image file upload

Response:

- `asset_uuid`
- `reference`
- `markdown_snippet`
- `mime_type`
- `byte_size`
- `width`
- `height`
- `original_filename`

Example response intent:

```json
{
  "asset_uuid": "123e4567-e89b-12d3-a456-426614174000",
  "reference": "flashcard-asset://123e4567-e89b-12d3-a456-426614174000",
  "markdown_snippet": "![Lecture slide](flashcard-asset://123e4567-e89b-12d3-a456-426614174000)"
}
```

### Content Fetch

Add a content endpoint:

- `GET /api/v1/flashcards/assets/{asset_uuid}/content`

This endpoint returns the raw image bytes with the stored MIME type. It is intended for authenticated programmatic fetches from the WebUI asset resolver, not for direct public embedding.

### Save Reconciliation

Existing flashcard create, update, and bulk update paths will be extended to:

- parse internal asset references from `front`, `back`, `extra`, and `notes`
- verify those assets exist in the current user DB and are not deleted
- attach referenced draft assets to the saved card
- detach assets that are no longer referenced by that card
- reject foreign or missing asset references with a validation error

The text fields remain the source of truth for placement. The asset table remains the source of truth for bytes and ownership.

## Inline Reference Format

The canonical persisted format is markdown with a custom scheme:

```md
![Alt text](flashcard-asset://<asset_uuid>)
```

Why this shape:

- works naturally with inline-first editing
- remains small in stored text
- is easy to regex-parse deterministically
- avoids external image blocking rules
- keeps export/import translation explicit instead of implicit

## Rendering Model

The markdown renderer will add a custom image component:

- if `src` is a normal URL or data URI, existing behavior remains
- if `src` starts with `flashcard-asset://`, resolve via authenticated fetch to an object URL

The object URL resolver should:

- cache per asset UUID
- avoid duplicate in-flight fetches
- support lazy resolution near viewport for large deck/document surfaces
- degrade to a small inline error state when fetch fails

This is a shared markdown enhancement, but it is inert outside flashcards because it only activates for the custom scheme.

## APKG Export Translation

APKG export must not emit raw app-internal references or markdown image syntax directly.

Export flow:

1. Read flashcard field content from the DB.
2. Convert `flashcard-asset://` markdown image references into Anki-friendly HTML `<img>` tags backed by data URIs or packaged media filenames.
3. Let the exporter package those images into the APKG media manifest.

Required exporter changes:

- support internal-ref-to-HTML translation before media extraction
- include `notes` in the exported note model for `tldw`-exported decks so notes images can round-trip

### Notes Policy For APKG

To satisfy the approved scope that includes images in `notes`, `tldw` exported APKGs will extend their models to preserve `notes`:

- Basic model fields: `Front`, `Back`, `Extra`, `Notes`
- Cloze model fields: `Text`, `Back Extra`, `Notes`

Templates will continue to display only study-facing fields. `Notes` is preserved as a hidden round-trip field for `tldw` decks.

Tradeoff:

- exported `tldw` APKGs remain valid Anki decks
- the additional `Notes` field is a `tldw` round-trip extension, not an Anki-default expectation

## APKG Import Translation

APKG import will become model-aware for media-bearing fields.

Import flow:

1. Read the APKG media manifest and numbered media files.
2. Parse note field definitions from the Anki model metadata instead of only relying on positional defaults.
3. For any supported image references in note fields:
   - read the packaged media bytes
   - validate MIME and size
   - create flashcard asset records
   - rewrite the field content to app-native markdown refs such as `![alt](flashcard-asset://<uuid>)`
4. Preserve `notes` when the source model contains a field explicitly named `Notes` or when importing a `tldw` APKG model.

Fallback behavior:

- generic third-party APKGs without a `Notes` field continue to import with `notes` empty
- field-name-aware mapping should fall back to the current positional logic when metadata is incomplete

## Search / FTS Normalization

We should not let internal asset tokens pollute flashcard search.

V1 will include search-safe shadow columns:

- `front_search`
- `back_search`
- `notes_search`

Behavior:

- save/import/update paths compute sanitized text for those columns
- sanitization strips internal asset reference tokens while preserving useful alt text
- flashcard FTS triggers index the sanitized search columns, not the raw persisted fields

This keeps search quality stable without sacrificing inline image placement in the real user-visible fields.

## Validation And Limits

### Text

- keep current flashcard text guardrails
- image support must not depend on increasing text caps

### Asset Upload

- allow raster formats only in v1
- validate MIME using server-side detection
- reject oversized images
- compute and store `sha256`

### APKG Media

- enforce per-image validation during import
- enforce total APKG media byte caps for import and export
- only package media actually referenced by exported card fields

### Access Control

- asset content fetch is authenticated
- save/update reconciliation only accepts references to assets in the current user DB
- no public unauthenticated flashcard image URLs in v1

## Lifecycle And Cleanup

- uploaded assets start unattached with `card_id = NULL`
- card save attaches referenced assets
- edits that remove the final reference detach the asset from that card
- stale unattached assets older than a configured TTL are eligible for cleanup
- attached assets on soft-deleted cards are not considered orphaned

## UX Behavior

Supported fields in v1:

- `front`
- `back`
- `extra`
- `notes`

In create drawer, edit drawer, and document-mode row editing:

- each supported field gets an `Insert image` action
- selecting a file uploads it immediately
- the returned markdown snippet is inserted at the cursor position or appended with a newline fallback
- previews render the managed image inline through the shared markdown renderer

Manage and review:

- no special-case renderer is needed beyond managed asset resolution inside markdown
- images appear where the field content places them

## Testing Strategy

Backend coverage:

- asset upload validation and fetch auth
- create/update/bulk update reference reconciliation
- stale draft cleanup behavior
- APKG export packaging for internal refs
- APKG import rewrite from packaged media to internal refs
- hidden `Notes` field round-trip for `tldw` APKG models
- FTS sanitization for asset-bearing text

Frontend coverage:

- markdown managed-image resolution
- create drawer insert-image flow
- edit drawer insert-image flow
- document-mode inline image insertion
- review/manage rendering of internal asset refs

## Success Criteria

This design is successful if:

- flashcard images are durable and inline-first across create/edit/review/manage
- authenticated rendering works without storing raw API URLs in card text
- APKG import/export round-trips image-backed cards, including `notes` for `tldw` decks
- flashcard search quality does not degrade because of asset tokens
- text field caps remain text guardrails instead of becoming binary transport exceptions
