# UX / HCI Audit Report: `/notes` Page

**Date:** 2026-02-17
**Scope:** Full Notes page (`/notes` route), Floating Notes Dock, backend API surface
**Methodology:** Code review of all frontend components, backend endpoints, schemas, store, and service modules

---

## 1. Notes List & Navigation

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 1.1 | Title truncation at 80 chars is reasonable but preview snippet at 100 chars may be too short for differentiating notes with similar openings | Nice-to-Have | UX/Usability Issue | `MAX_TITLE_LENGTH=80`, `MAX_PREVIEW_LENGTH=100` in `NotesListPanel.tsx:11-12`; truncation uses `...` ellipsis | Consider 120-150 chars for preview, or show the first non-title line of content rather than raw truncation |
| 1.2 | Search bar is visible but does not communicate that it is full-text (searches content via BM25, not just titles) | Important | Information Gap | Placeholder is "Search notes..." (`NotesManagerPage.tsx:1072`); backend uses FTS5 via `db.search_notes()` | Add helper text below the input: "Searches titles and content" or update placeholder to "Search titles & content..." |
| 1.3 | Keyword filter discoverable via `Select mode="tags"` but "Browse keywords" button is the only way to see all keywords at once; no count per keyword | Important | UX/Usability Issue | `Select` dropdown shows matching keywords; `Browse keywords` button opens `KeywordPickerModal` with count badge ("N available") but no per-keyword note count | Show note count next to each keyword in both the dropdown and the picker modal (e.g., "machine-learning (12)") |
| 1.4 | Active filters indicator exists but is only a conditional "Clear search & filters" button; no visual summary of what's currently filtered | Nice-to-Have | UX/Usability Issue | `hasActiveFilters` boolean drives display of clear button (`NotesManagerPage.tsx:1119-1129`); keyword tokens are visible in the Select but can be non-obvious | Add a filter summary bar (e.g., "Showing 5 of 42 notes matching 'ML' + keyword:research") above the list |
| 1.5 | No sorting options; notes always come in server-default order (by last_modified descending) | Important | Missing Functionality | `fetchNotes` calls `GET /api/v1/notes/` without sort params; backend `list_notes` uses DB default order | Add sort dropdown: Date Modified, Date Created, Title A-Z, Title Z-A. Backend already has the fields. |
| 1.6 | No visual indicators for note status (has keywords, has backlink, recently edited) in the list | Nice-to-Have | UX/Usability Issue | List items show keywords and backlink text, but no icons/badges for at-a-glance scanning | Add small icons: tag icon if has keywords, link icon if has conversation backlink, clock icon if edited within 24h |
| 1.7 | No bulk selection or multi-note operations | Important | Missing Functionality | Each note is a single click-to-select `<button>` (`NotesListPanel.tsx:264`); no checkboxes or shift-click | Add checkbox column or ctrl/shift-click for bulk delete, bulk export, or bulk keyword assignment |
| 1.8 | Empty state is actionable with "Create note" CTA and helpful examples | -- | -- | `FeatureEmptyState` component with examples and primary action button (`NotesListPanel.tsx:339-368`) | Good as-is |
| 1.9 | Selected note is clearly distinguished with `bg-surface2 border-l-4 border-l-primary` styling | -- | -- | Selected note gets left blue border and background change (`NotesListPanel.tsx:271-273`) | Good as-is |
| 1.10 | Pagination uses `Pagination simple` with page size 20; no infinite scroll or virtual list | Nice-to-Have | UX/Usability Issue | Fixed `pageSize=20` (`NotesManagerPage.tsx:128`); standard Ant Design pagination; `keepPreviousData` prevents flicker | For 100+ notes, consider virtual scrolling (react-window) or load-more pattern; current approach works but feels dated for a note-taking app |
| 1.11 | Page size is not user-configurable | Nice-to-Have | Missing Functionality | Hardcoded `pageSize=20`; `showSizeChanger={false}` on pagination (`NotesListPanel.tsx:393`) | Add page size selector (20, 50, 100) or persist user preference |

