# UX / HCI Review: Workspace Playground

**Reviewer perspective**: Potential research user + HCI/design expert
**Date**: 2026-02-17
**Scope**: `/workspace-playground` page - NotebookLM-style three-pane research interface
**Codebase version**: `dev` branch (commit `41eb33f6d`)

---

## 1. Source Management (SourcesPane, AddSourceModal)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 1.1 | Tab order in AddSourceModal places Upload first, which is correct for most users. However, "Library" (existing media) is last despite being zero-friction for returning users. | Nice-to-Have | UX/Usability Issue | Tabs: Upload > URL > Paste > Search > Library | Reorder to: Upload > Library > URL > Paste > Search. Returning users will most often pick from Library. |
| 1.2 | Drag-and-drop upload lacks progress bar for individual files. `beforeUpload` fires immediately and uploads sequentially, but the only feedback is the Ant Design upload list default behavior. | Important | UX/Usability Issue | `Dragger` component with `showUploadList: true`; no per-file progress callback. Processing state is binary (`setProcessing(true/false)`). | Add per-file upload progress via `onProgress` prop or at minimum show a per-file spinner. Show estimated time for large files. |
| 1.3 | No file size limit guidance. The `accept` attribute limits file types but not sizes. A 2 GB video upload will silently start and may time out. | Important | Information Gap | `accept` prop lists extensions; no `maxSize` check in `beforeUpload`. | Add `beforeUpload` size validation (e.g., 500 MB default), show limit in hint text, and reject oversized files with an actionable message. |
| 1.4 | URL tab accepts one URL at a time. No batch URL input. Researchers often have 5-10 URLs to add at once. | Important | Missing Functionality | Single `<Input>` with onPressEnter. | Add a `<TextArea>` mode for "one URL per line" batch input, with per-URL status indicators. |
| 1.5 | Web search results lack preview snippets. Only `title` and `url` are shown. Users cannot assess relevance before adding. | Important | Information Gap | `List.Item` renders `item.title` and `item.url` only. The API response likely includes `snippet`/`content` but it is not rendered. | Display `item.snippet` or `item.content` as a 2-line preview below each result. Add favicon if available. |
| 1.6 | Library tab loads 50 items with no pagination or infinite scroll. Users with large libraries will see an incomplete list. | Important | UX/Usability Issue | `results_per_page: 50`, no "load more" or pagination control. | Add "Load more" button or virtual scrolling. Show total count (e.g., "Showing 50 of 342"). |
| 1.7 | Source removal has no undo or confirmation. The X button removes immediately with `removeSource(source.id)`. Accidental clicks cause data loss. | Important | UX/Usability Issue | `removeSource` called directly on button click. No confirmation dialog, no undo. | Add either a "toast with undo" pattern (preferred) or a lightweight confirmation popover. |
| 1.8 | No source processing status indicator. Users cannot tell if a source is fully ingested, chunked, and ready for RAG queries. | Critical | Information Gap | `WorkspaceSource` type has `type` and `title` only. No `status` field (e.g., "processing", "ready", "error"). | Add a `status` field to `WorkspaceSource`. Show a spinner/badge for "processing" sources. Disable sources in chat context until ready. |
| 1.9 | Source metadata is minimal. Only title and type are shown. No page count, word count, duration, file size, or date added visible. | Nice-to-Have | Information Gap | `WorkspaceSource` interface defines `fileSize`, `duration`, `pageCount` as optional but they are never populated during `addSource`. | Populate metadata fields from the media API response. Display in a tooltip or expandable row. |
| 1.10 | Source ingestion error messages are generic. Upload errors show "Failed to upload file" or the raw error message. No guidance on resolution. | Important | UX/Usability Issue | `setError(t("playground:sources.uploadError", "Failed to upload file"))` | Include actionable detail: file type not supported, file too large, server unreachable, etc. Map common HTTP status codes to user-friendly messages. |
| 1.11 | Source list is not virtualized. With 50+ sources, rendering all items in a `space-y-1` div may cause scroll jank. | Nice-to-Have | UX/Usability Issue | Plain `div` with `.map()` rendering. | Use `react-window` or Ant Design's virtual list for large source counts. |
| 1.12 | No source reordering capability. Sources appear in add-order. Researchers may want to group related sources. | Nice-to-Have | Missing Functionality | Sources rendered in array order from store. | Allow drag-and-drop reordering (e.g., `@dnd-kit/sortable`). |

---

