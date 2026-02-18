# UX Review: Chat Dictionaries Page (`/dictionaries`)

**Date:** 2026-02-17
**Reviewer:** Claude (HCI/Design Expert + Power-User Perspective)
**Scope:** `DictionariesWorkspace.tsx`, `Manager.tsx` (~1,314 lines), backend endpoints, schemas, E2E tests

---

## 1. Dictionary List & Overview

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 1.1 | **No sorting on any column** | Important | UX/Usability Issue | Ant Design `Table` is used but no `sorter` prop is set on any column. Users with 10+ dictionaries cannot sort by name, entry count, or active status. | Add `sorter` to Name (alphabetical), Entry Count (numeric), and Active (boolean) columns. |
| 1.2 | **No filtering or search** | Important | UX/Usability Issue | No search input, no column filters. Users must visually scan the entire table to find a dictionary. | Add a search input above the table that filters by name/description. Add column filter on Active status. |
| 1.3 | **No inline active/inactive toggle** | Important | UX/Usability Issue | Active status is displayed as a read-only `<Tag>` ("Active"/"Inactive"). Toggling requires Edit modal -> Switch -> Save (3 clicks minimum). | Replace the Tag with a clickable `<Switch>` that calls `updateDictionary` inline. This is the most common operation for dictionaries. |
| 1.4 | **Missing "last modified" column** | Nice-to-Have | Information Gap | The API returns `updated_at` but the table does not display it. Users cannot tell which dictionaries were recently changed. | Add an "Updated" column with relative time (e.g., "3 hours ago"). |
| 1.5 | **No regex/literal breakdown in list** | Nice-to-Have | Information Gap | Entry count is shown but not the type breakdown. Users must open Stats modal to see regex vs literal split. | Show as "5 entries (2 regex)" or add a small badge. |
| 1.6 | **No dictionary-to-chat relationship** | Critical | Information Gap | There is no indication of which chat sessions use which dictionaries. The dictionary page is completely disconnected from chat. Users cannot tell if deactivating a dictionary will affect active conversations. | Add a "Used by" column or tooltip showing linked chat sessions. Warn before deactivation if sessions are active. |
| 1.7 | **No duplicate/clone action** | Nice-to-Have | Missing Functionality | Users who want to iterate on a dictionary must export JSON -> re-import -> rename. No single-click clone. | Add a "Duplicate" button in the actions column that creates a copy with " (copy)" suffix. |
| 1.8 | **No pagination for large lists** | Important | UX/Usability Issue | Ant Design Table defaults are used. With 50+ dictionaries, the page will become very long. The `Table` component does support pagination by default but this should be verified and configured with a reasonable page size. | Ensure pagination is configured (e.g., 20 per page) or add virtual scrolling for very large lists. |
| 1.9 | **CTA placement is adequate but could be improved** | Nice-to-Have | UX/Usability Issue | "New Dictionary" and "Import" buttons are top-right. This follows convention but the buttons lack distinctive styling differentiation between primary (create) and secondary (import) actions. | Current state is acceptable. Consider adding an icon to "New Dictionary" for visual weight. |

---

