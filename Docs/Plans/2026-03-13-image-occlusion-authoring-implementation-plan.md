# Image Occlusion Authoring Implementation Plan

Date: 2026-03-13  
Status: In Progress

## Goal

Add a `Transfer`-tab image occlusion authoring workflow that:

- accepts one uploaded image
- lets the user create rectangular occlusions
- generates masked/highlighted derived image assets
- builds editable flashcard drafts
- saves those drafts through bulk create

## Stage 1: Authoring Primitives

**Goal:** Build the occlusion region state model and lightweight pointer-driven authoring surface.

**Success Criteria:**

- user can load an image preview
- user can drag to create a rectangle
- rectangles are stored as normalized geometry
- user can label and remove regions

**Tests:**

- region drag creates normalized rectangle
- small accidental drags are ignored
- label is tracked per region
- region remove updates selection correctly

**Status:** Complete

## Stage 2: Derived Image Generation

**Goal:** Generate prompt and answer image blobs from the source image and selected regions.

**Success Criteria:**

- prompt image masks the selected region
- answer image highlights the selected region
- source image is downscaled to the configured max edge before export
- generation works for multiple regions

**Tests:**

- helper returns prompt and answer blobs for one region
- helper processes two regions deterministically
- oversize source image is scaled down

**Status:** Complete

## Stage 3: Draft And Save Flow

**Goal:** Convert generated image assets into editable flashcard drafts and persist through bulk create.

**Success Criteria:**

- source and derived assets upload through the managed asset endpoint
- drafts are editable before save
- save uses `useCreateFlashcardsBulkMutation`
- saved cards carry source provenance in `source_ref_id` and `notes`
- abandoned drafts rely on existing stale-asset cleanup instead of synchronous asset deletion

**Tests:**

- upload pipeline calls asset endpoint for source plus derived images
- generated drafts contain managed markdown refs
- save submits bulk payload with expected fields

**Status:** Complete

## Stage 4: Docs And Verification

**Goal:** Document the new authoring flow and verify the touched scope.

**Success Criteria:**

- study guide includes image occlusion authoring
- targeted frontend tests pass
- no backend changes are required for v1

**Tests:**

- targeted vitest suite for occlusion panel and helpers
- existing managed image markdown tests still pass

**Status:** Complete

## Implementation Notes

- Reuse `Transfer` draft review/save patterns from the existing `GeneratePanel`.
- Keep v1 frontend-only; do not add backend authoring endpoints.
- Reuse `uploadFlashcardAsset` for source and derived images.
- Store provenance in:
  - `source_ref_type = "manual"`
  - `source_ref_id = "image-occlusion:<source_asset_uuid>:<region_index>"`
  - `notes` metadata block

## Verification Commands

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/codex-flashcards-structured-qa-import/apps/packages/ui
bunx vitest run \
  src/components/Flashcards/tabs/__tests__/ImageOcclusionPanel.test.tsx \
  src/components/Flashcards/utils/__tests__/image-occlusion-canvas.test.ts \
  src/components/Common/__tests__/Markdown.flashcard-asset-image.test.tsx \
  src/services/__tests__/flashcard-assets.test.ts
```
