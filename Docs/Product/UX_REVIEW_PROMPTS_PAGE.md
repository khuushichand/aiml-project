# UX / HCI Review: Prompts Page

**Reviewer perspective**: Prompt engineering power user + HCI/design expert
**Date**: 2026-02-17
**Scope**: `/prompts` page - Four tabs (Custom, Copilot, Studio, Trash), CRUD operations, server sync, and full Prompt Studio sub-app
**Codebase version**: `dev` branch
**Key files analyzed**:
- Frontend: `apps/packages/ui/src/components/Option/Prompt/index.tsx` (1959 lines), `PromptDrawer.tsx` (521), `PromptActionsMenu.tsx` (136), `SyncStatusBadge.tsx` (132), `ProjectSelector.tsx` (109), `Studio/StudioTabContainer.tsx` (269), `Studio/Prompts/ExecutePlayground.tsx` (~200), `Studio/QueueHealthWidget.tsx` (141)
- Backend: `tldw_Server_API/app/api/v1/endpoints/prompts.py` (1210 lines)
- Services: `apps/packages/ui/src/services/prompt-sync.ts` (693 lines)

---

## 1. Custom Prompts Tab

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 1.1 | Search is client-side only; backend FTS5 search API (`POST /prompts/search`) with pagination and field-level filtering is unused. | Critical | Missing Functionality | `index.tsx:685-703` — `filteredData` uses `field.toLowerCase().includes(q)` on all loaded prompts. Backend `prompts.py:379-413` has `search_all_prompts()` with FTS5, `search_fields` param, `page`/`results_per_page`, and relevance scoring. | Wire the search input to call `POST /prompts/search` with debounce (300ms). Fall back to client-side for offline mode. This enables server-side pagination and relevance ranking. |
| 1.2 | No pagination — all prompts loaded into memory via `getAllPrompts()`. | Important | UX/Usability Issue | `index.tsx:132-135` — `useQuery({ queryKey: ["fetchAllPrompts"], queryFn: getAllPrompts })` fetches entire prompt list. No `page` or `limit` parameter. Table renders all `filteredData` at once. | Add cursor-based or page-based pagination. Backend search already supports `page` and `results_per_page` (default 20, max 100). For local IndexedDB, use Dexie's `.offset().limit()`. |
| 1.3 | Content preview truncated to 2 lines with no expand affordance. | Important | Information Gap | `index.tsx:1227` — `<span className="line-clamp-2">{systemText}</span>`. Same at line 1237 for user text. No "show more" button or expandable row. | Add an inline "Show more" toggle or enable row click to expand the preview in-place. Alternatively, show full content on hover via a popover. |
| 1.4 | No column sorting — fixed order: favorites first, then `createdAt` DESC. | Important | Missing Functionality | `index.tsx:706-710` — `items.sort((a, b) => Number(!!b.favorite) - Number(!!a.favorite) || (b.createdAt || 0) - (a.createdAt || 0))`. Ant Design `Table` has built-in `sorter` prop support but it's not configured on any column. | Add `sorter` to name, type, and date columns. Maintain favorites-first as the default but let users override with column header clicks. |
| 1.5 | No "Last Modified" column despite `updatedAt` existing in data. | Important | Information Gap | Table columns (`index.tsx:1154-1387`) include: favorite, title, content preview, keywords, type, sync, actions — but no date columns. All prompts have `createdAt` and `updatedAt` fields. | Add a "Modified" column rendering `updatedAt` as relative time (e.g., "2h ago"). Make it sortable. Consider also showing `createdAt` in a tooltip. |
| 1.6 | Export is JSON-only; backend supports CSV and Markdown formats. | Important | Missing Functionality | `index.tsx:734-754` — `triggerExport()` calls `exportPrompts()` (IndexedDB dump) and wraps result in `JSON.stringify`. Backend `prompts.py:518-574` has `GET /export` with `export_format: str = Query("csv", enum=["csv", "markdown"])` supporting CSV and Markdown with keyword filtering and field selection. | Add a format selector dropdown next to the Export button: JSON (local), CSV (server), Markdown (server). Use the backend `GET /export` endpoint for CSV/Markdown formats. |
| 1.7 | Import shows generic success; no per-prompt result details. | Nice-to-Have | Information Gap | `index.tsx:837-844` — success notification uses static i18n key `addSuccessDesc`. No count of imported/skipped/failed prompts. `importPromptsV2` returns but the result isn't inspected. | Show detailed import results: "Imported 12 prompts, 3 skipped (duplicate names), 1 failed (invalid format)". Return structured results from `importPromptsV2`. |
| 1.8 | Bulk ops limited to export and delete; no bulk keyword/sync operations. | Important | Missing Functionality | `index.tsx:984-1025` — Bulk action bar shows only "Export selected" and "Delete selected" buttons. No bulk keyword assignment, bulk push-to-server, or bulk favorite toggle. | Add bulk actions: "Add keyword", "Push to server", "Toggle favorite". These are common prompt library management operations. |
| 1.9 | "Use in Chat" modal is well-designed with clear system/quick/both options. | -- | Strength | `index.tsx:1857-1941` — Three-option modal with visual previews: "Use as System Instruction" (with Computer icon), "Insert as Message Template" (with Zap icon), "Use Both (Recommended)" (with Layers icon). Each shows a truncated preview of the prompt content. | (No issue — well done. Clear information hierarchy, good iconography, and the "Recommended" option is visually emphasized with a primary border.) |
| 1.10 | Tag filter uses OR logic but doesn't communicate this to the user. | Nice-to-Have | Information Gap | `index.tsx:680-684` — `items.filter((p) => (getPromptKeywords(p) || []).some((t: string) => tagFilter.includes(t)))`. The `.some()` call implements OR logic (match any selected keyword), but the UI doesn't indicate this. | Add a small label or toggle: "Match any keyword" / "Match all keywords". Default to OR but let users switch to AND for narrower results. |