## 2. Entry Management

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 2.1 | **Entry table columns are minimal** | Important | Information Gap | Entry table only shows: Pattern, Replacement, Enabled, Actions. Missing: type (only shown as tag on pattern), probability, group, case_sensitive, max_replacements. | Show at least type, probability, and group as columns. Use responsive column hiding on mobile. |
| 2.2 | **No inline editing** | Important | UX/Usability Issue | Every edit requires opening a modal. Changing a single replacement string requires: click Edit -> modal opens -> change field -> click Save (4 interactions). | Allow inline editing of Pattern and Replacement via click-to-edit cells. Keep modal for advanced fields (probability, timed effects, group). |
| 2.3 | **No bulk operations** | Important | Missing Functionality | Backend has `BulkEntryOperation` and `BulkOperationResponse` schemas defined, but no bulk endpoint is implemented. UI has no checkbox selection. Cannot enable/disable multiple entries at once, cannot bulk delete, cannot bulk assign to group. | Implement bulk entry endpoint on backend. Add row selection checkboxes and a bulk action bar (enable all, disable all, delete selected, set group). |
| 2.4 | **No entry reordering** | Nice-to-Have | Missing Functionality | Entries appear in database insertion order. There is no drag-to-reorder or manual priority control. Processing order may matter (earlier entries match first) but this is not communicated. | Add drag-to-reorder with a handle column, or at minimum document whether entry order affects processing priority. |
| 2.5 | **No entry search/filter within dictionary** | Important | UX/Usability Issue | With 50+ entries, no way to find a specific pattern except scrolling. Backend supports `group` filter on `GET /entries` but UI doesn't expose it. | Add a search input and group filter dropdown above the entry table. |
| 2.6 | **Group name field is unassisted** | Nice-to-Have | UX/Usability Issue | Group name is a plain text input. No autocomplete from existing groups in the dictionary. Users may create duplicate groups with different casing. | Add autocomplete/dropdown populated from existing groups in the current dictionary. |
| 2.7 | **Timed effects not exposed in add/edit forms** | Important | Missing Functionality | Backend supports `timed_effects` (sticky, cooldown, delay) via `TimedEffects` schema, and the API stores them. But neither the Add Entry form nor the Edit Entry modal has timed effects fields. The schema has proper validation (ge=0 constraints). | Add timed effects fields to the Advanced mode section of the Add Entry form and the Edit Entry modal. Include tooltips explaining each effect. |
| 2.8 | **Regex pattern validation is client-side only during add** | Nice-to-Have | UX/Usability Issue | `validateRegexPattern()` does client-side JS `new RegExp()` check during entry creation. This misses ReDoS detection (which only the server validates). The inline test popover also uses client-side regex. | Surface the server's ReDoS validation result during entry creation (call validate endpoint before save) or add a local ReDoS heuristic. |
| 2.9 | **Entry modal opens inside another modal** | Important | UX/Usability Issue | "Manage Entries" opens as a modal. Inside it, "Edit Entry" opens as a nested modal. This creates a confusing modal-within-modal experience. The outer modal can become partially hidden. | Convert the "Manage Entries" view to a drawer or inline panel instead of a modal. Alternatively, make it a full-page sub-route. |

---

## 3. Probability & Timed Effects Configuration

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 3.1 | **Probability uses numeric input, not slider** | Nice-to-Have | UX/Usability Issue | Probability is an `InputNumber` with min=0, max=1, step=0.01. While functional, users may not intuitively understand what 0.3 means in practice. | Add a slider alongside the number input. Add helper text like "Fires ~3 out of 10 messages". |
| 3.2 | **Timed effects completely absent from UI** | Critical | Missing Functionality | The backend fully supports sticky duration, cooldown period, and delay. `TimedEffects` schema is defined with `sticky`, `cooldown`, `delay` fields (all in seconds, ge=0). But the UI has zero fields for configuring timed effects. The entry forms don't include them at all. | Add timed effects configuration to both the Add Entry advanced mode and Edit Entry modal. Include clear labels with units ("seconds"), sensible defaults (0 = disabled), and tooltips. |
| 3.3 | **No explanation of probability vs max_replacements** | Nice-to-Have | Information Gap | Both fields control "how much" a replacement fires but in different ways. No help text distinguishes them. `LabelWithHelp` is used for max_replacements but the help text doesn't mention probability interaction. | Add a brief note: "Probability controls *whether* this entry fires. Max replacements limits *how many times* per message." |
| 3.4 | **Case sensitivity default may surprise users** | Nice-to-Have | UX/Usability Issue | Schema defaults `case_sensitive` to `True`. The Add Entry form's help text says "Recommended off for medical terms" but the form initializes with no value for `case_sensitive`, meaning the server default (`True`) takes effect. | Consider defaulting `case_sensitive` to `false` in the UI form, since most text-replacement use cases benefit from case-insensitive matching. |

---

