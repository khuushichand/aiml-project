# UX/HCI Expert Review: Media Multi (Library View)

## What You're Reviewing

The **Media Multi** page (`/media-multi`) is the multi-item media review and comparison interface in a media analysis and knowledge management application. It lets users search, filter, select, and inspect multiple ingested media items (videos, PDFs, audio transcripts, ebooks, web pages, etc.) side-by-side, in a focused single-item view, or in a scrollable stack. It supports content diffing, media-scoped RAG chat handoff, keyboard navigation, and session persistence.

### Current Layout (Desktop 1024px+)
```
┌──────────────────────────────────────────────────────────────────────────┐
│ Header Row                                                              │
│ [Search input            ] [Search] [Clear] [▼ Filters (badge)] [▓▓░ 3/30 selected] │
│                                                                          │
│ (if >5 selected) Tip: press Escape twice quickly to clear large selections │
├──────────────────────────────────────────────────────────────────────────┤
│ Collapsible Filter Section (id="filter-section")                         │
│ [Media types ▼ multi-select] [Keywords ▼ tags/search] [☐ Content] [Clear filters] │
├────────────────────┬──┬──────────────────────────────────────────────────┤
│ Results Sidebar    │  │ Viewer Panel                                     │
│ (w-1/3)            │<<│ (flex-1)                                         │
│                    │  │                                                  │
│ Results (42)       │  │ ┌─ Sticky Toolbar ──────────────────────────────┐│
│ Click to stack,    │  │ │ Row 1: [Viewer] [Compare|Focus|Stack]         ││
│ Shift+click range  │  │ │   [Vertical|Horizontal] [⚙ Options ▼]        ││
│                    │  │ │                                                ││
│ ┌────────────────┐ │  │ │ Row 2: [← Prev] Item 3 of 42 [Next →]       ││
│ │ ☐ Title        │ │  │ │   [Expand/Collapse ▼] [Compare content]      ││
│ │   video · date │ │  │ │   [💬 Chat about selection (3)] [?]          ││
│ │   snippet...   │ │  │ │                                                ││
│ ├────────────────┤ │  │ │ Row 3 (minimap): [Open items]                 ││
│ │ ☑ Title        │ │  │ │   [1. Doc A (pdf)] [2. Video B] [3. ...]     ││
│ │   pdf · date   │ │  │ └──────────────────────────────────────────────┘│
│ │   snippet...   │ │  │                                                  │
│ ├────────────────┤ │  │ ┌── Media Card ─────────────────────────────────┐│
│ │ ...virtual     │ │  │ │ Title              [Unstack] [Copy] [Copy An.]││
│ │   scrolled     │ │  │ │ #1 · pdf · 2025-01-15 · 45k chars            ││
│ │   list         │ │  │ │                                                ││
│ └────────────────┘ │  │ │ ┌─ Media Content ──────── [▼ Expand] ─┐      ││
│                    │  │ │ │ (collapsible, scrollable text area)  │      ││
│ [pagination ◄ ►]   │  │ │ └─────────────────────────────────────┘      ││
│                    │  │ │                                                ││
│                    │  │ │ ┌─ Analysis ───────────── [▼ Expand] ─┐      ││
│                    │  │ │ │ (collapsible summary/analysis text)  │      ││
│                    │  │ │ └─────────────────────────────────────┘      ││
│                    │  │ └────────────────────────────────────────────────┘│
│                    │  │                                                  │
│                    │  │ (more cards if Compare or Stack mode)             │
└────────────────────┴──┴──────────────────────────────────────────────────┘
```

- **Header**: Search input with enter-to-search, filter toggle with active filter badge, selection progress bar (green → yellow → red as limit approaches)
- **Filter Section** (collapsible, persisted): Media type multi-select (populated from results), keyword tag selector with server-side search, content-search toggle
- **Results Sidebar** (left, `w-1/3`): Paginated virtual-scrolled list with checkboxes, type tags, date, snippets; shift-click range selection
- **Sidebar Toggle**: Thin `<<`/`>>` bar between sidebar and viewer; full-width text bar on mobile
- **Viewer Panel** (right, `flex-1`): Sticky 3-row toolbar + media cards in selected view mode
- **Minimap** (Row 3): Horizontal button bar for ≤8 items; dropdown menu for >8 items

