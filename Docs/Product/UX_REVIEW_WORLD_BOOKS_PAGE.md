# World Books Page - HCI / Design Expert Review

**Date:** 2026-02-17
**Reviewed files:** `Manager.tsx` (1,157 lines), `WorldBooksWorkspace.tsx`, `entryParsers.ts`, `useActorWorldBooks.ts`, `world_book_schemas.py`, `characters_endpoint.py` (world book routes), `LorebookDebugPanel.tsx`, `lorebook-debug.ts`

---

## 1. World Book List & Overview (WorldBooksManager table)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 1.1 | No Last Modified column | Important | Information Gap | Table shows Name, Description, Attached To, Enabled, Entries, Actions. Backend returns `last_modified` in `WorldBookResponse` but the UI discards it. | Add a "Last Modified" column with relative time (e.g., "3 hours ago"). Essential for knowing which books are stale vs. actively maintained. |
| 1.2 | No Token Budget column | Nice-to-Have | Information Gap | Token budget is only visible inside the Edit modal's collapsed Advanced Settings section. Users cannot compare budgets across books at a glance. | Add a compact "Budget" column showing `token_budget` value. Power users tuning multiple books need this visible. |
| 1.3 | Orphaned books not visually flagged | Important | UX/Usability Issue | "Attached To" shows a dash ("—") for unattached books. This is subtle and doesn't communicate urgency. There's no filter for orphaned books. | Add a subtle warning badge (e.g., amber "Unattached" tag) for books with zero character attachments. Consider a filter toggle: "Show unattached only". |
| 1.4 | "Attached To" popover requires click | Nice-to-Have | UX/Usability Issue | Popover uses `trigger="click"`. Users must click to discover attached characters. No visual affordance indicates clickability beyond cursor:pointer on tags. | Add an expand icon or underline to signal interactivity. Consider showing the count inline (e.g., "3 characters") as a clickable link. |
| 1.5 | No search or filter on the book list | Critical | Missing Functionality | Zero search/filter controls. With 10+ world books, users have no way to narrow down the list short of scrolling. | Add a search input above the table that filters by name/description. Add dropdown filters for: Enabled status, Has attachments. |
| 1.6 | No column sorting | Important | Missing Functionality | Ant Design Table supports `sorter` prop on columns but none are configured. Users cannot sort by name, entry count, or enabled status. | Enable `sorter` on at minimum: Name (alphabetical), Entry Count (numeric), Enabled (boolean). Ant Design makes this trivial. |
| 1.7 | Enabled vs. Disabled visual distinction is weak | Nice-to-Have | UX/Usability Issue | Enabled = green `<Tag>`, Disabled = default gray `<Tag>`. The gray "Disabled" tag blends with the background, especially in light themes. | Use a more distinct color for Disabled (e.g., red or amber tag) or use a dimmed/strikethrough row style for disabled books. |
| 1.8 | No bulk enable/disable for world books | Important | Missing Functionality | Bulk operations exist only at the entry level (inside drawer). No row selection or bulk actions on the world book table itself. | Add row selection checkboxes to the main table with bulk Enable/Disable/Delete actions, mirroring the entry-level pattern. |
| 1.9 | Action buttons mix icons and text | Important | UX/Usability Issue | Edit and Delete use icon-only buttons (Pen, Trash2). "Entries", "Link", "Export", "Stats" use text-only buttons. Inconsistent affordance makes some actions harder to find. | Standardize: either all icon+tooltip (with aria-labels) or all text. Recommend icon+tooltip for space efficiency with proper accessibility labels. Alternatively, use an overflow `...` menu for secondary actions (Export, Stats, Link). |
| 1.10 | Empty state doesn't explain world books | Important | UX/Usability Issue | When `status === 'success'` and `data` is empty, the table simply shows Ant Design's default "No Data" empty state. No onboarding guidance. | Show a custom empty state explaining what world books are, with a "Create your first world book" CTA button and a brief example (like the entry empty state already does). |
| 1.11 | No quick-preview of entries from the book list | Nice-to-Have | Missing Functionality | To see any entries, users must open the full entries drawer. No expandable row or hover preview. | Add an expandable row (Ant Design Table `expandable` prop) showing the first 3-5 entries inline as a lightweight preview. |