## 4. Validation & Testing

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 4.1 | **Validation is hidden inside a Collapse panel** | Important | UX/Usability Issue | "Validate dictionary" and "Preview transforms" are inside an Ant Design `Collapse` component (accordion), collapsed by default. Users must expand the panel to access validation. Most users will never discover these features. | Move validation to a more prominent position - either a button in the entry manager header bar, or always-visible section. |
| 4.2 | **Validation results don't link to entries** | Nice-to-Have | UX/Usability Issue | Validation errors/warnings show `code`, `field`, and `message` but clicking them doesn't scroll to or highlight the offending entry in the table. | Make validation error items clickable, scrolling to and highlighting the offending entry row. |
| 4.3 | **Preview shows output but no diff** | Important | UX/Usability Issue | Preview shows original text in the input and processed text in a readonly textarea. No side-by-side diff or inline highlighting of what changed. Users must manually compare. | Add a simple diff view highlighting changed spans (green for insertions, strikethrough for removals). |
| 4.4 | **Inline entry test is well-implemented** | -- | Positive | Individual entries have a "Test" popover (Play icon) that lets users type sample text and see the result with client-side regex execution. This is a strong feature. | Maintain this feature. Consider adding a "copy result" button. |
| 4.5 | **No saved test cases** | Nice-to-Have | Missing Functionality | Preview text is ephemeral. Users must re-type sample text each time they open the preview panel. | Add a "Save test case" feature or persist the last preview text in local state. |
| 4.6 | **Validation disabled when no entries** | -- | Positive | The "Run validation" button is disabled and a helpful message is shown when entries are empty. Good guard. | No change needed. |

---

## 5. Import / Export

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 5.1 | **Import is JSON-only in the modal** | Important | Information Gap | The import modal only accepts JSON files (`accept="application/json"`). The backend supports both Markdown import (`POST /dictionaries/import`) and JSON import (`POST /dictionaries/import/json`), but the UI only exposes JSON import. | Add a format selector (JSON/Markdown) to the import modal. Alternatively, auto-detect format from file extension. |
| 5.2 | **No import preview** | Important | UX/Usability Issue | Import immediately creates the dictionary on file selection. Users cannot preview what will be created (name, entry count, groups) before committing. | Show a preview step: parse the file, display summary (name, N entries, M groups), then let user confirm. |
| 5.3 | **No conflict handling** | Important | Missing Functionality | If a dictionary with the same name already exists, the backend returns 409 Conflict. The UI shows a generic error notification. No merge, replace, or rename option is offered. | On 409, offer the user options: "Rename to X (2)", "Replace existing", or "Cancel". |
| 5.4 | **No paste-to-import** | Nice-to-Have | Missing Functionality | Users must save JSON/Markdown to a file before importing. Cannot paste content directly. | Add a textarea for paste-based import alongside the file upload. |
| 5.5 | **Export triggers immediate download** | -- | Positive | Both JSON and Markdown exports trigger a browser download with a descriptive filename (`{name}.json` / `{name}.md`). Clean implementation. | No change needed. |
| 5.6 | **Markdown export may lose advanced fields** | Nice-to-Have | Information Gap | Markdown export/import is handled server-side. It's unclear whether probability, timed effects, case sensitivity, and max_replacements survive the Markdown round-trip (these are non-standard Markdown fields). | Document Markdown format limitations. Recommend JSON for full-fidelity export. Show a warning if exporting a dictionary with advanced fields via Markdown. |

---

## 6. Statistics & Usage Insights

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 6.1 | **Statistics are basic** | Nice-to-Have | Information Gap | Stats modal shows: ID, Name, Total Entries, Regex Entries, Literal Entries, Groups, Average Probability, Total Usage Count. This is useful but limited. | Add: enabled vs disabled breakdown, entries with probability < 1.0, entries with timed effects, date created/last modified. |
| 6.2 | **No per-entry usage data** | Important | Missing Functionality | `total_usage_count` is shown at the dictionary level. No per-entry fire count. Users cannot identify unused entries or frequently-triggered ones. | Track and display per-entry usage counts. Highlight entries with zero usage for cleanup. |
| 6.3 | **`last_used` is always null** | Important | Information Gap | The `DictionaryStatistics` schema has `last_used` field, and the endpoint returns `last_used=None` always. The backend doesn't track this. | Implement `last_used` timestamp tracking in `ChatDictionaryService.process_text()`. |
| 6.4 | **No pattern conflict detection** | Nice-to-Have | Missing Functionality | Users cannot see overlapping patterns (e.g., "KCl" literal + `/KC.*/` regex). No shadowing analysis. | Add a "Pattern conflicts" section to statistics that identifies potentially overlapping entries. |

---