### Responsive Behavior
- **Mobile** (<1024px): Single-column layout; sidebar hidden by default with full-width toggle bar; view mode forced to Focus (single item); view mode selector hidden (badge shown instead)
- **Desktop** (≥1024px): Two-column `lg:flex-row` layout; sidebar toggleable via `<<`/`>>` bar; all three view modes available

---

## Feature Inventory (Currently Implemented)

### View Modes
- **Compare** (spread): Multiple selected cards displayed side-by-side (or stacked vertically depending on orientation setting); each card has an "Unstack" button to remove from view
- **Focus** (list): Single item displayed at a time with Prev/Next navigation and a dropdown item picker; auto-selected when only 1 item is selected
- **Stack** (all): All selected items in a scrollable vertical or horizontal list; no virtual scrolling (all rendered); position badges (`#1`, `#2`, etc.)
- **Auto-mode**: Automatically switches view mode based on selection count (1 → Focus, 2–4 → Compare, 5+ → Stack); shows toast notification on switch; can be disabled in Options

### Selection Mechanics
- **Click** to toggle individual items in the sidebar list
- **Shift+click** for contiguous range selection (adds all items between last click and current click)
- **Ctrl/Cmd+A** to select all visible items (up to limit)
- **30-item selection limit** with visual progress bar (green/yellow/red color coding) and remaining count
- **Selection warning** at 25+ items
- **Clear selection** with undo toast (15-second undo window for accidental clears)
- **Escape** to clear selection: single press for ≤5 items, double-tap required for >5 items (with hint toast)

### Content Inspection
- **Content section** per card: Collapsible, with configurable default height (~16em), scrollable when collapsed
- **Analysis section** per card: Collapsible, shows summary/analysis text
- **Expand/Collapse All**: Dropdown with separate controls for content and analysis sections
- **Collapse others on expand**: Optional setting that auto-collapses other cards when one is expanded
- **Copy Content** and **Copy Analysis**: Per-card clipboard copy with visual checkmark confirmation (2-second feedback)
- **Content loading**: Skeleton placeholders while fetching, error alerts with retry button

### Content Comparison
- **DiffViewModal**: Available when exactly 2 items are selected; line-by-line LCS diff algorithm
- **Unified view**: Traditional `+`/`-` prefixed diff with color coding (green for added, red for removed)
- **Side-by-side view**: Two-column layout with line numbers and aligned additions/deletions
- **Metadata diff**: Optional metadata difference display above the content diff
- **Keyboard navigation** in diff: Arrow keys, j/k, Page Up/Down, Home/End for scrolling

### Media-Scoped RAG Chat Handoff
- **"Chat about selection"** button: Navigates to the chat page with selected media IDs pre-loaded as RAG context
- Sets chat mode to `rag`, configures media IDs, dispatches custom events for composer focus
- Works with any number of selected items (filters to valid numeric IDs)

### Search & Filtering
- **Text search**: Searches title and content fields; results sorted by relevance when query is active
- **Media type filter**: Multi-select populated from available types in results (video, pdf, audio, etc.)
- **Keyword filter**: Tag-style selector with server-side keyword search and suggestions (up to 200 preloaded)
- **Content search toggle**: When enabled, fetches full content for each result and filters by keyword/query match within content body
- **Filter badge**: Shows count of active filters when filter section is collapsed, plus preview of active filter values
- **Clear filters** button: Resets all filters at once

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `j` / `↓` | Navigate to next item in results list |
| `k` / `↑` | Navigate to previous item in results list |
| `/` | Focus search input (with text selection) |
| `o` | Toggle content expand/collapse on focused card |
| `Ctrl`+`A` | Select all visible items (up to 30) |
| `Esc` | Clear selection (double-tap required for >5 items) |
| `Shift`+Click | Range selection in sidebar |

### Session State Persistence
- **Selection**: Selected item IDs persisted via settings registry; restored on mount
- **Focused item**: Focused item ID persisted and restored
- **View mode**: Persisted view mode setting (Compare/Focus/Stack)
- **Orientation**: Vertical/horizontal card layout persisted
- **Filter collapse state**: Whether the filter section is collapsed
- **Auto view mode**: Whether auto-mode is enabled
- **Clear session**: Options menu includes "Clear review session" to reset all persisted state

