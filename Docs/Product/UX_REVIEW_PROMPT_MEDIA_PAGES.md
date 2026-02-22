# UX/HCI Review Prompt for the `/media` Pages

> **Usage**: Paste this entire file as a prompt to a UX/HCI reviewer (human or AI) to guide a comprehensive audit of the Media experience. The prompt provides a detailed inventory of what exists today so the reviewer can focus on analysis rather than discovery.

**Scope**: `/media`, `/media-multi`, `/media-trash` pages — media library, content inspection, multi-item review, and trash management
**Date**: 2026-02-17
**Codebase version**: `dev` branch (commit `fb3a34fd0`)

---

## Review Prompt

Review the `/media` pages (`/media`, `/media-multi`, `/media-trash`) as both a potential researcher/power user and an HCI/design expert. This is the media library and content inspection hub for an AI-powered research assistant platform. Users ingest media (videos, audio, PDFs, ebooks, documents, emails, code, web pages), browse and search their library, read full content with section navigation, view AI-generated analyses, compare multiple items side-by-side, manage versions, and interact with media through chat.

The media experience spans **three routes** and **25+ sub-components**:
- `/media` — Single-item Media Inspector (`ViewMediaPage`, ~2200 lines): left sidebar with search/filter/results + right content viewer with section navigation, analysis, version history, editing
- `/media-multi` — Multi-Item Review (`MediaReviewPage`, ~1560 lines): Compare/Focus/Stack view modes for side-by-side content review with virtualized selection list
- `/media-trash` — Trash Management (`MediaTrashPage`, ~727 lines): restore, permanent delete, bulk ops

The backend exposes 40+ media endpoints (27 route files) covering CRUD, FTS5 search, metadata search, versioning (with rollback), file serving, document intelligence (outlines, insights, references, figures, annotations, reading progress), reprocessing, and 8 media-type-specific ingestion pipelines.

Produce a structured report covering the following areas. For each finding, rate severity (Critical / Important / Nice-to-Have) and classify as one of: Missing Functionality, Information Gap, UX/Usability Issue, or Accessibility Concern.

---

### 1. Media Discovery & Browsing (ViewMediaPage sidebar — SearchBar, FilterPanel, FilterChips, ResultsList, Pagination, JumpToNavigator)

What a researcher expects when navigating a personal media library:
- Is the sidebar search bar prominent enough? Does it communicate what it searches (title, content, both)? Is there placeholder text guidance? Does it support advanced query syntax (FTS5 operators) and is that discoverable?
- Is the media/notes kind toggle (switching between media items and notes) clear? Do users understand these are separate collections or does it feel like a confusing filter?
- Media type filtering: Are the type options (video, audio, document, pdf, ebook, email, code) presented clearly? Is multi-select intuitive? Does the filter sample actual types from the library or show all possible types?
- Keyword filtering: Is keyword tag autocomplete discoverable? Can users filter by multiple keywords (AND vs OR)? Is the "must have" vs "must not have" distinction exposed?
- Favorites: Is the favorites-only toggle discoverable? Is the star/favorite action on each result obvious? Is favorite state persisted reliably across sessions?
- Active filter chips (FilterChips): Do they clearly show what's currently filtering results? Is "clear all" available? Can individual filters be removed independently?
- Results list: Does each result show enough metadata at a glance (title, type, date, duration, source, keyword count)? Are truncated titles handled gracefully? Is the selected item visually distinct?
- Pagination: Is 20 items per page appropriate? Is total count shown? Can users change page size? Is pagination keyboard-navigable?
- JumpToNavigator: Is the quick-jump bar (shown for >5 results) intuitive? Does it communicate its purpose?
- Sidebar collapse: Is the collapse/expand toggle discoverable? Does the collapsed state remember across sessions? On small screens, does the sidebar become a drawer?
- Is there any sort control (by date, title, relevance, type)? The API supports `sort_by` — is it exposed in the UI?
- Can users browse by date ranges? The search API supports `date_range` — is this exposed?

### 2. Search Experience