## 7. Connection to Character Chat

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 7.1 | **Complete disconnect from chat sessions** | Critical | Missing Functionality | The dictionaries page has zero references to chat sessions. Users cannot see which dictionaries are applied to which chats, navigate between dictionaries and chats, or manage assignments from this page. | Add a "Used in Chats" section or link. Provide a "Quick assign to chat" action. |
| 7.2 | **No deactivation warning** | Important | UX/Usability Issue | When deactivating or deleting a dictionary, no warning about affected chat sessions. The confirmation dialog for deletion just says "Delete dictionary?" with no context. | Show "This dictionary is active and may affect N chat sessions. Are you sure?" |
| 7.3 | **No multi-dictionary processing order** | Important | Information Gap | When multiple dictionaries are active, the processing order is not shown or controllable. The `process_text` API accepts a single `dictionary_id` or processes all active ones, but order is undocumented. | Document and expose dictionary processing priority. Allow reordering of active dictionaries. |
| 7.4 | **Token budget not exposed** | Nice-to-Have | Information Gap | `token_budget` is exposed in the Preview panel but not in dictionary settings. Users cannot set a default token budget per dictionary. It's only a per-request parameter in the API. | Consider adding a default `token_budget` to the dictionary metadata for automatic application during chat processing. |
| 7.5 | **No transformation audit trail** | Nice-to-Have | Missing Functionality | No log of when dictionaries were applied, what text was transformed, or which entries fired during actual chat sessions. | Add a "Recent activity" tab showing recent transformations with timestamps, original/transformed text snippets, and chat session context. |

---

## 8. Error Handling & Edge Cases

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 8.1 | **Empty state lacks guidance** | Important | UX/Usability Issue | When no dictionaries exist, the table renders as an empty Ant Design table with no rows. No empty state illustration, no "Create your first dictionary" CTA, no example templates, no import suggestion. | Use `FeatureEmptyState` component (already imported and used for unsupported state) with actionable guidance: "Create your first dictionary" button, import option, and example use cases. |
| 8.2 | **Empty dictionary (no entries) lacks guidance** | Nice-to-Have | UX/Usability Issue | When the entry manager opens for a dictionary with no entries, the entry table is empty but there's no helpful guidance about what entries do or example patterns. | Add empty state text: "No entries yet. Add a pattern/replacement pair to start transforming text." with an example. |
| 8.3 | **Regex errors are understandable** | -- | Positive | Client-side regex validation shows the native JS `RegExp` error message. The error is displayed in a styled alert box with icon. Good implementation. | No change needed. |
| 8.4 | **Import malformed file errors are generic** | Nice-to-Have | UX/Usability Issue | If the JSON file has invalid structure, the error notification shows the backend's error message. No line number or field name guidance. | Parse client-side before sending to backend. Show specific validation errors about missing required fields. |
| 8.5 | **Deletion uses soft delete correctly** | -- | Positive | Delete calls `deleteDictionary(id)` which defaults to soft delete on the backend (`hard_delete=False`). Good safety measure. | No change needed. Consider adding a "Trash" view to recover soft-deleted dictionaries. |
| 8.6 | **No undo for destructive actions** | Nice-to-Have | UX/Usability Issue | After deleting an entry or dictionary, there is no undo. The confirmation dialog is the only safety net. | Add a brief toast notification with "Undo" action after entry deletion. For dictionaries, the soft-delete serves as implicit undo. |
| 8.7 | **Backend disconnection shows loading skeleton forever** | Nice-to-Have | UX/Usability Issue | If the server goes down after initial load, the query will fail on refresh. The `status === 'pending'` shows Skeleton, but there's no error state handling for `status === 'error'`. | Add error state rendering with a retry button. |
| 8.8 | **No concurrent edit protection** | Nice-to-Have | UX/Usability Issue | The backend has `version` field for optimistic locking on `ChatDictionaryResponse`, but the UI does not send `version` during updates. Two tabs editing the same dictionary could overwrite each other. | Include `version` in update requests and handle 409 Conflict with "Dictionary was modified by another session. Reload?" |

---

