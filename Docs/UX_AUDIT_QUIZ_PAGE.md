# Quiz Page (/quiz) — HCI & Design Expert Review

**Date:** 2026-02-17
**Reviewer:** HCI/Design Expert Audit
**Scope:** Five-tab quiz workspace (Take | Generate | Create | Manage | Results)
**Stack:** React, TanStack Query, Ant Design, FastAPI backend

---

## 1. Take Quiz Tab (TakeQuizTab)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 1.1 | No pre-quiz summary screen | Critical | Information Gap | Clicking "Start Quiz" immediately creates a server-side attempt and shows questions. No confirmation screen with question count, time limit, or passing score. | Add a pre-quiz interstitial showing quiz metadata (questions, time limit, passing score, difficulty) with "Begin" and "Cancel" buttons before starting the attempt. |
| 1.2 | Timer hook exists but is not wired in | Critical | Missing Functionality | `useQuizTimer.ts` is fully implemented with warning (5 min) and danger (1 min) thresholds, but **is never imported or used** in TakeQuizTab.tsx. Timed quizzes have no visible countdown. | Import `useQuizTimer` in TakeQuizTab, display a countdown timer in the Card header, color-code by state (normal/warning/danger), and call `handleSubmit` on expire. |
| 1.3 | Auto-save hook exists but is not wired in | Critical | Missing Functionality | `useQuizAutoSave.ts` is fully implemented with debounced local storage persistence and restore, but **is never imported or used** in TakeQuizTab.tsx. Navigating away loses all progress. | Import `useQuizAutoSave`, call `restoreSavedAnswers` on attempt start, debounce-save on each answer change, and `clearSavedProgress` on submit. |
| 1.4 | No question-by-question navigation | Important | UX/Usability Issue | All questions render in a single scrollable list. No ability to jump to a specific question, skip, or navigate forward/backward. For quizzes with 20+ questions this creates a poor experience. | Add a question navigator sidebar/header (numbered buttons) allowing jump-to-question, and optionally support previous/next pagination. |
| 1.5 | No unanswered-questions guard on submit | Important | UX/Usability Issue | Submit shows a warning toast if questions are unanswered, but does NOT highlight which questions are missing. User must scroll through all questions to find them. | Scroll to and visually highlight the first unanswered question; optionally show a summary of unanswered question numbers. |
| 1.6 | Quiz cards show minimal metadata | Important | Information Gap | Cards show name, description, question count, and time limit tag. Missing: passing score, difficulty, source material link, last attempt score, and creation date. | Add passing score badge, difficulty tag, source media link, and "Last score: X%" if previously attempted. |
| 1.7 | No sorting/filtering of quiz list | Nice-to-Have | UX/Usability Issue | Quiz list has pagination but no search, sort, or filter controls. Users with many quizzes cannot find specific ones. | Add search input (matching ManageTab pattern) and sort options (name, date, question count). |
| 1.8 | No indication of retake behavior | Nice-to-Have | Information Gap | "Retake Quiz" button exists but doesn't communicate whether questions/order will change on retake. | Add tooltip or description: "Same questions, same order" or "Questions may be reshuffled." |
| 1.9 | Fill-in-the-blank lacks format guidance | Important | Information Gap | Text input shows only a generic placeholder "Enter the correct answer...". No indication of case sensitivity, expected format, or character limits. | Add helper text below input: "Case-insensitive, exact match required" (or whatever the backend behavior is). Communicate answer expectations clearly. |
| 1.10 | No pass/fail indication without passing_score | Nice-to-Have | UX/Usability Issue | Results show pass/fail based on `quizDetails?.passing_score ?? 70` (hardcoded fallback). If no passing score was set, "70%" is assumed silently. | Display "No passing score set" or make the default explicit in the UI. |

---