## 2. World Book Creation & Editing (Create/Edit Modals)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 2.1 | Required vs. optional fields unclear | Nice-to-Have | UX/Usability Issue | Only "Name" has `rules={[{ required: true }]}`. Description, Enabled, and all Advanced Settings lack required/optional indicators. Ant Design shows a red asterisk for required fields, but the absence of indicators on optional fields could confuse new users. | Add "(optional)" text to Description label. This clarifies intent without adding visual noise. |
| 2.2 | Advanced Settings collapsed by default with no preview | Important | UX/Usability Issue | `<details>` element hides Scan Depth, Token Budget, and Recursive Scanning. New users won't know these exist. The defaults (Scan Depth: 5 in placeholder, Token Budget: 2048 in placeholder) don't match the backend defaults (Scan Depth: 3, Token Budget: 500). | **Critical mismatch**: Backend `WorldBookCreate` defaults are `scan_depth=3, token_budget=500`. UI placeholders say "Default: 5" and "Default: 2048". Fix placeholders to match actual backend defaults. Consider showing current defaults as actual values rather than placeholders. |
| 2.3 | Tooltip help text is adequate but could be richer | Nice-to-Have | UX/Usability Issue | `LabelWithHelp` provides inline `<Tooltip>` with one-sentence explanations. These are good. However, the help icon (3.5x3.5px) is very small and may be missed. | Increase help icon to 4x4 or 4.5x4.5 for better touch/click targets. Consider adding a "What are these?" link to documentation for first-time users. |
| 2.4 | No duplicate/clone world book feature | Nice-to-Have | Missing Functionality | Users must create from scratch or import JSON. No way to duplicate an existing book as a starting template. | Add a "Duplicate" action to the world book table row actions. Clone the book with name "Copy of {original}" and all entries. |
| 2.5 | No template system | Nice-to-Have | Missing Functionality | No pre-built templates. First-time users must figure out structure on their own. | Low priority for now. The entry empty state example (Hermione/Hogwarts) partially serves this purpose. A "Template" dropdown in the Create modal could offer "Fantasy Setting", "Sci-Fi Lore", "Product Knowledge Base" starters. |
| 2.6 | Create and Edit modals have duplicated form code | Nice-to-Have | UX/Usability Issue | The Create modal (lines 487-518) and Edit modal (lines 602-633) contain nearly identical form structures. This is a maintainability concern that can lead to divergent behavior. | Extract a shared `WorldBookForm` component. Not a user-facing issue directly, but inconsistencies between create/edit forms will confuse users if they diverge. |
| 2.7 | No validation for duplicate names | Important | UX/Usability Issue | The create form does not check for name uniqueness client-side. The server returns a 409 Conflict, but the error message is generic ("Failed to create world book"). | Add client-side name uniqueness validation against the loaded book list, or at minimum surface the server's conflict error with the specific message "A world book named '{name}' already exists". |

