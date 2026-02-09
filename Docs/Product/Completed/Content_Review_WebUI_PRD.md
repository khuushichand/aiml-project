# Content Review System (WebUI) - Product Requirements Document

## Document Info

| Field | Value |
|-------|-------|
| Feature Name | Content Review System (WebUI) |
| Status | Draft |
| Created | 2025-12-20 |
| Author | Codex |

---

## 1. Executive Summary

### Problem Statement

The current WebUI ingest flow at `apps/tldw-frontend/pages/media.tsx` sends content to the process-only endpoints by default. This means ingested content does not persist, which is a severe bug for the WebUI. Users also have no pre-storage review step to fix transcription or OCR errors before content is permanently stored.

### Proposed Solution

Fix WebUI ingest so it **stores by default** using `POST /api/v1/media/add`. Add an **optional Content Review** step that uses process-only endpoints to create drafts in IndexedDB, then lets users edit and commit to the server via a full-page editor.

### Success Criteria (No Telemetry)

No telemetry or analytics. Success is validated via user feedback and internal QA.

---

## 2. User Requirements

### 2.1 Target Users

- Power users who process large volumes of content (transcripts, articles, documents)
- Users who need high-quality, clean content for RAG/knowledge base
- Users working with audio/video content where transcription errors are common

### 2.2 User Stories

| ID | As a... | I want to... | So that... |
|----|---------|--------------|------------|
| US-1 | Content curator | Review transcripts before storage | I can fix speech-to-text errors |
| US-2 | Researcher | Filter out irrelevant sections | Only valuable content enters my knowledge base |
| US-3 | Knowledge worker | Edit metadata and keywords | Content is properly categorized |
| US-4 | Bulk importer | Review multiple items in one session | I can efficiently process batches |
| US-5 | Casual user | Skip review when I trust the source | I am not forced into extra steps |

### 2.3 Confirmed Requirements

| Requirement | Decision |
|-------------|----------|
| Edit Types | Text corrections, structural formatting, content filtering, metadata editing |
| Workflow | Optional review before storing; ingest still stores by default |
| UI Location | Dedicated full-page editor |
| Persistence | Drafts saved to IndexedDB (Dexie), per user |

---

## 3. Functional Requirements

### FR-0: Store by Default (Bug Fix)

- Default behavior uses `POST /api/v1/media/add` to persist content.
- Process-only endpoints are used **only** when review mode is enabled.
- This change corrects the WebUI bug where ingestion never stored content.

### FR-1: Review Mode Toggle

- Location: `apps/tldw-frontend/pages/media.tsx`.
- Two toggles:
  - `Store in Media Library` (default on).
  - `Review before storing` (visible only when store is on; default off).
- Persistence: last-used values saved in `localStorage`, scoped per user id (`userKey`).
- Defaults: toggle state is not cleared on logout; it is isolated by `userKey`.

### FR-2: Draft Creation

- Trigger: user clicks Ingest with review mode enabled.
- Process:
  1. Call media-type-specific process-only endpoint:
     - Audio/video: `/api/v1/media/process-audios` or `/api/v1/media/process-videos`
     - Documents/HTML/Markdown/XML: `/api/v1/media/process-documents`
     - PDFs: `/api/v1/media/process-pdfs`
     - Ebooks: `/api/v1/media/process-ebooks`
     - Emails: `/api/v1/media/process-emails`
     - Code: `/api/v1/media/process-code`
     - Web scraping: `/api/v1/media/process-web-scraping` (JSON payload)
     - MediaWiki dumps: `/api/v1/media/mediawiki/process-dump` (streaming)
  2. Save results as `ContentDraft` records in IndexedDB via Dexie.
  3. Group drafts under a `DraftBatch`.
  4. Redirect to `/content-review?batchId=...`.
- Source assets:
  - URLs: store original URL in the draft.
  - Files: store original file blob when possible.
  - Enforce a 100 MB cap; warn if exceeded and store without blob when allowed.
  - If the asset blob is missing for audio/video, mark `asset_status=missing` and require reattach (file or URL) before commit.
  - MediaWiki streaming yields one draft per item; each item inherits the batch id.

### FR-3: Content Review Page

- Route: `apps/tldw-frontend/pages/content-review.tsx`.
- Layout: sidebar list + editor panel.
- Editor features:
  - Markdown plain-text editor (no WYSIWYG).
  - Toolbar for markdown insertion.
  - Word/character count.
  - Auto-save with visual indicator.
  - Diff view (original vs edited markdown).