## 2. RAG-Powered Chat (ChatPane)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 2.1 | Source context tags overflow gracefully with horizontal scroll, but no "N more" indicator. With 15+ sources the scrollbar is the only cue that tags extend offscreen. | Nice-to-Have | UX/Usability Issue | `overflow-x-auto` on tag container. Tags capped at `max-w-[150px]` with truncation + tooltip. | Add a summary count tag at the end (e.g., "+8 more") or a collapsed "N sources selected" chip that expands on click. |
| 2.2 | Citations in responses are rendered by `PlaygroundMessage` component which supports `sources` and `toolCalls` props, but the workspace chat does not pass citation-specific source metadata back to the sources pane. No clickable citation -> source navigation. | Critical | Missing Functionality | `PlaygroundMessage` receives `sources={msg.sources}` but there is no cross-pane navigation handler (no `onCitationClick` prop, no store action to highlight a source in SourcesPane). | Add an `onSourceClick(mediaId)` callback that scrolls-to and highlights the referenced source in the SourcesPane. |
| 2.3 | Empty state example questions are static. They don't change based on selected source types (video vs. PDF vs. audio). | Nice-to-Have | UX/Usability Issue | Three hardcoded i18n keys: "Summarize the key points", "What are the main arguments", "Compare and contrast". | Vary examples based on source types. E.g., for video: "What was discussed at timestamp X?" For PDF: "Summarize chapter 3." |
| 2.4 | No explicit RAG vs. general chat toggle. Mode is auto-set by `setChatMode("rag")` when sources are selected and `"normal"` otherwise. Users cannot override this. | Important | Missing Functionality | `useEffect` syncs `setChatMode` from `selectedSourceIds`. No user toggle. | Add a small toggle/chip near the input: "RAG mode" / "General chat". Some queries benefit from general knowledge even with sources selected. |
| 2.5 | No stop-generation button. While streaming, the send button shows a spinner but there is no way to cancel a running generation. | Critical | UX/Usability Issue | `SimpleChatInput` renders `<Loader2>` when `isLoading`, button is `disabled`. No `onStop` callback. | Add a stop button (square icon) that calls an abort controller on the streaming fetch. This is essential for long-running RAG queries. |
| 2.6 | Chat history is not preserved per workspace. When switching workspaces, `switchWorkspace` resets `...initialStudioState` which clears artifacts but chat messages live in `useMessageOption` hook, not the workspace store. | Critical | Missing Functionality | Chat messages managed by `useMessageOption` hook (from `useStoreMessageOption`), not `useWorkspaceStore`. Workspace switch does not save/restore chat history. | Store chat message history per workspace (e.g., via `workspaceId` key in the message store). Save on switch, restore on load. |
| 2.7 | No clear/reset chat button visible in the ChatPane UI. Users must create a new workspace to start fresh. | Important | Missing Functionality | No reset/clear button rendered. The `useMessageOption` hook may support clearing but no UI trigger exists. | Add a "Clear chat" icon button in the chat header area. Confirm before clearing if messages exist. |
| 2.8 | No indication of retrieval quality. RAG responses don't show relevance scores, number of chunks retrieved, or confidence indicators. | Nice-to-Have | Information Gap | RAG call uses `enable_citations: true` but retrieved chunk metadata (scores, counts) is not displayed. | Show a collapsible "Retrieval info" section under each RAG response: chunks retrieved, avg relevance score, sources used. |
| 2.9 | No user-adjustable RAG parameters. `top_k` is hardcoded per output type (15-30). No UI for similarity threshold adjustment. | Nice-to-Have | Missing Functionality | `top_k: 20` hardcoded in generation functions. No settings panel. | Add an expandable "Advanced RAG settings" in the chat input area: top_k slider, similarity threshold, enable/disable reranking. |
| 2.10 | Chat input uses `Enter` to submit with `Shift+Enter` for newline. This is standard but not documented anywhere in the UI. | Nice-to-Have | Information Gap | `handleKeyDown` checks `e.key === "Enter" && !e.shiftKey`. | Add a small hint below the input: "Enter to send, Shift+Enter for new line". |
| 2.11 | Backend connectivity failure shows raw error messages from the `useMessageOption` hook. No per-pane or global connectivity indicator. | Important | UX/Usability Issue | No error boundary or connectivity check visible in ChatPane. | Add a connection status indicator. Show a banner "Unable to reach server" with retry button when requests fail. |

---