## 9. Responsive & Mobile Experience

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 9.1 | **Dictionary table has too many action buttons for mobile** | Important | UX/Usability Issue | Each row has 6 action buttons (Edit, Entries, JSON, MD, Stats, Delete) arranged in a flex-wrap row. On mobile, this creates a very wide or multi-line action area that dominates each row. | Consolidate actions into a "..." overflow menu on mobile. Keep Edit and Entries as primary actions, move export/stats/delete to dropdown. |
| 9.2 | **Entry management modal may be too narrow on mobile** | Important | UX/Usability Issue | The "Manage Entries" modal contains a full table + add entry form + collapse panels for validation/preview. On mobile (375px), Ant Design modals are already constrained. Nested modals (Edit Entry inside Manage Entries) compound the problem. | Convert entry management to a full-screen drawer on mobile. |
| 9.3 | **Touch targets meet minimum size** | -- | Positive | Action buttons use `min-w-[44px] min-h-[44px]` (or `min-w-[36px]` for some), meeting or nearly meeting the 44px accessibility recommendation. | Ensure all targets are at least 44px. The validation status buttons use 36px minimum which is slightly below recommendation. |
| 9.4 | **Add Entry form grid adapts** | -- | Positive | The Add Entry form uses `grid gap-3 sm:grid-cols-2` which collapses to single column on small screens. Good responsive design. | No change needed. |
| 9.5 | **Preview panel token budget/max iterations grid is narrow** | Nice-to-Have | UX/Usability Issue | Preview settings use `grid gap-2 sm:grid-cols-2` but inside a modal that's inside another modal, making the effective width very small on mobile. | Ensure these fields stack vertically when the modal width is too constrained. |

---

## 10. Accessibility

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 10.1 | **Action buttons have proper aria-labels** | -- | Positive | All action buttons have descriptive `aria-label` attributes including the dictionary/entry name (e.g., `aria-label="Edit dictionary Medical Terms"`). Excellent. | No change needed. |
| 10.2 | **Validation status buttons have context-aware labels** | -- | Positive | Validation status buttons change their `aria-label` based on state (e.g., "Dictionary X is valid. Click to re-validate."). Good screen reader experience. | No change needed. |
| 10.3 | **Active/inactive toggle is not keyboard-actionable from list** | Important | Accessibility Concern | Active status is displayed as a read-only `<Tag>`, not a toggle. Users cannot toggle active status via keyboard from the list view without opening the Edit modal. | Replace with inline `<Switch>` which is natively keyboard-accessible. |
| 10.4 | **Collapse panels lack aria-expanded** | Nice-to-Have | Accessibility Concern | Ant Design's `Collapse` component should handle `aria-expanded` natively, but this should be verified. The validate/preview panels should announce their expanded state. | Verify Ant Design Collapse provides proper ARIA attributes. Add `role="region"` if missing. |
| 10.5 | **Advanced mode toggle has aria-expanded** | -- | Positive | The "Advanced options" / "Simple mode" toggle button uses `aria-expanded={advancedMode}`. Good. | No change needed. |
| 10.6 | **Color contrast for status indicators** | Nice-to-Have | Accessibility Concern | Status uses semantic colors: `text-success` (green check), `text-warn` (yellow triangle), `text-danger` (red circle). These rely on icon + color for differentiation. Shape (circle vs triangle) provides secondary cue, which is good. | Verify color contrast ratios meet WCAG 2.1 AA (4.5:1 for text, 3:1 for UI components) across light and dark themes. |
| 10.7 | **Entry type badge is color-only** | Nice-to-Have | Accessibility Concern | The `<Tag color="blue">regex</Tag>` badge relies on blue color plus text label "regex". The text label is sufficient for screen readers, but the blue coloring adds no semantic value. | Current state is acceptable since the text "regex" provides the information. No change strictly needed. |
| 10.8 | **Modals should trap focus** | Nice-to-Have | Accessibility Concern | Ant Design's `Modal` component handles focus trapping and return-focus natively. This should work correctly but should be verified for nested modals (Edit Entry inside Manage Entries). | Test nested modal focus trapping with screen reader to ensure outer modal is inert when inner modal is open. |
| 10.9 | **Confirmation dialog is accessible** | -- | Positive | Deletion uses `confirmDanger` which renders an Ant Design modal with proper button labels. | No change needed. |

---