## 2. Note Editor

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 2.1 | Title input auto-focuses on new note creation | -- | -- | `titleInputRef.current?.focus()` in `handleNewNote` (`NotesManagerPage.tsx:407`) | Good as-is |
| 2.2 | Content area is a plain `<textarea>` with no auto-resize; relies on `h-full` flex sizing | Important | UX/Usability Issue | Raw `<textarea>` with `resize-none` and flex-fill height (`NotesManagerPage.tsx:1308-1319`); no auto-grow behavior | Consider CodeMirror/Monaco for a richer editor experience, or at minimum auto-resize the textarea to content height with a max |
| 2.3 | Markdown preview is toggle-only (edit OR preview); no side-by-side split view | Important | Missing Functionality | `showPreview` state toggles between `<textarea>` and `<MarkdownPreview>` (`NotesManagerPage.tsx:1281-1320`); no split mode | Add a three-state toggle: Edit / Split / Preview. Split mode shows editor and preview side-by-side. Power users expect this from any markdown editor |
| 2.4 | LaTeX math rendering is mentioned in the preview label ("Preview (Markdown + LaTeX)") but not in the editor placeholder | Nice-to-Have | Information Gap | Preview subtitle mentions LaTeX (`NotesManagerPage.tsx:1289`); editor placeholder says "Write your note here... (Markdown supported)" | Add a small "Markdown + LaTeX supported" note below the textarea, or link to a formatting help modal |
| 2.5 | Dirty state indicator ("Unsaved" orange tag) is visible next to the title | -- | -- | Orange `Tag` with "Unsaved" text in `NotesEditorHeader.tsx:77-81` | Good as-is |
| 2.6 | No keyboard shortcut for save (Ctrl/Cmd+S) | Critical | Missing Functionality | Save is button-only (`NotesEditorHeader.tsx:215-228`); no `onKeyDown` handler on the editor area for Ctrl+S | Add `useEffect` with `keydown` listener for Ctrl/Cmd+S that calls `saveNote()`. This is the single most expected keyboard shortcut in any editor |
| 2.7 | No editor formatting shortcuts (bold, italic, heading, list) | Important | Missing Functionality | Raw textarea with no toolbar for markdown formatting; users must know markdown syntax | Add a lightweight markdown toolbar (bold, italic, heading, link, code, list) that inserts syntax at cursor position |
| 2.8 | Toolbar action order is: [Open Conv] [New] [Preview] [Copy] [Export MD] [Save] [Delete] | Nice-to-Have | UX/Usability Issue | Actions grouped in `NotesEditorHeader.tsx:93-246`; Save is second-to-last, Delete is last | Move Save to the first position (leftmost) since it's the most frequent action; group destructive actions (Delete) separately with a divider |
| 2.9 | No word count, character count, or reading time estimate | Nice-to-Have | Missing Functionality | No metrics displayed anywhere in the editor area | Add a subtle footer bar showing word count, character count, and estimated reading time |
| 2.10 | No undo/redo beyond browser-native textarea undo | Nice-to-Have | Missing Functionality | Plain `<textarea>` provides browser Ctrl+Z/Y only; no revision history or comparison | Browser undo is acceptable for MVP; revision history is a stretch goal. Consider showing version number and "last saved at" timestamp |
| 2.11 | No auto-save mechanism; manual save only | Important | UX/Usability Issue | User must click Save or (ideally) use Ctrl+S; `isDirty` tracks unsaved state; `beforeunload` handler warns on page leave (`NotesManagerPage.tsx:955-963`) | Add debounced auto-save (e.g., 5 seconds after last edit) with a "Saving..." indicator. Fall back to manual save if auto-save fails |
| 2.12 | No support for embedded images or attachments | Nice-to-Have | Missing Functionality | Content is text-only; no drag-drop or paste handling for images | Long-term: support image upload with markdown image syntax insertion |

## 3. Keywords & Tagging

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 3.1 | Keyword input uses Ant Design `Select mode="tags"` which supports type-to-create and autocomplete | -- | -- | Both filter and editor keyword selects use `mode="tags"` with `onSearch` for autocomplete (`NotesManagerPage.tsx:1084-1095, 1251-1269`) | Good UX pattern |
| 3.2 | Autocomplete has 300ms debounce which is responsive | -- | -- | `debouncedLoadKeywordSuggestions` uses `setTimeout(300)` (`NotesManagerPage.tsx:927-929`) | Good as-is |
| 3.3 | KeywordPickerModal is a simple 2-column checkbox grid with search; no frequency indicators | Nice-to-Have | UX/Usability Issue | `Checkbox.Group` in `grid-cols-1 sm:grid-cols-2` layout (`KeywordPickerModal.tsx:100`); shows total count but no per-keyword note count | Add note count per keyword; sort by frequency; add recently-used section at top |
| 3.4 | No visual hierarchy among keywords (all same styling) | Nice-to-Have | UX/Usability Issue | Keywords displayed as plain `<span>` pills with `bg-surface2` in list, `Tag` components in dock | Consider color-coding by frequency or allowing user-defined colors |
| 3.5 | Keyword management (rename, merge, delete) not accessible from the notes page | Important | Missing Functionality | Backend has `DELETE /keywords/{id}` endpoint but no rename/merge; UI has no keyword management view | Add keyword management: rename, merge duplicates, delete unused keywords. Accessible from the Browse Keywords modal |
| 3.6 | No suggested/auto-generated keywords based on note content | Nice-to-Have | Missing Functionality | Keywords are fully manual; no AI suggestion | Leverage existing LLM integration to suggest keywords from note content (similar to auto-title) |
| 3.7 | Keywords in list panel show max 5 with "+N" overflow; consistent with editor display | -- | -- | `item.keywords.slice(0, 5)` with overflow count tooltip (`NotesListPanel.tsx:293-312`) | Good as-is |