## 3. Entry Management (Entries Drawer)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 3.1 | Drawer size calculation is incorrect | Critical | UX/Usability Issue | `size={screens.md ? "60vw" : "100%"}` — Ant Design Drawer `size` prop accepts `"default"` or `"large"`, not CSS values. Passing `"60vw"` may be silently ignored or cause unexpected behavior depending on Antd version. | Use `width={screens.md ? "60vw" : "100%"}` instead of `size`. Test on both mobile and desktop to verify correct rendering. |
| 3.2 | Entry table is not virtualized | Critical | UX/Usability Issue | Standard Ant Design `<Table>` renders all rows to DOM. With 50-100+ entries (common for detailed lorebooks), this will cause scroll jank and slow re-renders. | Use `virtual` prop on Ant Design Table (available in v5.x) or integrate `react-window`/`react-virtuoso`. For lorebook power users, 200+ entries is not uncommon. |
| 3.3 | Keyword input lacks structured editing | Important | UX/Usability Issue | Keywords are entered as a plain comma-separated `<Input>`. Users can't easily add/remove individual keywords. The `KeywordPreview` component shows parsed tags below the input but is only present in the "Add" form, not in the "Edit" modal. | Use Ant Design `<Select mode="tags">` for keyword entry. This provides visual tag chips, individual removal, and is more intuitive than comma-separated text. Add `KeywordPreview` to the Edit modal as well. |
| 3.4 | Content textarea has no character/token count | Important | Information Gap | `autoSize={{ minRows: 2, maxRows: 6 }}` but no indication of content length or estimated token cost. Users building budget-constrained lorebooks need this feedback to avoid overspending their token budget on a single entry. | Add a character count and estimated token count below the textarea (e.g., "342 chars / ~86 tokens"). Use the same estimation formula as the statistics endpoint. |
| 3.5 | Priority system is unexplained in the entry table | Important | UX/Usability Issue | Priority column shows a raw number (0-100). No visual indicator of what's "high" vs "low". The tooltip on the form says "Higher = more important" but this isn't visible in the table. | Add color coding or a progress-bar-style indicator. E.g., 0-33 = gray, 34-66 = blue, 67-100 = green. Or show as a fraction "75/100". |
| 3.6 | Appendable toggle is not explained | Important | Information Gap | Both Add and Edit forms show an "Appendable" switch with no tooltip or help text. Users have no idea what this does without external documentation. | Add a `LabelWithHelp` tooltip: "When enabled, this entry's content will be appended to other triggered content rather than standing alone. Useful for additive lore fragments." |
| 3.7 | No entry search or filter within the drawer | Important | Missing Functionality | Users must scroll through all entries to find a specific one. No search by keyword, content text, or filter by enabled status. | Add a search input at the top of the entry table that filters by keyword or content substring. Add filter toggles for Enabled/Disabled/All. |
| 3.8 | Bulk add mode separator formats not documented in UI | Important | UX/Usability Issue | The placeholder says `"One per line: keyword1, keyword2 -> content"` but `entryParsers.ts` supports `=>`, `->`, `|`, and `\t` (tab). Users won't discover all formats. | Add a help tooltip or expandable "Supported formats" section showing all separator examples. Consider adding a "Format guide" link. |
| 3.9 | Matching options hidden in collapsed `<details>` | Nice-to-Have | UX/Usability Issue | Case-sensitive, Regex, Whole-word are inside a collapsed "Matching Options" section. For power users who frequently use regex, this creates extra clicks for every entry. | Keep collapsed by default but persist the open/closed state per session. Or: show a compact inline row of toggle chips instead of a full collapsible section. |
| 3.10 | No regex validation before save | Important | UX/Usability Issue | When regex_match is enabled, the keyword is treated as a regex pattern. Invalid regex (e.g., unclosed brackets) will fail at match time, not at entry creation. | Validate regex patterns client-side on blur/submit. Show inline error "Invalid regex pattern: {error}" before allowing save. The backend has `_validate_regex_safety()` but the frontend doesn't call it. |
| 3.11 | Keyword Index is hidden in collapsed `<details>` | Nice-to-Have | UX/Usability Issue | The keyword index with conflict detection is inside a collapsed section at the bottom. Users may never discover this powerful diagnostic tool. | Make it always visible (collapsed by default is fine) but add a badge showing conflict count, e.g., "Keyword Index (2 conflicts)" to draw attention when problems exist. |
| 3.12 | No drag-and-drop reordering | Nice-to-Have | Missing Functionality | Entry order is determined by priority number only. No visual reordering. Users must manually edit priority numbers to change injection order. | Low priority. The priority number system works. Drag-and-drop would be nice but isn't essential given that priority-based ordering is the intended mechanism. |
| 3.13 | Bulk add sends entries sequentially | Important | UX/Usability Issue | Lines 1136-1141: `for (const entry of bulkParse.entries) { await tldwClient.addWorldBookEntry(...) }`. For 50+ entries, this will be very slow. | Batch the API calls (e.g., 10 at a time with `Promise.all`) or create a backend bulk-add endpoint. Show a progress indicator during bulk add. |