## 11. Information Gaps & Missing Functionality

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 11.1 | **No dictionary versioning / change history** | Nice-to-Have | Missing Functionality | Backend has a `version` field (optimistic locking counter) but no change history. Users cannot revert to a previous version of a dictionary. | Track dictionary change history. Allow viewing previous versions and reverting. |
| 11.2 | **No template dictionaries** | Important | Missing Functionality | New users must build dictionaries from scratch. No pre-built examples (accent generators, medical abbreviations, technical jargon). | Provide 2-3 starter templates: "Medical Abbreviations", "Chat Speak Translator", "Custom Terminology". |
| 11.3 | **No visual regex builder** | Nice-to-Have | Missing Functionality | Regex entries require users to know regex syntax. No visual builder or pattern explanation. | Add a "regex helper" link/tooltip that explains common patterns (e.g., `.*` = any text, `\b` = word boundary) with examples. |
| 11.4 | **No dictionary tagging/categorization** | Nice-to-Have | Missing Functionality | Dictionaries have name and description but no tags or categories. Users cannot organize dictionaries by purpose (medical, casual, roleplay). | Add tags to dictionary metadata for filtering and organization. |
| 11.5 | **No keyboard shortcuts** | Nice-to-Have | Missing Functionality | No keyboard shortcuts for common actions (new dictionary, validate, preview). All interactions require mouse. | Add: Ctrl+N (new dictionary), Ctrl+Enter (submit form), Ctrl+Shift+V (validate). |
| 11.6 | **No sharing / community dictionaries** | Nice-to-Have | Missing Functionality | Dictionaries can be exported as files but there's no way to share via URL or browse community contributions. | Future consideration: Add a "community gallery" or shareable link generation. |
| 11.7 | **No dictionary composition** | Nice-to-Have | Missing Functionality | Cannot include one dictionary inside another. Users who want a "base" dictionary plus specializations must duplicate entries. | Allow dictionary "includes" or inheritance for composition. |
| 11.8 | **Monolithic component architecture** | Important | UX/Usability Issue | `Manager.tsx` is a single 1,314-line component containing all CRUD, validation, preview, import/export, and entry management. This makes maintenance difficult and prevents lazy loading of rarely-used features. | Split into: `DictionaryList`, `DictionaryForm`, `EntryManager`, `EntryForm`, `ValidationPanel`, `PreviewPanel`, `ImportExport`, `StatsModal`. |

---

## Executive Summary

### Top 5 Critical Gaps (Power-User Adoption Blockers)

1. **Complete disconnect from chat sessions (7.1)** - Users cannot see which dictionaries are used in which chats, making the feature feel orphaned. This is the single biggest gap preventing the dictionaries feature from being useful in practice.

2. **Timed effects not exposed in UI (3.2)** - The backend supports sticky, cooldown, and delay effects, but the UI has zero fields for configuring them. This entire feature dimension is invisible to users.

3. **No inline active toggle (1.3)** - The most common dictionary operation (activate/deactivate) requires opening an edit modal. This should be a single click.

4. **No bulk entry operations (2.3)** - Managing dictionaries with 50+ entries is painful without multi-select enable/disable/delete. The backend schemas exist but the endpoint and UI don't.

5. **Empty state provides no guidance (8.1)** - New users see an empty table with no direction. No templates, no examples, no "getting started" flow.

### Top 5 Quick Wins (High Impact, Low Effort)

1. **Add inline active/inactive Switch** - Replace the read-only `<Tag>` with a `<Switch>` that calls `updateDictionary`. ~15 lines of code change.

2. **Add column sorting** - Add `sorter` props to Name, Entry Count, and Active columns. ~10 lines.

3. **Add empty state with FeatureEmptyState** - The component is already imported. Wire it up when `data?.length === 0`. ~20 lines.

4. **Show more columns in entry table** - Add type, probability, and group columns to the entry table. Currently only pattern, replacement, enabled, and actions are shown. ~20 lines.

5. **Make validation/preview more discoverable** - Move from collapsed accordion to always-visible action buttons in the entry manager header. ~30 lines.

### Suggested Priority Roadmap

**Phase 1: Core Usability (1-2 days)**
- Inline active/inactive toggle (1.3)
- Column sorting (1.1)
- Empty state guidance (8.1)
- Entry table additional columns (2.1)
- Error state handling (8.7)

**Phase 2: Entry Management UX (2-3 days)**
- Expose timed effects in forms (3.2, 2.7)
- Entry search/filter within dictionary (2.5)
- Import preview step (5.2)
- Markdown import support (5.1)
- Move validation/preview out of collapse (4.1)
- Preview diff view (4.3)

**Phase 3: Chat Integration (2-3 days)**
- Dictionary-to-chat relationship visibility (7.1)
- Deactivation warning (7.2)
- Multi-dictionary processing order (7.3)

**Phase 4: Power User Features (3-5 days)**
- Bulk entry operations (2.3)
- Template dictionaries (11.2)
- Dictionary duplicate/clone (1.7)
- Entry reordering (2.4)
- Component decomposition (11.8)
- Conflict handling on import (5.3)
- Per-entry usage tracking (6.2)
