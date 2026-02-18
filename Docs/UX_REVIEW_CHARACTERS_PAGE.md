# UX Heuristic Review: `/characters` Page

**Date:** 2026-02-17
**Reviewer:** Claude (automated code-level heuristic evaluation)
**Source:** Static analysis of all listed component files, hooks, services, and backend endpoints

---

## 1. Executive Summary

The `/characters` page is a functionally rich character-management surface with solid foundational patterns: soft-delete with undo, form-draft auto-save, keyboard shortcuts, debounced search with tag filtering, AI generation helpers, and good baseline ARIA coverage. However, discoverability issues undermine the investment—templates and advanced fields are buried behind collapsed/link-style affordances, the gallery view strips nearly all metadata from cards, and the page offers no way to quick-test a character without navigating away. For power users managing 50+ characters, the fixed 10-item page size, limited sort dimensions, and absence of filter-by-creator / last-used / date-created become real blockers. Addressing the top quick wins (template visibility, gallery card density, page-size selector, system-prompt guidance, and alternate-greeting UX) would noticeably improve all three user archetypes with minimal engineering cost.

---

## 2. Findings Table

| ID | Dimension | Finding | Severity | Recommendation |
|----|-----------|---------|----------|----------------|
| C-01 | 1 – First-use | Empty state (`FeatureEmptyState`) shows "No characters yet" + CTA but omits icon, examples, secondary action (import), and any mention of templates. | **Major** | Pass `icon={UserCircle2}`, add `examples` prop with 2-3 use-case bullets (e.g. "Create a writing coach", "Import a SillyTavern card"), and add `secondaryActionLabel="Import character"` with an import handler. |
| C-02 | 1 – First-use | Templates are hidden behind a small "Start from a template…" link inside the create modal; newcomers must already know to open the modal to discover them. | **Major** | Surface template cards in the empty state itself (or as a second row of the CTA area). In the create modal, default to showing the template chooser expanded on first visit. |
| C-03 | 1 – First-use | No explanation of how characters relate to chat sessions. A newcomer doesn't know that "Chat" will open a separate chat page. | **Minor** | Add a one-line note in the empty state description: "Characters are reusable personas you can chat with—each gets its own conversation history." |
| C-04 | 2 – IA & discoverability | Advanced fields collapse hides 13+ fields (personality, scenario, post_history_instructions, message_example, creator_notes, alternate_greetings, creator, character_version, prompt_preset, author_note, generation settings, extensions). Prompt preset and generation settings are particularly buried. | **Major** | Group advanced fields into logical sub-sections (Prompt control, Generation settings, Metadata) with named collapse panels so users can expand just the section they need. Elevate `prompt_preset` to the main form area (below system prompt) since it directly affects behavior. |
| C-05 | 2 – IA & discoverability | No explanation of "personality" vs "description" vs "system_prompt" in the form; these overlapping fields confuse newcomers and even experienced users. | **Minor** | Add concise help text or tooltip to each field clarifying its role, e.g. "Personality: adjectives and traits injected into context", "Description: brief blurb shown in listings", "System prompt: full behavioral instructions sent to the model". |
| C-06 | 2 – IA & discoverability | Gallery view shows only avatar + name + conversation-count badge—no description, tags, or system-prompt snippet. Users cannot distinguish similarly named characters without clicking each one. | **Major** | Add 1-2 lines of description text and up to 3 tag pills on each gallery card. The `CharacterGalleryCard` interface already receives the full character object; expose `description` and `tags` props. |
| C-07 | 2 – IA & discoverability | Mood images feature is documented in the character data model (prompt doc) but not implemented anywhere in the UI (`mood_image` / `moodImage` returns zero matches). | **Minor** | Either remove mood images from the data model documentation or add a "Mood images (coming soon)" placeholder in the advanced section to set expectations. |
| C-08 | 3 – Search & filtering | Table sorting limited to name and conversation count. No sort by last-used, last-modified, or creation date. | **Major** | Add `created_at` and `updated_at` columns (or at least sort options) to the table. Backend already stores timestamps. |
| C-09 | 3 – Search & filtering | No filter by creator, has-conversations, last-modified date range, or creation date. | **Minor** | Add a filter dropdown/popover with checkboxes: "Has conversations", "Created by me", and a date-range picker for created/modified. |
| C-10 | 3 – Search & filtering | Fixed page size of 10 (`DEFAULT_PAGE_SIZE = 10`) with no user control. Power users with 50+ characters must paginate heavily. | **Minor** | Add a page-size selector (10 / 25 / 50 / 100) next to the pagination control. Persist choice in `localStorage`. |
| C-11 | 3 – Search & filtering | Client-side filtering via `filterCharactersForWorkspace()` loads all characters into memory at once. At 200+ characters with base64 avatars, this will cause performance issues. | **Enhancement** | Implement server-side search/filter/pagination for the characters list endpoint, or at minimum strip `image_base64` from the listing response and lazy-load avatars. |
| C-12 | 3 – Search & filtering | Tag management is create-only (tags input via Ant Design `Select mode="tags"`). No rename, merge, delete, or bulk-tag management. | **Minor** | Add a "Manage tags" popover or modal that lists all tags with usage counts and allows rename/merge/delete. |
| C-13 | 4 – Creation & editing | Alternate greetings use `Select mode="tags"` component—a tag-style selector is awkward for multi-line greeting messages. No reorder capability. | **Major** | Replace with a dynamic list of `Input.TextArea` fields with drag-to-reorder handles and add/remove buttons. Each greeting should be editable as full text. |
| C-14 | 4 – Creation & editing | System prompt field has validation (min 10, max 2000) and a help string, but the placeholder is generic. No example of what a good system prompt looks like. | **Minor** | Provide a multi-line placeholder or a "Show example" toggle that displays a short sample prompt (e.g. from the Writing Assistant template). |
| C-15 | 4 – Creation & editing | Create and edit form markup is duplicated (~700 lines each) within the 4,521-line `Manager.tsx`. While not a direct UX issue, this increases the risk of form-behavior divergence (e.g. validation rules drifting between create and edit). | **Enhancement** | Extract a shared `<CharacterForm />` component accepting mode (`create` | `edit`) and initial values. |
| C-16 | 5 – Import/export | Import accepts only a single file at a time (`Upload` component, single-file mode). No multi-file or drag-and-drop batch import. | **Minor** | Enable `multiple` on the `Upload` component and loop through `fileList` to import each file sequentially, reporting per-file success/failure. |
| C-17 | 5 – Import/export | No import preview—file uploads directly; user sees result only via success/failure notification. | **Minor** | After parsing the file, show a preview card (name, description, avatar thumbnail, field count) with a "Confirm import" button before persisting. |
| C-18 | 5 – Import/export | YAML import not supported despite the prompt document claiming it. `accept` attribute is `".png,.webp,.json,.md,.txt"` with no `.yaml` / `.yml`. | **Minor** | Either add YAML parsing support or remove YAML from the documented supported formats to avoid confusion. |
| C-19 | 6 – Conversation integration | "Chat" button navigates away from the `/characters` page entirely. No quick-test or embedded chat capability. | **Major** | Add a slide-out or modal-based "Quick chat" that lets the user send 2-3 test messages without leaving the page. Alternatively, open chat in a new tab. |
| C-20 | 6 – Conversation integration | No way to set a "default" character that auto-loads when starting a new conversation from the chat page. | **Enhancement** | Add a "Set as default" action in the character menu. Store the default character ID in user preferences. |
| C-21 | 6 – Conversation integration | No conversation stats beyond count (no average length, most-used greeting, last active date). | **Enhancement** | Show `last_active` timestamp and average message count in the conversations modal header. |
| C-22 | 7 – Visual design | Gallery cards are 120px avatar + name only—very low information density for scanning large collections. | **Major** | (See C-06.) Increase card height slightly to fit 2-line description and tag row. Consider a "compact gallery" toggle for the current minimal layout. |
| C-23 | 7 – Visual design | Missing-avatar placeholder is a generic `UserCircle2` icon with no color variation. All avatar-less characters look identical in gallery view. | **Minor** | Generate a deterministic background color from the character name hash (e.g. `hsl(hash % 360, 60%, 80%)`) and overlay the first letter of the name for visual distinction. |
| C-24 | 8 – Error handling | Form allows name up to 75 characters (`MAX_NAME_LENGTH = 75` used for display truncation), but the backend schema allows up to 500 characters. Users can create names in the API that the UI truncates silently. | **Minor** | Add a `maxLength={75}` to the `<Input>` name field to make the constraint explicit, or increase the display truncation limit to match the API. |
| C-25 | 8 – Error handling | Soft-delete with 10-second undo toast is the only recovery mechanism. No "Recently deleted" / trash view to recover characters after the toast disappears. | **Minor** | Add a "Recently deleted" tab or filter that shows soft-deleted characters within the last 30 days, with a "Restore" button. |
| C-26 | 8 – Error handling | Bulk delete uses a confirm dialog that says "This action cannot be undone" (`bulk.deleteContent`), but single delete uses soft-delete with undo. The inconsistency is confusing. | **Minor** | Make bulk delete also use soft-delete with undo, or at minimum change the bulk confirmation text to match the actual behavior. |
| C-27 | 9 – Accessibility | Inline edit (name/description) is triggered by `onDoubleClick` only—not reachable via keyboard. | **Major** | Add an "Edit inline" keyboard handler (e.g. Enter or F2 when the cell is focused) or provide an explicit edit icon button that keyboard users can Tab to. |
| C-28 | 9 – Accessibility | No `prefers-reduced-motion` handling found anywhere in the Characters component tree. Hover transitions and modal animations may cause discomfort. | **Minor** | Wrap transition/animation classes in a `@media (prefers-reduced-motion: reduce)` override that removes or minimizes motion. |
| C-29 | 9 – Accessibility | No skip-to-content link or landmark roles specific to this page. Screen reader users must Tab through the full header/nav to reach content. | **Minor** | Add `role="main"` to the characters content region and a visually-hidden skip link at the top of the page. |
| C-30 | 9 – Accessibility | Keyboard shortcut tooltip lists shortcuts but is only visible on hover of a small icon button—not announced to screen readers proactively. | **Enhancement** | Add an `aria-describedby` on the page container pointing to a visually-hidden shortcut summary, or make the tooltip trigger accessible via focus (not just hover). |
| C-31 | 10 – Missing features | No character versioning or revision history—`character_version` is a free-text field, not a system-managed history. | **Enhancement** | Implement a version timeline showing diffs between saves (backend already supports versioned records). |
| C-32 | 10 – Missing features | No folders, collections, or favorites/pinning for organizing characters beyond tags. | **Enhancement** | Add a "Favorites" toggle (star icon) on each card/row, and consider folder/collection support for power users. |
| C-33 | 10 – Missing features | No lorebook/world-info integration on the character page. Backend supports world books, but the UI does not expose attachment. | **Enhancement** | Add a "World books" section in the advanced fields that lets users attach/detach world books from a character. |
| C-34 | 10 – Missing features | No character comparison view to diff two characters side-by-side. | **Enhancement** | Add a "Compare" action in bulk-select mode that opens a side-by-side diff of selected characters' fields. |

