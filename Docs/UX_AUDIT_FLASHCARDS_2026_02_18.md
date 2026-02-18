# UX/HCI Audit: Flashcards Page

**Date**: 2026-02-18
**Auditor**: Claude (HCI/Design evaluation)
**Scope**: `/flashcards` page — Review, Cards, Import/Export tabs
**Method**: Code-level analysis against Nielsen's 10 heuristics, Shneiderman's 8 golden rules, first-use walkthrough, competitive comparison

---

## 1. Executive Summary — Top 5 Highest-Impact Findings

| # | Finding | Severity | Heuristic | Impact |
|---|---------|----------|-----------|--------|
| 1 | **No LLM card generation exposed in UI** — The backend has a fully functional `flashcard_generate` adapter (text → cards via any LLM provider) but the UI offers zero access to it. Users must manually type every card. This is the single biggest missed opportunity in the product. | **Major** | Match between system and real world / Flexibility | Users can't leverage the core "tldw" value prop: turning media/notes into study material automatically |
| 2 | **No review history or learning analytics** — The `flashcard_reviews` table stores every rating with `answer_time_ms`, `scheduled_interval_days`, `new_ef`, `was_lapse` — but none of this is exposed. No stats dashboard, no per-card learning curve, no retention rate, no heatmap. | **Major** | Visibility of system status | Users have no insight into whether spaced repetition is working for them |
| 3 | **No card edit from Review tab** — When studying and finding a typo, there's no way to edit the current card without navigating to the Cards tab, finding it, and opening the edit drawer. The Review → Edit → Resume loop is broken. | **Major** | User control and freedom / Flexibility | Disrupts the core review flow; users must remember to fix cards later |
| 4 | **SM-2 jargon not explained** — Terms like "ease factor" (2.5), "interval" (0 days), "repetitions", "lapses", and rating labels (Again/Hard/Good/Easy mapped to 0/2/3/5) are presented without explanation. Non-Anki users won't understand what they mean. | **Major** | Help and documentation / Match between system and real world | Alienates the majority of users who haven't used Anki |
| 5 | **No deck-level statistics** — No card counts per deck (total, new, learning, due, mature), no per-deck progress indicators. The deck selector shows only names. | **Minor** | Visibility of system status | Users can't prioritize which deck to study or gauge collection health |

---

## 2. Heuristic Violations

### H1: Visibility of System Status

| ID | Issue | Severity | Location |
|----|-------|----------|----------|
| H1-1 | **No study statistics/analytics view.** Review history is tracked server-side (`flashcard_reviews` table: `answer_time_ms`, `new_ef`, `was_lapse`, `scheduled_interval_days`) but never surfaced. No cards-reviewed-today count, retention rate, average answer time, or study streaks. | Major | Missing entirely |
| H1-2 | **Deck selector shows no due counts.** The `<Select>` dropdown for deck filtering only shows deck names. It should show counts like `"Biology (12 due)"`. The data exists — `useDueCountsQuery` already fetches per-status counts, but only for the selected deck, not all decks in the selector. | Minor | `ReviewTab.tsx:306-325` |
| H1-3 | **Import results lack detail.** After import, the UI shows a generic "Imported" toast. The API returns `{imported, items, errors}` — the number of imported cards, error details with line numbers, and skipped items aren't shown. | Minor | `ImportExportTab.tsx:43` |
| H1-4 | **No scheduling feedback after rating.** When a user rates a card, they see "Success" toast. They don't see the _result_: "Next review in 4 days" or the new ease factor. The `FlashcardReviewResponse` has `due_at`, `ef`, `interval_days` but it's discarded after mutation. | Minor | `ReviewTab.tsx:207` |
| H1-5 | **Card metadata hidden in Cards tab.** In compact mode, `ef`, `interval_days`, `repetitions`, `lapses` aren't visible. In expanded mode, only `due_at` is shown. Users can't see _why_ a card is scheduled when it is. | Cosmetic | `ManageTab.tsx:1111-1193` |

### H2: Match Between System and Real World