## 4. Search & Filtering

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 4.1 | Search uses FTS5 (BM25 scoring) on the backend but this is not communicated to users | Important | Information Gap | Backend `search_notes()` uses SQLite FTS5; frontend calls `/api/v1/notes/search/?query=...` | Add placeholder text "Full-text search across titles and content" or a search help tooltip |
| 4.2 | Search results are not highlighted with matching terms | Important | UX/Usability Issue | Results show truncated preview (`truncateText(item.content, 100)`) without any match highlighting | Implement snippet highlighting: backend could return matched fragments, or frontend can highlight query terms in the preview |
| 4.3 | Keyword filter + text search can be combined; behavior is AND (both must match) | -- | -- | `fetchFilteredNotesRaw` sends both `query` and `tokens` params; backend `search_notes_with_keywords` requires all to match | Good as-is, but document the AND behavior for users |
| 4.4 | No advanced search syntax documented | Nice-to-Have | Information Gap | FTS5 supports phrase search with quotes and boolean operators, but this is not exposed to users | Add a "Search tips" popover: use quotes for phrases, prefix matching, etc. |
| 4.5 | No in-note search (Ctrl+F equivalent) | Nice-to-Have | Missing Functionality | Browser Ctrl+F works on the entire page but not specifically within the note content | Browser Ctrl+F is sufficient for MVP; could add dedicated in-editor search for large notes |
| 4.6 | No "recent notes" or "frequently accessed" quick-access section | Nice-to-Have | Missing Functionality | Notes list always shows paginated results or search results; no recency shortcuts | Add a "Recent" section at the top of the sidebar showing last 3-5 opened notes |
| 4.7 | Search input triggers on every keystroke (onChange sets query, which triggers React Query refetch) | Nice-to-Have | UX/Usability Issue | `onChange` sets `query` state immediately (`NotesManagerPage.tsx:1076-1079`); React Query re-fetches on queryKey change; `keepPreviousData` mitigates flickering | Add explicit debounce (300-500ms) on the search input to avoid excessive API calls during typing |

## 5. Conversation & Source Backlinks

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 5.1 | Backlink indicator shows raw conversation ID (UUID) which is not human-readable | Important | UX/Usability Issue | Displays "Linked to conversation {uuid}" in both list and editor header (`NotesListPanel.tsx:316-323`, `NotesEditorHeader.tsx:84-90`) | Fetch and display conversation title or topic instead of raw UUID; add tooltip with full ID for debugging |
| 5.2 | Navigation from note to linked conversation works (same tab, resets chat state) | -- | -- | `openLinkedConversation()` fetches chat, sets messages/history, navigates to "/" (`NotesManagerPage.tsx:596-680`) | Good as-is, though consider opening in a new tab or offering the choice |
| 5.3 | NoteQuickSaveModal pre-fills title and content; supports source URL display | -- | -- | `NoteQuickSaveModal.tsx` has `suggestedTitle`, `content`, `sourceUrl` props | Good as-is |
| 5.4 | No indicator in the notes list distinguishing notes with backlinks from standalone notes (without opening each note) | Nice-to-Have | UX/Usability Issue | Backlink text appears inline in list items only when `item.conversation_id` exists (`NotesListPanel.tsx:315-323`) | The inline text works but a small link icon would be more scannable for long lists |
| 5.5 | No way to see which media sources a note is related to | Important | Information Gap | Backend `NoteResponse` has no `source_id` or media link field; graph service has `source_membership` edges but this isn't surfaced in the main notes UI | Add media source display in the editor header when a note has source connections via the graph |
| 5.6 | Path from chat to notes (creating a note from a chat message) depends on external integration; not documented in the notes UI | Nice-to-Have | Information Gap | The `NoteQuickSaveModal` exists in `Sidepanel/Notes/` suggesting it's triggered from chat, but no in-notes-page documentation of this flow | Add a hint in the empty state: "You can also create notes directly from chat messages" |