## 4. Bulk Operations

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 4.1 | Bulk actions are above the table, easy to miss | Nice-to-Have | UX/Usability Issue | Enable/Disable/Delete buttons are in a small bar above the entry table. The "0 selected" text is tiny (text-xs). Selection state isn't prominent. | Add a floating action bar that appears when selection > 0, similar to Gmail's selection bar. Make the selected count more prominent. |
| 4.2 | No bulk Set Priority action in the UI | Important | Missing Functionality | Backend `BulkEntryOperation` supports `set_priority` operation. The UI only offers Enable, Disable, Delete. Set Priority is missing. | Add a "Set Priority" button that opens a popover with a priority slider/input, then calls `bulkOperate` with `operation: "set_priority"`. |
| 4.3 | No bulk move to another world book | Nice-to-Have | Missing Functionality | Users cannot move entries between world books. Must delete and re-create. | Would require a backend endpoint. Nice-to-have for reorganization workflows. |
| 4.4 | No bulk import from SillyTavern/Kobold formats | Important | Missing Functionality | Import only supports the tldw JSON format (`{ world_book: {...}, entries: [...] }`). No conversion from popular lorebook formats. | Add format detection/conversion for SillyTavern V2 lorebooks (character card `data.character_book` field) and Kobold lorebooks. These are the two most common interchange formats in the character chat community. |
| 4.5 | Select-all only selects visible page | Nice-to-Have | UX/Usability Issue | If the entry table is paginated (Ant Design default), select-all only selects the current page. No "Select all N entries" option. | Add a "Select all {total} entries" link that appears when header checkbox is checked, à la Google's pattern. |

## 5. Character Attachment (Relationship Matrix Modal)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 5.1 | Matrix scales poorly beyond ~10 characters | Important | UX/Usability Issue | Each character becomes a column. With 20+ characters, the table becomes very wide and requires horizontal scrolling. Column headers are truncated at 140px. | Add character grouping or a paginated matrix. Alternatively, switch to a list-based view for large character counts: "For each world book, show a multi-select dropdown of characters." |
| 5.2 | No visual distinction between new and existing attachments | Nice-to-Have | UX/Usability Issue | All checkboxes look the same. Users can't tell which attachments were pre-existing vs. just toggled in this session. | Highlight newly toggled checkboxes (e.g., blue ring for just-attached, amber for just-detached) until the modal is closed. |
| 5.3 | Per-attachment priority and enabled not settable from matrix | Important | Information Gap | `CharacterWorldBookAttachment` schema supports `enabled` and `priority` per attachment. The matrix only provides on/off toggle. Users cannot set per-character priority from the matrix. | Add a right-click or hover menu on checked cells: "Set priority", "Disable attachment". Or show priority as a small number inside the checkbox cell. |
| 5.4 | Single-book attachment modal duplicates functionality | Nice-to-Have | UX/Usability Issue | The "Link" button on each row opens a per-book attachment modal with a Select dropdown and Detach list. The Relationship Matrix modal does the same thing but for all books at once. Two paths to the same outcome. | Keep both but consider making the per-book modal a "quick attach" shortcut with a link to "Open full matrix" for advanced management. Reduces confusion about which tool to use. |
| 5.5 | Matrix toggle has no success/failure toast | Nice-to-Have | UX/Usability Issue | `handleMatrixToggle` calls attach/detach but provides no visual feedback beyond the checkbox state change. If the API call fails, the `onError` notification fires, but success is silent. | Add a brief success notification or at minimum a visual checkmark animation on toggle. The individual "Link" modal shows `notification.success({ message: 'Attached' })` but the matrix doesn't. |

## 6. Import/Export

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 6.1 | Import format is undocumented | Important | Information Gap | The import modal says "Import World Book (JSON)" but doesn't describe the expected format. Users must guess or export first to see the structure. | Add a "Format help" expandable section showing the expected JSON structure: `{ world_book: { name, description, ... }, entries: [{ keywords: [...], content: "..." }] }`. Or add a link to documentation. |
| 6.2 | Import preview is minimal | Nice-to-Have | UX/Usability Issue | Preview shows name, entry count, and conflict warning. No preview of actual entries or settings. | Add an expandable section in the preview showing the first 5 entries (keywords + content preview) and the world book settings (scan_depth, token_budget, etc.). |
| 6.3 | No SillyTavern/Kobold import support | Important | Missing Functionality | Only tldw's native JSON format is supported. Character chat users commonly have lorebooks in SillyTavern V2 card format or Kobold World Info format. | Add client-side format detection and conversion. SillyTavern lorebooks use `data.character_book.entries[]` with fields like `key`, `content`, `selective`, `constant`. Map these to tldw's schema. |
| 6.4 | Export is single-book only | Nice-to-Have | Missing Functionality | Export button on each row exports one book. No way to export all books at once or export selected books. | Add a "Export All" button to the header bar or support multi-select export. |
| 6.5 | Merge-on-conflict behavior is unclear | Important | UX/Usability Issue | The "Merge on conflict" checkbox has no explanation. Does it merge entries? Replace entries? Append entries? The backend `WorldBookImportResponse` says "Whether merged with existing book" but doesn't detail the strategy. | Add a tooltip: "When enabled, if a world book with the same name already exists, entries from the import will be added to the existing book. Existing entries are not removed or modified." (Verify this matches actual backend behavior.) |
| 6.6 | Native `<input type="file">` is unstyled | Nice-to-Have | UX/Usability Issue | The file picker uses a raw `<input type="file">` element. It looks out of place with the rest of the Ant Design UI. | Wrap in an Ant Design `<Upload>` component or a styled drag-and-drop zone for consistency. |