### Additional Features
- **Onboarding guide**: Dismissible 3-step guide shown on first use (select items → choose view → navigate)
- **Virtual scrolling**: Both sidebar list and viewer panel (Compare/Focus modes) use `@tanstack/react-virtual` for performance
- **Reduced motion**: Respects `prefers-reduced-motion` for scroll animations
- **ARIA live region**: Screen reader announcements for selection count changes
- **Error handling**: 404/410 items auto-removed from selection; other failures tracked with retry affordance
- **Initial media ID**: Can open with a specific media item pre-selected (via `LAST_MEDIA_ID_SETTING`)
- **Help modal**: Accessible keyboard shortcuts reference (useful on touch devices)
- **Demo mode / Offline states**: Route wrapper shows appropriate empty states when server is offline or media endpoints aren't available

---

## Review Dimensions

Please evaluate the page across these dimensions, providing specific findings for each:

### 1. Information Architecture & Navigation
- Is the two-panel layout (sidebar + viewer) immediately understandable to a first-time user?
- Does the 3-row sticky toolbar create cognitive overload, or does it provide useful orientation?
- Is the relationship between the sidebar (search/filter/select), the minimap (jump-to-item), and the viewer (inspect) clear?
- How does the user understand the difference between Compare, Focus, and Stack modes without trying all three?
- Are the Options dropdown items (auto-view, collapse others, review all, clear session) discoverable?
- Is the filter section's collapsed state clear — does a user know filters exist when the section is collapsed?
- How does the pagination in the sidebar interact with the "select all" action? (Does Ctrl+A select only the current page?)

### 2. Selection & Multi-View UX
- Is the 30-item selection limit communicated early enough to prevent frustration?
- Does the selection progress bar (green → yellow → red) provide useful feedback or visual noise?
- Is the double-tap Escape requirement for large selections intuitive, or does it break the expected "Escape cancels" pattern?
- Does the undo toast (15 seconds) provide enough time for recovery? Is it discoverable?
- How does selection state interact with pagination? (If I select items on page 1, then go to page 2 and select more, is this clear?)
- Is the "Unstack" button on cards in Compare mode clear enough vs. the sidebar checkbox toggle?
- When auto-view mode switches (e.g., from Compare to Stack), does the toast notification provide enough context, or is the mode change disorienting?

### 3. Search, Filter & Sort
- Is the content search toggle (`☐ Content`) clear about what it does? (It fetches full content for filtering — potentially slow.)
- Are keyword suggestions useful when there are hundreds of keywords? How is the user guided to find the right ones?
- Is there any sort control? (Currently: relevance when searching, default order when browsing.) Would sort options improve the experience?
- Does the filter badge on the collapsed filter section adequately communicate which filters are active?
- How does the search interact with pagination and selection? (Searching resets to page 1; does it clear selection?)
- What feedback does the user get during content search (which fetches details for all results)?

### 4. Content Inspection & Comparison
- Is the content/analysis expand/collapse per card intuitive? Does the user understand there are two separate collapsible sections?
- Does the content area's fixed default height (16em) work well for short items (a tweet) vs. long items (a 50-page transcript)?
- Is the DiffViewModal discoverable? (Only appears as a button when exactly 2 items are selected — is this constraint obvious?)
- Does the diff view handle very long documents well? (Line-by-line LCS on a 50k-character transcript)
- Are the "Copy Content" and "Copy Analysis" buttons well-positioned? Would a single copy dropdown be cleaner?
- Is the analysis section useful when it's empty ("No analysis available") for most items?

### 5. Batch Operations & Metadata Management
- Beyond selection + chat handoff + diffing, what batch operations would users expect?
- Can users tag, categorize, or annotate items from this view? (Currently: no — see backend capabilities below)
- Is there a way to delete or archive items from this view? (Currently: no)
- Can users export selected items (e.g., as a report, CSV, or chatbook)?
- Can users reprocess items (re-transcribe, re-summarize) from this view?