What a researcher expects from full-text search across their library:
- Does search feel fast? Is there debounce on keystroke search or does it require explicit submission?
- Are search results clearly ranked by relevance? Do results show matched snippets with highlighted terms?
- Does the search communicate "no results" states helpfully? Does it suggest alternative queries or relaxed filters?
- Is it clear whether search covers content, titles, or both? The API supports field selection (`fields: ["title", "content"]`) — is this choice surfaced?
- Metadata search: The API supports searching by DOI, PMID, PMCID, arXiv ID, Semantic Scholar ID — is any of this exposed in the UI?
- Can users search within a specific media type (e.g., "search only PDFs")?
- Does search integrate with the active filters, or does searching reset filters?

### 3. Content Viewing & Reading (ContentViewer)

What a researcher expects when reading/reviewing ingested content:
- Is the content area large enough for comfortable reading? Can users control font size, line width, or display density?
- Content format detection: The viewer auto-detects markdown/HTML/plain-text — does it always render correctly? Are there cases where markdown formatting appears as raw syntax?
- Is there a raw/rendered toggle for content that might render differently than expected?
- For long-form content: Is there a scroll position indicator? Can users bookmark or highlight passages? Is there a "back to top" action?
- Media section navigation (MediaSectionNavigator): Is the chapter/section tree panel discoverable? Does it clearly show document structure (headings, timestamps, sections)? Can users search within the tree? Does clicking a section scroll to the right position?
- Resume position: The system persists last-visited section per media item — is this communicated to the user? Is there a "resume reading" indicator?
- Analysis display: Is the AI-generated analysis visually distinguished from the source content? Can users expand/collapse it independently?
- Feature flags (`useMediaNavigationPanel`, `useMediaRichRendering`, `useMediaAnalysisDisplayModeSelector`): Are the different rendering modes intuitive? Can users switch between them without confusion?
- Copy actions: Can users copy content or analysis to clipboard? Is the copy action discoverable?
- For video/audio content: Are timestamps rendered as clickable links? Is duration displayed? Is there any embedded playback capability?
- For PDFs with original files: Is the "View original file" option prominent? Does the file viewer support in-browser rendering?

### 4. Media Detail & Metadata

What information a researcher expects to see about each media item:
- Is the title, type, author, and source URL clearly displayed? For URLs, are they clickable to visit the original source?
- Date information: Is ingestion date shown? Last modified date? Is there a "freshness" indicator for web-sourced content?
- For audio/video: Is duration displayed? Transcription model used? Language?
- Keywords: Are they editable inline? Can users add/remove keywords without opening a separate modal? Is keyword autocomplete available?
- Processing status: Is `chunking_status` (pending, completed) visible? Is `vector_processing` status shown? Would a researcher care about this or is it too technical?
- Content statistics: Word count is available in the response — is it displayed? Character count? Section count?
- File information: For items with original files (`has_original_file`), is the file size, type, and download action clear?
- Safe metadata (DOI, PMID, journal, license, etc.): For academic content, is this rich metadata displayed? Is it editable?
- Is there a direct link/permalink to each media item that can be shared or bookmarked?

### 5. Content Versioning & History (VersionHistoryPanel, DiffViewModal)

What a researcher expects from version-controlled content:
- Is version history discoverable from the content view, or is it buried in a submenu?
- Does the version list show meaningful metadata (version number, creation date, prompt used, who/what triggered it)?
- Diff view: Can users compare any two versions side-by-side? Is the diff rendering clear (additions in green, deletions in red)?
- Rollback: Is the rollback action prominent enough? Does it warn about consequences? Is there an undo for accidental rollback?
- Is it clear that editing content automatically creates a new version?
- Can users view the LLM prompt that generated each version's analysis? Is prompt history useful for researchers?
- Safe metadata versioning: Can users see how metadata changed between versions?

### 6. Analysis & AI Features (AnalysisModal, AnalysisEditModal, analysisPresets)

What a researcher expects from AI-powered content analysis:
- Is the "Generate Analysis" action discoverable? Is it clear what analysis does (summarize, extract key points, etc.)?
- Analysis presets: Are the preset configurations (in `analysisPresets.ts`) presented clearly? Can users understand what each preset will produce?
- Custom prompts: Can users provide their own analysis prompt? Is there guidance on effective prompts?
- Can users edit a generated analysis? Is the edit modal (AnalysisEditModal) user-friendly?
- Can users regenerate analysis with a different prompt or model without losing the previous version?
- Is analysis generation progress visible? Can it be cancelled?
- For items without analysis: Is the empty state helpful? Does it encourage the user to generate one?