## 7. Statistics Modal

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 7.1 | Statistics are read-only and not actionable | Important | UX/Usability Issue | The modal shows 11 statistics in a `<Descriptions>` component. Users can see "3 disabled entries" but can't click to filter to them. Pure information display with no interaction. | Make statistics clickable: "3 disabled entries" opens the entries drawer filtered to disabled. "5 regex entries" opens filtered to regex entries. |
| 7.2 | No cross-book statistics | Nice-to-Have | Information Gap | Statistics are per-book only. No way to see aggregate stats across all books, or keyword overlap between books. | Add a "Global Statistics" button that shows total entries, total keywords, cross-book keyword conflicts, and aggregate token budget. |
| 7.3 | Estimated token count methodology unclear | Nice-to-Have | Information Gap | "Estimated Tokens" is shown without explaining the tokenizer or estimation method. Backend uses `count_tokens()` but the user doesn't know if this is cl100k, GPT-4 tokenizer, or character-based approximation. | Add a small note: "Estimated using {tokenizer_name}" or "~4 characters per token". |
| 7.4 | No budget utilization comparison | Important | Information Gap | Statistics show total content length and estimated tokens but don't compare against the world book's token budget. Users can't tell if their entries will fit within budget. | Add "Token Budget: {budget}" and "Utilization: {estimated_tokens}/{budget} ({percentage}%)" with a visual progress bar. Highlight in red if estimated tokens exceed budget. |

## 8. Cross-Feature Integration

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 8.1 | No navigation from character page to world books | Important | Missing Functionality | Character pages and world books page are separate with no cross-linking. Users must manually navigate between them. | Add a "World Books" section to the character detail page showing attached books with quick links. Add "View character" links in the attachment popover. |
| 8.2 | LorebookDebugPanel exists but is not linked from world books page | Important | Information Gap | `LorebookDebugPanel.tsx` provides excellent runtime diagnostics (entries matched, tokens used, budget status, keyword conflicts) but is only accessible from within an active chat session. The world books management page has no reference to it. | Add a "Test matching" button to the world books page that opens a simplified version of the debug panel. Allow users to paste sample text and see which entries would fire. |
| 8.3 | processWorldBookContext API exists but isn't exposed in world books UI | Critical | Missing Functionality | The backend has a `ProcessContextRequest`/`ProcessContextResponse` with full diagnostics. `TldwApiClient` has `processWorldBookContext()`. This is the most powerful debugging tool for lorebook authors, but it's only accessible through `LorebookDebugPanel` during a live chat. | Add a "Test Keywords" panel to the entries drawer or a standalone modal. Input: sample chat text. Output: matched entries, token usage, budget status. This is the single most impactful feature for lorebook authoring quality. |
| 8.4 | Injection logs available via `getChatLorebookDiagnostics` but not surfaced | Nice-to-Have | Information Gap | Full per-turn injection diagnostics exist and can be exported from `LorebookDebugPanel`. But users must know to open the debug panel during a chat. | Add a "Lorebook Activity" tab or section to the chat session view showing which entries fired per turn. |