| ID | Issue | Severity | Location |
|----|-------|----------|----------|
| H2-1 | **SM-2 terminology unexplained.** "Ease factor", "interval", "repetitions", "lapses" appear in the data model and API but the UI uses them without context. The rating descriptions help (`"I didn't remember this card"`) but the interval previews (`"< 1 min"`, `"4 days"`) aren't explained. | Major | `ReviewTab.tsx:91-144` |
| H2-2 | **"Model type" terminology.** The create/edit forms use "Card template" as the label (good) but the API field is `model_type` and the internal values are `basic`, `basic_reverse`, `cloze`. The UI labels are clear (`"Basic (Question - Answer)"`) but "Cloze (Fill in the blank)" doesn't explain cloze syntax `{{c1::text}}`. | Minor | `FlashcardCreateDrawer.tsx:286-314` |
| H2-3 | **Rating scale mismatch.** The UI shows 4 buttons (Again/Hard/Good/Easy) mapped to values 0, 2, 3, 5. The SM-2 scale is 0-5 with ratings 1 and 4 unused. This works but the gap between Hard (2) and Good (3) is only 1 point while Easy (5) jumps 2 points from Good. The asymmetry isn't communicated. | Cosmetic | `useFlashcardShortcuts.ts:3-8` |

### H3: User Control and Freedom

| ID | Issue | Severity | Location |
|----|-------|----------|----------|
| H3-1 | **No card edit during review.** The Review tab shows the card content but has no "Edit this card" button. Users who spot errors must leave Review, navigate to Cards tab, find the card, and edit it. | Major | `ReviewTab.tsx:346-491` |
| H3-2 | **No card scheduling reset.** Users can't reset a card's SM-2 state (clear review history, return to "new"). If a card's ease factor drops too low or the scheduling feels wrong, there's no recovery. The API supports updating `ef`, `interval_days`, `repetitions`, `lapses` via PATCH, but the UI doesn't expose it. | Minor | `FlashcardEditDrawer.tsx` (missing) |
| H3-3 | **Undo scope is limited.** Review undo (10s, re-present card) and delete undo (30s, trash view) are good. But there's no undo for card edits, bulk moves, or import. | Cosmetic | Various |
| H3-4 | **No "cram" / study-outside-schedule mode.** Users can only study cards that are due. There's no way to review cards ahead of schedule (cram mode), study a specific subset regardless of due date, or do a "preview" session. | Minor | `ReviewTab.tsx` (missing) |

### H4: Consistency and Standards

| ID | Issue | Severity | Location |
|----|-------|----------|----------|
| H4-1 | **Tab naming inconsistency.** The tabs are "Review", "Cards", "Import / Export". Other app features use single-view patterns (Characters, Dictionaries). Flashcards is the only feature with 3 tabs, which is justified by the distinct workflows, but the mental model differs from the rest of the app. | Cosmetic | `FlashcardsManager.tsx:80-114` |
| H4-2 | **Create drawer opens from different locations.** The Review tab has a "Create a new card" button (top bar), the Cards tab has a FAB (bottom-right circle), and empty states have CTAs. The entry point varies by context, which is flexible but could confuse first-time users about where card creation "lives". | Cosmetic | `ReviewTab.tsx:327-335`, `ManageTab.tsx:1391-1403` |
| H4-3 | **Drawer width inconsistent.** Create and Edit drawers use `width: 520` (via styles.wrapper). The Move drawer uses `size={360}`. This inconsistency is minor but noticeable on desktop. | Cosmetic | `FlashcardCreateDrawer.tsx:168`, `ManageTab.tsx:1326` |

### H5: Error Prevention

| ID | Issue | Severity | Location |
|----|-------|----------|----------|
| H5-1 | **No cloze syntax validation in UI.** The backend validates that cloze cards contain `{{cN::...}}` patterns, but the Create/Edit form doesn't validate or preview cloze rendering. Users won't know the required syntax. | Minor | `FlashcardCreateDrawer.tsx:324-336` |
| H5-2 | **Empty front/back validation is form-level only.** The form marks front and back as `required: true` but there's no inline hint or character count. Large card content could hit the 8,192-byte field limit silently. | Cosmetic | `FlashcardCreateDrawer.tsx:325-351` |
| H5-3 | **Import format errors are swallowed.** The import panel's example shows the TSV format, but if a user pastes CSV with the wrong delimiter or bad encoding, the API error is generic. Error line numbers from the API response aren't displayed. | Minor | `ImportExportTab.tsx:36-49` |

### H6: Recognition Rather Than Recall