## 3. Studio & Output Generation (StudioPane)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 3.1 | The 9 output types are in a flat 2-column grid with no categorization. As the number grows, discoverability decreases. "Audio Overview" and "Data Table" serve very different use cases. | Nice-to-Have | UX/Usability Issue | Flat `grid grid-cols-2` rendering all 9 types equally. | Group into categories: "Study Aids" (Quiz, Flashcards), "Analysis" (Summary, Report, Timeline, Data Table), "Creative" (Mind Map, Slides, Audio). |
| 3.2 | Output type buttons have no descriptions. Users must guess what "Data Table" or "Audio Overview" produces. The `OUTPUT_TYPES` config in `workspace.ts` defines `description` fields but StudioPane doesn't render them. | Important | Information Gap | Button shows icon + label only. Tooltip shows label or "Select sources first". The `OutputTypeConfig.description` field exists in types but is unused in rendering. | Show descriptions in tooltips (on hover/focus). E.g., "Extract structured data into a table". |
| 3.3 | No cancel button for running generations. `isGeneratingOutput` disables all buttons but offers no way to abort. | Important | UX/Usability Issue | `isDisabled = !hasSelectedSources \|\| isGeneratingOutput`. No abort/cancel mechanism. | Add a "Cancel" button that appears during generation. Use `AbortController` for the underlying fetch calls. |
| 3.4 | No estimated generation time. Some outputs (Audio Overview with TTS) take 30+ seconds; others (Summary) complete in 5 seconds. Users have no time expectations. | Nice-to-Have | Information Gap | Status is `generating` with a spinner. No time estimate. | Show approximate time based on output type and source count. E.g., "Generating... (~15s for 3 sources)". |
| 3.5 | Mind Map renders as raw Mermaid markdown text in a modal (`whitespace-pre-wrap`). No actual diagram rendering. | Critical | UX/Usability Issue | `handleViewArtifact` shows `artifact.content` in a `<div>` with `whitespace-pre-wrap`. No Mermaid rendering library. | Integrate `mermaid.js` for inline diagram rendering. Add zoom/pan controls and export-to-PNG/SVG. |
| 3.6 | Flashcards and Quiz outputs are not editable after generation. Users cannot fix errors or customize cards. | Important | Missing Functionality | Generated content is stored as a text string. No edit UI. | Add an "Edit" action on completed artifacts. For flashcards/quizzes, render an editable card list. |
| 3.7 | Flashcards always go to the first deck or create a "Workspace Flashcards" deck. Users cannot choose a target deck. | Important | UX/Usability Issue | `const deckId = decks[0].id` or creates new "Workspace Flashcards" deck. | Show a deck selector dropdown before generation, or prompt after generation. |
| 3.8 | Quiz and Flashcards use only `mediaIds[0]`. Multi-source quiz/flashcard generation is not supported. | Important | Missing Functionality | `generateQuizFromMedia(mediaIds[0], ...)` and `generateFlashcards(mediaIds[0], ...)`. | Pass all selected `mediaIds` to generate cross-source study materials. |
| 3.9 | Audio Overview TTS settings are nested under a collapsible panel within the Output Types section. They're not contextually connected to the Audio Overview button. | Nice-to-Have | UX/Usability Issue | TTS settings panel is always visible (when expanded) regardless of which output the user intends to generate. | Show TTS settings as a popover/drawer that opens when the user clicks "Audio Overview" (before generation starts), or as an inline section that appears only when hovering/focusing the Audio Overview button. |
| 3.10 | No voice preview. Users must commit to full generation to hear a voice. | Important | Missing Functionality | Voice selection via `<Select>` dropdown. No audio preview. | Add a "Preview" button next to voice selection that plays a short sample sentence. |
| 3.11 | Generated outputs cannot be sent to chat for follow-up questions. No "Discuss this" action. | Important | Missing Functionality | Artifact action buttons: View, Download, Regenerate, Delete. No "Send to chat" or "Discuss" action. | Add a "Discuss" button that injects the artifact content as context into the chat pane with a prompt like "I generated this summary. Can you elaborate on point 3?". |
| 3.12 | Delete artifact has no confirmation. One click permanently removes a potentially time-consuming generation. | Important | UX/Usability Issue | `removeArtifact(artifact.id)` called directly. | Add undo-toast or confirmation popover for artifact deletion. |
| 3.13 | Data Table outputs as markdown text. No actual table rendering, sorting, filtering, or CSV export. | Important | UX/Usability Issue | Content is raw markdown table text displayed in `whitespace-pre-wrap` modal. | Parse markdown table and render as an interactive HTML table. Add CSV/Excel export button. |
| 3.14 | Regenerate creates a new artifact rather than replacing the existing one. Over time, the outputs list accumulates duplicate versions with no version comparison. | Nice-to-Have | UX/Usability Issue | `handleGenerateOutput(artifact.type)` creates a new artifact via `addArtifact`. Old one remains. | Add option: "Replace" (overwrite in place) vs. "New version" (keep both). For "New version", enable side-by-side comparison. |
| 3.15 | Generated outputs have a fixed `max-h-64` scroll area. With many outputs, the section competes for vertical space with the Notes section. | Nice-to-Have | UX/Usability Issue | `max-h-64 overflow-y-auto` on outputs container. | Make the outputs section dynamically sized or allow resizing the split between outputs and notes. |

---

