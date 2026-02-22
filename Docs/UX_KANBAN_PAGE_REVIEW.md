# UX Review: Kanban Page

**Date:** 2026-02-21
**Scope:** `/kanban` page — `apps/packages/ui/src/components/Option/KanbanPlayground/`
**Reviewed files:** `index.tsx`, `BoardView.tsx`, `CardDetailPanel.tsx`, `ImportPanel.tsx`, plus `services/kanban.ts`, `types/kanban.ts`, and all 7 backend endpoint files.

---

## 1. Information Architecture & Navigation

### 1.1 Board selector is a dropdown — should it be?

**Problem:** The board selector is a 200px-wide `<Select>` dropdown in the header. When users accumulate 10+ boards, the dropdown becomes a flat, unsorted list with no visual cues (no board description, card count, or last-modified date). Discovery and orientation are poor — you must remember the board name to find it.

**Impact:** Medium. Tolerable with few boards, painful as the count grows.

**Recommendation:** Add a "Board Gallery" view as the default landing (grid of cards showing board name, list/card counts, last-modified date). Keep the dropdown in the header as a quick-switcher once a board is open. The gallery replaces the current `<Empty>` state. Each gallery card should show:
- Board name (truncated with tooltip)
- `N lists, M cards` summary
- Last-modified relative timestamp
- Optional: colored dot or thumbnail of first list names

**Complexity:** Medium.

### 1.2 Board/Import tab split is odd

**Problem:** Import is a peer tab alongside Board view, but it's a one-time administrative action. Giving it a full tab elevates it to the same prominence as the core workflow. Users who never import will always see it; users who do import use it once.

**Impact:** Low. Doesn't actively harm, but wastes screen real estate.

**Recommendation:** Move "Import" into a dropdown menu (e.g., from a `...` or gear icon next to the "New Board" button). Options: `Import Board`, `Export Board`. This also creates a natural home for the missing Export feature. Remove the `<Tabs>` component entirely — the board view should be the only content area.

**Complexity:** Small.

### 1.3 No way to discover archived items

**Problem:** The API supports `archive/unarchive` for boards, lists, and cards. The UI only supports hard delete. Archived items are invisible and unreachable. The `listBoards` service function accepts `includeArchived` but `index.tsx:49` never passes it.

**Impact:** High. Users will permanently delete items they intended to temporarily hide, causing data loss anxiety. The PRD (U3, U5, U6, U10, U12, U20, U22, U38) explicitly requires archive/restore.

**Recommendation:**
1. Replace "Delete Board" / "Delete List" actions with "Archive" as the primary action, and "Delete Permanently" as a secondary danger action behind a confirmation.
2. Add an "Archived Items" section accessible from the board header (icon button with `Archive` lucide icon). This opens a drawer or modal listing archived boards, lists, and cards with "Restore" and "Delete Permanently" buttons.
3. In the board gallery (rec 1.1), show archived boards in a separate collapsed section.

**Complexity:** Medium.

---

## 2. Card Interaction & Detail Panel

### 2.1 Drawer is the right pattern, but it needs more content

**Problem:** The Drawer pattern (slide-in from right) is correct for this use case — it keeps the board visible for context. However, the drawer is sparse: only title, move-to-list, description, due date, and priority. The API supports labels, checklists, comments, start dates, and links, none of which are shown. The drawer feels like a form, not a card detail view.

**Impact:** Medium. The drawer works for what it shows, but the absence of checklists/labels/comments limits the board's utility.

**Recommendation:** Restructure the drawer into sections with clear visual hierarchy:
1. **Header:** Title (editable inline, not a form field), list badge (clickable to move), priority indicator
2. **Properties section:** Due date, start date, priority — compact horizontal layout
3. **Labels section:** Color-coded chips with `+ Add label` button
4. **Checklists section:** Collapsible checklists with progress bars and inline item creation
5. **Description:** Expandable text area (collapsed to 3 lines when not editing)
6. **Comments section:** Chronological list with input at top
7. **Activity section:** Read-only log (from the `/activities` endpoint)
8. **Footer metadata:** Created/updated timestamps, card ID

Auto-save on blur rather than requiring explicit "Save Changes" button click.

**Complexity:** Large (but can be staged — labels first, then checklists, then comments).

### 2.2 Card preview on board shows too little

**Problem:** The `KanbanCardPreview` component (`BoardView.tsx:728-764`) shows only:
- Card title
- A 2x2px priority dot (barely visible, title-only tooltip)
- Due date badge (with overdue/complete coloring)

