# UX/HCI Expert Review: Quick Ingest Modal

## What You're Reviewing

The **Quick Ingest Modal** is a globally accessible dialog for importing media into a research assistant and knowledge management application. It supports file uploads (drag-and-drop), URL-based ingestion (video, audio, web pages, documents), configurable processing presets, and per-item keyword tagging. It is the primary entry point for getting content into the system.

### Current Layout (Desktop 1024px+)
```
┌─────────────────────────────────────────────────────────────┐
│  Modal Header: "Quick Ingest"              [?] [×]          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  Queue    │  │ Options  │  │ Results  │   ← Tab bar      │
│  └──────────┘  └──────────┘  └──────────┘                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─── QUEUE TAB ──────────────────────────────────────────┐ │
│  │                                                        │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │         FileDropZone (drag & drop area)          │  │ │
│  │  │   "Drag files here or click to browse"           │  │ │
│  │  │   PDF, DOCX, EPUB, TXT, MD, audio/*, video/*    │  │ │
│  │  │   Max 500 MB per file                            │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │                                                        │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │ QueuedFileRow: [icon] filename.pdf  [12 MB]      │  │ │
│  │  │   [type tag] [status badge]    [🔍] [✕]          │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │ QueuedItemRow (URL entry):                       │  │ │
│  │  │   [URL input___________] [Type ▼] [Keywords___]  │  │ │
│  │  │                              [🔍 inspect] [✕]    │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │ (empty row for next entry)                       │  │ │
│  │  │   [URL input___________] [Type ▼] [Keywords___]  │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
├─── OPTIONS TAB ─────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Preset: [⚡ Quick] [★ Standard] [🔬 Deep] [⚙ Custom]   ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ Common:  [✓] Analysis  [✓] Chunking  [ ] Overwrite     ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ Audio:   Language [en____]  [ ] Diarization             ││
│  │ Docs:    [✓] OCR                                       ││
│  │ Video:   [✓] Captions                                  ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ Storage: [ ] Store to Remote DB  [ ] Review First       ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ ▶ Advanced Options (collapsed)                          ││
│  │   Model selectors, chunking strategy, embedding model,  ││
│  │   language, scraping method, custom fields...           ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ [Progress: 0/5 items · 0% · 0:00 elapsed]              ││
│  │                                                         ││
│  │              [ ▶ Ingest ]  (primary action)             ││
│  └─────────────────────────────────────────────────────────┘│
│                                                             │
├─── RESULTS TAB ─────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Progress: ████████░░ 80%  4/5 done · 2:34 elapsed      ││
│  │ Filter: [All ▼]  "4 succeeded, 1 failed"               ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ [✓ ok] video.mp4 — ingested  [View] [Chat] [JSON]      ││
│  │ [✓ ok] article.pdf — ingested  [View] [Chat] [JSON]    ││
│  │ [✗ err] bad-link.html — "Connection refused"            ││
│  │ ...                                                     ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ [Retry Failed] [Export Failed] [Open Media Viewer]      ││
│  │ [Open Content Review] [Health Diagnostics]              ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Responsive Behavior
- The modal is a fixed-size dialog overlay; no dedicated tablet/mobile layout breakpoints are defined.
- On small screens the modal fills most of the viewport; internal content scrolls.

### Inspector Drawer
A slide-out side drawer (`QuickIngestInspectorDrawer`) appears when the user clicks the inspect icon on a queued item. It shows:
- Detected media type and status
- Warnings (e.g., unsupported format)
- Reattach button for file entries that lost their File reference (e.g., after page reload)
- First-time introduction with usage tips (dismissible, persisted)

---

## Feature Inventory (Currently Implemented)

### Input Methods
- **File upload**: Drag-and-drop zone with MIME and extension validation; 500 MB per-file limit
- **URL entry**: Free-text URL input with auto-type detection (Auto, HTML, PDF, Document, Audio, Video)
- **Type override**: Per-item dropdown to force media type when auto-detection is wrong
- **Always-present empty row**: A blank URL row is always available at the bottom of the queue for quick addition

### Queue Management
- Add files via drag-and-drop or file picker
- Add URLs by typing into rows
- Remove individual items (file or URL)
- Retry failed items (re-add to queue from Results tab)
- Requeue failed items for manual inspection
- Queue state persisted to localStorage across sessions

### Processing Presets
- **Quick** (lightning): No analysis, no chunking, no overwrite — fastest path
- **Standard** (star, recommended): Analysis + chunking + OCR + captions enabled
- **Deep** (microscope): Everything on, including overwrite and diarization; review-before-storage enabled
- **Custom**: Auto-detected when settings diverge from any named preset
- Presets are persisted per-user in browser storage and configurable via a Settings page

### Processing Options
- **Common toggles**: Perform analysis, perform chunking, overwrite existing
- **Type-specific defaults**: Audio language + diarization, document OCR, video captions
- **Storage toggles**: Store to remote DB, review before storage (routes to Content Review page)
- **Advanced options** (collapsible): Dynamically rendered from server schema — model selectors (LLM, embedding), chunking strategy/template, language, scraping method, and arbitrary custom fields

### Results & Post-Processing
- Progress bar with percentage, item counter, and elapsed time
- Per-item status: ok/error with outcome tags (ingested, processed, skipped, failed)
- Filter results by status (All, Success, Error)
- Per-result actions: Open in Media Viewer, Discuss in Chat, Download JSON
- Batch actions: Retry Failed URLs, Requeue Failed, Export Failed List
- Health Diagnostics link for server status check
- Open Content Review (when review-before-storage was enabled)

### Keyword/Tag Handling
- **Per-URL-row keywords field**: Comma-separated input with auto-normalization
  - Strips special characters, collapses whitespace, deduplicates (case-insensitive)
- **File entries**: Keywords set at upload time via type defaults (no per-file keyword field visible)
- **Batch-level keywords**: Can be set via advanced options; applied to all items in the batch
- Keywords passed as comma-separated string in API `keywords` field

### State Persistence
- Queue (rows + files), presets, common options, storage toggles, advanced values, and UI preferences all persisted to localStorage
- Global Zustand store tracks: queued count, last-run summary, recent failure flag
- Auto-tab switching: opens to Queue tab; switches to Results when processing starts; resets to Queue on re-open

### Global Integration
- Opened via `QuickIngestButton` in the app layout (always accessible)
- Custom DOM events: `tldw:open-quick-ingest`, `tldw:open-quick-ingest-intro`, `tldw:quick-ingest-ready`, `tldw:quick-ingest-force-intro`
- Connection status check before processing (blocks if server offline/unconfigured)

---

## Review Dimensions

Please evaluate the modal across these dimensions, providing specific findings for each:

### 1. Information Architecture & Progressive Disclosure
- Is the 3-tab structure (Queue → Options → Results) the right mental model, or does it fragment a naturally linear flow?
- Can a first-time user understand the relationship between queueing items, configuring options, and viewing results without guidance?
- Are the preset buttons (Quick/Standard/Deep) discoverable and do they communicate what changes?
- Is the "Advanced Options" section appropriately hidden, or do important settings get buried?
- How does the modal communicate the difference between "process only" (ephemeral) and "ingest" (persist to DB)?
- Is the Inspector Drawer discoverable? Does the inspect icon communicate its purpose?

### 2. Mid-Ingestion Cancellation & Progress Feedback
This is a **key improvement area**. Evaluate the current state and propose improvements:
- **Current behavior**: Once processing starts, the `running` flag disables the UI; items are submitted sequentially via the batch service. There is no per-item cancel, no batch abort, and no pause/resume.
- **Backend capability**: The async job API (`POST /api/v1/media/ingest/jobs`) supports per-job cancellation (`DELETE /api/v1/media/ingest/jobs/{job_id}`) and per-job progress polling. The sync API (`POST /api/v1/media/add`) does not support mid-request cancellation.
- **Questions to address**:
  - How should the UI surface a "Cancel All" / "Cancel This Item" affordance during processing?
  - Should the frontend switch from synchronous `/media/add` to async `/media/ingest/jobs` to enable cancellation?
  - What should happen to already-completed items when the user cancels remaining items?
  - How should progress be communicated: per-item status updates, overall progress bar, estimated time remaining?
  - What visual state should a cancelled item show in the Results tab?
  - How should the system handle partial completion (3 of 5 ingested, 2 cancelled)?

### 3. Per-Item Metadata Editing
This is a **key improvement area**. Evaluate and propose a design for per-item metadata editing:
- **Current state**: URL entries have a keywords field per row. File entries have no visible per-item metadata editing — keywords come from batch defaults. Neither URL nor file entries have editable title or author fields.
- **Backend support**: The `/media/add` endpoint accepts `title`, `author`, and `keywords` fields, but they apply batch-wide. There is no per-item override in a single batch call — each item would need its own API call for unique metadata.
- **Questions to address**:
  - How should per-item metadata editing (title, author, keywords) be exposed without making every queue row overwhelming?
  - Should the Inspector Drawer become the editing surface for per-item metadata?
  - How should the UI handle the tension between "quick" (batch defaults) and "precise" (per-item overrides)?
  - What is the right default: inherit batch keywords, or start empty per item?
  - Should file entries show the detected filename as an editable title field?
  - How should metadata inheritance work: item-level overrides batch-level, or item-level appends to batch-level?
  - What happens if a user sets per-item metadata and then changes the preset? (Override preserved? Reset?)

### 4. Per-Batch Keyword Tagging
This is a **key improvement area**. Evaluate the current keyword workflow and propose improvements:
- **Current state**: Keywords are per-URL-row (comma input) or set in advanced options (batch-wide). There is no prominent batch-level keyword input in the Options tab — it's buried in advanced settings.
- **Questions to address**:
  - Should there be a visible "Batch Keywords" field in the Options tab (outside advanced)?
  - How should batch keywords interact with per-item keywords? (Append? Override? Merge with dedup?)
  - Should the system suggest keywords based on detected content type, URL domain, or file names?
  - Is the current keyword normalization (strip special chars, dedup, case-insensitive) sufficient?
  - Should keywords support autocomplete from the user's existing keyword vocabulary?
  - How should the keyword UI scale from "I just want to tag everything 'research'" to "I need precise per-item taxonomy"?

### 5. User Flows & Task Completion
Evaluate these critical flows for friction, dead ends, and missing affordances:
- **Quick single-file ingest**: Drop a PDF → accept defaults → ingest → view result
- **Batch URL ingest**: Paste 10 YouTube URLs → set batch keywords → select Standard preset → ingest → monitor progress → handle 2 failures
- **Mixed media batch**: 3 files + 5 URLs of mixed types → set per-type options (audio language, document OCR) → ingest → review results
- **Precise ingest**: Add 3 items → set unique title/author/keywords per item → choose Deep preset → enable review-before-storage → ingest → review in Content Review
- **Re-ingest after failure**: Previous run had 3 failures → retry failed → 1 still fails → export failed list → manually fix URL → re-add
- **Mid-process cancel**: Start 10-item batch → 4 complete → cancel remaining → view partial results → retry cancelled items later

### 6. Information Density & Error Communication
- What information does the user need during processing that isn't shown? Consider:
  - Per-item progress (transcription %, download %, chunking step)
  - Estimated time remaining (per item and total)
  - Server queue depth (how many items ahead of mine?)
  - File size / duration for queued items (to set processing time expectations)
  - Disk space / quota information
  - Which processing step is active per item (downloading → transcribing → chunking → embedding)
- Are error messages from the backend propagated clearly?
- How does the modal communicate server offline vs. misconfigured vs. rate-limited states?
- Is the connection status indicator visible enough before the user hits "Ingest"?

### 7. Responsive Design & Modal Ergonomics
- Is a modal the right container for this workflow, or would a dedicated page/panel serve better for large batches?
- How does the modal behave when the queue has 20+ items? 50+? Scrolling? Virtualization?
- Can the user resize or expand the modal for complex batches?
- Is the tab bar always visible, or can it scroll out of view?
- How does the drop zone interact with the modal overlay (drag from desktop into modal)?
- Is the primary action button ("Ingest") always visible, or does the user need to scroll?

### 8. Accessibility & Keyboard Navigation
- Can every queue operation (add URL, add file, remove item, change type, edit keywords) be completed via keyboard?
- Is the drag-and-drop zone accessible? Is there a fallback file picker triggered by keyboard?
- Are tab switches keyboard-navigable (arrow keys within tab bar)?
- Does the Inspector Drawer trap focus appropriately?
- Are progress updates announced to screen readers (live regions)?
- Are status badges (ok/error) conveyed through more than just color?
- Is the preset selection keyboard-accessible?

---

## Backend Capabilities Available (Not All Surfaced in UI)

These backend features exist but may not be fully exposed in the Quick Ingest modal. Assess which would most benefit users if surfaced:

| Capability | Backend Support | UI Status |
|---|---|---|
| Async job submission with per-job progress | Full (`POST /ingest/jobs`) | Not used — modal uses sync `/add` |
| Per-job cancellation | Full (`DELETE /ingest/jobs/{id}`) | Not exposed |
| Per-job progress polling (percent + message) | Full (`GET /ingest/jobs/{id}`) | Not exposed |
| Batch polling by batch_id | Full (`GET /ingest/jobs?batch_id=X`) | Not exposed |
| Priority queue routing (heavy vs lightweight) | Full (auto by media type) | Not exposed |
| Per-item title field | Full (`title` in AddMediaForm) | Not exposed in queue UI |
| Per-item author field | Full (`author` in AddMediaForm) | Not exposed in queue UI |
| Claims extraction | Full (`perform_claims_extraction`) | Not in presets or Options UI |
| Contextual chunking (LLM-augmented) | Full (`enable_contextual_chunking`) | Hidden in advanced options |
| Embedding generation on ingest | Full (`generate_embeddings`) | Hidden in advanced options |
| Hierarchical chunking | Full (`hierarchical_chunking`) | Hidden in advanced options |
| Rolling summarization | Full (`perform_rolling_summarization`) | Not exposed |
| Start/end time trimming (audio/video) | Full (`start_time`, `end_time`) | Not exposed |
| Hotwords for transcription | Full (`hotwords`) | Not exposed |
| Voice Activity Detection filter | Full (`vad_use`) | Not exposed |
| Confabulation check of analysis | Full (`perform_confabulation_check_of_analysis`) | Not exposed |
| Email ingestion (attachments, mbox, PST) | Full | Not exposed in Quick Ingest |
| Custom cookies for URL downloads | Full (`use_cookies`, `cookies`) | Not exposed |
| Bring-Your-Own-Key for analysis LLM | Full (`api_provider`, `model_name`) | Partial (model selector in advanced) |
| Chunking templates | Full (`chunking_template_name`, `auto_apply_template`) | Exposed (template selector) |
| Content Review batch routing | Full | Exposed (review-before-storage toggle) |

---

## Comparable Products

When benchmarking, consider how these tools handle media ingestion modals and batch upload workflows:

| Product | Key Features to Benchmark |
|---|---|
| **NotebookLM** (Google) | Source upload panel: drag files or paste URLs, per-source status, simple "Add" flow with zero configuration, source-level metadata display after processing |
| **Zotero** | Add item by URL/DOI/ISBN, auto-metadata extraction (title, author, date, tags), per-item tag editing inline, batch tagging via right-click, drag-and-drop PDF with auto-rename |
| **Raindrop.io** | Multi-URL paste, auto-title/thumbnail extraction, per-item and batch tag editor, tag autocomplete from vocabulary, collection assignment during import |
| **Pocket / Omnivore** | One-click save from URL, automatic content extraction, batch tag application, simple queue with status indicators, minimal configuration |
| **Notion Web Clipper** | URL capture with destination picker, tag/property assignment at clip time, per-item title editing before save |
| **DEVONthink** | Batch import with per-item metadata panel, smart group assignment, auto-tagging by content analysis, progress display with cancel per item |
| **Eagle** | Batch image/file import, drag-and-drop with preview grid, per-item and batch tag editing, folder assignment, import progress with thumbnails |
| **YouTube Studio Upload** | Multi-file upload with per-item title/description/tags editing, upload progress per file, cancel individual uploads, draft/publish workflow |
| **Calibre** | Batch ebook import, per-book metadata editing (title, author, tags, series), auto-metadata download, bulk metadata apply, progress bar with cancel |
| **Tana / Mem.ai** | Paste-and-capture with auto-structuring, minimal-config ingestion, automatic tagging suggestions, incremental processing feedback |

---

## Output Format

For each finding, provide:

| Field | Description |
|-------|-------------|
| **ID** | Sequential (e.g., QI-001) |
| **Dimension** | Which review dimension (1-8) |
| **Severity** | Critical / Major / Minor / Enhancement |
| **Finding** | Clear description of the issue or gap |
| **Impact** | Who is affected and how (first-time users, power users, batch importers, researchers organizing a corpus, etc.) |
| **Recommendation** | Specific, actionable suggestion with enough detail to implement |
| **Comparable** | How other tools handle this (if applicable) |

### Severity Definitions
- **Critical**: Blocks core task completion or causes data loss (e.g., queued items lost on modal close, cannot cancel runaway ingestion, silent failures with no error display)
- **Major**: Significant friction in common workflows; users may abandon the feature (e.g., cannot tag individual items, no way to cancel a 30-minute video transcription, progress feedback too vague)
- **Minor**: Noticeable but workaroundable; affects polish and trust (e.g., file size not shown on queue row, preset descriptions unclear, keyword dedup not visible)
- **Enhancement**: Not a problem today but would meaningfully improve the experience (e.g., keyword autocomplete, estimated processing time, drag-to-reorder queue)

---

## Summary Deliverables

1. **Executive Summary**: 3-5 sentence overview of the Quick Ingest modal's UX maturity, strengths, and most urgent gaps
2. **Top 5 Priority Fixes**: Highest-impact improvements ranked by effort-to-impact ratio
3. **Cancellation Design Proposal**: Detailed mockup/wireframe of mid-ingestion cancellation UX, including:
   - Which API path to use (sync vs async)
   - Cancel button placement and states
   - Per-item vs batch-level cancel affordances
   - Partial completion handling and result display
4. **Per-Item Metadata Editing Design**: Proposed interaction pattern for editing title/author/keywords per queued item, including:
   - Inline vs drawer-based editing
   - Inheritance model (batch defaults → per-item overrides)
   - Visual treatment of items with custom metadata vs defaults
5. **Batch Keyword Workflow**: Recommended design for batch-level keyword tagging, including:
   - Field placement in the Options tab
   - Interaction with per-item keywords (append vs override)
   - Autocomplete / suggestion behavior
6. **Competitive Gap Analysis**: Features present in 3+ comparable tools but missing here, ranked by user expectation
7. **Information Gaps Table**: Backend data available but not surfaced in UI, with priority rating (High / Medium / Low) and rationale
8. **Detailed Findings Table**: All findings in the structured format above