---

## 2. Prompt Drawer (Create/Edit)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 2.1 | No character count or token estimate in the editor. | Important | Information Gap | `PromptDrawer.tsx:372-378` and `436-442` — System and user prompt `Input.TextArea` fields with `autoSize` but no character/token counter. Prompt engineers need to know prompt length for context window budgeting. | Add a character count below each textarea (e.g., "1,234 chars / ~308 tokens"). Use a simple `text.length / 4` heuristic or tiktoken for accurate counts. Show warning when approaching common model limits. |
| 2.2 | Template variable highlighting and validation missing despite backend support. | Important | Missing Functionality | `PromptDrawer.tsx:436-442` — Plain `Input.TextArea` with no syntax highlighting. Backend `prompts.py:45,69-75` has `_TEMPLATE_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")` and `_extract_template_variables()` for `{{variable}}` syntax. The Execute Playground (`ExecutePlayground.tsx:61-64`) also extracts variables but only within Studio. | Add inline highlighting for `{{variable}}` patterns in the textarea (or use a code editor component). Show extracted variables as chips below the field. Validate that referenced variables exist when template is used. |
| 2.3 | Few-shot examples are read-only — user must go to Studio to edit. | Important | UX/Usability Issue | `PromptDrawer.tsx:140-158` — When `fewShotExamples` exist, renders only a count and a "Edit examples in Prompt Studio" hint text. No inline editor. | Add an inline collapsible editor for few-shot examples (input/output pairs) directly in the drawer. Allow add/remove/reorder. This removes the Studio round-trip for a common task. |
| 2.4 | Version history inaccessible from Custom tab drawer. | Important | Missing Functionality | `PromptDrawer.tsx:161-170` — Shows `versionNumber` as static text: "Version {{version}}". No link to version history. The Studio tab has a `VersionHistoryDrawer.tsx` component but it's only accessible from `StudioPromptsTab`. | Add a "View history" link next to the version number that opens the `VersionHistoryDrawer` or navigates to the Studio tab with the prompt pre-selected. Only show for synced prompts with `serverId`. |
| 2.5 | Draft auto-save uses a single global key, risking cross-prompt contamination. | Important | UX/Usability Issue | `PromptDrawer.tsx:51-56` — `useFormDraft({ storageKey: "tldw-prompt-drawer-draft", formType: mode, editId: initialValues?.name, ... })`. The `editId` is based on `initialValues?.name` which could collide across prompts with similar names, and the base `storageKey` is global. | Use `storageKey: \`tldw-prompt-drawer-draft-\${editId || 'new'}\`` where `editId` is the prompt's unique ID (not name). This prevents draft contamination when switching between prompts. |
| 2.6 | Drawer fixed at 480px width — overflows on mobile viewports. | Nice-to-Have | UX/Usability Issue | `PromptDrawer.tsx:234` — `<Drawer styles={{ wrapper: { width: 480 } }}>`. On screens narrower than 480px, the drawer content overflows or gets clipped by Ant Design's viewport constraint. | Use responsive width: `width={window.innerWidth < 640 ? '100%' : 480}` or Ant Design's `size` prop. On mobile, the drawer should be full-width. |
| 2.7 | No unsaved changes warning on close. | Important | UX/Usability Issue | `PromptDrawer.tsx:236-237` — `onClose={onClose}` with no dirty-check. In `index.tsx:1792-1796`, `onClose` simply sets `setDrawerOpen(false)`. Auto-save draft exists but the user isn't warned that closing discards uncommitted changes. | Check if form is dirty (`form.isFieldsTouched()`) on close. If dirty, show a confirmation: "You have unsaved changes. Close anyway?" with options to save, discard, or cancel. |

---