- Section filtering:
  - Checkbox UI for section selection when sections exist.
  - Manual edits disable section toggles unless reset to original.
- Metadata panel:
  - Title, keywords, and custom fields.
  - Source reattach flow when `asset_status=missing`.

### FR-4: Draft Actions

| Action | Behavior |
|--------|----------|
| Save Draft | Persist edits to IndexedDB |
| Reattach Source | Provide file or URL when `asset_status=missing` |
| Discard | Delete draft with confirmation |
| Mark Reviewed | Set status to `reviewed`, optionally advance |
| Commit | Send edited content + metadata to server |
| Skip | Navigate only, no status change |
| Commit All | Commit only `reviewed` items |

### FR-5: Edit History

- Store up to 10 snapshots per draft.
- Undo and reset to original content supported.
- Revision count scales down for large drafts.
- When storage cap is hit, evict oldest snapshots before blocking auto-save.

### FR-6: Draft Lifecycle

| Status | Description |
|--------|-------------|
| pending | Created, not yet reviewed |
| in_progress | Opened and edited |
| reviewed | Marked ready for commit |
| committed | Successfully sent to server |
| discarded | Deleted by user |

State transitions:
- Create -> pending
- Open/edit -> in_progress
- Mark Reviewed -> reviewed
- Commit -> committed (auto-mark reviewed if needed)
- Discard -> discarded
- Skip -> no status change

### FR-7: Auto-Cleanup

- Drafts expire after 30 days (configurable).
- Committed/discarded drafts cleaned after 7 days.
- Empty batches removed after 24 hours.
- Storage cap 100 MB for draft content + source assets.
- Eviction order when over cap: drop old snapshots -> drop asset blobs -> block new drafts
  until user clears storage or reduces retention.

---

## 4. Technical Architecture (WebUI)

### 4.1 Data Flow

```
Media Page (pages/media.tsx)
  |
  |-- review disabled --> POST /media/add (stores immediately)
  |
  |-- review enabled --> POST /media/process-* (no persistence)
                           |
                           v
                      Dexie drafts
                           |
                           v
                    /content-review
                           |
                           v
                     Commit flow:
                     POST /media/add
                     PUT /media/{id}
                     PATCH /media/{id}/metadata
```

### 4.2 Client Storage (Dexie)

- Per-user database name: `tldw-content-review-{userKey}`.
- `userKey` is the authenticated user id; drafts and toggle state are isolated by user id.
- When user changes, open a different DB; do not auto-clear previous users' drafts.

Tables:

```
contentDrafts: 'id, batchId, status, mediaType, createdAt, updatedAt, expiresAt'
draftBatches: 'id, createdAt, updatedAt'
draftAssets: 'id, draftId, createdAt'
```

Draft schema (stored payloads):

```
ContentDraft:
  id, batchId, status, mediaType
  title, author, keywords[]
  original_content, edited_content
  sections[] (optional)
  source: { kind: 'url'|'file'|'stream', url?, filename?, mime?, size?, checksum? }
  asset_status: 'present'|'missing'
  custom_metadata: { [key: string]: string }
  createdAt, updatedAt, expiresAt

DraftSection:
  id, label, start_char, end_char, include

DraftAsset:
  id, draftId, kind, blob?, filename?, mime?, size?, createdAt
```

### 4.3 Commit Flow

1) Persist base media:
- Use `POST /api/v1/media/add` (FormData).
- `media_type` required, plus original source when available.

2) Apply edits:
- `PUT /api/v1/media/{media_id}` with updated content/title/keywords.
- `PATCH /api/v1/media/{media_id}/metadata` for custom fields.
  - Backend note: `PUT /api/v1/media/{media_id}` updates FTS and creates a document version,
    sets `chunking_status='pending'`, but does not reset `vector_processing`. To avoid stale
    embeddings, the commit flow must also trigger re-chunking/embedding by either:
    - Updating the backend to reset `vector_processing=0` when content changes, or
    - Adding a dedicated reprocess endpoint (e.g., `POST /api/v1/media/{media_id}/reprocess`).

Source rules:
- Audio/video commits require original asset. If missing, block commit.
- Non-audio/video can fall back to synthetic `.md`/`.txt` upload; store original media type in safe metadata as `original_media_type`.

### 4.4 State Management

- No Zustand in WebUI. Use local React state and hooks.
- Draft operations are centralized in `lib/drafts.ts`.

---

## 5. UI/UX Specifications

### 5.1 Content Review Page Layout