---

## 3. Top 5 Quick Wins

| # | Finding ID | Change | Effort | Impact |
|---|-----------|--------|--------|--------|
| 1 | C-01, C-02 | **Enrich empty state with icon, examples, import CTA, and surface template cards** directly in the empty state or expanded by default in create modal. | Low (props already supported by `FeatureEmptyState`) | High — transforms newcomer first-use from blank screen to guided onboarding |
| 2 | C-06, C-22 | **Add description + tags to gallery cards.** `CharacterGalleryCard` already receives the full record; add 2 lines of description and up to 3 tag pills. | Low (~20 lines of JSX) | High — gallery view becomes usable for scanning and identification |
| 3 | C-10 | **Add page-size selector** (10/25/50/100) next to pagination, persisted in localStorage. | Low (Ant Design `Pagination` supports `pageSize` + `showSizeChanger`) | Medium — unblocks power users with large libraries |
| 4 | C-14 | **Improve system prompt placeholder** with a concrete example and add a "Show example" link that inserts the Writing Assistant template's prompt. | Low (copy change + small handler) | Medium — helps newcomers write effective prompts |
| 5 | C-13 | **Replace tag-selector for alternate greetings** with a dynamic list of `Input.TextArea` fields with add/remove buttons. | Medium (~100 lines refactor) | High — current UX is actively frustrating for multi-line greetings |