| ID | Issue | Severity | Location |
|----|-------|----------|----------|
| H6-1 | **Source references not shown.** Cards have `source_ref_type` (media/message/note/manual) and `source_ref_id` fields, but the UI never displays where a card came from. Users can't trace back to the original content. | Minor | Service layer has fields; UI ignores them |
| H6-2 | **Keyboard shortcuts require memorization.** The `?` modal is good but shortcuts aren't hinted inline beyond "Press Space to flip" and "Press 1-4 to rate". The keyboard badge on rating buttons (showing "1", "2", etc.) is excellent. Cards tab has a small `?` hint but it's easy to miss. | Cosmetic | `ReviewTab.tsx:405-408`, `ManageTab.tsx:808-816` |

### H7: Flexibility and Efficiency of Use

| ID | Issue | Severity | Location |
|----|-------|----------|----------|
| H7-1 | **No LLM card generation.** The backend has `flashcard_generate` adapter accepting text + provider + model + difficulty + format + focus topics. This is completely absent from the UI. Even a basic "Generate cards from text" textarea would be transformative. | Major | Missing entirely |
| H7-2 | **No JSON/JSONL import in UI.** The backend supports `POST /flashcards/import/json` for JSON array and JSONL files, but the Import panel only handles CSV/TSV paste/drop. | Minor | `ImportExportTab.tsx` (only CSV/TSV) |
| H7-3 | **Single-tag filter only.** The Cards tab filter accepts one tag at a time (typed into an Input). There's no tag browser, tag autocomplete from existing tags, or multi-tag intersection/union filter. | Minor | `ManageTab.tsx:866-892` |
| H7-4 | **No sort control.** Cards are always ordered by `due_at`. Users can't sort by creation date, ease factor, last reviewed, or alphabetically. The API supports `order_by: "due_at" | "created_at"` and could be extended. | Minor | `useFlashcardQueries.ts:122` |
| H7-5 | **No bulk tag operation.** The floating action bar has Move, Export, Delete — but no "Add tag" or "Remove tag" for bulk operations. | Cosmetic | `ManageTab.tsx:1299-1310` |

### H8: Aesthetic and Minimalist Design

| ID | Issue | Severity | Location |
|----|-------|----------|----------|
| H8-1 | **Review tab top bar is busy.** A full-width Select + a primary "Create a new card" button are always visible, even mid-review. The create CTA competes with the review flow and is more relevant to the Cards tab. | Cosmetic | `ReviewTab.tsx:305-336` |
| H8-2 | **Import/Export tab is sparse.** The two-column layout (import left, export right) works on desktop but feels empty. Neither panel has enough content to justify the full width. On mobile, they stack well. | Cosmetic | `ImportExportTab.tsx:253-270` |

### H9: Help Users Recognize, Diagnose, and Recover from Errors

| ID | Issue | Severity | Location |
|----|-------|----------|----------|
| H9-1 | **Version conflict error is opaque.** Optimistic locking failures surface as generic API errors. The `expected_version` mechanism should produce a clear "This card was modified elsewhere. Reload to see changes." message. | Minor | `ManageTab.tsx:729-747` |
| H9-2 | **Review failure lacks retry.** If `reviewMutation.mutateAsync` fails (network error, version conflict), the error message is shown but there's no retry mechanism. The card state may be inconsistent. | Minor | `ReviewTab.tsx:208-212` |

### H10: Help and Documentation

| ID | Issue | Severity | Location |
|----|-------|----------|----------|
| H10-1 | **No onboarding or feature explanation.** First-time users see the empty Review tab with "No flashcards yet" + "Create a flashcard" / "Import a deck" buttons. There's no explanation of what spaced repetition is, why it works, or how the SM-2 algorithm schedules reviews. | Major | `ReviewTab.tsx:493-600` |
| H10-2 | **No cloze syntax help.** Users selecting "Cloze" card template receive no guidance on `{{c1::answer}}` syntax. A brief inline example or help link is needed. | Minor | `FlashcardCreateDrawer.tsx:306-313` |
| H10-3 | **No import format documentation.** The import panel shows one example line but doesn't document all accepted columns (deck, front, back, tags, notes, extra, model_type, reverse) or that tags can be space or comma-delimited. | Minor | `ImportExportTab.tsx:53-63` |

---

## 3. Per-Tab Findings

### 3.1 Review Tab (`tabs/ReviewTab.tsx`)