## 2. Generate Quiz Tab (GenerateTab)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 2.1 | Media list limited to 100 items, no pagination | Important | UX/Usability Issue | `results_per_page=100` hardcoded. Users with >100 media items cannot access all content. No indication that the list is truncated. | Implement infinite scroll or server-side search in the Select dropdown. Show "Showing 100 of X" when truncated. |
| 2.2 | Progress indicator is fake (fixed at 50%) | Important | UX/Usability Issue | During generation, a progress bar shows `percent={50}` with `status="active"` animation. This is a cosmetic loading indicator, not real progress. | Either remove the misleading progress bar and use only the spinner, or implement real progress via polling/streaming. Add estimated time text. |
| 2.3 | No cancel button during generation | Important | Missing Functionality | The generate mutation has no abort mechanism. The `AbortSignal` is supported in `quizzes.ts` (`generateQuiz(request, options?)`) but not wired in the UI. | Add a "Cancel" button that triggers `AbortController.abort()` during generation. |
| 2.4 | No explanation of difficulty levels or question counts | Nice-to-Have | Information Gap | Difficulty options (easy/medium/hard/mixed) have no tooltips explaining what each means. No guidance on optimal question count per source length. | Add tooltips or descriptions for each difficulty level. Add helper text like "Recommended: 5-10 questions per 1000 words of source." |
| 2.5 | No focus topics input | Nice-to-Have | Missing Functionality | The backend `quiz_generator.py` accepts `focus_topics` but the frontend form does not expose this field. | Add an optional "Focus Topics" text input with autocomplete from source content. |
| 2.6 | Generated quiz not previewable before save | Important | UX/Usability Issue | After generation, the user is auto-navigated to Take tab. No opportunity to preview or edit the generated quiz first. | After generation, show a preview/edit screen before navigating, or navigate to Manage tab's edit modal instead. |
| 2.7 | Error messages are generic | Nice-to-Have | UX/Usability Issue | Generation failure shows "Failed to generate quiz" without actionable context (e.g., source too short, content type mismatch). | Pass through server error detail to the toast message when available. |

---

## 3. Create Quiz Tab (CreateTab)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 3.1 | No question reordering | Important | Missing Functionality | Questions can only be added/deleted. No drag-and-drop or move up/down to reorder. The `order_index` field exists in the schema but is not exposed. | Add drag-and-drop reordering (Ant Design's `dnd-kit` integration) or move up/down buttons. |
| 3.2 | No draft/autosave mechanism | Important | UX/Usability Issue | If the user navigates away (switches tabs or closes browser) while creating a quiz with 10+ questions, all work is lost. No save-as-draft, no unsaved-changes warning. | Add `beforeunload` handler, autosave to local storage, and an "Unsaved changes" warning when switching tabs. |
| 3.3 | Multiple choice options fixed at 4 | Important | UX/Usability Issue | The form always renders exactly 4 option fields. Users cannot add a 5th option or reduce to 2-3. The backend supports variable option counts. | Allow dynamic add/remove of options with min=2 and max=6. |
| 3.4 | No quiz preview before save | Nice-to-Have | Missing Functionality | No way to see the quiz as a learner would experience it before saving. | Add a "Preview" button that renders a read-only version of the quiz. |
| 3.5 | Sequential question creation (N+1 API calls) | Nice-to-Have | UX/Usability Issue | Save creates the quiz first, then each question one-by-one in sequence. A 20-question quiz makes 21 API calls. No progress indicator during save. | Add a progress bar during save ("Saving question 3 of 20") or batch the questions in a single API call if backend supports it. |
| 3.6 | No explanation field visibility | Nice-to-Have | Information Gap | The explanation field exists in the question form but there's no indication that it will be shown to learners after grading. | Add helper text: "Shown to the learner after they submit the quiz." |
| 3.7 | Time limit UX is unclear | Nice-to-Have | UX/Usability Issue | Time limit `InputNumber` label says "Time limit" but doesn't indicate the unit. Backend stores `time_limit_seconds` but UI uses minutes. | Add unit suffix "(minutes)" to the label or use a time picker component. |

---

