# Image Occlusion Authoring Design

Date: 2026-03-13  
Status: Approved

## Summary

This design adds a repo-native image occlusion authoring workflow to flashcards without introducing a new review model or scheduler path.

V1 will let a user upload one image, draw rectangular occlusion regions, label each region, generate standard flashcard drafts, review/edit those drafts, and save them through the existing flashcards bulk-create path.

The key decision is to represent occlusion cards as ordinary `basic` flashcards backed by managed image assets:

- `front` shows a masked prompt image
- `back` shows the answer text plus a highlighted answer image
- derived images are stored as managed flashcard assets using existing upload infrastructure

This keeps study, export, scheduling, document mode, and markdown rendering unchanged.

## Product Fit

The current repo now has:

- managed flashcard image assets
- authenticated markdown image rendering
- create/edit/document image insertion
- APKG round-trip for image-backed cards
- transfer-tab draft review and save flows

Image occlusion should build on those primitives instead of creating a special card runtime.

## Explicit Decisions

- Do not add a new flashcard `model_type` for v1.
- Do not change study/review scheduling or rating behavior.
- Do not require backend image-processing endpoints for v1.
- Do not support polygons, freehand masks, or grouped hide-all cards in v1.
- Do not support reopening existing image occlusion cards in the occlusion editor in v1.

## V1 Scope

### Entry Surface

Add a new `Image Occlusion` authoring panel inside `Transfer`.

Why:

- it already hosts multi-card authoring workflows
- it already supports editable draft review before save
- it avoids overloading the single-card create drawer with a batch workflow

### Authoring Flow

1. User selects one image file.
2. The panel renders a preview with an absolute-position overlay layer.
3. User drags to create rectangular regions.
4. Each region gets a required answer label.
5. User optionally sets deck and tags for the batch.
6. User generates drafts.
7. The panel uploads:
   - the original source image
   - one masked prompt image per region
   - one highlighted answer image per region
8. The panel creates editable flashcard drafts from those uploaded asset refs.
9. User reviews, edits, removes, and saves drafts through the existing transfer flow.

### Card Shape

Each occlusion becomes one `basic` flashcard draft:

- `front`
  - short prompt text
  - markdown image for the masked prompt asset
- `back`
  - answer label
  - markdown image for the highlighted answer asset
- `tags`
  - user-entered tags
  - optional `image-occlusion` system tag in v1
- `notes`
  - lightweight provenance block including:
    - source asset reference
    - normalized region geometry
    - occlusion label

The notes payload is intentionally human-readable because v1 does not reopen cards in an occlusion editor.

## UI Design

### Panel Layout

The `Image Occlusion` panel should follow the same shape as the existing `Generate` panel:

- help copy
- deck selector
- tag input
- source image picker
- authoring canvas
- generated draft list
- save button

### Occlusion Canvas

Use a lightweight DOM overlay instead of introducing a large canvas/annotation library.

Behavior:

- render the uploaded image inside a bounded container
- place an absolutely positioned interaction layer above it
- support pointer drag to create rectangles
- store region geometry as normalized percentages:
  - `x`
  - `y`
  - `width`
  - `height`
- show numbered overlays for created regions
- allow selecting a region from the canvas or side list
- allow deleting the selected region

### Region Editing

Each region has:

- index
- answer label
- normalized geometry summary
- remove action

V1 only requires answer label editing, not resizing an existing rectangle after creation. A user can delete and redraw if needed.

## Image Generation Model

Derived images are generated in the browser with `canvas`.

### Prompt Image

For each region:

- draw the original source image
- fill the selected rectangle with an opaque dark mask
- draw a subtle outline around the masked rectangle

### Answer Image

For each region:

- draw the original source image
- draw a bright outline around the selected rectangle
- lightly tint the selected rectangle for emphasis

This keeps the review-side renderer simple because the result is just a normal image.

## Data And Persistence

### No New Backend API For Authoring

V1 reuses:

- `POST /api/v1/flashcards/assets`
- existing managed markdown image refs
- existing bulk flashcard create

Asset lifecycle note:

- source and derived assets are uploaded before the user saves drafts
- if the user abandons the flow, those assets remain unattached temporarily
- this is acceptable in v1 because the existing stale flashcard-asset cleanup can reclaim unattached assets later

### Provenance

Each saved card should include:

- `source_ref_type = "manual"`
- `source_ref_id = "image-occlusion:<source_asset_uuid>:<region_index>"`

And `notes` should append a short occlusion metadata block.

Recommended block shape:

```text
[image-occlusion]
source=flashcard-asset://<source_uuid>
region=x,y,width,height
label=<answer>
```

This is enough to trace generated cards back to the uploaded source image even before a full occlusion metadata table exists.

## Performance And Guardrails

- use existing asset byte caps for uploaded source and derived images
- limit image occlusion generation to one source image per batch in v1
- cap region count per generation run, recommended at `25`
- cap rendered source image dimensions before derived export, recommended at `1600px` max edge

The max-edge cap matters because one large lecture screenshot could otherwise create many oversized derived images.

## Testing

### Frontend

- region creation from pointer drag
- label validation
- draft generation from two or more occlusions
- upload sequencing for source plus derived assets
- save flow uses bulk create
- generated draft editing/removal still works

### Residual Risks

- browser canvas/image decode behavior can differ in tests
- very large images may need dimension downscaling to stay within asset caps
- metadata in `notes` is intentionally transitional and not yet editable through a structured occlusion editor

## Non-Scope

- reopen/edit existing occlusion cards
- polygon or freehand masks
- grouped hide-all / reveal-one Anki parity modes
- backend occlusion metadata schema
- APKG-native occlusion note types
- automatic OCR or label suggestion

## Success Criteria

This design succeeds if a user can:

- author rectangular occlusions from one uploaded image
- generate image-backed card drafts without leaving `Transfer`
- save those drafts as normal flashcards
- study/export them using the existing flashcards pipeline