**Strengths:**
- Clean card display with Markdown rendering via `MarkdownWithBoundary`
- Good rating button design: colored, iconic (X/Minus/Check/Star), with keyboard shortcut badges and interval previews
- WCAG AA contrast ratios noted in code comments (`ReviewTab.tsx:101-139`)
- Undo mechanism with visible countdown timer and `role="timer"` + `aria-live="polite"` (`ReviewTab.tsx:459-485`)
- `ReviewProgress` component with remaining count, reviewed count, time estimate, sr-only status, and `aria-live="polite"` (`ReviewProgress.tsx:31-63`)
- Next-due-date display with "next review: X days from now" and card count (`ReviewTab.tsx:550-589`)
- "You're all caught up!" celebration with emoji and session stats (`ReviewTab.tsx:529-542`)
- Auto answer-time tracking (`answerStartTimeRef`) without user input
- LLM tutorial residue detection (`review-card-hygiene.ts`) — clever, filters out instructional junk cards

**Issues:**
1. **No edit button on current card** — Can't fix errors mid-review
2. **Create CTA in top bar is distracting** during active review — should be contextual (only in empty states)
3. **"Show Answer" button has no animation/transition** — card content just appears. A flip animation would provide spatial continuity
4. **Extra field shown below Back without label** — just indented and muted, not clearly labeled as "Extra / Hint"
5. **No progress bar visualization** — only text counts. A progress bar (reviewed/total) would provide better visual feedback
6. **Deck selector resets reviewed count** — expected behavior, but no warning that progress tracking restarts

### 3.2 Cards Tab (`tabs/ManageTab.tsx`)

**Strengths:**
- Comprehensive filter system: search (FTS5), deck, tag, due status segmented control
- Two density modes (compact/expanded) with toggle
- Full keyboard navigation (j/k, Enter to edit, Space to select, Delete, Esc)
- Sophisticated selection model: per-page, cross-results ("Select all N"), visual badge differentiation
- Floating action bar appears on selection with Move/Export/Delete
- 30-second soft-delete with trash view and per-item undo
- Type-to-confirm modal for bulk deletes >100 items
- Progress modal for long-running bulk operations
- Duplicate and Move actions per card
- FAB (floating action button) for quick card creation
- Colorblind-accessible selection indicators (Check vs CheckCheck icons)
- 44px touch targets on checkboxes and undo buttons

**Issues:**
1. **Tag filter is a plain text input** — no autocomplete from existing tags, no multi-tag support
2. **No sort control** — always by due_at; no option to sort by created, ease, last reviewed
3. **No bulk tag operation** — can bulk move and bulk delete but not bulk tag
4. **No inline card preview in compact mode** — must switch to expanded or click to toggle preview
5. **Focused item ring styling may not be visible** on all themes — `ring-2 ring-primary` relies on primary color contrast
6. **Empty state logic is in a ternary based on filter state** — works but the conditional text could be clearer about what "no cards match your filters" means vs "no cards exist"
7. **Trash view loses context** — "Deleted cards appear here for 30 seconds" but doesn't show which batch/action triggered the deletion

### 3.3 Import/Export Tab (`tabs/ImportExportTab.tsx`)

**Strengths:**
- Clean two-column layout (import + export)
- File drop zone with drag-and-drop support (`FileDropZone` component)
- Multiple delimiter options (tab, comma, semicolon, pipe)
- Header toggle switch
- Import limits shown when available
- APKG export option (Anki-compatible)

**Issues:**
1. **No JSON/JSONL import** — backend supports it, UI doesn't
2. **No import preview** — users can't see parsed results before committing
3. **No import error detail display** — API returns line-by-line errors but UI shows generic toast
4. **Single example line** — format documentation is minimal; doesn't mention accepted column names
5. **No export preview/count** — users don't know how many cards will be exported before clicking
6. **Export options are minimal** — no include_reverse, include_header, extended_header, delimiter, or tag/query filter (only deck filter)
7. **No APKG import** — can export to APKG but can't import from it (backend limitation)
8. **"CSV" label for export when default is TSV** — the export panel says "CSV" but the default behavior produces TSV. Could confuse users who expect comma-delimited output.

---

## 4. Missing Information Inventory