## 4. Manage Quiz Tab (ManageTab)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 4.1 | Soft-delete undo toast may not be noticed | Important | UX/Usability Issue | 8-second undo uses `message.success()` toast which auto-dismisses and appears briefly in the top-center. If user is scrolled down or focused elsewhere, they may miss it. | Use a more persistent notification (e.g., Ant `notification` API with manual close) or an inline undo banner at the deletion point. |
| 4.2 | No question reordering in edit modal | Important | Missing Functionality | The edit modal lists questions with `order_index` in the form but no drag-and-drop or move buttons. Questions can only be added/deleted. | Add reorder controls matching the Create tab recommendation. |
| 4.3 | Nested pagination is confusing | Important | UX/Usability Issue | The quiz list has pagination, and the questions within the edit modal have separate pagination. Two levels of pagination create cognitive load. | Use virtualized scrolling for questions inside the modal instead of pagination, or make the modal full-screen to accommodate all questions. |
| 4.4 | No quiz duplication | Nice-to-Have | Missing Functionality | No "Duplicate" action to clone a quiz for creating variations. | Add a "Duplicate" button that copies the quiz and all questions into a new quiz. |
| 4.5 | No quiz export | Nice-to-Have | Missing Functionality | No export to JSON, CSV, or PDF. The DocumentWorkspace `QuizPanel` has JSON export but the main quiz page does not. | Add export options (JSON for portability, PDF for printing). |
| 4.6 | No bulk operations | Nice-to-Have | Missing Functionality | No checkbox selection or bulk delete/export. | Add selectable rows with bulk action toolbar. |
| 4.7 | No source media link | Nice-to-Have | Information Gap | Quiz cards don't show which media item the quiz was generated from, even though `media_id` exists in the data. | Display source media name as a clickable link when `media_id` is present. |
| 4.8 | Undo cancelled if user navigates away | Important | UX/Usability Issue | If the user switches tabs during the 8-second undo window, the timeout fires in the background and the delete is committed. The undo button is no longer accessible. | Persist the pending deletion state across tab switches, or commit immediately and implement server-side "undelete" within a grace period. |

---

## 5. Results & Analytics Tab (ResultsTab)

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 5.1 | No drill-down into individual attempt details | Critical | Missing Functionality | The attempt history shows score/time per attempt but there is **no way to click an attempt and see question-by-question results**. The detailed review is only visible immediately after submission. | Add a "View Details" action on each attempt row that loads the attempt's answer breakdown. |
| 5.2 | No filtering by quiz, date, or score | Important | Missing Functionality | The attempt list is a flat, unfiltered paginated list. No ability to filter by specific quiz, date range, or pass/fail status. | Add filter dropdowns: quiz name, date range, pass/fail toggle. |
| 5.3 | No trend visualization | Important | Missing Functionality | Statistics are purely numeric (average score, average time). No charts showing improvement over time, per-quiz trends, or score distribution. | Add a line chart showing score trend over time (even a simple sparkline would add value). |
| 5.4 | Stats calculated only from current page | Important | UX/Usability Issue | `stats` is computed from `attempts` which is the current page slice (default 10). With 100+ attempts, stats only reflect the visible page, not all-time performance. | Fetch aggregate stats from the server (add a `/quizzes/stats` endpoint) or calculate from all attempts, not just the current page. |
| 5.5 | No retry action from results | Nice-to-Have | UX/Usability Issue | Users seeing a low score cannot directly retake that quiz from the results view. They must switch to the Take tab and find it. | Add a "Retake" button on each attempt row that navigates to TakeQuizTab with `startQuizId`. |
| 5.6 | No results export | Nice-to-Have | Missing Functionality | No CSV or PDF export of results/analytics. | Add export button for attempt history. |
| 5.7 | Hardcoded 70% passing threshold | Nice-to-Have | UX/Usability Issue | `isPassing = percentage >= 70` is hardcoded in ResultsTab rather than reading the quiz's actual `passing_score`. | Look up each quiz's `passing_score` from `quizMap` (extend it to include this field) and use that for pass/fail coloring. |

---