---

## 4. Top 5 Strategic Improvements

| # | Finding IDs | Improvement | Effort | Impact |
|---|------------|-------------|--------|--------|
| 1 | C-04 | **Restructure advanced fields into named sub-sections** (Prompt control, Generation settings, Metadata) and elevate `prompt_preset` to the main form. | Medium — form layout refactor + extract shared form component (C-15) | High — makes critical prompt/generation settings discoverable; reduces 4,500-line file |
| 2 | C-19 | **Add "Quick chat" slide-out panel** for testing a character without navigating away. Could reuse existing chat components in a constrained view. | High — requires embedding chat in a modal/drawer with session management | High — single most-requested feature gap; eliminates round-trips between pages |
| 3 | C-08, C-09, C-11 | **Implement server-side search, filter, and pagination** with sort by created/modified/last-used + filter by creator, has-conversations, date range. | High — backend endpoint changes + frontend filter UI | High — critical for scalability beyond 50 characters; eliminates client-side performance risk |
| 4 | C-27, C-28, C-29 | **Accessibility overhaul**: add keyboard-accessible inline edit (F2/Enter), `prefers-reduced-motion` overrides, skip-to-content link, and landmark roles. | Medium — spread across multiple components | High — currently blocks keyboard-only and motion-sensitive users from core workflows |
| 5 | C-25, C-31 | **Add "Recently deleted" view and character version history.** Soft-deleted characters shown in a filtered tab; version timeline with diff view. | High — backend supports versioning but UI needs new views | Medium — provides safety net and audit trail for character evolution |