## 4. Quick Notes (QuickNotesSection)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 4.1 | Notes section is at the bottom of the Studio pane, below Output Types and Generated Outputs. Users must scroll down or collapse other sections to reach it. | Important | UX/Usability Issue | QuickNotesSection renders as the last flex child, filling remaining height. On small screens, it may be invisible without scrolling. | Make the Studio pane's three sections independently collapsible (already done). Consider making Notes the default-expanded section or giving it equal visual weight. |
| 4.2 | No "Save to notes" action on chat messages. Users cannot capture an AI response as a note without manual copy-paste. | Critical | Missing Functionality | `PlaygroundMessage` has no "Save to notes" action. No cross-pane note integration. | Add a "Save to notes" action button on each chat message that pre-populates the note content and optionally sets the title from the message context. |
| 4.3 | Keyword tagging has no auto-complete. Users must manually type keywords each time. | Nice-to-Have | UX/Usability Issue | Plain `<Input>` with comma-separated parsing. No typeahead. | Add auto-complete from previously used keywords (fetch from notes API). |
| 4.4 | Note search in the Load modal is full-text via API. But there's no way to search across workspace notes specifically (only global notes). | Nice-to-Have | Information Gap | Search calls `/api/v1/notes/search/` without workspace filtering. | Filter by `workspace_tag` when searching to show workspace-specific notes first. |
| 4.5 | Only one note can be open at a time. No note list for the current workspace. Users must use the Load modal to switch between notes. | Important | Missing Functionality | `currentNote` is a single object in the store. No workspace note list. | Add a mini note list sidebar or tabs within the Quick Notes section showing all notes for the current workspace. |
| 4.6 | Notes are plain text only. No markdown rendering, no bold/italic, no code blocks, no lists. | Important | Missing Functionality | `<TextArea>` renders plain text. No markdown preview or rich text editor. | Add a split-view or toggle between edit/preview. Use a lightweight markdown editor (e.g., `@uiw/react-md-editor`). |
| 4.7 | Version conflict message is clear but doesn't offer a "Reload latest" action. Users must manually close, reload the note, and re-edit. | Nice-to-Have | UX/Usability Issue | Error toast: "Note was modified elsewhere. Please reload and try again." | Add a "Reload" button in the toast that fetches the latest version and merges changes. |
| 4.8 | No note export. Users cannot download individual notes or bulk export from the workspace. | Nice-to-Have | Missing Functionality | No export action button. | Add "Download as .md" button in the note toolbar. |

---

## 5. Workspace Management (WorkspaceHeader)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 5.1 | Workspace switcher dropdown shows max 5 recent workspaces. No way to see all saved workspaces. | Important | UX/Usability Issue | `.slice(0, 5)` in menu items. Max 10 saved in store. | Add a "View all workspaces" option that opens a modal with full list, search, and metadata. |
| 5.2 | Workspace metadata in dropdown is limited to name and source count. No last-accessed date, no creation date. | Nice-to-Have | Information Gap | Menu item shows `workspace.name` and `(N sources)`. `lastAccessedAt` is stored but not displayed. | Show relative time ("2 hours ago") and source count in the dropdown. |
| 5.3 | Rename button is hidden until header is hovered (CSS `[header:hover_&]:opacity-100`). Users may not discover it. | Nice-to-Have | UX/Usability Issue | Pencil icon has `opacity-0` with `[header:hover_&]:opacity-100`. | Always show at reduced opacity (e.g., `opacity-40`) instead of full invisible. |
| 5.4 | No workspace duplication. Users cannot fork a research session. | Nice-to-Have | Missing Functionality | No "Duplicate" action in the workspace menu. | Add "Duplicate workspace" menu item that deep-copies sources, notes, and settings. |
| 5.5 | Workspace deletion has no confirmation dialog. The delete button in the dropdown calls `deleteWorkspace(id)` directly after `e.stopPropagation()`. | Critical | UX/Usability Issue | `handleDeleteWorkspace` calls `deleteWorkspace(id)` immediately. Deletes from `savedWorkspaces` with no undo. | Add confirmation dialog or undo-toast: "Workspace 'X' deleted. Undo?" |
| 5.6 | Switching workspaces clears all workspace-specific state. Sources, artifacts, and notes are lost because state is stored in a single Zustand store, not per-workspace storage. | Critical | Missing Functionality | `switchWorkspace` sets `...initialSourcesState, ...initialStudioState`. Comment: "A full implementation would need separate storage per workspace." | Implement per-workspace persistence. Either use separate localStorage keys per workspace ID or serialize/deserialize workspace snapshots on switch. This is the highest-priority architectural gap. |
| 5.7 | No workspace archive feature. Delete is the only removal option. | Nice-to-Have | Missing Functionality | Only `deleteWorkspace` action. | Add soft-delete/archive with ability to restore. |
| 5.8 | Workspace state (chat scroll position, collapsed panes) is not fully preserved on switch. Pane collapse state is global, not per-workspace. | Nice-to-Have | UX/Usability Issue | `leftPaneCollapsed` and `rightPaneCollapsed` are persisted globally, not per workspace. | Store pane states per workspace as part of the workspace snapshot. |

---