### 7. Multi-Item Review (MediaReviewPage — /media-multi route)

What a researcher expects when comparing multiple sources:
- Is the `/media-multi` route discoverable from the main `/media` page? Is there a clear entry point?
- View modes (Compare/Focus/Stack): Are these three modes intuitive? Do the icons/labels clearly communicate the layout difference? Is the auto-switching (1 item -> Focus, 2-4 -> Compare, 5+ -> Stack) helpful or confusing?
- Orientation toggle (horizontal/vertical): Is this useful? Does vertical split work well for side-by-side text comparison?
- Selection UX: Is shift-click range selection discoverable? Is the 30-item limit communicated before users hit it? Is the selection progress bar useful?
- Item cards in viewer: Do they show enough metadata (title, type, date, duration, source, transcript length)? Are expandable content/analysis sections useful for quick scanning?
- Copy actions per card: Can users copy content or analysis from individual cards? Is this discoverable?
- "Unstack" (remove from comparison): Is this action clear? Can users undo it?
- Open items minimap (<=8 as buttons, >8 as dropdown): Is the threshold appropriate? Is the minimap useful for navigation?
- Can users transition from single-item view (`/media`) to multi-item review (`/media-multi`) while preserving their selection?
- First-use help modal: Is the onboarding guide helpful? Does it cover the key interactions? Is the `?` shortcut reference always accessible?
- Can users annotate or tag differences between compared items?
- Is there any "diff" capability between two media items' content?

### 8. Trash Management (MediaTrashPage — /media-trash route)

What a researcher expects for managing deleted content:
- Is the trash page discoverable from the main media page? Is there a trash icon/count badge?
- Does each trashed item show enough context to decide whether to restore or permanently delete (title, type, deletion date, original content preview)?
- Bulk operations: Is select-all intuitive? Is bulk restore/delete clearly communicated? Is the batched execution (groups of 10 with delays) visible as progress?
- "Empty trash" action: Is it sufficiently guarded against accidental use? Does it show how many items will be permanently deleted?
- Is undo available after permanent deletion, or is the warning sufficient?
- Can users search within trash?
- Is there an auto-purge policy (items older than X days)? If so, is it communicated?

### 9. Chat Integration

What a researcher expects when discussing media with an AI:
- "Chat with media" and "Chat about media" (RAG): Are these two distinct actions clear? Does the user understand the difference?
- When initiating chat from the media page, is the transition smooth? Is it clear that the media context has been passed to the chat?
- Can users return to the media page from chat and resume where they left off?
- Is there a way to initiate chat about multiple selected media items (RAG over a selection)?

### 10. Keyboard Shortcuts & Power User Features

What power users expect for efficient media management:
- `j`/`k` navigation between items: Is it discoverable? Does it conflict with other page shortcuts?
- `ArrowLeft`/`ArrowRight` for pagination: Is this intuitive or could it conflict with text navigation?
- `?` for shortcuts overlay (KeyboardShortcutsOverlay): Is the overlay comprehensive? Does it cover all available shortcuts?
- `Ctrl+A` for select-all in multi-review: Does it behave as expected? Does it select all on current page or all results?
- `Escape` double-tap to clear selection (for >5 items): Is the double-tap requirement communicated? Is it frustrating?
- `o` to toggle expand in multi-review: Is this discoverable?
- Are there missing shortcuts that power users would expect (e.g., quick search focus, toggle sidebar, next/prev page)?
- Developer tools section (DeveloperToolsSection in ContentViewer): What is this? Should it be hidden from regular users?

### 11. Responsive & Mobile Experience

How well does the sidebar + content layout adapt to smaller screens:
- Does the sidebar collapse to a drawer on mobile? Is the toggle discoverable?
- Are touch targets large enough (>=44px) for result items, filter controls, pagination, and action buttons?
- Is the content viewer usable on mobile without horizontal scrolling?
- Does the multi-item review page (`/media-multi`) work at all on mobile? Three-column comparisons would be very cramped.
- Is the MediaSectionNavigator (chapter tree) usable on mobile? Is it a floating panel or does it take over the screen?
- Are modals (analysis, edit, version diff) properly sized on mobile? Can they be dismissed by swiping?
- Is the search/filter experience usable with a mobile keyboard?

### 12. Performance & Perceived Speed