## 6. Cross-Tab Interaction & Information Flow

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 6.1 | No transition from Results to retake | Important | UX/Usability Issue | After reviewing results, there's no way to navigate directly to retaking a specific quiz. | Add cross-tab navigation callbacks to ResultsTab. |
| 6.2 | Tab state not preserved on switch | Important | UX/Usability Issue | `QuizPlayground` stores `activeTab` but no per-tab state. Switching from a quiz mid-take back to Take tab would reset the view (though attempt state is preserved in React state as long as component doesn't unmount). | Use `destroyInactiveTabPane={false}` on Ant Tabs to keep tab state mounted, or persist critical state to a store. |
| 6.3 | No tab badges | Nice-to-Have | Information Gap | Tabs show static labels. No counts like "Take (5)" or "Results (2 new)". | Add badge counts to tab labels showing available quizzes, unfinished attempts, or new results. |
| 6.4 | No unified search | Nice-to-Have | Missing Functionality | Search exists only in ManageTab. No global quiz search across tabs. | Add a search bar in the QuizPlayground header that filters across all tabs. |
| 6.5 | Generate → Take transition skips preview | Important | UX/Usability Issue | After successful generation, `onNavigateToTake()` is called immediately. The user is dumped into the Take tab with no indication of which quiz was just generated. | Pass the generated quiz ID to TakeQuizTab and highlight/auto-select it, or navigate to Manage for preview first. |

---

## 7. Quiz-to-Flashcard Integration

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 7.1 | No quiz-to-flashcard conversion | Important | Missing Functionality | Zero integration between quiz and flashcard systems. No ability to convert missed quiz questions into flashcards for targeted review. The systems share a database (`ChaChaNotes_DB`) but have no cross-referencing. | Add a "Create Flashcards from Missed Questions" action in quiz results that generates flashcard front/back from question_text/correct_answer. |
| 7.2 | No cross-navigation | Nice-to-Have | Missing Functionality | No links between `/quiz` and `/flashcards` pages. `return-to.ts` lists both as valid targets but no component uses cross-navigation. | Add contextual links: "Study these topics with flashcards" in results, "Test your knowledge with a quiz" in flashcards. |
| 7.3 | No shared generation flow | Nice-to-Have | Missing Functionality | Cannot generate both quiz and flashcard deck from the same source in one flow. The Workspace StudioPane groups them under "learning-tools" type but they're generated independently. | Add a "Generate Study Materials" flow that creates both quiz and flashcard deck from selected media. |

---

## 8. Connection State & Feature Availability

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 8.1 | Demo mode stub | Nice-to-Have | Information Gap | `QuizWorkspace` checks `useDemoMode()` and shows a demo badge, but the actual demo experience is just a disabled state with a "Demo Mode" tag. No sample quiz data. | Provide a pre-loaded sample quiz in demo mode so users can experience the full flow without a server. |
| 8.2 | Feature unavailable message is minimal | Nice-to-Have | UX/Usability Issue | When `capabilities.hasQuizzes` is false, QuizWorkspace shows a generic "not available" message. Doesn't explain how to enable the feature. | Add actionable guidance: "Quizzes require server version X.Y+ — update your server to enable this feature." |
| 8.3 | Beta badge placement | Nice-to-Have | Information Gap | Beta badge exists but its implications aren't communicated (data might be reset, features may change). | Add a tooltip on the beta badge explaining what "beta" means for user data. |

---

## 9. Responsive & Mobile Experience

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 9.1 | Five tabs may overflow on mobile | Important | UX/Usability Issue | Ant Design's `Tabs` component handles overflow with scroll arrows, but five tab labels ("Take", "Generate", "Create", "Manage", "Results") may be cramped on small screens. | Test on 320px viewport; consider abbreviating labels on mobile or using icons with text. |
| 9.2 | Quiz grid responsive but not optimized | Nice-to-Have | UX/Usability Issue | Take tab uses `grid={{ xs: 1, sm: 2, md: 2, lg: 3, xl: 3, xxl: 4 }}` which is reasonable, but card actions (Start Quiz button) may be small on mobile. | Ensure all interactive elements meet 44px minimum touch target size. |
| 9.3 | Create tab question builder on mobile | Important | UX/Usability Issue | The Create tab's question builder with 4 inline option inputs, radio selectors, and delete buttons would be difficult to use on narrow screens. No responsive adaptation. | Stack option inputs vertically on mobile, use larger touch targets for radio/delete buttons. |
| 9.4 | Timer (once wired) needs mobile consideration | Important | UX/Usability Issue | When the timer is eventually wired in, it must remain visible without scrolling on mobile during quiz-taking. | Use a sticky/fixed timer bar at the top of the quiz-taking view. |

---

## 10. Performance & Perceived Speed

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 10.1 | No optimistic mutations | Nice-to-Have | UX/Usability Issue | Create, update, and delete operations wait for server confirmation before updating UI (except ManageTab's soft-delete which is optimistic). Answer selection is instant (local state). | Implement optimistic updates for quiz creation/update to improve perceived speed. |
| 10.2 | Quiz list re-fetches on tab switch | Nice-to-Have | UX/Usability Issue | React Query caching mitigates this, but default stale times aren't explicitly configured on quiz queries, so background refetches may occur on every tab switch. | Set explicit `staleTime: 30_000` on quiz list queries to avoid unnecessary refetches. |
| 10.3 | ResultsTab fetches all quizzes (limit: 200) | Nice-to-Have | UX/Usability Issue | `useQuizzesQuery({ limit: 200 })` in ResultsTab fetches up to 200 quizzes just for name mapping. This is wasteful if the user has few attempts. | Denormalize quiz name into the attempt response, or fetch names on-demand. |
| 10.4 | No skeleton loading states | Nice-to-Have | UX/Usability Issue | All tabs show a centered `<Spin size="large">` during loading. No skeleton screens that hint at the incoming layout. | Replace spinners with Ant Design's `Skeleton` component for cards and lists. |

---

## 11. Error Handling & Edge Cases

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 11.1 | No offline attempt recovery | Critical | UX/Usability Issue | If the server becomes unreachable during quiz submission, the attempt is lost. The auto-save hook (if wired) saves locally but there's no retry-submit mechanism. | Add retry logic for failed submissions: save answers locally, show "Submission failed — retry?" prompt, and auto-retry when connection is restored. |
| 11.2 | No double-submit protection | Important | UX/Usability Issue | The submit button has `loading={submitAttemptMutation.isPending}` which provides visual feedback, but rapid double-clicks could theoretically queue two submissions before the first's loading state kicks in. | Add `disabled={submitAttemptMutation.isPending}` alongside loading, or debounce the submit handler. |
| 11.3 | Quiz with 0 questions can be started | Important | UX/Usability Issue | If all questions in a quiz are deleted, `total_questions` may still be >0 (stale count). Starting such a quiz would show an empty question list with no helpful message. | Check question count on attempt start; show "This quiz has no questions" error state. |
| 11.4 | No version conflict UI | Important | UX/Usability Issue | The `errorMessages.ts` categorizes 409 conflicts correctly, but no component shows a "refresh and retry" action — just a toast message. | Add a "Refresh" button in the conflict error message that invalidates the relevant query. |
| 11.5 | Timer expiry during network outage | Nice-to-Have | UX/Usability Issue | If the timer expires and `onExpire` calls `handleSubmit` but the server is unreachable, the auto-submit fails silently with only a toast. | Queue the submission for retry and clearly communicate "Your time expired — we'll submit your answers when the connection is restored." |
| 11.6 | localStorage/IndexedDB unavailable | Nice-to-Have | UX/Usability Issue | `useQuizAutoSave` catches storage errors and logs warnings, but doesn't inform the user that their progress won't be saved. | Show a one-time dismissible warning: "Auto-save unavailable — your progress won't be preserved if you navigate away." |

---

## 12. Information Gaps & Missing Functionality

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 12.1 | No practice mode (immediate feedback) | Important | Missing Functionality | All quizzes are graded only after full submission. No option for per-question immediate feedback. The `QuizPanel` (DocumentWorkspace) has this feature but the main quiz page does not. | Add a "Practice Mode" toggle that shows correct/incorrect immediately after each answer, similar to `QuizPanel`'s "Check Answer" behavior. |
| 12.2 | No review mode | Important | Missing Functionality | No way to browse questions and answers without starting a graded attempt. Users wanting to study without pressure cannot do so. | Add "Review Mode" that shows questions with answers/explanations without grading. |
| 12.3 | No answer shuffling | Important | Missing Functionality | Multiple choice options are always in the same order. Retakes test memory of option position, not knowledge. | Shuffle option order per attempt (client-side or server-side), preserving correctness mapping. |
| 12.4 | No question pools / randomization | Nice-to-Have | Missing Functionality | Every attempt shows all questions in the same order. No "draw N of M" pool behavior. | Support question pools with configurable random draws. |
| 12.5 | No rich media in questions | Nice-to-Have | Missing Functionality | Questions are text-only. No support for images, code blocks, math/LaTeX, or audio clips. | Support markdown or HTML rendering in question text and explanations. |
| 12.6 | No additional question types | Nice-to-Have | Missing Functionality | Only multiple_choice, true_false, fill_blank. Missing: matching, ordering, short answer (essay), multi-select. | Prioritize multi-select and matching question types as next additions. |
| 12.7 | No quiz sharing or assignment | Nice-to-Have | Missing Functionality | No share-via-link, no assigning quizzes to other users, no due dates. Single-user focused. | Add shareable quiz links and optional assignment dates for multi-user mode. |
| 12.8 | No hints system | Nice-to-Have | Missing Functionality | No "Reveal hint" option with point penalty for harder questions. | Add optional hints per question with configurable point deduction. |
| 12.9 | No partial credit for fill-in-the-blank | Nice-to-Have | Missing Functionality | Fill-in-the-blank uses exact match. No synonym handling, close-match scoring, or case-insensitivity communication. | Implement fuzzy matching (Levenshtein distance) and/or accept multiple correct answers. |
| 12.10 | No quiz import from standard formats | Nice-to-Have | Missing Functionality | No import from QTI, Moodle XML, Kahoot, or even CSV/JSON. | Add JSON import at minimum (since export is planned), then consider QTI for interoperability. |
| 12.11 | No per-question time limits | Nice-to-Have | Missing Functionality | Only overall quiz timer exists. No per-question time pressure. | Add optional per-question time limit with auto-advance. |
| 12.12 | No print-friendly format | Nice-to-Have | Missing Functionality | No print CSS or PDF export for offline quizzing. | Add `@media print` styles and/or PDF generation endpoint. |
| 12.13 | No source citations in explanations | Nice-to-Have | Information Gap | AI-generated explanations don't link back to the specific passage in the source material. | Include source chunk references in generated explanations; render as clickable links to the source document. |

---

## 13. Accessibility

| # | Finding | Severity | Type | Current State | Recommendation |
|---|---------|----------|------|---------------|----------------|
| 13.1 | Zero custom ARIA attributes anywhere | Critical | Accessibility Concern | Grep for `aria-` across all Quiz components returns **zero results**. All accessibility relies entirely on Ant Design's built-in defaults (which are limited). | Conduct a systematic ARIA audit and add: `aria-label` on icon-only buttons, `aria-live` regions for dynamic content, `aria-describedby` for form fields with helper text. |
| 13.2 | Timer not announced to screen readers | Critical | Accessibility Concern | When the timer is wired in, `useQuizTimer` updates state every second. Without `aria-live="polite"` (or `"assertive"` in danger zone), screen reader users will have no awareness of remaining time. | Add an `aria-live` region for timer updates. Use `polite` for normal updates (once per minute), `assertive` for danger zone (last 60 seconds). |
| 13.3 | Radio groups lack fieldset/legend | Important | Accessibility Concern | Multiple choice and true/false render `Radio.Group` without wrapping `<fieldset>` and `<legend>` elements. Screen readers cannot associate options with their question. | Wrap each question's radio group in a fieldset with the question text as legend (Ant's Radio.Group may handle this — verify with screen reader testing). |
| 13.4 | Progress bar lacks ARIA attributes | Important | Accessibility Concern | `<Progress percent={progress} />` renders visually but may not communicate to screen readers. Need `aria-valuenow`, `aria-valuemax`, `aria-label`. | Add `aria-label="Quiz completion progress"` and verify Ant's Progress component sets `aria-valuenow`/`aria-valuemax`. |
| 13.5 | Undo toast not keyboard-accessible | Important | Accessibility Concern | The 8-second undo toast in ManageTab uses `message.success()` which is not focus-trapped and may not be reachable via keyboard. | Use `notification` API with a focusable "Undo" button, or implement an inline undo banner. |
| 13.6 | Color-only correct/incorrect indicators | Important | Accessibility Concern | Results use green Tag for correct and red Tag for incorrect. Users with color vision deficiencies may not distinguish them. Icons (checkmark/X) are used in ResultsTab but not in TakeQuizTab results. | Add checkmark/X icons alongside color in TakeQuizTab results view. Ensure sufficient contrast ratios. |
| 13.7 | Modal focus management | Nice-to-Have | Accessibility Concern | ManageTab's edit modals use Ant's Modal which has built-in focus trapping, but custom focus management (returning focus to trigger button on close) should be verified. | Verify focus returns to the triggering button when modals close; add if missing. |
| 13.8 | Form validation errors not linked to fields | Nice-to-Have | Accessibility Concern | Create tab's form validation errors appear via toast messages rather than inline with `aria-describedby` linking. Screen readers cannot associate errors with fields. | Use Ant Form's built-in `validateStatus` and `help` props to show inline errors associated with each field. |

---

## Executive Summary

### Top 5 Critical Gaps Blocking Learner/Researcher Adoption

1. **Timer hook not wired in (1.2)** — Timed quizzes are fundamentally broken: the countdown exists in code but is invisible to users. A learner has no idea how much time remains.

2. **Auto-save not wired in (1.3)** — Navigating away mid-quiz (accidental or intentional) destroys all progress. The code to save/restore exists but isn't connected. This is a data-loss bug in practice.

3. **No drill-down into past attempt details (5.1)** — The Results tab shows only aggregate scores. Learners cannot review which questions they got wrong in previous attempts — the core learning loop is broken after the immediate post-submission screen.

4. **Zero accessibility (ARIA) attributes (13.1)** — The entire quiz module has no custom ARIA attributes. Screen reader users cannot effectively use any part of the quiz workflow. This is both an accessibility and compliance concern.

5. **No pre-quiz confirmation screen (1.1)** — Clicking "Start Quiz" immediately creates a server-side attempt with no preview of what they're committing to. There's no going back.

### Top 5 Quick Wins (High Impact, Low Effort)

1. **Wire in `useQuizTimer`** — The hook is fully implemented. Importing it and adding a timer display to the Card header is ~20 lines of code.

2. **Wire in `useQuizAutoSave`** — Similarly fully implemented. Connecting it to TakeQuizTab is ~15 lines of changes.

3. **Add `aria-label` to icon-only buttons and `aria-live` regions** — A systematic pass adding ARIA attributes across all tabs. Medium effort but high accessibility impact.

4. **Add "View Details" link on ResultsTab attempt rows** — Route to TakeQuizTab in a read-only results mode showing the answer breakdown. The data structures already exist.

5. **Show real quiz metadata on cards** — Adding passing score, difficulty, and source media name to quiz cards using data that's already fetched.

### Suggested Priority Roadmap

**Phase 1: Fix the Broken (1-2 days)**
- Wire in `useQuizTimer` (1.2)
- Wire in `useQuizAutoSave` (1.3)
- Add pre-quiz confirmation screen (1.1)
- Fix double-submit protection (11.2)
- Handle 0-question quiz edge case (11.3)

**Phase 2: Complete the Learning Loop (3-5 days)**
- Add drill-down into past attempt details (5.1)
- Add "Retake" action from results (5.5, 6.1)
- Add practice mode with immediate feedback (12.1)
- Add answer shuffling for retakes (12.3)
- Persist tab state across switches (6.2)
- Fix stats to be all-time, not per-page (5.4)

**Phase 3: Accessibility Pass (2-3 days)**
- Systematic ARIA audit and remediation (13.1-13.8)
- Timer screen reader announcements (13.2)
- Color-independent correct/incorrect indicators (13.6)
- Form validation error linking (13.8)
- Keyboard navigation testing

**Phase 4: Enhance the Workflow (1-2 weeks)**
- Question reordering in Create/Manage (3.1, 4.2)
- Draft/autosave for Create tab (3.2)
- Dynamic option count for multiple choice (3.3)
- Generated quiz preview/edit before save (2.6)
- Media list pagination/search in Generate (2.1)
- Results filtering and trend visualization (5.2, 5.3)
- Cancel button for generation (2.3)

**Phase 5: Cross-Feature Integration (1-2 weeks)**
- Quiz-to-flashcard conversion (7.1)
- Cross-navigation between quiz and flashcards (7.2)
- Review mode (12.2)
- Export/import (4.5, 5.6, 12.10)
- Rich media in questions (12.5)
- Additional question types (12.6)

---

*Total findings: 82 across 13 categories*
*Severity breakdown: 6 Critical, 30 Important, 46 Nice-to-Have*
*Type breakdown: 29 Missing Functionality, 11 Information Gap, 33 UX/Usability Issue, 9 Accessibility Concern*