## 9. Responsive & Mobile Experience

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 9.1 | Main table overflows on mobile | Critical | UX/Usability Issue | The 7-column table (icon, Name, Description, Attached To, Enabled, Entries, Actions with 6 buttons) will overflow on screens < 768px. No responsive column hiding or card layout. | On mobile (< md breakpoint): hide Description and Attached To columns. Collapse action buttons into a dropdown/overflow menu. Or switch to a card-based layout for mobile. |
| 9.2 | Entries drawer is full-width on mobile | Nice-to-Have | UX/Usability Issue | `screens.md ? "60vw" : "100%"` correctly goes full-width on mobile. However, the entry table inside the drawer is still a full table with 5 columns, which may be cramped. | On mobile, hide the Priority and Enabled columns from the entry table. Show them only in the edit modal. |
| 9.3 | Action button touch targets are too small | Important | Accessibility Concern | Icon-only buttons (`type="text" size="small"`) render at approximately 24-28px. Touch targets should be >= 44px per WCAG/Apple HIG guidelines. | Increase `size` to `"middle"` on mobile breakpoints, or add padding to ensure 44px minimum touch area. |
| 9.4 | Character matrix is unusable on mobile | Critical | UX/Usability Issue | The matrix modal at `width="90vw"` displays a grid with potentially many columns. On a 375px phone, each column gets ~30px. Checkboxes become untappable. | On mobile, replace the matrix with a list view: for each world book, show a multi-select dropdown of characters. Or paginate the matrix to show 3-4 characters at a time. |
| 9.5 | Modals may not be scrollable on short viewports | Nice-to-Have | UX/Usability Issue | The Create/Edit modals with expanded Advanced Settings and the Statistics modal with 11 rows could exceed viewport height on short screens (e.g., landscape mobile). | Ensure all modals use `style={{ maxHeight: '80vh', overflow: 'auto' }}` or Ant Design's built-in scroll support. |

## 10. Error Handling & Edge Cases

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 10.1 | Entry list doesn't paginate or virtualize | Critical | UX/Usability Issue | All entries are fetched and rendered at once. A world book with 500 entries will load all into DOM. | See 3.2. Implement virtualization or server-side pagination (the backend already returns `total` count). |
| 10.2 | Import error messages are generic | Important | UX/Usability Issue | `catch (err) { setImportError(err?.message \|\| 'Invalid JSON') }`. JSON parse errors show the raw parser message which may be cryptic. Missing field errors show "Invalid file: missing world_book.name" which is good. | Improve error messages for common cases: "File is not valid JSON (check for trailing commas)", "File is missing the 'world_book' field", "File is missing entries (found 0 entries)". |
| 10.3 | No optimistic locking in UI for concurrent edits | Important | UX/Usability Issue | Backend `WorldBookResponse` includes a `version` field for optimistic locking, and the `update_world_book` endpoint doesn't currently require `expected_version`. Two users editing the same book will silently overwrite each other. | Pass `version` to the update request. Show a "This world book was modified by someone else" error on 409 Conflict. This is particularly important for collaborative scenarios. |
| 10.4 | Delete undo timer is client-side only | Important | UX/Usability Issue | The 10-second undo grace period uses `setTimeout` (line 437). If the user closes the tab or navigates away, the timer fires on `useEffect` cleanup (line 320-325 clears timers on unmount) — meaning navigation cancels the delete. But a page refresh after the timer fires but before cleanup would lose the pending delete state. | This is an acceptable trade-off. Document the behavior: "Navigating away cancels pending deletions." Consider adding a "Pending deletions" indicator if any timers are active. |
| 10.5 | No handling of character deletion with attached world books | Nice-to-Have | UX/Usability Issue | If a character is deleted, the "Attached To" column will show stale data until the query refetches. No explicit handling of orphaned attachments. | The attachment query refetch on `invalidateQueries` should handle this. Consider adding a "Clean up orphaned attachments" option in the statistics or a global maintenance action. |
| 10.6 | Recursive scanning circular reference not warned | Nice-to-Have | Missing Functionality | Backend has `MAX_RECURSIVE_DEPTH` protection (from `constants.py`). But the UI doesn't warn users about potential circular references when enabling recursive scanning. | Add a warning banner when recursive scanning is enabled: "Recursive scanning can cause entries to trigger each other. The system limits recursion to {MAX_RECURSIVE_DEPTH} levels." |