## 6. Cross-Pane Interaction & Information Flow

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 6.1 | No drag-and-drop from Sources to Chat. Users cannot drag a source onto the chat to ask about it specifically. | Nice-to-Have | Missing Functionality | No drag handlers on source items. Chat has no drop zone. | Add drag-to-ask: dropping a source into chat auto-selects only that source and opens a prompt. |
| 6.2 | No "Send to chat" for generated outputs. Artifacts live in StudioPane with no way to inject into conversation. | Important | Missing Functionality | No action connects artifacts to chat input/context. | Add "Discuss in chat" button on artifacts that sends content to chat as a context message. |
| 6.3 | Citation-to-source navigation is absent. When chat responses reference sources, clicking them does not highlight or scroll to the source in SourcesPane. | Critical | Missing Functionality | `PlaygroundMessage` renders citation markers but no `onCitationClick` handler is wired to workspace source navigation. | Implement citation click -> source highlight in SourcesPane (scroll to source, flash highlight, optionally open source preview). |
| 6.4 | No "Add to Notes" for generated output text. Users must view -> copy -> paste into notes. | Important | Missing Functionality | No text selection -> note action. No "Add to Notes" button on artifacts. | Add "Save to notes" action on artifacts and a text-selection context menu "Add selection to notes". |
| 6.5 | No unified search across sources, chat, and notes. Each pane has its own search (sources search, notes search), but no global search. | Nice-to-Have | Missing Functionality | Separate search in SourcesPane (client-side filter) and QuickNotesSection (Load modal API search). Chat has no search. | Add a Cmd+K / Ctrl+K global search that searches across all three domains. |
| 6.6 | The relationship between "selected sources" and chat context is clear thanks to the `ChatContextIndicator` blue tags. However, deselecting a source mid-conversation does not warn that previous answers were grounded in it. | Nice-to-Have | UX/Usability Issue | Source selection changes immediately sync via `useEffect` to `setRagMediaIds`. | Show a brief notification: "Source context changed. Previous answers may reference sources no longer selected." |
| 6.7 | Workspace switching has no visual transition. The entire page content swaps instantly. | Nice-to-Have | UX/Usability Issue | `switchWorkspace` sets new state synchronously. | Add a brief fade-out/in or progress indicator to make the context switch visually obvious. |

---

## 7. Responsive & Mobile Experience

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 7.1 | Mobile tab navigation is well-structured (Sources \| Chat \| Studio) using Ant Design Tabs with badges. | -- | -- | Good implementation. `centered` tabs with icon + label + count badges. | (No issue - well done.) |
| 7.2 | Source checkboxes (Ant `<Checkbox>`) render at default size which may be below 44px touch target on mobile. | Important | Accessibility Concern | Default Ant Design checkbox size (~16px hit area). | Increase touch area with padding wrapper or use `className` to set min touch target 44x44px on mobile. |
| 7.3 | The delete source button is invisible until hover (`opacity-0 group-hover:opacity-100`). On touch devices, hover doesn't exist - the button is permanently hidden. | Critical | UX/Usability Issue | CSS: `opacity-0 ... group-hover:opacity-100`. No touch equivalent. | Use `@media (hover: none)` to always show the delete button on touch devices, or add swipe-to-delete. |
| 7.4 | Add Source modal is 600px wide (`width={600}`). On mobile this will be constrained by viewport but Ant Design Modal's mobile handling may not be optimal. | Nice-to-Have | UX/Usability Issue | `width={600}` hardcoded. Ant Design Modal adds viewport-relative max-width. | Add responsive width: `width={isMobile ? "100%" : 600}` and use `styles={{ body: { maxHeight: '70vh' } }}` for mobile. |
| 7.5 | Drag-and-drop in the Upload tab doesn't degrade to a simple file picker button on mobile. The `Dragger` component may be hard to use on touch devices. | Important | UX/Usability Issue | `<Dragger>` renders a large drop zone. On mobile, tap works (opens file picker), but the "drag files" instruction is misleading. | Change text to "Tap to select files" on mobile. Add a visible "Browse files" button. |
| 7.6 | TTS settings panel in Studio has small `<Select>` dropdowns and a `<Slider>`. These are hard to operate accurately on mobile touch screens. | Nice-to-Have | UX/Usability Issue | Ant Design `<Slider>` and `<Select size="small">`. | Use `size="large"` variants on mobile. Increase slider track height. |
| 7.7 | Tablet drawers (Sources: 320px, Studio: 360px) may obscure the chat pane when open. Users cannot see chat while browsing sources. | Nice-to-Have | UX/Usability Issue | Drawer `styles={{ wrapper: { width: 320 } }}` on a 768px tablet leaves ~448px for chat, but the drawer overlay may cover it. | Use `mask={false}` or a slide-over that pushes content rather than overlaying. |
| 7.8 | Generated outputs with mind maps, data tables, and slides content render as plain text in modals - not optimized for small screens. | Important | UX/Usability Issue | Modal width is 600px for text content, no mobile adaptation. | Use full-screen modals on mobile (`width="100%"`, `height="100dvh"`) for viewing generated content. |

---