### 6. User Flows & Task Completion
Evaluate these critical flows for friction, dead ends, and missing affordances:
- **Literature review triage**: Search → filter by type (pdf) → select 10 papers → read summaries in Stack mode → compare 2 key papers in Diff view → chat about findings
- **Transcript comparison**: Select 2 meeting recordings → Compare mode → diff content → identify differences
- **Bulk keyword discovery**: Browse all items → filter by keyword → see what's tagged vs. untagged → add missing keywords (not currently possible)
- **Media audit**: Browse all items → sort by date → identify old/stale items → delete or archive (not currently possible from this view)
- **Cross-reference check**: Search for a topic → select relevant items across types (video + pdf + web) → Stack view → read through → chat about the collection
- **Error recovery**: Item fails to load → retry → still fails → what does the user do? Can they remove just that item from selection?

### 7. Responsive Design & Performance
- Does the forced Focus mode on mobile feel like a reasonable adaptation or a loss of capability?
- Is the sidebar toggle bar intuitive on mobile (full-width text bar vs. thin `<<`/`>>` on desktop)?
- How does the virtual scrolling perform with 30 selected items, each with expanded content?
- Are touch targets adequate for the sidebar checkboxes, minimap buttons, and toolbar controls?
- Does the content search toggle (which fetches all item details) scale to pages with 50+ results?
- What happens to the minimap when 30 items are selected? (Switches to dropdown — is this transition smooth?)

### 8. Accessibility & Keyboard Navigation
- Keyboard navigation completeness: can every feature be reached without a mouse? (View mode selector, Options dropdown, filter controls, minimap, expand/collapse)
- Screen reader experience: ARIA labels on sidebar items (`role="button"`, `aria-selected`), live region for selection count — are these sufficient?
- Focus management: where does focus go after selecting an item? (Currently: viewer panel with delay.) After clearing selection? After closing the diff modal?
- Can the diff modal be navigated entirely by keyboard? (Yes — j/k, arrows, PgUp/PgDn, Home/End)
- Are the toolbar's nested dropdowns (Options, Expand/Collapse) keyboard-accessible?
- Color contrast: does the selection progress bar rely solely on color to communicate state?
- Touch target sizes: the sidebar checkbox area is explicitly sized at 44×44px — are other interactive elements similarly sized?

---

## Backend Capabilities Available (Not Surfaced in Media Multi UI)

These backend endpoints exist under `/api/v1/media/` but are **not currently accessible** from the Media Multi page. Assess which would most benefit users if surfaced:

| Capability | Backend Endpoint | UI Status |
|---|---|---|
| Metadata search with field operators | `POST /search` (field boosting, sort options) | Partial (basic search only) |
| Date range filtering | `GET /` (query params) | Not exposed |
| Sort options (date, title, relevance, type) | `GET /` and `POST /search` | Not exposed |
| Per-item keyword CRUD (add/remove/set modes) | `PUT /{id}/keywords` | Not exposed |
| Bulk keyword update | `POST /bulk/keyword-update` | Not exposed |
| Patch media item metadata (title, etc.) | `PATCH /{id}` | Not exposed |
| Version history and rollback | `GET /{id}/versions`, `PUT /{id}/versions/{v}/rollback` | Not exposed |
| Create content version | `POST /{id}/versions` | Not exposed |
| AI-generated document insights | `POST /{id}/insights` | Not exposed |
| Document navigation tree | `GET /{id}/navigation` | Not exposed |
| Document outline / table of contents | `GET /{id}/outline` | Not exposed |
| Reference extraction with enrichment | `GET /{id}/references` | Not exposed |
| Figure/table extraction | `GET /{id}/figures` | Not exposed |
| Annotations CRUD (highlights, notes) | `GET/POST/PUT/DELETE /{id}/annotations` | Not exposed |
| Annotation sync (batch) | `POST /{id}/annotations/sync` | Not exposed |
| Reading progress tracking | `GET/PUT /{id}/progress` | Not exposed |
| Reprocess with new options (re-transcribe, etc.) | `POST /{id}/reprocess` | Not exposed |
| Soft delete (trash) | `DELETE /{id}` | Not exposed |
| Restore from trash | `POST /{id}/restore` | Not exposed |
| Permanent delete | `DELETE /{id}/permanently` | Not exposed |
| Trash listing and empty trash | `GET /trash`, `POST /trash/empty` | Not exposed |
| File download with byte-range streaming | `GET /{id}/file` (supports Range header) | Not exposed |
| Media statistics | `GET /statistics` | Not exposed |
| ETag/conditional caching | `GET /{id}` (If-None-Match support) | Not exposed |
| Ingest jobs status monitoring | `GET /ingest-jobs/{id}` | Not exposed |