## 3. Sync & Conflict Management

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 3.1 | **No conflict resolution UI** despite full backend support — `resolveConflict()` is never called from any UI component. | Critical | Missing Functionality | `prompt-sync.ts:604-647` — `resolveConflict(localId, resolution)` implements three modes: `keep_local` (push local to server), `keep_server` (pull server to local), `keep_both` (unlink and re-push). `getConflictInfo()` at line 581-598 retrieves both local and server versions for comparison. `SyncStatusBadge.tsx:57-63` renders a red "Conflict" tag when `syncStatus === "conflict"`. However, clicking the conflict badge does nothing — no modal, no drawer, no resolution flow. The `PromptActionsMenu.tsx` has push/pull/unlink actions but no "Resolve conflict" option. | Add a `ConflictResolutionModal` that: (1) shows side-by-side diff of local vs. server prompts using `getConflictInfo()`, (2) offers three buttons: "Keep Mine", "Keep Server", "Keep Both", (3) calls `resolveConflict()` with the chosen mode. Trigger this modal when user clicks the red conflict badge or from the actions menu. |
| 3.2 | Auto-sync failures are silent — no user-facing notification when project resolution fails. | Important | UX/Usability Issue | `index.tsx:298-327` — `syncPromptAfterLocalSave()` catches errors and returns `{ attempted: true, success: false, error: ... }`. The caller at `index.tsx:538-548` shows a warning notification only after explicit save. But `autoSyncPrompt()` in `prompt-sync.ts:211-252` silently marks prompts as `syncStatus: 'pending'` when `resolveAutoSyncProjectId()` fails (line 229-241), with the error message going into the return value that nobody displays. | Surface sync failures in a toast notification. When `autoSyncPrompt` returns `success: false`, show: "Sync failed: {error}. Your changes are saved locally." Add a persistent badge on the Prompts tab showing count of pending syncs. |
| 3.3 | No batch sync operations — push/pull one prompt at a time. | Important | Missing Functionality | `PromptActionsMenu.tsx:41-60` — Push/pull/unlink actions are per-prompt only. No "Sync all pending" or "Pull all outdated" bulk action. `prompt-sync.ts:656-668` has `getAllPromptsWithSyncStatus()` that returns sync state for all prompts, but it's unused in any UI. | Add a "Sync all" button in the toolbar when pending prompts exist. Show a progress indicator: "Syncing 3 of 12 prompts..." Use `getAllPromptsWithSyncStatus()` to identify actionable prompts. |
| 3.4 | Conflict detection is timestamp-only — may produce false positives. | Nice-to-Have | UX/Usability Issue | `prompt-sync.ts:558-561` — `const hasConflict = local.serverUpdatedAt !== serverUpdatedAt && (local.updatedAt || 0) > (local.lastSyncedAt || 0)`. This timestamp comparison can trigger false conflicts when the server timestamp changes due to metadata-only updates (e.g., keyword normalization) while content is identical. | Add content hash comparison (`SHA256(system_prompt + user_prompt)`) alongside timestamps. Only flag as conflict when both timestamps differ AND content hashes differ. |
| 3.5 | ProjectSelector has no inline project creation — user must switch to Studio tab first. | Nice-to-Have | Missing Functionality | `ProjectSelector.tsx:60-63` — When `projects.length === 0`, shows static `Empty` component with text "No projects available. Create a project in Prompt Studio first." No "Create project" button. | Add a "Create Project" button in the empty state that calls `createProject()` directly. Or add a small "+" button next to the Select dropdown. |
| 3.6 | Sync column hidden when offline — loses context about sync state. | Nice-to-Have | UX/Usability Issue | `index.tsx:1298-1312` — `...(isOnline ? [{ title: "Sync", key: "syncStatus", ... }] : [])`. When offline, the entire sync column disappears, removing visual cues about which prompts are synced/local/pending. | Keep the sync column visible when offline but with a muted appearance. Show the last known sync status with a "Sync unavailable (offline)" tooltip. This preserves context. |

---

## 4. Copilot Tab

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 4.1 | `{text}` placeholder requirement is undocumented until validation fails. | Important | Information Gap | `index.tsx:1827-1836` — Copilot edit form has a validator: `if (value && value.includes("{text}")) { return Promise.resolve() }` that rejects prompts without `{text}`. But the form field has no hint text or placeholder explaining the requirement. The error message is from `t("managePrompts.form.prompt.missingTextPlaceholder")` which fires only on submit. | Add a helper text below the textarea: "Must include `{text}` — this placeholder is replaced with the selected text when the copilot runs." Also highlight the `{text}` pattern inline. |
| 4.2 | No "Copy to Custom" action to fork copilot prompts. | Important | Missing Functionality | `index.tsx:1496-1514` — Copilot table actions column has only an edit button (`<Pen>`). No "Duplicate to Custom", "Copy to clipboard", or "Use in Chat" actions. Users who want to iterate on a copilot prompt must manually recreate it in the Custom tab. | Add a "Copy to Custom" action that creates a new custom prompt pre-filled with the copilot's content. Also add a "Copy to clipboard" action for quick use outside the app. |
| 4.3 | No search or filter on copilot table. | Nice-to-Have | Missing Functionality | `index.tsx:1473-1520` — Copilot table renders all items with no search input, type filter, or keyword filter. Unlike the Custom tab which has a full filter toolbar. | Add a search bar and keyword filter to the copilot table header, consistent with the Custom tab's UX pattern. |
| 4.4 | `setAllCopilotPrompts([single])` may accidentally replace all prompts. | Important | UX/Usability Issue | `index.tsx:628-633` — `updateCopilotPrompt` calls `setAllCopilotPrompts([{ key: data.key, prompt: data.prompt }])` with a single-element array. If the API interprets this as "set ALL copilot prompts to this list", editing one prompt would delete all others. | Verify the `setAllCopilotPrompts` API contract. If it's a full replacement, change to a per-prompt update endpoint. If it's an upsert, rename the function to `upsertCopilotPrompt` for clarity. |