| API Data | Available In | Exposed in UI | Impact |
|----------|-------------|---------------|--------|
| `flashcard_reviews` table (every rating, answer_time_ms, new_ef, was_lapse, scheduled_interval_days) | DB | **No** — no review history display, no analytics | High — users can't track learning progress |
| `source_ref_type` + `source_ref_id` (media/message/note/manual origin) | Flashcard model | **No** — not shown on cards, no link-back | Medium — can't trace cards to source content |
| `conversation_id` + `message_id` (chat origin) | Flashcard model | **No** — not shown | Medium — chat-generated cards aren't linked |
| `ef` (ease factor) | Flashcard model | **No** — not shown in card list or edit drawer | Low — mainly for power users |
| `interval_days` | Flashcard model | **Partial** — shown as relative time on due cards | Low |
| `repetitions` count | Flashcard model | **No** | Low — useful for identifying cards never reviewed |
| `lapses` count | Flashcard model | **No** | Medium — identifies "leech" cards that keep being forgotten |
| `FlashcardReviewResponse` (new_ef, interval, due_at after rating) | Review mutation | **Discarded** — only "Success" toast shown | Medium — no scheduling feedback |
| `FlashcardGenerateConfig` (LLM card generation) | Workflows adapter | **No** — not exposed anywhere | **Critical** — core differentiator not available |
| Import error details (line numbers, field errors, skipped count) | Import response | **No** — generic "Imported" toast | Medium — users can't fix import issues |
| Deck statistics (card counts by status) | Derivable from list queries | **Partial** — `useDueCountsQuery` exists but only for selected deck | Medium |
| `GET /flashcards/export` query/tag filters | Export endpoint | **No** — only deck_id filter in UI | Low |
| Export options (include_reverse, include_header, extended_header, delimiter) | Export endpoint | **No** — hardcoded csv/apkg choice only | Low |
| Bulk create endpoint (`POST /flashcards/bulk`) | API | **Not directly** — import uses it internally | Low |

---

## 5. Workflow Friction Map

### 5.1 Creating a First Flashcard and Studying It

| Step | Action | Friction | Clicks |
|------|--------|---------|--------|
| 1 | Navigate to /flashcards | None | 1 |
| 2 | See empty Review tab: "No flashcards yet" | **No explanation of what flashcards are or why** | 0 |
| 3 | Click "Create a flashcard" | Navigates to Cards tab (tab switch) | 1 |
| 4 | Cards tab is empty — click "Create your first card" OR notice FAB | **Two CTAs compete** (empty state button vs FAB) | 1 |
| 5 | Fill Create Drawer: select/create deck, type front, type back | Deck creation is inline (good). Minimum fields: front + back. | 3-5 |
| 6 | Click "Create" | Card created, drawer closes, list shows card | 1 |
| 7 | Navigate back to Review tab | **Manual tab switch required** — no "Start reviewing" CTA after creation | 1 |
| 8 | Card appears for review. Click "Show Answer" | | 1 |
| 9 | Rate card (1-4) | | 1 |
| **Total** | | | **~10 clicks, 2 tab switches** |

**Recommendations:**
- After creating first card, offer "Start reviewing now" button
- Skip deck requirement for first card (create a "Default" deck automatically)
- Add brief onboarding text explaining spaced repetition value

### 5.2 Importing an Existing CSV Collection

| Step | Action | Friction | Clicks |
|------|--------|---------|--------|
| 1 | Navigate to Import/Export tab | | 1 |
| 2 | Read format hint: "Paste TSV/CSV lines: Deck, Front, Back, Tags, Notes" | **Minimal documentation — what about Extra, model_type?** | 0 |
| 3 | Drag file or paste content | File drop zone is clear | 1 |
| 4 | Select delimiter (if not TSV) | Default is Tab — good for Anki exports | 0-1 |
| 5 | Toggle "Has header" if needed | Default ON — correct assumption | 0-1 |
| 6 | Click "Import" | | 1 |
| 7 | See "Imported" toast | **No detail: how many imported? Any errors? Skipped?** | 0 |
| **Total** | | | **~4 clicks** |

**Recommendations:**
- Show import results: "42 cards imported to 3 decks, 2 errors (lines 15, 23)"
- Add format documentation link or expandable help
- Add import preview before committing

### 5.3 Daily Review Session

| Step | Action | Friction |
|------|--------|---------|
| 1 | Navigate to /flashcards | Review tab is default — good |
| 2 | (Optional) Select a deck | Deck selector is prominent — good |
| 3 | See ReviewProgress: "12 cards remaining, 0 reviewed, ~3 min left" | **Excellent — clear at a glance** |
| 4 | Study: Show Answer → Rate → next card → repeat | **Smooth core loop. Keyboard shortcuts (Space, 1-4) work well** |
| 5 | Spot a typo on a card | **No edit button. Must leave review to fix.** |
| 6 | Rate incorrectly — hit Ctrl+Z within 10s | **Good undo. Countdown timer visible.** |
| 7 | All cards done — see celebration | **"You're all caught up!" with count + next due date — good** |