## 11. Information Gaps & Missing Functionality

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 11.1 | No keyword testing/debugging in the management UI | Critical | Missing Functionality | The most common lorebook authoring workflow is: write entry -> test if it triggers -> adjust keywords. Currently, testing requires starting an actual chat session and checking the LorebookDebugPanel. | Build a "Test Match" panel (see 8.3). This is the #1 missing feature for lorebook authors. |
| 11.2 | No entry groups/folders | Important | Missing Functionality | All entries are in a flat list. Lorebooks for complex worlds often have natural groupings (Geography, Characters, History, Magic System). | Add an optional "group" or "category" tag to entries. Filter by group in the entry table. This requires a backend schema change but significantly improves organization for large lorebooks. |
| 11.3 | No entry versioning | Nice-to-Have | Missing Functionality | Backend tracks `last_modified` and `version` on world books but not on individual entries. Users can't see change history or roll back entry edits. | Low priority. Entry-level versioning is complex and rarely needed. Focus on world-book-level export as the "backup" mechanism. |
| 11.4 | No AI-assisted entry generation | Nice-to-Have | Missing Functionality | Users must manually write all lore content. No integration with the chat/LLM APIs to generate entries from descriptions. | Add a "Generate with AI" button that takes a topic/description and generates keyword-content pairs. This leverages existing LLM infrastructure and would be a strong differentiator. |
| 11.5 | No token budget visualization | Important | Missing Functionality | Users can't preview how close they are to the token budget in a typical conversation scenario. The statistics show total tokens but not budget utilization. | Add a budget visualization bar to both the statistics modal and the entries drawer header. "123/500 tokens used (24.6%)". Color-code: green < 70%, amber 70-90%, red > 90%. |
| 11.6 | No relationship mapping between entries | Nice-to-Have | Missing Functionality | Entries that reference each other (via recursive scanning) have no visual connection. Users can't see the "dependency graph" of their lore. | Long-term feature. A simple version: show "Referenced by" links when an entry's content contains keywords from other entries. |

## 12. Accessibility

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 12.1 | Icon-only buttons have aria-labels (partial) | Important | Accessibility Concern | Edit and Delete buttons on the main table have `aria-label="Edit world book"` and `aria-label="Delete world book"`. Entry-level Edit/Delete also have labels. But "Entries", "Link", "Export", "Stats" text buttons lack explicit aria-labels (they have visible text, which serves as their label, so this is acceptable). | Adequate for text-labeled buttons. Ensure all icon-only buttons consistently have aria-labels. The current implementation is mostly good. |
| 12.2 | Drawer focus management untested | Important | Accessibility Concern | Ant Design Drawer should handle focus trapping automatically. However, with the complex form inside (entry table, modals within drawer), focus order may be unpredictable. The `destroyOnHidden` prop helps by removing DOM elements on close. | Test with screen reader and Tab key navigation. Verify: (1) Focus moves to drawer on open, (2) Focus is trapped within drawer, (3) Focus returns to trigger button on close. |
| 12.3 | `<details>/<summary>` elements may not announce properly | Important | Accessibility Concern | "Advanced Settings" and "Matching Options" use native `<details>/<summary>`. Screen reader support varies. Some screen readers announce the expanded/collapsed state, others don't. | Add `aria-expanded` attribute to `<summary>` elements, or replace with Ant Design Collapse component which has built-in ARIA support. |
| 12.4 | Keyword conflict detection not announced to screen readers | Important | Accessibility Concern | Red-colored conflict tags in the Keyword Index are visual-only. Screen readers won't convey that a keyword has conflicts. | Add `aria-label` to conflict tags: `aria-label="{keyword}: conflict - {variantCount} content variations"`. Or use `role="alert"` for a summary of conflicts. |
| 12.5 | Toggle switches lack descriptive labels | Nice-to-Have | Accessibility Concern | Enabled/Disabled toggles in forms use `<Switch>` with only a form label. The toggle state ("on"/"off") is announced by Ant Design's Switch component, but the meaning ("enabled" vs "disabled") may not be clear without the visual label context. | Add `checkedChildren="On" unCheckedChildren="Off"` to Switch components for screen reader clarity. |
| 12.6 | Matrix checkbox grid keyboard navigation | Important | Accessibility Concern | The character attachment matrix is a table of checkboxes. Tab navigation would require pressing Tab through every checkbox (potentially 100+). No arrow-key grid navigation. | Implement `role="grid"` with arrow-key navigation on the matrix table, or add a "Skip to next world book row" keyboard shortcut. |
| 12.7 | Color contrast for muted text | Nice-to-Have | Accessibility Concern | `text-text-muted` class is used extensively. Depending on the theme's actual color value, this may not meet WCAG AA 4.5:1 contrast ratio. | Audit `text-text-muted` against background colors in both light and dark themes. Ensure >= 4.5:1 for body text and >= 3:1 for large text. |
| 12.8 | Form validation errors not linked via aria-describedby | Important | Accessibility Concern | Ant Design Form.Item uses `rules` for validation and renders error messages below fields. By default, Ant Design v5 should link errors via `aria-describedby`, but this should be verified. | Test that validation error messages are announced when a field receives focus. If not, add explicit `aria-describedby` linking. |