## 6. Note Graph & Linking

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 6.1 | Note graph feature is fully implemented in the backend but has zero UI presence on the `/notes` page | Critical | Missing Functionality | Backend has `GET /notes/graph`, `GET /notes/{id}/neighbors`, `POST /notes/{id}/links`, `DELETE /notes/links/{id}` endpoints with Cytoscape format support (`notes_graph.py`); `NoteGraphService` supports BFS traversal, edge types (manual, wikilink, backlink, tag_membership, source_membership); **none of this is rendered in the UI** | This is the single biggest gap. Add: (1) a "Related Notes" panel showing neighbors, (2) a full graph visualization view using Cytoscape.js or d3-force, (3) UI for creating/deleting manual links between notes |
| 6.2 | No support for `[[wikilinks]]` in the editor | Important | Missing Functionality | Backend supports wikilink edge type but the editor is a plain textarea with no wikilink parsing or autocomplete | Add `[[` trigger for note title autocomplete; parse wikilinks in preview mode as clickable links to other notes |
| 6.3 | No visual display of backlinks (notes linking TO the current note) | Important | Missing Functionality | Graph service computes backlink edges but they're not shown in the note editor | Add a "Backlinks" section below the editor showing notes that reference the current note |
| 6.4 | No way to browse the entire note graph as a knowledge map | Important | Missing Functionality | `/api/v1/notes/graph` endpoint exists with configurable radius, max_nodes, and Cytoscape format | Add a dedicated graph view (full page or modal) with interactive zoom/pan/click-to-open navigation |

## 7. Export & Sharing

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 7.1 | Three export formats (MD, CSV, JSON) are available via dropdown in the list panel | -- | -- | `Dropdown` with three menu items in `NotesListPanel.tsx:78-133`; individual note export as MD via header button | Good as-is |
| 7.2 | Single note export is MD-only (from editor header); no single-note CSV or JSON export | Nice-to-Have | UX/Usability Issue | `exportSelected` generates a `.md` file (`NotesManagerPage.tsx:689-709`); bulk export has all three formats | Add format choice for single-note export, or at minimum Copy as JSON |
| 7.3 | MD export preserves title as `# heading` but does not include keywords in the output | Nice-to-Have | UX/Usability Issue | Export creates `# ${title}\n\n${content}` (`NotesManagerPage.tsx:692`) | Include keywords as YAML frontmatter or a `Tags:` line at the top of the exported markdown |
| 7.4 | CSV export includes keywords joined with semicolons; usable in spreadsheets | -- | -- | Keywords joined with `; ` separator (`NotesManagerPage.tsx:847`) | Good as-is |
| 7.5 | No import capability | Important | Missing Functionality | No file import UI or backend endpoint for importing notes from markdown, JSON, or other tools | Add import from JSON (matching export format) and markdown files; essential for data portability |
| 7.6 | No print-friendly view or PDF export | Nice-to-Have | Missing Functionality | No print CSS or PDF generation | Add print stylesheet for the markdown preview; consider server-side PDF generation |
| 7.7 | Clipboard copy copies raw content (not as markdown with title) | Nice-to-Have | UX/Usability Issue | `navigator.clipboard.writeText(content)` copies content only (`NotesManagerPage.tsx:683`) | Option to copy with title as markdown heading |
| 7.8 | Export limit warning at 1000 pages is shown but could be more prominent | Nice-to-Have | UX/Usability Issue | `MAX_EXPORT_PAGES=1000`; shows `message.warning` when limit reached (`NotesManagerPage.tsx:753-755`) | Show the warning before starting the export if total exceeds 100,000 notes |