**Recommendations:**
- Add "Edit" button on the review card (opens drawer, returns to review after save)
- Show post-rating scheduling: "Next review: Wed Feb 21"

### 5.4 Editing a Card Mid-Review

| Step | Action | Friction |
|------|--------|---------|
| 1 | See a card with an error during review | |
| 2 | Click... nothing. No edit button on review card. | **Dead end.** |
| 3 | Switch to Cards tab | Review state (position, count) may be disrupted |
| 4 | Search for the card (by front text) | May need to remember the exact text |
| 5 | Find card, click Edit, fix, Save | |
| 6 | Switch back to Review tab | Reviewed count is preserved (good) |
| **Total** | | **6+ steps for a simple typo fix** |

**Recommendation:** Add an "Edit" icon button in the review card header. Open edit drawer as overlay. On save, return to review with the updated card.

### 5.5 Bulk Organizing Cards

| Step | Action | Friction |
|------|--------|---------|
| 1 | Browse Cards tab | Filters (deck, search, tag, due status) work well |
| 2 | Select cards (checkbox per row or "Select all") | **Excellent: per-page and cross-results selection** |
| 3 | Floating action bar appears with Move/Export/Delete | **Good discoverability** |
| 4 | Want to bulk-tag cards | **Not available in floating bar. Must edit individually.** |
| 5 | Bulk Move: select deck in drawer → Move | Works, no progress indicator for small batches |
| 6 | Bulk Delete: confirm → 30s undo window | **Good: type-to-confirm for >100, trash view, undo** |

**Recommendation:** Add "Tag" action to floating bar.

### 5.6 Exporting to Anki (APKG)

| Step | Action | Friction |
|------|--------|---------|
| 1 | Navigate to Import/Export tab | |
| 2 | In Export panel, select deck (or all) | |
| 3 | Select format: "APKG (Anki)" | **Good — clear label** |
| 4 | Click Export | Download starts |
| 5 | Open in Anki | **Works — scheduling state preserved** |
| **Total** | | **~4 clicks, straightforward** |

**Notes:** APKG export is well-implemented. The exporter preserves SM-2 scheduling state, handles cloze cards, extracts embedded media. Export options (include_reverse, include_header, extended_header) are not exposed in the UI but available in the API.

---

## 6. Prioritized Recommendations

### Quick Wins (Low effort, high impact)

| # | Recommendation | Effort | Impact | Files |
|---|----------------|--------|--------|-------|
| Q1 | **Add "Edit" button to review card** — Opens FlashcardEditDrawer as overlay during review | Low | High | `ReviewTab.tsx` |
| Q2 | **Show import result details** — Display count imported, errors with line numbers, skipped items from API response | Low | Medium | `ImportExportTab.tsx` |
| Q3 | **Show scheduling feedback after rating** — Use `FlashcardReviewResponse.due_at` to show "Next review: Wed Feb 21" in toast | Low | Medium | `ReviewTab.tsx` |
| Q4 | **Add cloze syntax help** — Show inline example `{{c1::answer}}` when "Cloze" template is selected | Low | Medium | `FlashcardCreateDrawer.tsx`, `FlashcardEditDrawer.tsx` |
| Q5 | **Add deck due-count badges** — Show "(12 due)" next to deck names in the review deck selector | Low | Medium | `ReviewTab.tsx`, `useFlashcardQueries.ts` |
| Q6 | **Add sort control to Cards tab** — Add a dropdown: "Sort by: Due date / Created / Ease factor" | Low | Medium | `ManageTab.tsx`, `useFlashcardQueries.ts` |
| Q7 | **Expose more export options** — Add checkboxes for include_reverse, include_header, delimiter selection | Low | Low | `ImportExportTab.tsx` |
| Q8 | **Show source reference on cards** — Display a small badge/link when `source_ref_type` !== 'manual' | Low | Low | `ManageTab.tsx`, `FlashcardEditDrawer.tsx` |

### Medium-Term (Moderate effort, high impact)