## 8. Performance & Perceived Speed

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 8.1 | No skeleton/loading states on initial page load. If workspace state is large, the localStorage parse + date reviver may cause a visible flash of empty content. | Important | UX/Usability Issue | `onRehydrateStorage` callback processes dates but no loading skeleton shown during rehydration. | Show skeleton placeholders in each pane until Zustand's `onRehydrateStorage` completes. |
| 8.2 | Source additions close the modal immediately after `addSource`. This is good (optimistic UI). But there's no indication that server-side processing (chunking, embedding) continues in the background. | Important | Information Gap | `closeModal()` called after source is added to store. Server processing continues silently. | Show a processing badge on the source card. When processing completes (webhook or polling), update status to "ready". |
| 8.3 | Chat streaming uses `useSmartScroll` with 120px threshold. This is appropriate. The `aria-live="polite"` on the container is good for screen readers. | -- | -- | Good implementation. | (No issue - well done.) |
| 8.4 | Generated outputs list is capped at `max-h-64` (256px) with overflow scroll. This is fine for performance but the list is not virtualized. | Nice-to-Have | UX/Usability Issue | Plain `.map()` rendering in a scrollable div. | Not an issue until ~50+ artifacts. Low priority. |
| 8.5 | Workspace store uses a custom `createWorkspaceStorage` that re-parses and re-stringifies on every `getItem`. This double-parse could be slow for large persisted states. | Nice-to-Have | UX/Usability Issue | `getItem` does `JSON.parse(value, dateReviver)` then `JSON.stringify(parsed)`. | Optimize: apply date revival in `onRehydrateStorage` only (already done), and use standard `localStorage` in `getItem`. |
| 8.6 | `ExistingTab` in AddSourceModal fetches 50 items on mount every time the modal opens. No caching. | Nice-to-Have | UX/Usability Issue | `useEffect(() => { loadMedia() }, [loadMedia])` triggers on every mount. | Cache the media list in the workspace store or use a SWR/TanStack Query pattern with stale-while-revalidate. |

---

## 9. Error Handling & Edge Cases

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 9.1 | No sources + chat attempt: Empty state correctly guides user with "Select sources from the Sources pane, then ask questions". But the chat input is still enabled, allowing general chat. This is actually a feature, not a bug. | -- | -- | Good - allows both RAG and general chat. Empty state is helpful. | Clarify in the empty state: "Or type a message for general AI chat without sources." |
| 9.2 | Batch URL ingestion fails silently for individual URLs. The `SearchTab.handleAddSelected` catches errors per URL and continues. No per-URL error feedback to user. | Important | UX/Usability Issue | `catch { // Continue with other URLs }` - silent failure. After loop, only successfully added sources are shown. | Track per-URL success/failure. After batch completion, show: "Added 3 of 5 sources. 2 failed: [URL1 - timeout], [URL2 - not found]". |
| 9.3 | No global error boundary for the workspace. If any component throws, the entire page crashes. | Important | UX/Usability Issue | No `<ErrorBoundary>` wrapper around the workspace. | Add an error boundary around `<WorkspacePlayground>` that shows a "Something went wrong" message with a "Reload workspace" button. |
| 9.4 | localStorage quota exhaustion is not handled. Large workspaces with many artifacts could exceed the ~5 MB localStorage limit. | Important | UX/Usability Issue | Zustand's `persist` middleware doesn't handle `QuotaExceededError`. | Wrap `setItem` in try-catch. On quota error, show a warning: "Workspace data is too large to save locally. Consider deleting old outputs." |
| 9.5 | Two-tab workspace race condition: Two browser tabs both modify the same workspace store in localStorage. Last-write-wins with no merge strategy. | Nice-to-Have | UX/Usability Issue | No `storage` event listener or cross-tab sync. | Add `window.addEventListener('storage', ...)` to detect external changes and prompt the user to reload. Or use `BroadcastChannel` for cross-tab sync. |
| 9.6 | Page refresh during generation loses in-progress artifacts. The artifact is saved to state as "generating" but the actual HTTP request is lost. | Important | UX/Usability Issue | Artifacts persist with status "generating" but the associated promise is gone after refresh. | On rehydration, check for artifacts with status "generating" and reset them to "failed" with message "Generation was interrupted. Click regenerate to try again." |
| 9.7 | No undo for destructive actions. Delete source, delete artifact, delete workspace, clear note - all are immediate with no undo. | Important | UX/Usability Issue | All delete/clear actions are immediate. | Implement a consistent undo pattern: toast with "Undo" button for 5 seconds. Soft-delete in store, purge after timeout. |

---