---

## Comparable Products

When benchmarking, consider how these tools handle multi-item media/document management:

| Product | Key Features to Benchmark |
|---|---|
| **NotebookLM** (Google) | Multi-source workspace, source-grounded chat, audio overview generation, per-source citation, source panel with highlights, collaborative notebooks |
| **Zotero** | Library grid/list views, saved searches, tag management, annotation management, related items, reader with highlights/notes, collection-based organization, quick search with filters |
| **Mendeley** | Document library with metadata editing, reading lists, annotations sync, search within PDFs, paper recommendations, group libraries |
| **DEVONthink** | Multi-panel document browser, AI classification, see-also suggestions, concordance, rich search operators, replicants (multi-location items), smart groups |
| **Readwise Reader** | Feed reader + document library, highlighting with spaced repetition, document-level notes, filtered views, ghostreader AI annotations, keyboard-first navigation |
| **Raindrop.io** | Visual bookmarking with grid/list/moodboard views, smart collections, full-text search across saved pages, tagging with auto-suggestions, bulk operations |
| **Papers** (ReadCube) | PDF library with smart collections, annotation tools, inline citation search, metadata auto-lookup, reading lists, enhanced PDF reader |
| **Paperpile** | Reference manager with integrated PDF viewer, shared folders, annotation collaboration, smart search, label/folder organization |
| **Eagle** | Visual asset manager with grid/waterfall/list views, color/tag/folder filtering, batch operations, smart folders, annotation tools |
| **Calibre** | Ebook library manager with metadata editing, format conversion, virtual libraries, saved searches, column customization, bulk metadata download |

---

## Output Format

For each finding, provide:

| Field | Description |
|-------|-------------|
| **ID** | Sequential (e.g., UX-001) |
| **Dimension** | Which review dimension (1-8) |
| **Severity** | Critical / Major / Minor / Enhancement |
| **Finding** | Clear description of the issue or gap |
| **Impact** | Who is affected and how (new users, power users, mobile users, researchers, etc.) |
| **Recommendation** | Specific, actionable suggestion |
| **Comparable** | How other tools handle this (if applicable) |

### Severity Definitions
- **Critical**: Blocks core task completion or causes data loss (e.g., selection silently lost on navigation, content not loadable, search returns wrong results)
- **Major**: Significant friction in common workflows; users may abandon the feature (e.g., cannot manage items from the review view, diff unusable on long documents, no sort controls)
- **Minor**: Noticeable but workaroundable; affects polish and trust (e.g., filter state unclear when collapsed, minimap transition jarring, empty analysis sections)
- **Enhancement**: Not a problem today but would meaningfully improve the experience (e.g., inline keyword editing, document outline panel, reading progress indicators)

---

## Summary Deliverables

1. **Executive Summary**: 3-5 sentence overview of the Media Multi page's UX maturity, strengths, and most urgent gaps
2. **Top 5 Priority Fixes**: Highest-impact improvements ranked by effort-to-impact ratio
3. **Competitive Gap Analysis**: Features present in 3+ comparable tools but missing here, ranked by user expectation
4. **Information Gaps Table**: Backend data and operations available but not surfaced in UI, with priority rating (High / Medium / Low) and rationale
5. **Selection & View Mode Deep Dive**: Dedicated analysis of the selection mechanics (progress bar, limits, undo, cross-page behavior) and view mode switching (auto-mode, transitions, mobile degradation)
6. **Batch Operations Roadmap**: What batch operations (tagging, deleting, exporting, reprocessing) should be added first, based on user task analysis and backend readiness
7. **Detailed Findings Table**: All findings in the structured format above