## 8. AI-Powered Features

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 8.1 | AI title generation exists in backend but is not exposed in the notes page UI | Important | Missing Functionality | Backend has `POST /notes/title/suggest` endpoint and `generate_note_title()` with heuristic/LLM strategies (`note_title.py`); `NoteCreate.auto_title` flag exists; **no UI button to trigger title generation** | Add a "Generate Title" button (sparkle icon) next to the title input that calls the suggest endpoint and shows a preview before accepting |
| 8.2 | Title strategy (heuristic vs LLM) is not configurable by users | Nice-to-Have | Information Gap | Strategy is determined by server config `NOTES_TITLE_DEFAULT_STRATEGY` and `NOTES_TITLE_LLM_ENABLED` flag | If LLM is enabled, show a dropdown to choose strategy; otherwise hide the option |
| 8.3 | No AI assistance for note content (summarize, expand, suggest related) | Nice-to-Have | Missing Functionality | Only title generation is implemented; no content-level AI features | Future: add "Summarize", "Expand outline", "Suggest keywords" actions in the editor toolbar |
| 8.4 | Topic monitoring (sensitive content detection) runs silently on save | Nice-to-Have | Information Gap | `get_topic_monitoring_service().schedule_evaluate_and_alert()` called on create/update (`notes.py:552-575`) but no user-visible indication | If topic monitoring flags content, surface the alert to the user rather than silently logging |

## 9. Floating Notes Dock

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 9.1 | Dock button (`NotesDockButton`) has good accessibility (aria-label, aria-pressed, aria-haspopup, aria-expanded) | -- | -- | `NotesDockButton.tsx:56-63` has proper ARIA attributes | Good as-is |
| 9.2 | Dock supports multiple draft notes with tab-switching UI (pill tabs at bottom) | -- | -- | `notes` array in store; tab pills with active state and close buttons (`NotesDockPanel.tsx:792-838`) | Good as-is |
| 9.3 | Drag-and-resize works; position persists to localStorage via zustand persist | -- | -- | `persist` middleware with `partialize` for position/size (`notes-dock.tsx:231-239`); `resize: "both"` CSS | Good as-is |
| 9.4 | No keyboard shortcut to toggle the dock | Important | Missing Functionality | Dock is opened only via click on `NotesDockButton`; no global keyboard shortcut | Add a global keyboard shortcut (e.g., Ctrl/Cmd+Shift+N) to toggle the dock |
| 9.5 | Dock note content is not synced with the main notes page | Nice-to-Have | UX/Usability Issue | Dock saves directly to API; main page uses React Query cache; no cross-invalidation | After saving in the dock, invalidate the notes list React Query cache so the main page reflects changes |
| 9.6 | Dock has unsaved changes protection (modal on close) | -- | -- | `unsavedModalOpen` state with Save/Discard/Cancel options (`NotesDockPanel.tsx:842-866`) | Good as-is |
| 9.7 | Dock has "Open Notes page" link at the bottom of the archive panel | -- | -- | `navigate("/notes")` link (`NotesDockPanel.tsx:677-681`) | Good as-is |
| 9.8 | No markdown preview in dock editor (plain textarea only) | Nice-to-Have | Missing Functionality | Dock uses `TextArea` without preview toggle | For a quick-capture tool, this is acceptable; full preview belongs on the main page |

## 10. Version Control & Conflict Handling

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 10.1 | Version conflict (409) shows actionable error with "Reload notes" button | -- | -- | `handleVersionConflict` displays an error message with inline reload button (`NotesManagerPage.tsx:432-461`) | Good as-is |
| 10.2 | No indication of when a note was last saved or current version number | Nice-to-Have | Information Gap | Version is tracked internally (`selectedVersion` state) but not displayed to the user | Show "Version N, last saved at {time}" in the editor footer |
| 10.3 | No version history or diff view | Important | Missing Functionality | Backend tracks version numbers but no history table; `soft_delete` + version is the extent of versioning | Long-term: add a revisions table and diff view. Medium-term: show version number and last modified timestamp |
| 10.4 | Soft delete exists but no "trash" view to find/restore deleted notes | Important | Missing Functionality | Backend has `POST /notes/{id}/restore` endpoint; frontend has no UI for browsing or restoring deleted notes | Add a "Trash" section (accessible from sidebar) showing soft-deleted notes with a "Restore" action |
| 10.5 | Browser close/navigate with unsaved changes triggers `beforeunload` warning | -- | -- | `window.addEventListener('beforeunload', handler)` (`NotesManagerPage.tsx:955-963`) | Good as-is |
| 10.6 | Two tabs editing same note: no real-time conflict detection, only on save | Nice-to-Have | UX/Usability Issue | Version is checked on save via `expected_version` header; no polling or WebSocket for live conflict detection | For MVP this is acceptable; long-term consider polling the note version every 30s to warn early |
| 10.7 | Discard confirmation dialog works when switching notes with unsaved changes | -- | -- | `confirmDiscardIfDirty` shows Discard/Cancel dialog (`NotesManagerPage.tsx:391-400`) | Good as-is |