| # | Recommendation | Effort | Impact | Files |
|---|----------------|--------|--------|-------|
| M1 | **Build a study statistics dashboard** — Cards reviewed today, retention rate (from `was_lapse`), average answer time, streak, per-deck progress. Use `flashcard_reviews` table data. | Medium | High | New component, new API endpoint or query |
| M2 | **Expose LLM card generation** — Add "Generate from text" panel in Import/Export or a dedicated tab. Text input + provider/model selector + difficulty + count → preview generated cards → import. | Medium | **Critical** | New component, integrate with Workflows adapter |
| M3 | **Add tag autocomplete** — Fetch existing tags from cards, provide typeahead in the tag filter and tag inputs. Support multi-tag filter. | Medium | Medium | `ManageTab.tsx`, `FlashcardCreateDrawer.tsx` |
| M4 | **Add card scheduling info panel** — In the edit drawer, show read-only SM-2 metadata: ease factor, interval, repetitions, lapses, review count, last reviewed. Add "Reset scheduling" button. | Medium | Medium | `FlashcardEditDrawer.tsx` |
| M5 | **Add JSON/JSONL import** — File upload with format detection, preview table, import. Backend already supports it. | Medium | Medium | `ImportExportTab.tsx`, new component |
| M6 | **Add bulk tag operation** — "Add tag" and "Remove tag" actions in the floating selection bar. | Medium | Medium | `ManageTab.tsx` |
| M7 | **Add onboarding/first-use flow** — When user has 0 decks/cards: explain spaced repetition, show a "Quick start" wizard (create first card, import, or generate from content). | Medium | High | `ReviewTab.tsx`, new component |
| M8 | **Import preview** — Before committing, show a table of parsed cards with column mapping. Allow users to fix issues before import. | Medium | Medium | `ImportExportTab.tsx`, new component |

### Strategic (High effort, transformative)

| # | Recommendation | Effort | Impact |
|---|----------------|--------|--------|
| S1 | **"Generate flashcards" from any media/note** — Deep integration with media viewer and notes: "Generate flashcards from this transcript/document/note" button. Uses the existing Workflows flashcard_generate adapter. | High | Transformative |
| S2 | **Review history & learning analytics** — Heatmap (GitHub-style), retention curve per card, cards-per-day chart, leech detection (high-lapse cards), time-per-card analysis. Requires new API endpoint to query `flashcard_reviews` with aggregation. | High | High |
| S3 | **Card preview during review (cram mode)** — Allow studying cards outside their SRS schedule. Filter by deck/tag, show all cards regardless of due date, optionally update scheduling. | High | Medium |
| S4 | **Rich media cards** — Support images, audio clips, LaTeX math rendering on card front/back. The Markdown renderer likely supports LaTeX already; images would need upload/storage integration. | High | Medium |
| S5 | **Study session settings** — Max new cards/day, max reviews/day, learning steps, order preferences (random vs order). Per-deck configuration stored server-side. | High | Medium |

---

## 7. Competitive Gap Analysis

### Feature Comparison: Flashcards vs Anki vs Mochi vs Quizlet

| Feature | tldw Flashcards | Anki Desktop | Mochi | Quizlet |
|---------|----------------|--------------|-------|---------|
| **Spaced repetition algorithm** | SM-2 | SM-2 (modified) + FSRS | SM-2 variant | Simple SRS (paid) |
| **Card types** | Basic, Reverse, Cloze | Basic, Reverse, Cloze, Custom | Basic, Cloze | Basic, True/False |
| **Rich media** | Markdown + LaTeX | HTML + Images + Audio + Video + LaTeX | Markdown + Images | Images + Audio |
| **Deck management** | Basic (name, description) | Hierarchical decks, subdecks, tags | Folders, nested decks | Sets, folders |
| **Import formats** | CSV/TSV, JSON/JSONL (API) | APKG, CSV, plain text | Markdown, CSV, Anki | CSV, Quizlet, Anki |
| **Export formats** | CSV/TSV, APKG | APKG, plain text | Markdown, Anki | CSV, PDF, print |
| **Statistics** | Session count only | Comprehensive: reviews/day, retention, intervals, added/day, card states | Basic stats | Basic completion % |
| **Study modes** | Due cards only | Custom study (cram, preview, tag filter) | Focused review | Learn, Test, Match, Write |
| **Card generation** | Backend only (LLM) | Via add-ons | Built-in AI | AI-enhanced (paid) |
| **Keyboard shortcuts** | Space, 1-4, j/k, Ctrl+Z | Space, 1-4, E to edit, * to flag | Limited | None |
| **Mobile** | Responsive (untested) | Dedicated apps | Web-responsive | Dedicated apps |
| **Sync** | Single-server (sync_log table) | AnkiWeb sync | Cloud sync | Cloud sync |
| **Community decks** | No | Shared decks (AnkiWeb) | Shared templates | Public sets |
| **Leech detection** | Lapses tracked but not surfaced | Auto-suspend leeches | No | No |
| **Card flagging during review** | No | Flag 1-7, Mark | No | Star |
| **Undo** | 10s re-rate | Full undo | Limited | No |
| **Edit during review** | No | Yes (E key) | Yes | No |
| **Custom study/cram** | No | Yes | No | Yes (via modes) |