## 10. Information Gaps & Missing Functionality

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 10.1 | No collaborative workspaces. Everything is client-side localStorage. | Nice-to-Have | Missing Functionality | All state in browser localStorage. | Long-term: sync workspaces to server. Short-term: add workspace export/import as JSON. |
| 10.2 | No source annotations or highlighting. Users cannot mark up documents within the workspace. | Nice-to-Have | Missing Functionality | Sources are references only, no content viewer. | Add a source preview pane that allows highlighting and annotation. |
| 10.3 | No source comparison or cross-document analysis tools. | Nice-to-Have | Missing Functionality | No diff/compare feature. | Add "Compare sources" output type that analyzes claims across 2+ sources. |
| 10.4 | No workspace export. Users cannot export all sources, chat, notes, and outputs as a bundle. | Important | Missing Functionality | No export action. | Add "Export workspace" (ZIP with sources, chat JSON, notes MD, outputs). |
| 10.5 | No workspace templates. Every workspace starts blank. | Nice-to-Have | Missing Functionality | `initializeWorkspace(name = "New Research")` creates empty workspace. | Add template presets: "Literature Review", "Meeting Notes", "Course Study" with pre-configured output types and example prompts. |
| 10.6 | No chat branching. Users cannot explore alternate lines of inquiry from the same conversation point. | Nice-to-Have | Missing Functionality | Linear message array. | Support message variants (already present in `PlaygroundMessage` props: `variants`, `activeVariantIndex`) - extend to full conversation branching. |
| 10.7 | No output version history. Regenerating creates a new artifact with no way to compare versions. | Nice-to-Have | Missing Functionality | New artifacts are prepended to list. No versioning link between regenerated outputs. | Track `previousVersionId` on regenerated artifacts. Add "Compare versions" view. |
| 10.8 | No keyboard shortcuts for power users. No Cmd+K, no Ctrl+Shift+S, no pane toggle shortcuts. | Important | Missing Functionality | Only Enter-to-submit and Escape-to-cancel in inline editors. | Add shortcuts: Cmd+1/2/3 for pane focus, Cmd+N for new note, Cmd+Enter for submit, Cmd+Shift+N for new workspace. Show shortcut hints in tooltips. |
| 10.9 | No citation manager integration. Cannot export to Zotero, Mendeley, BibTeX. | Nice-to-Have | Missing Functionality | No export format for citations. | Add BibTeX export for workspace sources. |
| 10.10 | No token/cost budget visibility. Users don't know how much each generation costs. | Nice-to-Have | Information Gap | No cost tracking. | Display estimated token usage and cost per generation. Show cumulative workspace cost. |

---

## 11. Accessibility

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 11.1 | Chat container has proper ARIA attributes: `role="log"`, `aria-live="polite"`, `aria-relevant="additions"`, `aria-label`. | -- | -- | Good implementation at ChatPane line 219-223. | (No issue - well done.) |
| 11.2 | Pane toggle buttons have `aria-label` attributes from i18n keys. | -- | -- | Good implementation in WorkspaceHeader and SourcesPane. | (No issue.) |
| 11.3 | Collapsible sections in StudioPane use `<button>` elements with click handlers but lack `aria-expanded` attribute. Screen readers cannot determine section state. | Important | Accessibility Concern | `<button onClick={() => setStudioExpanded(!studioExpanded)}>` without `aria-expanded`. | Add `aria-expanded={studioExpanded}` and `aria-controls="studio-output-types"` with matching `id` on the content region. |
| 11.4 | Output action buttons (View/Download/Regenerate/Delete) rely on tooltips for labels. They have no `aria-label` on the `<button>` elements. | Critical | Accessibility Concern | `<button onClick={...}>` with `<Tooltip title="View">` wrapping, but no `aria-label` on the button itself. Tooltip content is not accessible to screen readers by default. | Add `aria-label` to every icon-only button. E.g., `aria-label={t("common:view", "View")} `. |
| 11.5 | Source remove button has `aria-label={t("common:remove", "Remove")}`. Good. But the button is hidden from sighted users on non-hover (opacity-0) - already addressed in 7.3. | Important | Accessibility Concern | `aria-label` is set, but `opacity-0` makes it invisible to sighted keyboard users even though it's still focusable. | Ensure `focus-visible` shows the button: add `:focus-visible { opacity: 1 }` in addition to `group-hover`. |
| 11.6 | Add Source modal uses Ant Design `<Modal>` which handles focus trapping correctly. | -- | -- | Good - Ant Design Modal has built-in focus trap. | (No issue.) |
| 11.7 | The TTS settings panel dropdowns (Select, Slider) are all keyboard-operable via Ant Design defaults. | -- | -- | Good - Ant Design components are keyboard-accessible. | (No issue.) |
| 11.8 | Color contrast for source type icons varies. Unselected sources use `text-text-muted` on `bg-surface2` which may not meet WCAG AA 4.5:1 ratio depending on theme. | Nice-to-Have | Accessibility Concern | `bg-surface2 text-text-muted` - contrast depends on CSS variable values. | Audit with browser devtools. Ensure all text/icon colors meet WCAG AA (4.5:1 normal text, 3:1 large text/UI components). |
| 11.9 | Mobile tab badges use `bg-primary` with `text-white`. The `bg-success` badge on Studio tab may have lower contrast. | Nice-to-Have | Accessibility Concern | `bg-success` color not verified for contrast with white text. | Verify `bg-success` + `text-white` meets 4.5:1 contrast. Use `bg-primary` for all badges if success color fails. |
| 11.10 | The chat scroll-to-bottom button has appropriate `aria-label` and `title`. Good. | -- | -- | Good implementation at ChatPane line 285-290. | (No issue.) |
| 11.11 | No skip-navigation links or landmark regions. The three-pane layout has no `<nav>`, `<main>`, or `role="navigation"` landmarks for screen reader navigation. | Important | Accessibility Concern | Chat pane uses `<main>` tag. Source and Studio panes use `<aside>`. But no skip links, no `role="complementary"`, no `aria-label` on the asides. | Add `aria-label` to each `<aside>` (e.g., "Sources panel", "Studio panel"). Add skip-navigation links. |