```
+==================================================================+
|  HEADER (Layout)                                                  |
+================+===+==============================================+
|                |   |                                              |
|  BATCH INFO    | T |  EDITOR HEADER                               |
|  [Progress]    | O |  [<] [>] "Video Title" 3/20  [Copy] [...]   |
|                | G |                                              |
|  FILTERS       | G |  TOOLBAR                                     |
|  [Status]      | L |  [B] [I] [H1] [Link] [List] | [Undo] [Redo] |
|  [Type]        | E |                                              |
|                |   |  CONTENT AREA                                |
|  ITEM LIST     |   |  +----------------------------------------+  |
|  +----------+  |   |  |                                        |  |
|  | Item 1   |  |   |  |  # Welcome                            |  |
|  +----------+  |   |  |                                        |  |
|  | Item 2 * |  |   |  |  This is the main content...          |  |
|  +----------+  |   |  |                                        |  |
|  | Item 3   |  |   |  +----------------------------------------+  |
|  +----------+  |   |  2,450 words | 14,320 chars | Saved 2m ago  |
|                |   |                                              |
|                |   |  METADATA (collapsible)                      |
|                |   |  [v] Title, Keywords, Custom fields          |
|                |   |                                              |
|  BULK ACTIONS  |   |  ACTION BAR                                  |
|  [Commit All]  |   |  [Discard] [Save Draft] [Mark Reviewed ->]  |
+================+===+==============================================+
```

### 5.2 Key Interactions

| Interaction | Behavior |
|-------------|----------|
| Click item | Load draft into editor, auto-save previous |
| Edit content | Mark dirty, debounce auto-save (2s) |
| Previous/Next | Navigate between drafts |
| Mark Reviewed | Set reviewed, advance |
| Reattach Source | Open modal to attach file or URL when asset is missing |
| Commit | Send to server, toast result |
| Discard | Confirmation then delete |
| Show Original | Toggle diff view |

### 5.3 Empty/Error States

| State | Display |
|-------|---------|
| No drafts | "No content to review. Use Media Ingest to add content." |
| All committed | "All items reviewed and committed!" |
| Commit error | Error toast; draft remains |
| Offline | Warning banner; commit disabled |
| Missing source asset | Warning with reattach flow; commit disabled until source is provided |
| Reattach failed | Error banner with retry and guidance |
| Storage cap exceeded | Warning with fallback options |

### 5.4 Source Reattach UX (Missing Assets)

Trigger: `asset_status=missing` on a draft or commit attempt without a source asset.

Flow:
1) Editor header shows a persistent warning banner: "Source required to commit this item."
2) Action bar shows `Reattach Source`.
3) Reattach modal with two tabs:
   - Upload file (shows size limit, accepted types, and local storage warning)
   - Provide URL (validates URL and warns about auth/cookies if required)
4) On success: set `asset_status=present`, update draft source, show toast, enable Commit.
5) On failure: keep `asset_status=missing`, show inline error and retry.

Modal error states:
- File too large for local storage: allow commit-time upload only; keep blob unset and show "will upload on commit" label.
- Invalid file type: show allowed types for the draft `mediaType`.
- URL fetch blocked/invalid: show error and keep URL entry editable.
- Offline: disable submit, keep draft editable with auto-save.

---

## 6. Implementation Plan (WebUI)

### Phase 1: Storage Layer (Dexie)

Files:
- Add `apps/tldw-frontend/lib/drafts.ts`
- Add `apps/tldw-frontend/types/content-review.ts`
- Add `dexie` dependency

Deliverables:
- Dexie schema + CRUD operations
- Draft cleanup + storage cap checks
- Unit tests for CRUD

### Phase 2: Ingest Flow Fix + Review Toggle

File:
- Modify `apps/tldw-frontend/pages/media.tsx`

Deliverables:
- Store by default using `/media/add`
- Review toggle creates drafts and redirects
- Toggle persistence in localStorage

### Phase 3: Content Review Page

File:
- Add `apps/tldw-frontend/pages/content-review.tsx`

Deliverables:
- Sidebar list + editor
- Auto-save + diff view
- Commit/discard actions

### Phase 4: Config Settings

File:
- Modify `apps/tldw-frontend/pages/config.tsx`

Deliverables:
- Content Review settings section
- Clear drafts action
- Draft retention controls

---

## 7. Testing Requirements

### 7.1 Unit Tests

- Dexie CRUD (drafts, batches, assets)
- Draft lifecycle transitions
- Section filtering composition
- Storage cap warnings

### 7.2 Integration Tests