How responsive does the interface feel:
- Does the initial page load show skeleton states for the sidebar (results list) and content area?
- Is search debounced appropriately? Does the results list update smoothly?
- For items with large content (10K+ words): Does the ContentViewer render without visible lag? Is there virtualization for extremely long content?
- Multi-item review: Does the virtualized list (`@tanstack/react-virtual`) perform well with 100+ items? Do detail fetches for stacked items cause visible waterfall loading?
- Version history and diff: Does loading the diff between two large versions cause UI freezing?
- Session restore: Does restoring last media ID, selection, and focused item from storage cause visible hydration delay?
- Media type sampling on mount (to populate filter options): Does this cause a flash of empty/incorrect filter state?

### 13. Error Handling & Edge Cases

How gracefully does the interface handle failure:
- What happens when the backend is unreachable? The page checks `useServerOnline()` and `useServerCapabilities()` — is the `FeatureEmptyState` helpful and actionable?
- What happens when a media item's detail fetch fails? Is there a retry mechanism? Is the error message specific?
- What happens when content rendering fails (malformed HTML, huge markdown)? Does the rich HTML sanitizer (DOMPurify-based) handle all edge cases?
- What happens when a user tries to view a media item that was deleted by another client/tab?
- Is there undo for soft-delete? The code supports restore — but is the undo action presented immediately after deletion (e.g., toast with "Undo" button)?
- What happens when keyword editing fails (network error mid-save)?
- Multi-review: What happens when one of 5 selected items fails to load? Does it show an error card with retry, or does it break the entire view?
- Trash: What happens when bulk delete fails partway through (items 1-5 deleted, item 6 fails)?

### 14. Information Gaps & Missing Functionality

What capabilities would researchers expect that appear to be absent:
- **Bulk operations on main list**: No bulk delete, bulk keyword tag, bulk export from the main `/media` view — only trash has bulk ops
- **Export/Import**: No direct media export from the UI (only via chatbooks endpoint); no way to export a set of media items as a research bundle
- **Collection/folder organization**: No way to group media into collections, projects, or folders beyond keyword tagging
- **Source comparison/diff**: No ability to diff the content of two media items against each other
- **Annotation & highlighting**: No inline annotation, bookmarking, or text highlighting within content
- **Reading progress tracking**: The API has `/reading-progress` endpoints — are they used in the UI?
- **Document intelligence**: The API has `/outline`, `/insights`, `/references`, `/figures`, `/annotations` endpoints — are any of these surfaced?
- **Embedded media playback**: No audio/video player for items with original files
- **Thumbnail/preview generation**: No visual preview for PDFs, videos, or images
- **Batch ingestion monitoring**: No ingest job tracking UI (the API has `/ingest-jobs/*` endpoints)
- **Reprocessing UI**: The API supports `POST /{id}/reprocess` for re-chunking and re-embedding — is this exposed?
- **Advanced search UI**: Metadata search (DOI, PMID, arXiv ID, journal), date range filtering, exact phrase matching — all supported by API but potentially not in UI
- **Source quality indicators**: No relevance scores, credibility signals, or completeness indicators
- **Token/cost tracking**: No visibility into processing costs (LLM calls, embedding generation)
- **Integration with citation managers**: No Zotero/Mendeley/BibTeX export
- **Scheduled re-ingestion**: No way to re-fetch URL sources for updated content
- **Collaborative features**: No sharing, commenting, or multi-user access to media items
- **Content statistics dashboard**: No overview of library composition (media types distribution, total word count, storage usage)

### 15. Accessibility

- Can the sidebar (search, filters, results list) be fully navigated via keyboard?
- Are media type filter checkboxes properly labeled with `aria-label`?
- Does the content viewer announce content changes to screen readers when switching items (`aria-live`)?
- Is the MediaSectionNavigator tree accessible (proper `role="tree"`, `aria-expanded`, keyboard navigation)?
- Are action buttons (delete, edit, analyze, copy, chat) consistently labeled with `aria-label` or visible text?
- Is color contrast sufficient for: type badges, keyword chips, selected vs unselected items, active filter chips, pagination controls?
- Can the version history panel and diff view be operated without a mouse?
- In multi-review: Are view mode toggles, orientation switch, and item cards keyboard-accessible?
- Does the keyboard shortcuts overlay itself follow accessibility patterns (focus trap, Escape to close)?
- Are drag-and-drop interactions (if any) paired with accessible alternatives?