---

## Executive Summary

### Top 5 Critical Gaps That Would Block User Adoption

1. **No keyword testing/debugging in the management UI (11.1, 8.3)** — Lorebook authors need a "Test Match" feature to validate their keyword configurations against sample text without starting a live chat. The backend API (`processWorldBookContext`) already exists; it just needs a UI.

2. **No search or filter on the world book list (1.5)** — With more than a handful of world books, the page becomes unmanageable. This is table-stakes functionality for any list management interface.

3. **Entry table not virtualized — performance cliff at 50+ entries (3.2, 10.1)** — Power users with detailed lorebooks will hit DOM rendering limits quickly. The page will feel broken for the most engaged users.

4. **Mobile experience is broken for core workflows (9.1, 9.4)** — The main table and character matrix are unusable on mobile. Given that character chat is popular on mobile devices, this blocks a significant user segment.

5. **Default values mismatch between UI and backend (2.2)** — UI says "Default: 5" for scan depth but backend defaults to 3. UI says "Default: 2048" for token budget but backend defaults to 500. This will cause silent misconfiguration.

### Top 5 Quick Wins (High Impact, Low Effort)

1. **Fix default value mismatches (2.2)** — Change placeholder text in Create/Edit forms to match backend defaults (scan_depth: 3, token_budget: 500). 5-minute fix.

2. **Add column sorting to the main table (1.6)** — Add `sorter` prop to Name, Entry Count, Enabled columns. Ant Design provides this out of the box. ~15 minutes.

3. **Add a search input above the world book table (1.5)** — Simple client-side text filter on name/description. ~30 minutes.

4. **Fix drawer `size` to `width` prop (3.1)** — Change `size=` to `width=` on the Entries Drawer for correct responsive sizing. 2-minute fix.

5. **Add LabelWithHelp to Appendable toggle (3.6)** — Wrap the "Appendable" label with a tooltip explanation. ~5 minutes.

### Suggested Priority Roadmap

**Phase 1 — Fixes and Foundation (1-2 days)**
- Fix default value mismatches (2.2)
- Fix drawer width prop (3.1)
- Add search and sorting to world book table (1.5, 1.6)
- Add Appendable tooltip (3.6)
- Add content character/token count in entry form (3.4)
- Fix bulk add to batch API calls (3.13)

**Phase 2 — Power User Features (3-5 days)**
- Build "Test Match" panel using processWorldBookContext API (11.1, 8.3)
- Virtualize entry table (3.2)
- Add entry search/filter within drawer (3.7)
- Add token budget utilization to statistics (7.4, 11.5)
- Add SillyTavern import format support (6.3, 4.4)
- Replace keyword input with tag-style Select (3.3)

**Phase 3 — Mobile and Accessibility (2-3 days)**
- Responsive table layout for mobile (9.1)
- Mobile-friendly matrix alternative (9.4)
- Touch target sizing (9.3)
- ARIA improvements for details/summary, conflict tags, matrix grid (12.3, 12.4, 12.6)
- Form validation aria-describedby audit (12.8)

**Phase 4 — Polish and Differentiation (ongoing)**
- Empty state with onboarding guidance (1.10)
- Duplicate/clone world book (2.4)
- Entry groups/categories (11.2)
- AI-assisted entry generation (11.4)
- Cross-book navigation from character pages (8.1)
- Actionable statistics (7.1)
- Bulk operations on world books (1.8)