## 11. Responsive & Mobile Experience

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 11.1 | Sidebar has collapse/expand toggle with smooth animation | -- | -- | `sidebarCollapsed` state with `transition-all duration-300`; chevron button for toggle (`NotesManagerPage.tsx:1026-1192`) | Good as-is |
| 11.2 | Sidebar width is fixed at 380px; no responsive breakpoint handling | Important | UX/Usability Issue | `w-[380px]` hardcoded (`NotesManagerPage.tsx:1028`); on screens < 768px both sidebar and editor will be cramped | Add responsive breakpoints: auto-collapse sidebar on mobile, or switch to a single-panel layout with navigation drawer |
| 11.3 | Editor toolbar buttons are `size="small"` (Ant Design) which may be too small for touch | Important | Accessibility Concern | All toolbar buttons use `size="small"` (`NotesEditorHeader.tsx`); Ant Design small buttons are ~24px height | Ensure touch targets are >= 44px on mobile; consider responsive sizing or a mobile-specific toolbar layout |
| 11.4 | KeywordPickerModal uses `sm:grid-cols-2` which adapts to single column on mobile | -- | -- | `grid-cols-1 sm:grid-cols-2` (`KeywordPickerModal.tsx:100`) | Good responsive pattern |
| 11.5 | Floating dock on mobile would overlap most of the viewport | Nice-to-Have | UX/Usability Issue | Dock minimum size is 360x360; on mobile screens this would cover nearly everything | Hide the dock button on mobile (< 768px) or convert to a full-screen overlay on small screens |
| 11.6 | No viewport meta handling specific to notes page | Nice-to-Have | UX/Usability Issue | Standard Next.js viewport; no pinch-zoom disable for the editor | Acceptable for MVP |

## 12. Performance & Perceived Speed

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 12.1 | Loading state shows Ant Design `Spin` component during fetch | -- | -- | `isFetching` drives `<Spin />` in `NotesListPanel.tsx:139-142` | Good, though skeleton loading would feel snappier |
| 12.2 | React Query with `keepPreviousData` prevents flash of empty state during refetch | -- | -- | `placeholderData: keepPreviousData` in `useQuery` (`NotesManagerPage.tsx:282`) | Good as-is |
| 12.3 | Note detail loading shows no skeleton/loading state in the editor | Nice-to-Have | UX/Usability Issue | `loadingDetail` state exists (`NotesManagerPage.tsx:133`) but is not used to show any visual feedback in the editor area | Show a loading skeleton or spinner in the editor when `loadingDetail` is true |
| 12.4 | Keyword autocomplete has 300ms debounce; responsive enough | -- | -- | `setTimeout(300)` debounce (`NotesManagerPage.tsx:927`) | Good as-is |
| 12.5 | Search input has no debounce; triggers on every keystroke via React Query | Nice-to-Have | UX/Usability Issue | `onChange` sets `query` which is part of `queryKey`, triggering immediate refetch (`NotesManagerPage.tsx:1076-1079`) | Add 300-500ms debounce on the search input to batch rapid keystrokes |
| 12.6 | Markdown preview rendering performance for large notes is unquantified | Nice-to-Have | UX/Usability Issue | `<MarkdownPreview content={content} size="sm" />` renders on every toggle; no lazy rendering or virtualization | For notes > 10K chars, consider lazy rendering or a loading state during initial render |
| 12.7 | Bulk export fetches all notes in 100-item chunks, blocking the UI | Nice-to-Have | UX/Usability Issue | `exportAll`, `exportAllCSV`, `exportAllJSON` are sequential async loops with no progress indicator (`NotesManagerPage.tsx:713-900`) | Show a progress bar or "Exporting X of Y notes..." message during bulk export |
| 12.8 | `KeywordPickerModal` is lazy-loaded via `React.lazy` | -- | -- | `React.lazy(() => import(...))` with `Suspense` (`NotesManagerPage.tsx:36, 1325`) | Good code-splitting practice |