- Review toggle enabled -> process-only -> drafts created
- Commit flow uses `/media/add` then `PUT` and `PATCH`
- Commit flow triggers reprocess (vector_processing reset or reprocess endpoint called)
- Audio/video commit requires source asset

### 7.3 Manual Checklist

- Store by default: ingest creates media on server
- Review toggle creates drafts and navigates
- Auto-save persists after reload
- Commit single/all respects reviewed-only rule
- Missing source blocks audio/video commits
- Edited content is re-chunked/embedded (no stale search results)

---

## 8. Security Considerations

- Drafts may contain sensitive data; show warning when enabling review.
- Provide "Clear drafts" in Config.
- Do not log draft content.
- All requests use existing auth via `apiClient`.

---

## 9. Performance Considerations

### 9.1 Large Content Handling

| Content Size | Strategy |
|--------------|----------|
| < 100 KB | Full revision snapshots |
| 100 KB - 500 KB | Max 5 revisions |
| 500 KB - 2 MB | Max 3 revisions |
| > 2 MB | Single revision |

### 9.2 Batch Limits

- Recommended batch size <= 50 items
- Sidebar list uses virtualization

### 9.3 Storage Management

- Drafts expire after 30 days (configurable)
- Cleanup on app startup
- Storage cap warning at 100 MB
- When exceeding cap or browser quota, auto-save pauses and a banner offers:
  clear drafts, drop assets, or reduce revision history.

---

## 10. Future Enhancements (Out of Scope)

| Enhancement | Description | Priority |
|-------------|-------------|----------|
| AI-assisted corrections | Auto-fix transcription errors using LLM | High |
| Template formatting | Apply formatting rules automatically | Medium |
| Section detection | Auto-detect chapters/sections in transcripts | Medium |
| Collaborative review | Multiple users review same batch | Low |
| External editor | Open in external editor (e.g., VS Code) | Low |

---

## 11. Dependencies

### Internal

- Media processing endpoints
- `apiClient` in `apps/tldw-frontend/lib/api.ts`

### External

- Dexie.js (new dependency)

---

## 12. Backend Change Proposal (Media Reprocess API)

### 12.1 Endpoint

`POST /api/v1/media/{media_id}/reprocess`

Purpose: re-chunk and re-embed existing media content after edits without re-uploading the source.

Auth/RBAC:
- `MEDIA_UPDATE` permission
- Rate limit key: `media.reprocess` (or reuse `media.update`)

Request (JSON):
```
{
  "perform_chunking": true,
  "chunk_method": "sentences",
  "chunk_size": 1000,
  "chunk_overlap": 200,
  "chunk_language": "en",
  "chunking_template": "default",
  "generate_embeddings": true,
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-large",
  "force_regenerate_embeddings": true
}
```

Behavior (background job):
1) Validate media exists, active, and owned/visible to user.
2) Fetch current `Media.content`, `title`, `type`.
3) Re-chunk content using provided options or defaults:
   - Delete existing `UnvectorizedMediaChunks` for the media id.
   - Insert new unvectorized chunks.
   - Update chunk-level FTS (existing triggers).
4) Update `Media.chunking_status` to `completed` when chunks are written.
5) If `generate_embeddings=true`, trigger embeddings regeneration:
   - Reset `vector_processing=0` and/or enqueue `/api/v1/media/{media_id}/embeddings` with `force_regenerate`.
6) Return `202 Accepted` with a `job_id` and status payload.

Responses:
- `202 Accepted`: `{ "media_id": 123, "status": "accepted", "job_id": "mrj_..." }`
- `404 Not Found`: media missing or deleted
- `409 Conflict`: media in trash or version conflict during update
- `422 Unprocessable Entity`: invalid chunking/embedding options

Notes:
- This endpoint does not re-transcribe or re-ingest source assets; it operates on stored `Media.content`.
- Uses existing chunking/embedding utilities to stay consistent with ingestion defaults.

---

## 13. File Change Summary (WebUI)

| File | Action | Notes |
|------|--------|-------|
| apps/tldw-frontend/package.json | Modify | Add dexie dependency |
| apps/tldw-frontend/types/content-review.ts | Add | Draft types |
| apps/tldw-frontend/lib/drafts.ts | Add | Dexie CRUD + cleanup |
| apps/tldw-frontend/pages/media.tsx | Modify | Store by default + review toggle |
| apps/tldw-frontend/pages/content-review.tsx | Add | Review UI |
| apps/tldw-frontend/pages/config.tsx | Modify | Content Review settings |