---

### Output Format

For each section, produce:

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|

Then provide an executive summary with:
1. Top 5 critical gaps that would block researcher adoption
2. Top 5 quick wins (high impact, low effort)
3. Suggested priority roadmap (what to build first, second, third)

---

### Key Files for Reference

**Frontend — Page Components**
- `apps/packages/ui/src/components/Review/ViewMediaPage.tsx` — Main media inspector, sidebar + content viewer (~2200 lines)
- `apps/packages/ui/src/components/Review/MediaReviewPage.tsx` — Multi-item review, compare/focus/stack (~1560 lines)
- `apps/packages/ui/src/components/Review/MediaTrashPage.tsx` — Trash management (~727 lines)

**Frontend — Media Sub-Components**
- `apps/packages/ui/src/components/Media/ContentViewer.tsx` — Content display, analysis, versions, editing (~1890 lines)
- `apps/packages/ui/src/components/Media/SearchBar.tsx` — Search input (~77 lines)
- `apps/packages/ui/src/components/Media/FilterPanel.tsx` — Type/keyword/favorites filters (~208 lines)
- `apps/packages/ui/src/components/Media/FilterChips.tsx` — Active filter display (~92 lines)
- `apps/packages/ui/src/components/Media/ResultsList.tsx` — Sidebar results list (~274 lines)
- `apps/packages/ui/src/components/Media/Pagination.tsx` — Shared pagination (~265 lines)
- `apps/packages/ui/src/components/Media/JumpToNavigator.tsx` — Quick-jump navigation (~85 lines)
- `apps/packages/ui/src/components/Media/MediaSectionNavigator.tsx` — Chapter/section tree (~289 lines)
- `apps/packages/ui/src/components/Media/AnalysisModal.tsx` — Analysis generation (~572 lines)
- `apps/packages/ui/src/components/Media/AnalysisEditModal.tsx` — Analysis editing (~271 lines)
- `apps/packages/ui/src/components/Media/ContentEditModal.tsx` — Content editing (~219 lines)
- `apps/packages/ui/src/components/Media/VersionHistoryPanel.tsx` — Version history (~489 lines)
- `apps/packages/ui/src/components/Media/DiffViewModal.tsx` — Version diff (~274 lines)
- `apps/packages/ui/src/components/Media/KeyboardShortcutsOverlay.tsx` — Shortcuts reference (~124 lines)
- `apps/packages/ui/src/components/Media/analysisPresets.ts` — Analysis preset configurations (~39 lines)
- `apps/packages/ui/src/components/Media/types.ts` — MediaResultItem type (~9 lines)

**Frontend — Hooks & Utilities**
- `apps/packages/ui/src/hooks/useMediaNavigation.ts` — Section navigation hook (~123 lines)
- `apps/packages/ui/src/utils/media-detail-content.ts` — Content extraction utility (~82 lines)

**Frontend — API Service**
- `apps/packages/ui/src/services/tldw/TldwMedia.ts` — Media API service (~44 lines)

**Backend — Media Endpoints** (27 route files in `tldw_Server_API/app/api/v1/endpoints/media/`)
- `listing.py` — Search and list media items
- `item.py` — CRUD for individual items
- `versions.py` — Version history and rollback
- `file.py` — File serving and downloads
- `navigation.py` — Section/chapter navigation
- `reading_progress.py` — Reading progress tracking
- `document_outline.py`, `document_insights.py`, `document_references.py`, `document_figures.py`, `document_annotations.py` — Document intelligence
- `reprocess.py` — Re-chunking and re-embedding
- `ingest_jobs.py` — Ingestion job tracking
- `process_videos.py`, `process_audios.py`, `process_pdfs.py`, `process_documents.py`, `process_ebooks.py`, `process_emails.py`, `process_code.py`, `process_web_scraping.py` — Type-specific ingestion

**Backend — Schemas**
- `tldw_Server_API/app/api/v1/schemas/media_request_models.py` — Request schemas (~845 lines)
- `tldw_Server_API/app/api/v1/schemas/media_response_models.py` — Response schemas (~348 lines)

**Backend — Database**
- `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py` — Database schema v22 (~19,000 lines)