## 13. Error Handling & Edge Cases

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 13.1 | Backend unreachable shows connection problem banner with retry button | -- | -- | `ConnectionProblemBanner` with retry action (`NotesListPanel.tsx:203-225`) | Good as-is |
| 13.2 | Save failure shows generic error message; user's work is preserved in local state | -- | -- | On save error, `message.error` is shown but content remains in state (`NotesManagerPage.tsx:525-531`) | Good - no data loss on save failure |
| 13.3 | Version conflict error has "Reload notes" button for recovery | -- | -- | Inline reload button in error message (`NotesManagerPage.tsx:432-461`) | Good as-is |
| 13.4 | No undo for note deletion | Important | UX/Usability Issue | Delete is soft-delete on backend but UI has no "Undo" toast or trash recovery | Add a "Note deleted - Undo" toast with a short timeout (5-10 seconds) that calls the restore endpoint |
| 13.5 | Deleting a note with incoming graph links is not handled in UI | Nice-to-Have | UX/Usability Issue | Backend soft-deletes the note; graph edges pointing to it would reference a deleted node; no warning shown | Show a warning if the note has incoming links: "This note is referenced by N other notes. Deleting it will break those links." |
| 13.6 | Export limit warning is shown as a toast that could be missed | Nice-to-Have | UX/Usability Issue | `message.warning` for limit reached during export | Consider a pre-export confirmation dialog showing estimated count |
| 13.7 | Keyword creation failure is silently swallowed on save | Nice-to-Have | UX/Usability Issue | Backend logs keyword errors but returns success; frontend doesn't know if a keyword failed to attach | Surface partial keyword failures in a warning toast: "Note saved but 1 keyword failed to attach" |

## 14. Accessibility

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 14.1 | Sidebar collapse button has proper `aria-label` for both states | -- | -- | Dynamic aria-label "Expand sidebar" / "Collapse sidebar" (`NotesManagerPage.tsx:1176-1183`) | Good as-is |
| 14.2 | All toolbar buttons have `aria-label` attributes | -- | -- | Every button in `NotesEditorHeader.tsx` has `aria-label` matching tooltip text | Good as-is |
| 14.3 | Version conflict error uses `role="alert"` and `aria-live="assertive"` | -- | -- | `handleVersionConflict` error span has ARIA attributes (`NotesManagerPage.tsx:437-439`) | Good as-is |
| 14.4 | Notes list items are `<button>` elements, keyboard accessible | -- | -- | Each note is a `<button type="button">` (`NotesListPanel.tsx:264`) | Good as-is |
| 14.5 | No `aria-current` or `aria-selected` on the currently selected note in the list | Important | Accessibility Concern | Selected note has visual styling but no ARIA attribute for screen readers | Add `aria-current="true"` or `aria-selected="true"` to the selected note button |
| 14.6 | KeywordPickerModal uses Ant Design `Modal` which has built-in focus trapping | -- | -- | Standard `Modal` component (`KeywordPickerModal.tsx:34`) | Good as-is |
| 14.7 | Editor panel has `aria-disabled` when disabled, but the textarea lacks `aria-label` | Nice-to-Have | Accessibility Concern | `aria-disabled` on wrapper div (`NotesManagerPage.tsx:1197`); textarea has `placeholder` but no explicit `aria-label` | Add `aria-label="Note content"` to the textarea |
| 14.8 | Pagination controls are standard Ant Design `Pagination` with keyboard support | -- | -- | `Pagination simple size="small"` (`NotesListPanel.tsx:384-394`) | Good as-is |
| 14.9 | Floating dock dialog has `role="dialog"` and `aria-label` | -- | -- | `NotesDockPanel.tsx:501` sets `role="dialog"` and `aria-label` | Good as-is |
| 14.10 | No skip-to-content link for the notes page | Nice-to-Have | Accessibility Concern | Standard two-panel layout without skip navigation | Add skip links: "Skip to notes list", "Skip to editor" |

## 15. Information Gaps & Missing Functionality

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 15.1 | No note templates (meeting notes, research summary, etc.) | Nice-to-Have | Missing Functionality | Notes always start blank | Add a template picker on new note creation with 3-5 common templates |
| 15.2 | No folders/notebooks for hierarchical organization | Important | Missing Functionality | Notes are flat; keywords provide the only organizational axis | Consider adding notebooks or collections as a higher-level grouping |
| 15.3 | No pinned/favorited notes for quick access | Nice-to-Have | Missing Functionality | No pinning mechanism | Add a pin/star toggle that keeps notes at the top of the list |
| 15.4 | No note duplication/cloning | Nice-to-Have | Missing Functionality | No "Duplicate note" action | Add a "Duplicate" button that creates a new note with the same content |
| 15.5 | No trash/recycle bin view | Important | Missing Functionality | Soft delete exists but no UI to browse or restore deleted notes; backend `POST /notes/{id}/restore` exists | Add "Trash" tab or filter showing soft-deleted notes with restore/permanent delete actions |
| 15.6 | No keyboard shortcuts cheat sheet | Nice-to-Have | Missing Functionality | No help overlay for keyboard shortcuts | Add a "?" keyboard shortcut that shows available shortcuts |
| 15.7 | No rich text/WYSIWYG alternative to raw markdown | Nice-to-Have | Missing Functionality | Editor is raw markdown textarea; preview is view-only | Consider offering a toggle between markdown source and a WYSIWYG editor (e.g., Tiptap, Milkdown) |
| 15.8 | No table of contents for long notes | Nice-to-Have | Missing Functionality | No TOC generation from markdown headings | Auto-generate a floating TOC sidebar for notes with 3+ headings |
| 15.9 | No calendar/timeline view of notes | Nice-to-Have | Missing Functionality | Notes only shown as paginated list | Add a timeline or calendar view showing notes by creation/modification date |
| 15.10 | No offline editing support | Nice-to-Have | Missing Functionality | Notes require server connection; `editorDisabled` when offline | Implement local draft storage with sync-on-reconnect |