---

## Executive Summary

### Top 5 Critical Gaps That Would Block Researcher Adoption

1. **Workspace state is not preserved when switching workspaces (5.6, 5.5, 2.6)** - This is the single biggest architectural issue. Users will lose all their work (sources, chat history, outputs, notes) when they switch to a different workspace. The store comment explicitly acknowledges this: "A full implementation would need separate storage per workspace." Until this is fixed, workspace switching is destructive, not useful.

2. **No stop-generation button (2.5, 3.3)** - Long-running RAG queries and TTS generation cannot be cancelled. Users are locked out of the entire Studio pane during generation with no escape hatch. This is a fundamental interactivity requirement.

3. **Mind Map renders as raw text, not a diagram (3.5)** - The mind map is one of the 9 headline output types, but it produces raw Mermaid markup in a plain text modal. This is confusing and feels broken. Either integrate Mermaid.js rendering or remove the output type.

4. **No citation -> source navigation (2.2, 6.3)** - In a research tool, the ability to trace answers back to their sources is essential. Currently, citations in chat responses are display-only with no interactivity. This breaks the core RAG value proposition.

5. **Delete source/workspace has no undo (1.7, 5.5, 9.7)** - Multiple destructive actions (delete source, delete workspace, delete artifact, clear note) are immediate and irreversible. In a research context where users accumulate work over hours, accidental deletion is catastrophic.

### Top 5 Quick Wins (High Impact, Low Effort)

1. **Add `aria-expanded` to collapsible sections and `aria-label` to icon buttons (11.3, 11.4)** - ~30 min of work. Fixes critical accessibility gaps. Pattern: add 2-3 ARIA attributes per collapsible section and per icon-only button.

2. **Show output type descriptions in tooltips (3.2)** - ~15 min. The descriptions already exist in `OUTPUT_TYPES` config in `workspace.ts`. Just render `OutputTypeConfig.description` in the tooltip instead of repeating the label.

3. **Fix opacity-0 delete button for touch and keyboard (7.3, 11.5)** - ~15 min. Add `focus-visible:opacity-100` and `@media(hover: none) { opacity: 100 }` to the source remove button CSS.

4. **Add confirmation for workspace deletion (5.5)** - ~20 min. Wrap `deleteWorkspace` call in `Modal.confirm()`. Prevents accidental workspace loss.

5. **Reset stuck "generating" artifacts on rehydration (9.6)** - ~15 min. In `onRehydrateStorage`, map any artifact with `status === "generating"` to `status: "failed", errorMessage: "Generation was interrupted"`.

### Suggested Priority Roadmap

**Phase 1: Foundation (Critical - Do First)**
- Implement per-workspace storage so switching doesn't destroy data (5.6)
- Add stop-generation / abort capability for chat and output generation (2.5, 3.3)
- Add undo-toast pattern for destructive actions (1.7, 5.5, 3.12, 9.7)
- Fix accessibility gaps: ARIA attributes, focus-visible, touch target sizing (11.3, 11.4, 7.3, 11.5, 11.11)

**Phase 2: Research Workflow (Important - Do Second)**
- Citation -> source navigation (2.2, 6.3)
- "Save to notes" action on chat messages (4.2)
- "Discuss in chat" action on generated artifacts (3.11, 6.2)
- Integrate Mermaid.js for mind map rendering (3.5)
- Batch URL input (1.4)
- Source processing status indicators (1.8)

**Phase 3: Polish & Power Features (Nice-to-Have - Do Third)**
- RAG mode toggle (2.4)
- Voice preview for TTS (3.10)
- Keyboard shortcuts (10.8)
- Markdown support in notes (4.6)
- Interactive data table rendering (3.13)
- Global cross-pane search (6.5)
- Workspace export/import (10.4)
- Library pagination in Add Source modal (1.6)
- Output versioning and comparison (10.7, 3.14)

---

*Report generated from static code analysis of `apps/packages/ui/src/components/Option/WorkspacePlayground/` and supporting modules.*