### Key Competitive Gaps

1. **Statistics/Analytics** — Anki's stats view is considered best-in-class. tldw has the data (review history) but zero UI.
2. **Edit during review** — Anki allows pressing "E" to edit mid-review. tldw doesn't.
3. **AI card generation** — tldw has the backend but not the UI. Mochi and Quizlet both offer AI generation. This is tldw's unique advantage (media-to-cards pipeline) that's currently unrealized.
4. **Custom study/cram** — Both Anki and Quizlet offer ways to study outside the normal schedule. tldw only shows due cards.
5. **Card flagging** — Anki lets users flag cards during review (e.g., "needs editing", "leech"). tldw has no equivalent.
6. **Hierarchical organization** — Anki supports subdecks. tldw has flat decks only.

### Unique tldw Advantages (vs competitors)

1. **Media integration** — No competitor can generate flashcards from video transcripts, PDFs, EPUBs, or notes within the same platform
2. **MCP integration** — AI agents can create, manage, and review flashcards programmatically
3. **Source tracking** — Cards can link back to their media/note/message origin (when surfaced in UI)
4. **Open architecture** — Self-hosted, no subscription, full API access, LLM-provider agnostic
5. **APKG export** — Full Anki compatibility including scheduling state preservation

---

## 8. Accessibility Assessment

### Strengths
- Rating buttons have explicit `aria-label` with description and shortcut key (`ReviewTab.tsx:429`)
- Rating button group has `role="group"` with `aria-label` (`ReviewTab.tsx:419`)
- Undo countdown uses `role="timer"` and `aria-live="polite"` (`ReviewTab.tsx:477-478`)
- Trash item expiry uses `role="timer"` and contextual `aria-live` (`ManageTab.tsx:1228-1229`)
- ReviewProgress uses `role="status"`, `aria-live="polite"`, `aria-atomic="true"` with sr-only text (`ReviewProgress.tsx:32-39`)
- Large icons (24px, `size-6`) on rating buttons for colorblind accessibility (`ReviewTab.tsx:434-435`)
- Keyboard shortcut badges provide visual differentiation beyond color (`ReviewTab.tsx:439-441`)
- 44px minimum touch targets on checkboxes and buttons (`ManageTab.tsx:950, 1087`)
- Colorblind-friendly selection indicators (Check vs CheckCheck icons) (`ManageTab.tsx:972-976`)
- Focus ring styling on rating buttons (`focus:ring-2 focus:ring-offset-2`) (`ReviewTab.tsx:430`)

### Gaps
- **Focus trap in drawers** — Ant Design Drawer handles focus trapping, but not verified for the Move drawer or type-to-confirm modal
- **Screen reader card navigation** — The Cards tab list items don't have `role="listitem"` (Ant Design `<List>` may handle this automatically)
- **Color-only due indicators** — The green dot for "due now" in compact mode relies on color alone (tiny `w-2 h-2 rounded-full bg-success`). Should have an accompanying text label or tooltip
- **Review card content** — Card front/back content rendered via `MarkdownWithBoundary` — accessibility of rendered markdown (heading levels, link text, image alt) depends on card content, not the component
- **No skip-to-content** or landmark regions — The tabs structure doesn't use `<main>`, `<nav>`, or skip links

---

## 9. Responsive Design Notes

- Main container: `max-w-6xl p-4` — constrains width on desktop, full width on mobile
- Import/Export: `grid-cols-1 lg:grid-cols-2` — stacks on mobile, side-by-side on desktop (good)
- Deck selector: `min-w-64 max-w-full flex-1` — takes available width (good)
- Rating buttons: `flex flex-wrap gap-2 justify-center` — wraps on narrow screens (good)
- Floating action bar: `fixed bottom-4 left-1/2 -translate-x-1/2` — centered on all widths (good)
- FAB: `fixed bottom-6 right-6` — always visible (good)
- Card list: `flex-wrap` on filter bar, responsive text truncation
- **Not tested**: Touch gestures (swipe to rate), mobile Safari keyboard, narrow viewport (<375px)
- **Concern**: Keyboard shortcut hint `hidden sm:inline` hides on mobile but shortcuts may not work on mobile anyway