---

## Executive Summary

### Top 5 Critical Gaps That Would Block Researcher Adoption

1. **No Ctrl/Cmd+S keyboard shortcut for save** (2.6) -- The single most fundamental editor shortcut is missing. Every researcher will instinctively press Ctrl+S and nothing will happen. This creates immediate friction and data loss anxiety.

2. **Note graph is fully built in backend but completely invisible in the UI** (6.1) -- The backend supports manual links, wikilinks, backlinks, tag membership edges, Cytoscape format, BFS traversal, and neighbors queries. None of this power is surfaced. For a knowledge management tool, graph navigation is the differentiating feature.

3. **No trash/recycle bin view for soft-deleted notes** (15.5, 10.4) -- Backend supports soft-delete and restore, but users have no way to find or recover deleted notes. This creates data loss fear, especially for researchers managing large collections.

4. **No auto-save mechanism** (2.11) -- Researchers expect auto-save from any modern editor. Currently, manual save is the only option. Combined with the missing Ctrl+S shortcut, this means work is easily lost.

5. **AI title generation exists in backend but has no UI trigger** (8.1) -- The backend has a complete title suggestion endpoint with heuristic and LLM strategies, but the UI provides no button to invoke it. This is wasted backend capability.

### Top 5 Quick Wins (High Impact, Low Effort)

1. **Add Ctrl/Cmd+S save shortcut** -- Single `useEffect` with `keydown` handler. ~10 lines of code. Massive usability improvement.

2. **Add `aria-current="true"` to selected note in list** -- One attribute addition. Fixes screen reader accessibility.

3. **Show conversation title instead of UUID in backlink display** -- Fetch conversation title on load, display human-readable name. Moderate effort, high readability improvement.

4. **Add debounce to search input** -- Wrap query state update in a 300ms debounce. Prevents excessive API calls. ~5 lines of code.

5. **Add "Generate Title" button** -- Wire up existing `/notes/title/suggest` endpoint to a sparkle icon button next to the title input. Backend is already done.

### Suggested Priority Roadmap

**Phase 1: Foundation (Week 1-2)**
- Add Ctrl/Cmd+S save shortcut
- Add search input debounce
- Fix accessibility: `aria-current` on selected note, `aria-label` on textarea
- Show "Searches titles and content" helper text
- Add loadingDetail visual feedback in editor
- Add "Generate Title" button wiring up existing backend

**Phase 2: Core Knowledge Features (Week 3-5)**
- Add "Related Notes" panel using `/notes/{id}/neighbors` endpoint
- Add trash view with restore capability
- Add sorting options (date, title)
- Add auto-save with debounce (5s after last edit)
- Add markdown formatting toolbar (bold, italic, heading, list, link)
- Show conversation title instead of UUID in backlinks

**Phase 3: Graph & Navigation (Week 6-8)**
- Build interactive graph visualization (Cytoscape.js) using existing `/notes/graph` endpoint
- Add `[[wikilink]]` autocomplete in editor
- Add manual link creation UI between notes
- Add backlinks section showing notes that link to current note
- Add search result highlighting

**Phase 4: Power User Features (Week 9-12)**
- Side-by-side editor/preview split view
- Bulk note operations (multi-select, batch keyword assignment)
- Note import from JSON/Markdown
- Keyword management (rename, merge, delete)
- Note templates
- Pinned/favorited notes
- Keyboard shortcuts cheat sheet
- Dock keyboard shortcut (Ctrl+Shift+N)

**Phase 5: Polish & Mobile (Week 13+)**
- Responsive mobile layout with single-panel mode
- Infinite scroll or virtual list for large collections
- Revision history with diff view
- AI keyword suggestions
- Calendar/timeline view
- Rich text/WYSIWYG editor option