---

## 5. Trash Tab

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 5.1 | No search in trash. | Nice-to-Have | Missing Functionality | `index.tsx:1525-1663` — Trash tab renders a table with name, deleted date, and actions (restore/permanent delete). No search input or filter. Users with many deleted prompts cannot find specific items. | Add a search input to the trash tab that filters by prompt name. Reuse the same search component pattern from the Custom tab. |
| 5.2 | No "days remaining" before auto-purge. | Nice-to-Have | Information Gap | `index.tsx:1547-1549` — Banner says "automatically deleted after 30 days" but individual rows show only "Deleted: 3 days ago" (via `formatDeletedAt` at line 1527-1537). No "X days remaining" indicator. | Add a "Remaining" column or tooltip showing days until auto-purge: `30 - daysSinceDeleted`. Color-code items nearing expiration (< 7 days: red, < 14 days: orange). |
| 5.3 | No bulk restore. | Nice-to-Have | Missing Functionality | `index.tsx:1592-1660` — Trash table has no `rowSelection` prop (unlike the Custom tab). Each prompt must be restored individually via its row action button. | Add `rowSelection` to the trash table with a bulk "Restore selected" action bar, mirroring the Custom tab's bulk action pattern. |
| 5.4 | No content preview in trash table. | Nice-to-Have | Information Gap | `index.tsx:1594-1656` — Trash table columns: title (name + author), deleted date, actions. No content/prompt preview column. Users must restore a prompt to see its content. | Add a truncated content preview column (reuse the Custom tab's content column renderer). Or show content in a tooltip on hover. |

---

## 6. Studio Tab

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 6.1 | Disabled sub-tabs don't explain why — no "select a project first" tooltip on the disabled segments. | Important | UX/Usability Issue | `StudioTabContainer.tsx:162-218` — Sub-tabs (Prompts, Test Cases, Evaluations, Optimizations) have `disabled: !selectedProjectId` but no tooltip explaining the disabled state. Ant Design `Segmented` doesn't natively support per-option tooltips on disabled items. A warning banner at line 253-261 appears after switching to a non-project tab, but only if you manage to click it. | Wrap each disabled option in a `<Tooltip>` with "Select a project first". Or show the warning banner proactively when hovering disabled tabs. Consider auto-navigating to Projects tab when a disabled tab is clicked. |
| 6.2 | Queue Health Widget shows raw metrics without interpretation. | Nice-to-Have | Information Gap | `QueueHealthWidget.tsx:96-138` — Widget shows three numbers inline: queue depth (clock icon), processing count (green dot), success rate (%). The tooltip (lines 37-93) shows a detailed grid with labels. But there's no natural-language summary like "All systems healthy" or "3 jobs stuck — check server logs". | Add a one-line summary in the tooltip header: "Healthy — all jobs processing normally" or "Degraded — 3 failures in last hour (90% success)". Use the existing `hasIssues` flag (line 22) to drive this. |
| 6.3 | Icon-only sub-tabs on mobile are hard to distinguish. | Important | UX/Usability Issue | `StudioTabContainer.tsx:154-218` — Each sub-tab has `<span className="hidden sm:inline">{label}</span>` which hides text labels below the `sm` breakpoint. On mobile, users see only icons: `FolderKanban`, `FileText`, `TestTube`, `BarChart3`, `Sparkles` — all similar-sized lucide icons that may be difficult to distinguish without labels. | Add `aria-label` to each icon (see finding 7.8). Consider using a vertical tab list or a dropdown selector on mobile instead of a horizontal icon-only segmented control. |
| 6.4 | No WebSocket for real-time progress — polls every 30 seconds instead. | Nice-to-Have | UX/Usability Issue | `StudioTabContainer.tsx:57-62` — `useQuery({ queryFn: getPromptStudioStatus, refetchInterval: 30000 })`. Evaluation and optimization jobs can take minutes; users see stale status for up to 30 seconds. | Reduce poll interval to 5s during active jobs (when `status.processing > 0`). Long-term: add WebSocket subscription for real-time job status updates. |
| 6.5 | Execute Playground: provider and model are plain text inputs with no validation or suggestions. | Important | UX/Usability Issue | `ExecutePlayground.tsx:177-199` (implied from Form.Item definitions) — Provider and model fields are optional plain `<Input>` elements. No dropdown of configured providers, no model autocomplete, no validation that the specified provider is available. | Replace with `<Select>` dropdowns populated from `GET /api/v1/llm/providers`. Show available models per selected provider. Fall back to server defaults when left empty. |
| 6.6 | Hardcoded references may not reflect user's available models. | Nice-to-Have | Information Gap | `ExecutePlayground.tsx:52-57` — Form initializes with `provider: undefined, model: undefined`. The backend falls back to configured defaults, but the UI doesn't show what those defaults are. Users have no visibility into which model will actually be used. | Show the server's default provider/model as placeholder text in the Select fields: "Default: openai / gpt-4o-mini". Fetch defaults from server config or status endpoint. |

---

## 7. Accessibility

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 7.1 | Screen reader status announcements div is properly implemented. | -- | Strength | `index.tsx:1668-1675` — `<div role="status" aria-live="polite" aria-atomic="true" className="sr-only" id="prompts-status-announcer" />`. This allows dynamic status updates to be announced to screen readers. | (No issue — well done.) |
| 7.2 | Keyboard table navigation works well with Enter/Space to open drawer. | -- | Strength | `index.tsx:1392-1404` — Table rows have `tabIndex: 0`, `role: "row"`, and `onKeyDown` handler for Enter/Space to open the edit drawer. `className` includes `focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary` for visible focus. | (No issue — well done.) |
| 7.3 | Action buttons have proper `aria-label` attributes. | -- | Strength | `PromptActionsMenu.tsx:91,108,125` — Edit button has `aria-label={t("managePrompts.tooltip.edit")}`, Use in Chat has `aria-label={t("option:promptInsert.useInChat")}`, More actions has `aria-label={t("common:moreActions")}`. | (No issue — well done.) |
| 7.4 | Favorite button has `aria-pressed` for toggle state. | -- | Strength | `index.tsx:1177` — `aria-pressed={!!record?.favorite}` on the favorite star button. This correctly communicates toggle state to assistive technology. | (No issue — well done.) |
| 7.5 | Prompt type column uses `role="group"` with `aria-label` for icon pairs. | -- | Strength | `index.tsx:1273-1276` — `<div role="group" aria-label={t("managePrompts.type.ariaLabel", { type: typeDescription })}>`. The System/Quick icons are `aria-hidden="true"` since the group label provides context. | (No issue — well done.) |
| 7.6 | Copilot edit button lacks focus styles and has a small touch target. | Important | Accessibility Concern | `index.tsx:1500-1510` — `<button className="text-text-muted">` with no explicit focus ring styles. The `<Pen className="size-4" />` icon makes the button only 16x16px — well below the 44x44px WCAG touch target recommendation. | Add `focus:outline-none focus:ring-2 focus:ring-primary` to the button class. Wrap in a `p-2` padding container to increase the touch target to at least 32x32px. |
| 7.7 | Disabled Studio tabs don't explain their state to screen readers. | Important | Accessibility Concern | `StudioTabContainer.tsx:162-218` — Disabled segmented options have `disabled: !selectedProjectId` but Ant Design's `Segmented` component doesn't add `aria-disabled` or descriptive text to disabled options. Screen reader users encounter a control they can't activate without understanding why. | Add `aria-label` with explanation: `aria-label="Prompts (select a project first)"` on disabled options. Or use `title` attribute as a fallback for both visual and screen reader users. |
| 7.8 | Studio sub-tab icons missing `aria-label` on mobile (text labels hidden). | Important | Accessibility Concern | `StudioTabContainer.tsx:154-218` — `<span className="hidden sm:inline">{label}</span>` hides text below `sm` breakpoint. The remaining icon elements (e.g., `<FolderKanban className="size-4" />`) have no `aria-label`. Screen readers on mobile would announce the segment without a meaningful label. | Add `aria-label={label}` to each icon or to the outer `<span>` wrapper. This ensures the label is always available to assistive technology regardless of viewport size. |
| 7.9 | No keyboard shortcut help panel. | Nice-to-Have | Missing Functionality | `index.tsx:890-911` — Keyboard shortcuts exist: `N` (new prompt), `/` (focus search), `Esc` (close drawer). These are documented in tooltips (`index.tsx:1030` — "New prompt (N)") but there's no comprehensive shortcut help panel. | Add a "Keyboard shortcuts" button (or `?` key trigger) that shows a modal listing all available shortcuts. Common pattern in developer tools. |

---

## 8. Responsive & Mobile Experience

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 8.1 | Fixed-width search and filter inputs compete on narrow screens. | Nice-to-Have | UX/Usability Issue | `index.tsx:1094,1101,1112` — Search input: `style={{ width: 260 }}`, type filter: `style={{ width: 130 }}`, keyword filter: `style={{ minWidth: 180 }}`. Total minimum width: 570px + gaps. On screens < 640px, these wrap but may still be cramped. | Use responsive widths: `style={{ width: '100%' }}` on mobile with `flex-wrap` and `flex-1` for even distribution. The `flex-wrap items-center gap-2` container already wraps, but fixed widths prevent inputs from filling available space. |
| 8.2 | 7-column table exceeds mobile viewport with no horizontal scroll indicator. | Important | UX/Usability Issue | `index.tsx:1152-1413` — Custom prompts table has 7 columns: checkbox, favorite (48px), title, content, keywords, type (80px), sync (100px), actions (140px). Minimum total: ~900px. On mobile, Ant Design Table adds horizontal scroll, but there's no visual cue (arrow or fade) indicating scrollable content. | Add a subtle gradient fade on the right edge of the table container to signal horizontal overflow. Or collapse less-important columns (keywords, type) on mobile using responsive column hiding. |
| 8.3 | Bulk action buttons may fall below touch target minimums. | Nice-to-Have | Accessibility Concern | `index.tsx:993-1017` — Bulk export and delete buttons use `px-2 py-1 text-sm` which creates roughly 28px-tall touch targets. WCAG recommends minimum 44x44px for touch targets. | Increase padding to `px-3 py-2` on mobile or add a `min-h-[44px]` class. Apply `@media (hover: none)` to conditionally increase sizing on touch devices. |

---

## 9. Error Handling & Edge Cases

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 9.1 | Firefox Private Mode handling is well-implemented. | -- | Strength | `index.tsx:226-239` — `guardPrivateMode()` checks `isFireFoxPrivateMode` and shows a descriptive error notification explaining the IndexedDB limitation. Lines 1677-1689 show a persistent `Alert` banner when private mode is detected. All mutating actions (create, edit, import, bulk ops) call `guardPrivateMode()` first. | (No issue — well done. Thorough handling of a browser-specific limitation.) |
| 9.2 | Partial load errors show a clear alert with specific detail per source. | -- | Strength | `index.tsx:205-222` — Separate error tracking for `promptLoadFailed` and `copilotLoadFailed`. The `loadErrorDescription` concatenates specific messages for each data source. Lines 1690-1707 render an `Alert` with the combined description. | (No issue — well done. Per-source error messages help users understand exactly what failed.) |
| 9.3 | Bulk delete aborts on first failure — no partial success reporting. | Important | UX/Usability Issue | `index.tsx:494-516` — `bulkDeletePrompts` uses `for (const id of ids) { await deletePromptById(id) }` with a single `onError` handler. If the 3rd of 10 deletions fails, items 4-10 are skipped. The error notification shows only the single failure message. | Use `Promise.allSettled()` for bulk operations. After completion, show: "Deleted 7 of 10 prompts. 3 failed." Allow retry on failed items. |
| 9.4 | Deep-link to non-existent prompt shows a warning notification. | -- | Strength | `index.tsx:190-202` — When `?prompt=<id>` references a prompt not found in data, a `notification.warning` is shown with "Prompt not found" and "may have been deleted" description. The URL param is cleaned up. | (No issue — well done. Good handling of stale bookmarks and shared links.) |
| 9.5 | Malformed JSON import gives a generic error with no detail. | Important | UX/Usability Issue | `index.tsx:845-850` — `catch (e)` block shows `t("managePrompts.notification.someError")` regardless of whether the error is invalid JSON, wrong schema, or empty file. `JSON.parse(text)` at line 782 throws a generic `SyntaxError`. | Distinguish error types: invalid JSON ("File is not valid JSON — check formatting"), wrong schema ("File format not recognized — expected an array of prompts"), empty file ("File is empty"). Show the JSON parse error position for syntax errors. |
| 9.6 | No error boundary around the Prompts page component. | Important | UX/Usability Issue | `index.tsx:68-1959` — `PromptBody` is a single large component with no `<ErrorBoundary>` wrapper. An unhandled exception in any render path (e.g., corrupt IndexedDB data with unexpected null fields) crashes the entire page. | Wrap `<PromptBody>` in an error boundary that shows a "Something went wrong" fallback with a "Reload page" button. Alternatively, wrap each tab's content independently to isolate failures. |

---

## 10. Missing Functionality & Backend Gaps

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 10.1 | Collections API has full backend but no UI. | Important | Missing Functionality | `prompts.py:1158-1204` — Backend has `POST /collections/create` and `GET /collections/{id}` endpoints for grouping prompts into named collections. `PromptCollectionCreateRequest` accepts name, description, and prompt IDs. No frontend component references collections. | Add a "Collections" section in the Custom tab or as a 5th tab. Show collection cards with prompt counts. Allow drag-and-drop to add prompts to collections. Collections solve the "flat keyword" limitation (finding 10.6). |
| 10.2 | No prompt usage tracking. | Nice-to-Have | Missing Functionality | "Use in Chat" action (`index.tsx:1338-1362`) navigates to `/chat` after setting the prompt, but doesn't record usage. No `usageCount` or `lastUsedAt` field exists on prompts. | Add `usageCount` and `lastUsedAt` fields to the prompt schema. Increment on "Use in Chat". Show in the table and enable sorting by most-used. |
| 10.3 | No prompt sharing or export link. | Nice-to-Have | Missing Functionality | Export is file-based only (JSON download). No way to generate a shareable link or URL for a specific prompt. Deep-linking exists (`?prompt=<id>`) but only within the same browser's IndexedDB. | For synced prompts, generate a shareable URL: `/prompts?prompt=<serverId>&source=studio`. The recipient can then pull the prompt from the server. |
| 10.4 | No quick test from Custom tab — must navigate to Studio. | Nice-to-Have | Missing Functionality | The Custom tab's actions menu (`PromptActionsMenu.tsx:64-84`) has: duplicate, delete, push/pull/unlink. No "Test" or "Execute" action. The Execute Playground (`ExecutePlayground.tsx`) is only accessible from the Studio Prompts sub-tab. | Add a "Quick test" action in the Custom tab's menu for synced prompts that opens the `ExecutePlayground` directly. For local-only prompts, offer a simplified test modal that sends the prompt to `/chat/completions`. |
| 10.5 | Prompt Studio settings not accessible from Prompts page. | Important | Missing Functionality | `prompt-studio-settings.ts` manages `defaultProjectId` and `autoSyncWorkspacePrompts` preferences, but these settings are only read programmatically — no UI allows the user to view or change them from the Prompts page. | Add a settings gear icon in the Studio tab header that opens a small settings popover/drawer: default project selector, auto-sync toggle, sync frequency. |
| 10.6 | No categorization beyond flat keywords — no folders or hierarchy. | Nice-to-Have | Missing Functionality | Keywords (`index.tsx:1244-1257`) are flat tags with no hierarchy or grouping. The tag filter (`index.tsx:1108-1118`) is a multi-select dropdown. For users with 100+ prompts across different domains (coding, writing, research), flat keywords become unwieldy. | Implement the Collections API (finding 10.1) as the primary organizational structure. Allow nesting or use a two-level keyword system (category → tags). Long-term: add a folder tree view alongside the table. |

---

## Executive Summary

### Top 5 Critical Gaps

1. **No conflict resolution UI (3.1)** — The `resolveConflict()` function in `prompt-sync.ts:604-647` implements three resolution strategies (`keep_local`, `keep_server`, `keep_both`) and `getConflictInfo()` at line 581-598 retrieves both versions for comparison. The `SyncStatusBadge` correctly renders a red "Conflict" tag. But there is zero UI to actually resolve conflicts — no modal, no side-by-side diff, no action buttons. Users see the red badge and have no recourse except to manually push or pull, which is a lossy operation without comparison.

2. **Search is client-side only (1.1)** — The backend `POST /prompts/search` endpoint (at `prompts.py:379-413`) provides FTS5 full-text search with field selection, pagination (`page`/`results_per_page`), deleted-item filtering, and relevance scoring. The UI ignores this entirely, using `string.toLowerCase().includes(query)` across all loaded prompts (`index.tsx:685-703`). This means no pagination, no relevance ranking, no server-side field filtering, and memory issues with large prompt libraries.

3. **Backend features invisible to users (10.1, 1.6, 2.2, 2.4)** — Four significant backend capabilities have no corresponding UI:
   - **Collections** (`prompts.py:1158-1204`): create, fetch, manage prompt groups
   - **CSV/Markdown export** (`prompts.py:518-574`): `export_format` parameter supports `csv` and `markdown`
   - **Template variables** (`prompts.py:45,69-86`): `_extract_template_variables()` and `_render_template()` for `{{variable}}` syntax
   - **Version history**: `VersionHistoryDrawer.tsx` exists in Studio but is inaccessible from the Custom tab where most users work

4. **No character/token count in the prompt editor (2.1)** — For a tool focused on prompt engineering, the editor lacks the most basic prompt-length feedback. Users cannot see character count, estimated token count, or context window budget. This is table-stakes for any prompt management tool (LangSmith, PromptLayer, and OpenAI Playground all show token counts).

5. **Studio sub-tab icons inaccessible on mobile (6.3, 7.8)** — Below the `sm` breakpoint, `StudioTabContainer.tsx:157` hides text labels with `hidden sm:inline`, leaving only generic lucide icons (`FolderKanban`, `FileText`, `TestTube`, `BarChart3`, `Sparkles`). These icons lack `aria-label` attributes, making them inaccessible to screen readers on mobile. Sighted users may also struggle to distinguish between similar-sized monochrome icons.

### Key Strengths

1. **"Use in Chat" modal (1.9)** — The three-option prompt insertion modal (`index.tsx:1857-1941`) is exceptionally well-designed. It shows clear visual previews of system vs. user prompt content, uses distinct icons and labels for each mode, and highlights the recommended "Use Both" option with a visually distinct border and background.

2. **Accessibility foundations (7.1-7.5)** — The Custom tab has strong a11y fundamentals: screen reader status div, keyboard-navigable table rows with Enter/Space support, `aria-label` on all action buttons, `aria-pressed` on the favorite toggle, and `role="group"` with descriptive `aria-label` on the type indicator column.

3. **Firefox Private Mode handling (9.1)** — Comprehensive detection and communication of IndexedDB limitations in Firefox Private Mode, with both a persistent banner and per-action guard checks that prevent data loss.

4. **Server sync architecture (prompt-sync.ts)** — The sync service is well-architected with clean separation: `pushToStudio`, `pullFromStudio`, `linkPrompts`, `unlinkPrompt`, `resolveConflict`, `getSyncStatus`, `getConflictInfo`. The types are well-defined (`SyncResult`, `ConflictInfo`, `ConflictResolution`). The auto-sync project resolution chain is thorough (check preferred → check defaults → check first available → create new → fail gracefully).

5. **Deep-link support (9.4)** — The `?prompt=<id>` and `?tab=<tab>` URL parameters enable bookmarkable prompt states. Invalid deep links show a helpful warning notification and clean up the URL. The `?project=<id>` filter parameter allows cross-feature navigation from Studio projects to filtered Custom tab views.

---

## Quick Wins (Implementable in < 1 hour each)

| # | Finding Ref | Change | Size | Time |
|---|-------------|--------|------|------|
| 1 | 7.8 | Add `aria-label={label}` to each Studio sub-tab icon element in `StudioTabContainer.tsx:154-218` | S | 15 min |
| 2 | 3.2 | Surface sync failure reasons in toast notifications — add `notification.warning()` call when `autoSyncPrompt` returns `success: false` in `index.tsx:298-327` | S | 30 min |
| 3 | 1.5 | Add "Last Modified" column to the Custom tab table — render `record.updatedAt` with relative time formatting (reuse `formatDeletedAt` pattern from trash tab) | S | 30 min |
| 4 | 1.7 | Show import result details — modify `importPromptsV2` to return `{ imported: number, skipped: number }` and display in success notification | S | 30 min |
| 5 | 4.1 | Add copilot `{text}` placeholder guidance — add `help` prop to the copilot edit `Form.Item` with explanation text | S | 15 min |

---

## Priority Roadmap

### Phase 1: Critical Fixes (1-2 weeks)

| Priority | Finding | Effort |
|----------|---------|--------|
| P0 | 3.1 — Build conflict resolution modal with side-by-side diff | M |
| P0 | 1.1 — Wire search input to backend `POST /prompts/search` with debounce | M |
| P1 | 2.1 — Add character/token count to prompt editor textareas | S |
| P1 | 7.8 — Add `aria-label` to Studio sub-tab icons | S |
| P1 | 6.1 — Add tooltips to disabled Studio sub-tabs explaining prerequisite | S |
| P1 | 9.6 — Wrap `PromptBody` in an error boundary | S |

### Phase 2: Core UX Improvements (2-4 weeks)

| Priority | Finding | Effort |
|----------|---------|--------|
| P1 | 1.4 — Add column sorting to Custom tab table | S |
| P1 | 1.5 — Add "Last Modified" column | S |
| P1 | 1.6 — Add CSV/Markdown export via backend endpoint | M |
| P1 | 2.2 — Template variable highlighting and extraction | M |
| P1 | 2.7 — Unsaved changes warning on drawer close | S |
| P1 | 3.3 — Batch sync operations ("Sync all pending") | M |
| P1 | 4.2 — "Copy to Custom" action for copilot prompts | S |
| P1 | 6.5 — Replace text inputs with provider/model Select dropdowns in Execute Playground | M |
| P2 | 1.2 — Add pagination (frontend + backend search integration) | M |
| P2 | 2.3 — Inline few-shot example editor in drawer | M |
| P2 | 2.4 — Version history access from Custom tab drawer | M |
| P2 | 1.8 — Bulk keyword assignment and bulk sync | M |

### Phase 3: Feature Enrichment (4-8 weeks)

| Priority | Finding | Effort |
|----------|---------|--------|
| P2 | 10.1 — Collections UI backed by existing API | L |
| P2 | 10.5 — Prompt Studio settings UI | M |
| P2 | 10.4 — Quick test from Custom tab | M |
| P3 | 5.1-5.4 — Trash tab enhancements (search, bulk restore, preview) | M |
| P3 | 10.2 — Usage tracking (count, last used) | M |
| P3 | 6.4 — WebSocket for real-time job progress | L |
| P3 | 8.2 — Responsive table with column collapsing on mobile | M |
| P3 | 4.3 — Copilot tab search and filter | S |

**Effort key**: S = < 1 day, M = 1-3 days, L = 3-5 days