---

## 5. Missing Functionality Matrix

| Feature | Newcomer | Power User | Accessibility User | Priority |
|---------|:--------:|:----------:|:------------------:|----------|
| Quick-test / preview chat (C-19) | High | High | Medium | **P1** |
| Character versioning / revision history (C-31) | Low | High | Low | P2 |
| Folders / collections / favorites (C-32) | Low | High | Low | P2 |
| Server-side search & pagination (C-11) | Low | High | Medium | **P1** |
| Lorebook / world-info integration (C-33) | Low | High | Low | P3 |
| Bulk import (multi-file) (C-16) | Low | High | Low | P2 |
| Import preview (C-17) | Medium | Medium | Medium | P2 |
| Character comparison view (C-34) | Low | Medium | Low | P3 |
| Default character for new chats (C-20) | Medium | Medium | Medium | P2 |
| Sharing / community gallery | Low | Medium | Low | P3 |
| Usage analytics beyond conversation count (C-21) | Low | Medium | Low | P3 |
| Recently deleted / trash view (C-25) | Medium | High | Medium | P2 |
| Tag rename / merge / bulk management (C-12) | Low | High | Low | P2 |
| Reduced-motion support (C-28) | Low | Low | **High** | **P1** |
| Skip-to-content & landmarks (C-29) | Low | Low | **High** | **P1** |
| Keyboard-accessible inline edit (C-27) | Low | Medium | **High** | **P1** |

---

*End of review.*