Missing from the preview: description snippet, labels, checklist progress, comment count, whether the card has attachments/links. This makes the board a wall of identical-looking white rectangles differentiated only by title text.

**Impact:** High. Users must click into every card to understand its state. This defeats the purpose of a visual board.

**Recommendation:** Enhance `KanbanCardPreview` to show:
1. **Labels:** A row of small color-coded rectangles (no text, just color — like Trello's compact view) above the title
2. **Checklist progress:** `3/5` with a mini progress bar if any checklists exist
3. **Comment count:** Small speech-bubble icon with count
4. **Description indicator:** Small document icon if description is non-empty (no text preview — too noisy)
5. **Priority:** Replace the 2px dot with a colored left border (4px) spanning the full card height — much more visible
6. **Cover image:** If metadata contains an image URL, show it as a card header (deferred)

**Complexity:** Medium (depends on backend response including label/checklist/comment summaries — the `GET /boards/{id}` endpoint may need to include these counts).

### 2.3 Move-to-list UX is clunky

**Problem:** Moving a card in the detail panel requires: (1) open dropdown, (2) select target list, (3) click "Move" button. Three steps for a common action. The current list is shown as a label but not integrated with the dropdown.

**Impact:** Low-Medium. Drag-and-drop covers most move scenarios; the panel move is a secondary path.

**Recommendation:** Replace with a single dropdown that shows all lists with the current one pre-selected and marked. Selecting a different list triggers the move immediately (no separate Move button). Add a position selector (top/bottom/specific position) as an optional disclosure.

**Complexity:** Small.

---

## 3. Creation & Editing Flows

### 3.1 Card quick-add is too minimal

**Problem:** The card quick-add (`BoardView.tsx:637-673`) only accepts a title via `Input.TextArea`. Users who want to set priority or due date must: create card → click card → open drawer → set fields → save. For rapid task capture this is fine, but for structured input it's 5 clicks too many.

**Impact:** Medium. Power users creating many cards with deadlines will feel friction.

**Recommendation:** Add optional "quick-set" chips below the title input during card creation:
- Priority: Four small colored buttons (L/M/H/U) — click to toggle
- Due date: A small calendar icon that opens a date picker inline
These should be collapsed by default and shown via a `...` expansion to keep the quick-add simple for minimal usage.

**Complexity:** Small-Medium.

### 3.2 Board creation is bare

**Problem:** The "Create New Board" modal (`index.tsx:229-250`) only asks for a board name. The `BoardCreate` type supports `description`, `activity_retention_days`, and `metadata`, none of which are exposed.

**Impact:** Low. Board description isn't visible anywhere in the current UI anyway.

**Recommendation:** Add an optional description textarea to the create modal (collapsed by default). Don't expose `activity_retention_days` or `metadata` — those are admin concerns. When the board gallery (rec 1.1) is implemented, show the description there.

**Complexity:** Small.

### 3.3 List creation is discoverable but lacks rename

**Problem:** The "Add List" button at the end of the board (`BoardView.tsx:443-483`) works well — it's in the natural flow. However, the list menu (`SortableList`) only has "Delete List" — there's no "Rename List" option. The `updateList` API exists but isn't wired up.

**Impact:** Medium. Users who typo a list name have no recourse except delete and recreate (losing all cards).

**Recommendation:** Add "Rename List" to the dropdown menu. Use inline editing: clicking "Rename" converts the list name span to an `<Input>` with Enter-to-save and Escape-to-cancel, identical to the list creation flow.

**Complexity:** Small.

---

## 4. Missing Functionality Prioritization

### 4.1 Ranked by UX impact

Based on the gap between API capabilities and current UI, ranked by user impact:

| Rank | Feature | Justification | Complexity |
|------|---------|---------------|------------|
| 1 | **Archive/Restore** | Only hard delete exists; data loss anxiety, PRD P1 | Medium |
| 2 | **Labels** | Color-coded categorization is core kanban; no filtering without it | Medium |
| 3 | **Search/Filter** | Can't find cards across boards; essential at 50+ cards | Medium |
| 4 | **Checklists** | Subtask tracking is the #2 reason people use kanban (after status tracking) | Medium-Large |
| 5 | **Board Export** | No way to backup; import exists but export doesn't | Small |
| 6 | **List Rename** | Can't fix typos without destroying the list | Small |
| 7 | **Card Copy/Duplicate** | Useful for templated work; API supports it | Small |
| 8 | **Comments** | Single-user use case reduces urgency; still useful for notes | Medium |
| 9 | **Start Dates** | Planning use case; due date alone is usually sufficient | Small |
| 10 | **Card Links** | Connecting to media/notes; deferred per PRD | Large |
| 11 | **Bulk Operations** | Power-user feature; low priority for initial UX | Medium |

### 4.2 How labels should integrate

**In the detail panel:** A "Labels" section between the properties section and description. Shows assigned labels as colored chips with `x` to remove. An `+ Add` button opens a popover with: existing board labels (click to toggle), a "Create new label" input with color picker.

**On the board:** Labels appear as small color bars above the card title in `KanbanCardPreview`. Clicking a label in the board header area toggles filtering.

### 4.3 How checklists should integrate

**In the detail panel:** Below labels. Each checklist has a title, progress bar (`3/5`), and collapsible item list. Items have checkboxes, text, and delete button. "Add item" input at the bottom of each checklist. "Add checklist" button creates a new named checklist.

**On the board:** Checklist progress icon (`CheckSquare` lucide icon + `3/5` text) in the badges row of `KanbanCardPreview`.

### 4.4 How search/filter should be presented

**Recommendation:** A search/filter bar between the board header and the lists area. Components:
1. **Search input:** Text search across card titles and descriptions (uses `GET /search` endpoint)
2. **Label filter:** Multi-select dropdown of board labels
3. **Priority filter:** Multi-select of priority levels
4. **Due date filter:** Overdue / Due today / Due this week / No date

When any filter is active, cards that don't match should be dimmed (not hidden) to maintain spatial awareness. A "Clear filters" button should appear when filters are active.

**Complexity:** Medium.

---

## 5. Drag-and-Drop & Micro-interactions

### 5.1 Drag overlay and drop zones

**Problem:** The drag overlay (`BoardView.tsx:487-499`) shows a simplified preview for cards and a minimal text-only preview for lists. There are no visual drop-zone indicators — users must guess where the card will land. The list overlay (`opacity-80, bg-surface`) doesn't match the actual list appearance.

**Impact:** Medium. Drag-and-drop works but feels imprecise.

**Recommendation:**
1. **Drop zone highlighting:** When dragging a card, highlight valid drop zones (list columns) with a subtle border glow or colored top border. Show a "ghost" insertion indicator (a thin colored line) at the exact position the card will land.
2. **List drag overlay:** Show a miniature version of the list (name + card count + first 2-3 card titles) to help users confirm what they're dragging.
3. **Smooth animations:** Use `transform` transitions for reordering rather than instant re-render. The `@dnd-kit` library supports this via `animateLayoutChanges`.

**Complexity:** Medium.

### 5.2 No undo for any action

**Problem:** Deleting a card, list, or board is irreversible from the UI perspective. Moving a card has no undo. The delete confirmations (`Popconfirm`) help, but accidental actions still happen. The PRD (U39) explicitly requires undo.

**Impact:** High. Users will lose work and lose trust.

**Recommendation:** Implement a toast-based undo pattern:
1. When a destructive action occurs (delete, move), show a toast with "Card deleted. Undo" (with a 10-second countdown).
2. "Undo" triggers the reverse API call (restore for deletes, move-back for moves).
3. Technically feasible because the backend uses soft deletes — the `/restore` endpoints exist for boards, lists, and cards.
4. For non-delete actions like card moves, store the previous `list_id` and `position` in a small undo stack (1-3 actions deep).

**Complexity:** Medium.

### 5.3 Error feedback is adequate but could be contextual

**Problem:** All errors go through `message.error()` toasts. For network failures during drag-and-drop, a toast that appears far from the interaction point is disorienting.

**Impact:** Low. Toasts work for most cases.

**Recommendation:** For drag-and-drop failures specifically, snap the card back to its original position with a brief shake animation. Keep toasts for form-level errors.

**Complexity:** Small.

---

## 6. Responsive Design & Density

### 6.1 Fixed list width

**Problem:** Lists are `w-72` (288px) via `flex-shrink-0 w-72` (`BoardView.tsx:601`, `443`). This is appropriate for desktop but doesn't adapt. On a 1920px monitor, this means 5-6 visible lists; on a 1366px laptop, 3-4 with horizontal scroll.

**Impact:** Low-Medium. The fixed width is a reasonable default but doesn't optimize for available space.

**Recommendation:** Keep `w-72` as the default. Add a compact mode toggle (in board header) that reduces list width to `w-60` (240px) and uses smaller card padding/font-size. On screens < 768px, switch to a single-list view with a list selector dropdown.

**Complexity:** Medium.

### 6.2 Card container max-height overflow

**Problem:** The card container has `max-h-[500px] overflow-y-auto` (`BoardView.tsx:625`). With many cards, users scroll within a scrollable container that itself may be in a scrollable page — nested scrolling is disorienting. 500px may cut off content on shorter screens.

**Impact:** Medium. Nested scroll is a known UX anti-pattern.

**Recommendation:** Set `max-height` dynamically based on viewport height: `max-h-[calc(100vh-250px)]` (subtracting header, tabs, board header, and padding). This ensures the card container fills available vertical space without competing with page scroll. Add a subtle scroll indicator (gradient fade at the bottom) when content overflows.

**Complexity:** Small.

### 6.3 No mobile/tablet adaptation

**Problem:** No responsive breakpoints exist. The horizontal list layout requires a wide viewport. On tablet/narrow windows, horizontal scrolling is the only escape.

**Impact:** Medium (depends on user base — if primarily desktop, lower priority).

**Recommendation:**
- **Tablet (768-1024px):** Reduce list width, hide board stats, compress card previews
- **Mobile (<768px):** Show one list at a time with a swipeable list selector or dropdown. The card detail panel should become full-screen instead of a side drawer.

**Complexity:** Large.

---

## 7. Keyboard Accessibility & Power Users

### 7.1 No keyboard shortcuts

**Problem:** Zero keyboard shortcuts are implemented. The PRD (U37) requires them. Power users have no way to work without a mouse.

**Impact:** High for accessibility, Medium for general UX.

**Recommendation:** Implement these shortcuts (shown via `?` help modal):

| Shortcut | Action |
|----------|--------|
| `N` | New card (focus quick-add in current/first list) |
| `B` | New board |
| `L` | New list |
| `/` or `Ctrl+K` | Focus search |
| `Esc` | Close detail panel / cancel current action |
| `Arrow keys` | Navigate between cards (when board is focused) |
| `Enter` | Open focused card's detail panel |
| `D` | Set due date on focused card |
| `P` | Set priority on focused card |
| `1-4` | Quick-set priority (1=low, 4=urgent) |

Use a keyboard shortcut hook that only activates when no input is focused.

**Complexity:** Medium.

### 7.2 No arrow-key card navigation

**Problem:** Users can't navigate between cards or lists using the keyboard. Tab-order follows DOM order but isn't visually indicated (no focus rings on cards).

**Impact:** High for accessibility (WCAG 2.1 AA non-compliance).

**Recommendation:** Add `tabIndex={0}` to cards and lists. Add visible focus styles (ring-2 ring-primary). Implement arrow key navigation: Left/Right between lists, Up/Down between cards within a list.

**Complexity:** Medium.

### 7.3 Drag-and-drop keyboard accessibility

**Problem:** `@dnd-kit/react` supports keyboard DnD (`KeyboardSensor`), but the current implementation (`BoardView.tsx`) doesn't configure it — only pointer interaction works.

**Impact:** High for accessibility.

**Recommendation:** Enable `@dnd-kit`'s keyboard sensor. When a card is focused and the user presses Space/Enter, enter drag mode. Arrow keys move the item; Space/Enter confirms; Escape cancels. Announce the action via `aria-live` region ("Card 'Fix login bug' moved to In Progress, position 3").

**Complexity:** Medium.

---

## 8. Empty States & Onboarding

### 8.1 First-time empty state is helpful but could be richer

**Problem:** When no boards exist, the empty state says "No boards yet. Create your first board" with a "Create Board" button (`index.tsx:117`). When boards exist but none is selected, it says "Select an existing board to get started". These are functional but don't explain what the Kanban feature is for in this application's context.

**Impact:** Low.

**Recommendation:** Enhance the first-time empty state:
- Add a brief subtitle: "Organize your research tasks, track media processing, or plan projects with boards and cards."
- Add a "Create Sample Board" button that creates a pre-populated board (e.g., "Research Project" with lists: Backlog, In Progress, Review, Done, and 2-3 sample cards showing different features like priority, due dates).
- Show 2-3 small illustrations or icons representing the board/list/card hierarchy.

**Complexity:** Small.

### 8.2 Empty board (no lists) state

**Problem:** When a board has no lists, the board view shows only the header, the "Add List" button, and empty space. There's no guidance.

**Impact:** Low.

**Recommendation:** Show a centered message: "This board is empty. Start by creating your first list — common choices are 'To Do', 'In Progress', and 'Done'." Optionally offer a "Quick Setup" button that creates these three default lists in one click.

**Complexity:** Small.

### 8.3 Empty list (no cards) state

**Problem:** When a list has no cards, only the "Add card" text button is shown at the bottom of the list. The list column looks empty and might be mistaken for a UI glitch.

**Impact:** Low.

**Recommendation:** Show a subtle placeholder inside empty lists: light dashed border with "Drop cards here or click + to add" centered in 50% opacity text. This also serves as a drop-target indicator for drag-and-drop.

**Complexity:** Small.

---

## 9. Additional Issues

### 9.1 No optimistic updates for drag-and-drop

**Problem:** When a card is dragged, the UI waits for the API response before reflecting the change (via `queryClient.invalidateQueries`). On slow connections, the card snaps back to its original position momentarily before re-rendering in the new position. This breaks the direct-manipulation illusion.

**Impact:** Medium. Makes drag-and-drop feel sluggish and unreliable.

**Recommendation:** Implement optimistic updates for drag-and-drop operations:
1. In `handleDragEnd`, immediately update the local React Query cache with the new card/list positions.
2. Fire the API call in the background.
3. On error, roll back the cache to the previous state and show a toast.

React Query's `onMutate`/`onError` pattern supports this directly.

**Complexity:** Medium.

### 9.2 Delete confirmations for boards and cards but not lists

**Problem:** Board delete uses `Popconfirm` with "Delete this board? All lists and cards will be deleted." Card delete uses `Popconfirm` in the detail panel. But list delete (`SortableList` menu) fires `onDeleteList` directly without confirmation, which calls `deleteListMutation.mutate(list.id)` immediately. A list with 50 cards can be deleted with one accidental click.

**Impact:** High. Data loss from an unconfirmed destructive action.

**Recommendation:** Wrap the "Delete List" menu item in a `Popconfirm` or a Modal.confirm that says "Delete list '{name}'? All {N} cards in this list will also be deleted."

**Complexity:** Small.

### 9.3 `newCardTitle` state is shared across all lists

**Problem:** `BoardView` has a single `newCardTitle` state (`BoardView.tsx:72`) shared across all lists. If a user starts adding a card to List A, types a title, then clicks "Add card" in List B, the title from List A is reused (or cleared). Only one list can be in "adding" mode at a time (`addingCardListId`), but the shared title state can cause subtle confusion.

**Impact:** Low (the single-active constraint mitigates it).

**Recommendation:** Move `newCardTitle` into the `SortableList` component as local state, or key it by list ID in a `Record<number, string>`. This allows opening multiple add-card inputs simultaneously if desired in the future.

**Complexity:** Small.

### 9.4 No loading feedback during card creation

**Problem:** `createCardMutation` doesn't show a loading indicator on the "Add" button. The button can be clicked multiple times, potentially creating duplicate cards (mitigated by `client_id` idempotency on the backend, but the UX is still confusing).

**Impact:** Low.

**Recommendation:** Pass `loading={createCardMutation.isPending}` to the Add button in the card quick-add area, and disable the button while pending.

**Complexity:** Small.

---

## Summary: Priority Matrix

### Quick wins (Small complexity, High/Medium impact)
1. Add delete confirmation to lists (9.2)
2. Add list rename to dropdown menu (3.3)
3. Dynamic card container max-height (6.2)
4. Loading state on card creation button (9.4)
5. Move Import to overflow menu (1.2)

### Medium effort, High impact
6. Archive/Restore UI (1.3)
7. Undo via toast (5.2)
8. Enhanced card preview — labels, checklists, priority border (2.2)
9. Keyboard shortcuts (7.1)
10. Optimistic DnD updates (9.1)

### Larger efforts worth planning
11. Board gallery view (1.1)
12. Labels CRUD + filtering (4.1 rank 2)
13. Search/filter bar (4.1 rank 3)
14. Checklists in detail panel (4.1 rank 4)
15. Responsive/mobile layout (6.3)
16. Full keyboard accessibility + DnD a11y (7.2, 7.3)
17. Card detail panel restructure with auto-save (2.1)
