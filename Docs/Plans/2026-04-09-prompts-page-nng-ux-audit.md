# UX Audit: /prompts Page (NNG Heuristic Evaluation)

## Context

This is a comprehensive UX audit of the `/prompts` page, evaluated against Nielsen Norman Group's 10 usability heuristics from four persona perspectives:

- **Researcher / knowledge worker** (non-technical): Comfortable with Notion, Google Scholar, Zotero. Uses prompts for systematic research workflows and templates for literature analysis. Does not know prompt engineering terminology.
- **Student / self-directed learner** (non-technical): Uses prompts for study aids, essay templates, assignment formatting. Comfortable with apps but not dev tools.
- **Content Creator / prompt engineer** (intermediate): Manages prompt libraries, creates reusable templates. Understands prompt engineering concepts but not ML optimization.
- **Technical power user**: Developer/ML engineer. Uses structured prompts, evaluations, optimizations, sync, and version control. Comfortable with APIs and config files.

**Deliverable**: Heuristic scorecard with file:line references + persona journey maps.

**Scoring scale**: 1=Critical failures throughout, 2=Major usability issues, 3=Moderate issues (workable but painful), 4=Minor issues only, 5=Exemplary.

**Prior work**: This builds on `Docs/Plans/2026-04-08-knowledge-workspace-nng-ux-audit.md` (Knowledge QA & Workspace audit) and `Docs/Plans/2026-04-05-acp-first-time-ux-audit.md` (ACP audit). Those audits covered other pages but not the Prompts workspace.

**Caveat**: Line numbers were verified at time of writing but may drift with future commits. Use surrounding code context to locate if line numbers are stale.

**Page structure**: The `/prompts` page is a 3-panel layout with 4 workspace segments (Custom, Copilot, Studio, Trash). The Studio segment contains a 5-tab sub-application (Projects, Prompts, Test Cases, Evaluations, Optimizations). The orchestrator component is 2884 lines (`index.tsx`) with 8 extracted hooks, 50+ component files total.

---

## Part 1: Main Page (Custom/Copilot/Trash) -- NNG Heuristic Scorecard

### H1: Visibility of System Status -- Score: 3.5/5

**Strengths:**
- Sync status badges with color-coded icons and hover tooltips (`SyncStatusBadge.tsx:44-78`)
- Batch sync progress: "Syncing 3 of 12 prompts..." with progress bar
- Loading states use Skeleton components while data fetches
- Draft recovery banner: "Unsaved draft found (30 min ago)" with Restore/Dismiss
- Selection count feedback: "3 selected" with highlighted bulk action bar
- Project filter banner: "Filtering by project #123" with clear button
- Server search fallback notification when offline (`index.tsx:718`)

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| P1 | No explicit offline banner at page level -- user must infer offline state from disabled buttons and missing features. PromptsWorkspace.tsx has no offline indicator. | High | All | `PromptsWorkspace.tsx:17-38` |
| P2 | Conflict status badge says "Conflict" with tooltip "Local and server versions differ" but no hint that the badge is clickable to resolve | Med | Researcher, Student | `SyncStatusBadge.tsx:64-65` |
| P3 | "Keep both" in ConflictResolutionModal has no explanation of what it does (creates a copy? merges?) | Med | All | `ConflictResolutionModal.tsx` |
| P4 | Copilot/Studio segments silently redirect to Custom when offline (`index.tsx:651-654`) with no explanation | Med | All | `index.tsx:651-654` |

---

### H2: Match Between System and Real World -- Score: 2.5/5

**Strengths:**
- "Create reusable prompts for recurring tasks, workflows, and team conventions" -- friendly, business-focused description
- "AI Instructions" label (with tooltip "Also known as 'System prompt'") in PromptDrawer already improved from raw jargon
- "Message Template" instead of raw "User prompt" in PromptDrawer
- Smart collections: "Recently Used", "Most Used", "Favorites" -- familiar mental models
- Starter cards with templates: "Code Review Assistant", "Meeting Summary", "Research Analyst"

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| P5 | "Few-shot examples" heading uses ML jargon. Description "Add input/output examples to improve response consistency" helps but the heading is intimidating | High | Researcher, Student | `PromptDrawer.tsx:634` |
| P6 | "System"/"Quick"/"Mixed" type filter labels have no tooltips explaining what each type means | High | Student, Researcher | `FacetedFilters.tsx:20-22` |
| P7 | "Structured prompt" alert says "Raw text fields are now locked for compatibility" -- doesn't explain what structured prompts are or why a user would want one | High | All non-technical | `PromptDrawer.tsx:961-962` |
| P8 | "Sync" column header and sync filter options (Local/Pending/Synced/Conflict) assume user understands version-control concepts | Med | Student, Researcher | `index.tsx:1623-1624` |
| P9 | PromptInspectorPanel uses hardcoded "System prompt" / "User prompt" labels (not i18n, not the improved "AI Instructions" / "Message Template") | Med | All | `PromptInspectorPanel.tsx:98, 109` |

---

### H3: User Control and Freedom -- Score: 3.5/5

**Strengths:**
- Escape key closes drawer/editor/shortcuts modal
- Undo via Trash: soft-deleted prompts recoverable for 30 days
- "Clear selection" always visible in bulk action bar
- Draft autosave every 30s with Restore/Dismiss options
- Keyboard shortcuts well-documented (N, E, /, Escape, Space, ?, Cmd+K, Cmd+N, Cmd+S)
- Conflict resolution: three options ("Keep mine", "Keep both", "Keep server")
- Drawer close with unsaved changes: Cancel/Discard/Save confirmation

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| P10 | Legacy-to-structured prompt conversion is one-way with only an info alert, not a warning. No rollback possible. | Med | Content Creator, Technical | `PromptDrawer.tsx:961` |
| P11 | "Empty Trash" permanently deletes all items with a single confirmation -- no name-typing safeguard for this destructive action | Med | All | `index.tsx` (trash segment) |
| P12 | Individual prompt delete from Custom tab has no confirmation (only bulk delete does) | Low | All | `hooks/usePromptEditor.tsx` |

---

### H4: Consistency and Standards -- Score: 3.0/5

**Strengths:**
- Standard table/list pattern (query -> filter -> results)
- Consistent icon + text for actions throughout
- Color-coding consistent: green=Synced, gold=Pending, red=Conflict, blue=Local
- Ant Design components used consistently

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| P13 | "Keywords" vs "Tags" -- PromptDrawer label says "Keywords" but FacetedFilters section header says "Tags" | High | All | `PromptDrawer.tsx:1139` vs `FacetedFilters.tsx:128` |
| P14 | "Title" vs "Name" -- FullPageEditor uses "Title" (hardcoded), Drawer uses i18n `form.title.label`, form field internally named `name` | Med | Technical | `PromptFullPageEditor.tsx:402` vs `PromptDrawer.tsx:912-913` |
| P15 | "System prompt"/"User prompt" in InspectorPanel vs "AI Instructions"/"Message Template" in Drawer | Med | All | `PromptInspectorPanel.tsx:98,109` vs `PromptDrawer.tsx` |
| P16 | Quick test modal uses "System prompt" / "Quick prompt" -- a third variant of the same labels | Med | All | `index.tsx:2622-2638` |
| P17 | Create buttons: "Create prompt" vs "Create Prompt" vs "New prompt" capitalization varies | Low | All | Various components |

---

### H5: Error Prevention -- Score: 3.0/5

**Strengths:**
- Title field required validation: "Please enter a title"
- Template variable syntax validation with error highlighting
- Import mode selection (Merge vs Replace) prevents accidental data loss
- Offline mode gracefully degrades -- features disabled, not erroring
- Trash 30-day auto-delete with countdown: "7 days left", "Due now" (red)
- Token count with budget warnings ("High token load", "Approaching high token load") at `PromptDrawer.tsx:474-477`

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| P18 | "Something went wrong" generic error in ProjectSelector and usePromptSync | High | All | `ProjectSelector.tsx:86`, `hooks/usePromptSync.tsx:408,418` |
| P19 | Import error handling shows generic notification (`managePrompts.notification.someError`) without explaining what was wrong with the file | Med | Content Creator, Technical | `hooks/usePromptImportExport.tsx:100-104,174-176` |
| P20 | "Replace (backup)" import mode doesn't preview what will be replaced | Med | Content Creator | `hooks/usePromptImportExport.tsx` |
| P21 | Template variable syntax error shown as red text only -- no `aria-invalid="true"` for screen readers | Low | All (accessibility) | `PromptDrawer.tsx` |

---

### H6: Recognition Rather Than Recall -- Score: 4.0/5

**Strengths:**
- Smart collections (All, Favorites, Recently Used, Most Used, Untagged) with counts
- Filter presets: save/load/delete custom filter combinations
- Keyboard shortcuts panel with all 9 shortcuts documented
- Starter cards with templates for empty state
- Search with debounce across title, content, tags
- Tag filter with "Show N more..." progressive disclosure

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| P22 | Bulk action bar only appears when items selected -- first-time users won't discover multi-select capability | Med | Student, Researcher | `PromptBulkActionBar.tsx` |
| P23 | Filter presets feature (save/load) exists but has no onboarding or tooltip explaining it | Low | All | `FilterPresets.tsx` |
| P24 | Tag match mode (Any/All) toggle only appears when tags selected -- logic isn't intuitive for non-technical users | Low | Student, Researcher | `FacetedFilters.tsx` |

---

### H7: Aesthetic and Minimalist Design -- Score: 3.5/5

**Strengths:**
- Progressive disclosure: "Advanced" section in drawer collapsed by default (few-shot examples, modules)
- Expandable help for AI Instructions / Message Template ("Learn more" / "Show less")
- Faceted filters show only 5 tags, expand on demand ("Show N more...")
- View mode options (table/gallery) and density (comfortable/compact/dense)
- Collapsible sidebar with icon-only mode
- Lazy loading for PromptDrawer, FullPageEditor, InspectorPanel, GalleryCard

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| P25 | Mobile toolbar: all filter controls stack vertically at `w-full` on mobile with `flex-wrap` -- 10+ controls | High | All mobile | `PromptListToolbar.tsx:83` |
| P26 | Conflict resolution modal shows 6 sections (side-by-side comparison, 2 columns, 3 rows) on a 960px modal -- overwhelming | Med | Student, Researcher | `ConflictResolutionModal.tsx` |
| P27 | Collapsed sidebar (48px, icon-only) has no text labels -- just icons with tooltips, easy to miss | Low | Student | `PromptSidebar.tsx:93-180` |

---

### H8: Help and Documentation -- Score: 2.5/5

**Strengths:**
- Contextual help inline in Drawer: "AI Instructions define behavior, sets context/tone/capabilities"
- Expandable "Learn more" for system/user prompts with examples
- Keyboard shortcut panel accessible via ? key
- Empty state guidance: "No custom prompts yet" with use cases and template links
- Sync status tooltips: "Synced with server (30m ago)", "Local changes not yet synced"

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| P28 | No help link or documentation for "Structured prompts" -- what they are, when to use, how to convert | High | All non-technical | `PromptDrawer.tsx:961` |
| P29 | "System"/"Quick"/"Mixed" types have no explanation anywhere | High | Student, Researcher | `FacetedFilters.tsx:20-22` |
| P30 | Filter presets: no explanation of purpose or how to save/load | Low | All | `FilterPresets.tsx` |
| P31 | Sync concepts (Local/Pending/Synced/Conflict) have no onboarding or help link | Med | Student, Researcher | `SyncStatusBadge.tsx` |

---

### H9: Help Users Recognize, Diagnose, and Recover from Errors -- Score: 3.0/5

**Strengths:**
- Server pull failures give specific messages: "You don't have permission to open this shared prompt"
- Offline degradation: features disabled with explanation, not errors
- Draft autosave prevents data loss on crash
- Trash provides 30-day recovery window

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| P32 | "Something went wrong" appears in 3+ locations with no actionable guidance | High | All | `ProjectSelector.tsx:86`, `hooks/usePromptSync.tsx:408,418` |
| P33 | Failed sync operations show no retry button -- user must manually re-trigger | Med | Technical | `hooks/usePromptSync.tsx` |
| P34 | Import failures: generic notification without explaining what was wrong (bad JSON? missing fields? duplicate?) | Med | Content Creator | `hooks/usePromptImportExport.tsx:100-104` |

---

### H10: Flexibility and Efficiency of Use -- Score: 4.0/5

**Strengths:**
- 9 keyboard shortcuts: N (new), E (edit), Enter (inspector), Space (toggle select), Escape (close), ? (help), / (search), Cmd+N, Cmd+K, Cmd+S
- Multiple interaction paths: edit via button, double-click, keyboard shortcut, right-click menu
- Gallery and table view modes with density options
- Filter presets for power users
- Bulk operations (export, tag, favorite, delete, push to server)

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| P35 | Missing Cmd+A (select all) -- standard shortcut expected by power users | Low | Technical | `index.tsx` |
| P36 | Shortcuts only work when focus is NOT in an input field -- no guidance on this constraint | Low | All | `index.tsx` keyboard handler |
| P37 | "/" shortcut for search only works unfocused; typing "/" in search field inserts the character | Low | Technical | `index.tsx` |

---

**Main Page Average: (3.5 + 2.5 + 3.5 + 3.0 + 3.0 + 4.0 + 3.5 + 2.5 + 3.0 + 4.0) / 10 = 3.25/5**

---

## Part 2: Studio Workspace -- NNG Heuristic Scorecard

### H1: Visibility of System Status -- Score: 3.0/5

**Strengths:**
- QueueHealthWidget provides real-time queue status with color-coded health indicators
- Evaluations/Optimizations show live status badges (Running, Pending, Completed, Failed) with spinners
- Progress bars for optimization iterations (e.g., "5 / 10")
- Toast notifications for all state changes (saved, deleted, archived)

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| S1 | WebSocket errors logged silently -- user won't know real-time updates stopped | High | Technical | Studio WebSocket components |
| S2 | No retry UI for failed operations -- user must navigate away and back | Med | All | Studio tab components |
| S3 | Tab disabled states when no project selected show message but no clear indication of WHY tabs are disabled | Med | Student, Researcher | `Studio/StudioTabContainer.tsx:365` |

---

### H2: Match Between System and Real World -- Score: 2.0/5

**Strengths:**
- Familiar workflow: Projects -> Prompts -> Test Cases -> Evaluations -> Optimizations
- Clear action labels: "Create Prompt", "Push to Server", "Archive"
- Token count uses intuitive "~200 tokens" format

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| S4 | "MIPRO", "Bootstrap", "Hyperparameter", "Genetic" optimization strategy names completely unexplained | Critical | All non-technical | `Studio/Optimizations/CreateOptimizationWizard.tsx:86,95` |
| S5 | "F1 Score", "Accuracy", "Pass Rate" evaluation metrics undefined | High | Student, Researcher | `Studio/Evaluations/EvaluationsTab.tsx:191` |
| S6 | "Mark as golden" for test cases: "golden" is ML jargon meaning "reference/ground truth answer" | High | Student, Researcher, Content Creator | `Studio/TestCases/TestCasesTab.tsx:197,252` |
| S7 | "Assembly config", "block separator", "legacy_system_roles" -- highly technical terms in structured editor | Med | All non-technical | `Structured/StructuredPromptEditor.tsx` |

---

### H3: User Control and Freedom -- Score: 3.5/5

**Strengths:**
- Escape key closes editors
- Cancel buttons on all modals
- Draft autosave every 5 seconds with recovery
- Projects can be archived (soft-delete) and restored
- Cmd/Ctrl+S saves in PromptFullPageEditor

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| S8 | Structured prompt conversion is one-way (legacy->structured) with no rollback | Med | Content Creator | `PromptDrawer.tsx:961` |
| S9 | Selection state lost on tab navigation -- selecting test cases, then switching tabs, then switching back loses the selection | Med | Technical | Studio tab components |
| S10 | Deleting a project while viewing its prompts resets the tab but provides no UX feedback about what happened | Low | All | `Studio/StudioTabContainer.tsx` |

---

### H4: Consistency and Standards -- Score: 3.5/5

**Strengths:**
- Consistent component library (Ant Design + custom Button)
- Unified color palette (primary, danger, warn, success)
- Table structure identical across all 5 tabs
- Icon sizing consistent (size-4 for buttons, size-3 for badges)
- Confirmation modal pattern reused

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| S11 | "Title" vs "Name" vs "Prompt Name" varies across Studio tabs | Med | All | Various Studio components |
| S12 | Status tag colors inconsistent: Projects use Tag colors (green=active), Evaluations use CheckCircle/XCircle icons | Low | Technical | Studio tab components |
| S13 | Button labels: "Create Prompt" vs "Create" vs "Run Evaluation" -- no consistent pattern | Low | All | Various Studio components |

---

### H5: Error Prevention -- Score: 3.0/5

**Strengths:**
- Form validation on required fields
- Confirmation dialogs for destructive actions
- Duplicate detection with "(Copy)" suffix

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| S14 | Empty test case inputs allowed -- no validation that inputs are non-empty | Med | Technical | `Studio/TestCases/TestCaseFormModal.tsx` |
| S15 | No merge preview before committing conflict resolution | Med | Technical | `ConflictResolutionModal.tsx` |
| S16 | Generic "Could not save Studio settings" error with only `error?.message` appended | Med | All | Studio settings |

---

### H6: Recognition Rather Than Recall -- Score: 2.5/5

**Strengths:**
- 5 tabs clearly labeled with icons
- Search in Projects, Prompts, TestCases
- URL sync with active tab (`?subtab=prompts`)

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| S17 | Must select project first for 4/5 tabs -- "Select a project first" message repeated in 4+ places with no shortcut to Projects tab | High | All | `Studio/StudioTabContainer.tsx:365,397,421,441,464` |
| S18 | No breadcrumbs showing: Project X > Prompt Y > Version Z | Med | All | Studio Prompts components |
| S19 | No global search across projects -- search is scoped to current table only | Med | Technical | Studio tab components |
| S20 | Duplicate prompt creation doesn't navigate to the new copy | Low | Content Creator | Studio Prompts tab |

---

### H7: Aesthetic and Minimalist Design -- Score: 2.5/5

**Strengths:**
- Clean whitespace and visual hierarchy
- Settings in popover, Advanced in collapse (progressive disclosure)
- Empty states with contextual examples

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| S21 | StudioPromptsTab: 6 columns (Name + Description + Preview + Version + Updated + Actions) -- too dense | Med | All | `Studio/Prompts/StudioPromptsTab.tsx` |
| S22 | StructuredPromptEditor: 4 simultaneous panels (BlockList + BlockEditor + Variables + Preview) | High | Student, Researcher | `Structured/StructuredPromptEditor.tsx` |
| S23 | Full-page editor modal blocks out everything -- can't reference other prompts while editing | Med | Content Creator | `PromptFullPageEditor.tsx` |
| S24 | Multiple status colors (5+ for evaluations/optimizations) hard to distinguish for color-blind users | Low | All (accessibility) | Studio Evaluations/Optimizations |

---

### H8: Help and Documentation -- Score: 2.0/5

**Strengths:**
- Helpful empty state examples in FeatureEmptyState components
- Inline tooltips on some complex controls
- QueueHealthWidget has detailed tooltip breakdown

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| S25 | Zero "?" help icons or documentation links in any Studio tab | Critical | All | Entire Studio directory |
| S26 | Optimization strategies (MIPRO, Bootstrap, Genetic, Hill Climbing, Bayesian, Grid/Random Search) have NO descriptions | Critical | All non-technical | `Studio/Optimizations/CreateOptimizationWizard.tsx:86-120` |
| S27 | Evaluation metrics (F1, accuracy, precision, recall, BLEU, ROUGE, perplexity, latency, cost) undefined | High | Student, Researcher | `Studio/Evaluations/EvaluationsTab.tsx` |
| S28 | "Golden mark" purpose not explained: "Mark important test cases as 'golden' for regression testing" is the only hint | Med | Student, Researcher | `Studio/TestCases/TestCasesTab.tsx:252` |
| S29 | No "Getting started" flow or onboarding for any Studio feature | Med | All | `Studio/StudioTabContainer.tsx` |

---

### H9: Help Users Recognize, Diagnose, and Recover from Errors -- Score: 3.0/5

**Strengths:**
- Error notifications use red + icon consistently
- Success notifications provide confirmation (green + checkmark)
- Skeleton loaders set loading time expectation

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| S30 | "Could not save settings" without stating WHICH setting failed | Med | Technical | Studio settings |
| S31 | Failed evaluations/optimizations show error tag but no troubleshooting guidance | Med | Technical | Studio Evaluations/Optimizations |
| S32 | API error messages (`error?.message`) displayed raw/untranslated in notifications | Low | All | Various Studio components |

---

### H10: Flexibility and Efficiency of Use -- Score: 3.0/5

**Strengths:**
- Double-click edit shortcut in tables
- Filter/sort in all tables
- Bulk import/export of test cases
- Mobile/desktop view toggle

**Issues:**

| # | Issue | Sev | Personas | File:Line |
|---|-------|-----|----------|-----------|
| S33 | No keyboard shortcuts for tab switching (Cmd+1-5) | Med | Technical | `Studio/StudioTabContainer.tsx` |
| S34 | Creating a prompt requires: Projects tab -> Select -> Prompts tab -> Create (multi-step) | Med | Content Creator | Studio flow |
| S35 | Search doesn't include version history | Low | Technical | Studio Prompts tab |
| S36 | No "select all" shortcut for test cases or prompts in Studio | Low | Technical | Studio tab components |

---

**Studio Average: (3.0 + 2.0 + 3.5 + 3.5 + 3.0 + 2.5 + 2.5 + 2.0 + 3.0 + 3.0) / 10 = 2.80/5**

**Combined Weighted Average (60% Main / 40% Studio): 3.07/5**

---

## Part 3: Persona Journey Maps

### Journey A: Researcher -- "Create a reusable research analysis prompt"

**Page: /prompts (Custom workspace)**

| Step | Action | Experience | Friction | Issue Refs |
|------|--------|------------|----------|------------|
| 1 | Navigate to /prompts | Sees "Create reusable prompts for recurring tasks..." | None -- clear purpose statement | -- |
| 2 | First visit: sees empty state | Starter cards: "Code Review Assistant", "Meeting Summary", "Research Analyst" | Good templates, but none match academic research specifically | -- |
| 3 | Clicks "Research Analyst" template | Drawer opens with pre-filled content | Good starting point | -- |
| 4 | Wants to customize: add tags | Sees form field labeled "Keywords". But sidebar says "Tags". Which is it? | Terminology confusion -- are keywords and tags the same thing? | P13 |
| 5 | Notices "Few-shot examples" section | Heading is intimidating. Reads description: "Add input/output examples to improve response consistency" | Understands the concept from description but the heading deterred initial exploration | P5 |
| 6 | Saves prompt. Wants to organize into a collection | Collections exist in sidebar but no "New Collection" button is immediately visible from the table view | Must navigate sidebar to find collection creation -- not discoverable from main action bar | -- |
| 7 | Looks at sidebar filters. Sees "System", "Quick", "Mixed" | No tooltips. Doesn't know what these mean. Guesses "System" is for AI behavior, "Quick" for templates. | No way to learn what types mean without trial and error | P6, P29 |
| 8 | Wants to use prompt in chat. Clicks "Use in Chat" | Insert modal offers "Use as System Instruction", "Insert as Message Template", "Use Both (Recommended)" | Clear, well-designed insertion flow | -- |
| 9 | Returns later. Wants to find the prompt | Uses search box. Types part of name. Found quickly. | Good search with debounce | -- |
| 10 | Wants to see recently used prompts | Clicks "Recently Used" in sidebar smart collections | Good -- exactly the mental model expected | -- |

**Verdict**: Good for basic create/find/use flow. Primary friction is jargon in advanced features and inconsistent terminology.

---

### Journey B: Student -- "Find and use a study prompt template"

**Page: /prompts (Custom workspace)**

| Step | Action | Experience | Friction | Issue Refs |
|------|--------|------------|----------|------------|
| 1 | Arrives at /prompts | Empty state with starter cards | Templates are professional-focused (Code Review, Meeting Summary) -- nothing study-specific | -- |
| 2 | Clicks "+ New" to create own prompt | Drawer opens. Fields: Title, AI Instructions, Message Template | "AI Instructions" label is clearer than "System prompt" but student still doesn't know what to put here | -- |
| 3 | Writes a study prompt. Saves it. | Success notification. Prompt appears in table. | Smooth | -- |
| 4 | Sees "Sync" column in table | "Local" badge appears. What does this mean? | Doesn't understand sync concepts. No help available. | P8, P31 |
| 5 | Goes offline (campus Wi-Fi drops) | No offline banner. Some buttons silently stop working. Clicks "Copilot" tab -- redirected to Custom with no explanation. | Very confusing -- what happened? Why can't I see Copilot prompts? | P1, P4 |
| 6 | Tries to import prompts from a classmate | Import button opens file picker. Selects JSON file. | "Replace (backup)" vs "Merge" -- doesn't know what "backup" means in this context | P20 |
| 7 | Import fails due to bad JSON format | Generic error notification. No guidance on correct format. | Student doesn't know how to fix the file | P19, P34 |
| 8 | Wants keyboard shortcuts | Types "?" -- shortcuts panel opens | Good -- 9 shortcuts clearly listed | -- |
| 9 | On mobile: toolbar has 10+ stacked controls | Overwhelmed by filter options crowding the small screen | Can't find the Create button amid the clutter | P25 |

**Verdict**: Basic flows work but the student encounters multiple friction points: jargon, offline confusion, import errors, and mobile clutter.

---

### Journey C: Content Creator -- "Organize and version a prompt library"

**Page: /prompts (Custom workspace + Studio)**

| Step | Action | Experience | Friction | Issue Refs |
|------|--------|------------|----------|------------|
| 1 | Creates 20+ prompts for different use cases | Drawer workflow is smooth for each prompt | Repetitive -- no bulk creation option, but acceptable | -- |
| 2 | Wants to organize with tags | Adds tags to each prompt. Notices drawer says "Keywords" but sidebar filter says "Tags" | Confusion: is searching "Tags" the same as filtering "Keywords"? | P13 |
| 3 | Uses filter presets to save a "Marketing prompts" view | Finds "Save Preset" button in sidebar | Good feature, but no onboarding -- discovered by exploration only | P23, P30 |
| 4 | Switches to table density "compact" | Works well for large libraries | Good for power users | -- |
| 5 | Wants version history for a prompt | Opens inspector panel. Sees version info. | Can view versions but only in Studio Prompts tab, not from Custom | -- |
| 6 | Navigates to Studio tab | "Select a project first" -- must create a project before doing anything | 5 steps to get to prompt editing: Studio tab -> Projects tab -> Create -> Back to Prompts tab -> Create | S17, S34 |
| 7 | Creates a structured prompt | "Structured prompt" alert appears. "Raw text fields are now locked." What? | Doesn't understand the benefit. No help link. No undo. | P7, P10, P28 |
| 8 | Structured editor opens: 4 panels simultaneously | BlockList + BlockEditor + Variables + Preview | Overwhelming -- too many panels for a non-developer | S22 |
| 9 | Exports prompt library | Clicks "Export" -- gets JSON. Wants CSV for sharing with team. | Export format options unclear | -- |

**Verdict**: Good for basic library management. Structured prompts and Studio are significant barriers due to jargon and complexity.

---

### Journey D: Technical Power User -- "Set up evaluation pipeline for prompt optimization"

**Page: /prompts (Studio workspace)**

| Step | Action | Experience | Friction | Issue Refs |
|------|--------|------------|----------|------------|
| 1 | Goes directly to Studio tab | Creates a project. Good. Navigates to Prompts sub-tab. | None -- workflow is logical | -- |
| 2 | Creates structured prompt with template variables | StructuredPromptEditor works well. Variable editor clear. | Good for this persona | -- |
| 3 | Creates test cases for evaluation | Marks some as "golden" | Understands the ML concept. Description "for regression testing" helps. | -- |
| 4 | Creates an evaluation | Selects metrics. Sees "F1", "Accuracy", "Pass Rate" | Understands these (ML background). But no inline documentation for threshold values. | S27 |
| 5 | Wants to optimize the prompt | Creates optimization run. Sees strategy options: MIPRO, Bootstrap, Genetic... | Understands MIPRO and Bootstrap conceptually but no tooltips explaining trade-offs (speed vs quality) | S4, S26 |
| 6 | Optimization running. Checks progress. | Progress bar shows 5/10 iterations. Queue health widget visible. | Good status feedback | -- |
| 7 | Wants keyboard shortcuts in Studio | Tries Cmd+1 to switch tabs. Nothing. Tries N for new prompt. Nothing. | Must click tabs manually -- keyboard shortcuts only work in Custom workspace | S33 |
| 8 | Wants to search across all projects | Types in search box -- only searches current project's prompts | Must switch projects to find prompts in other projects | S19 |
| 9 | WebSocket connection drops silently | Doesn't notice. Evaluation status badge doesn't update. Manually refreshes. | Lost trust in real-time status. Starts polling manually. | S1 |
| 10 | Wants to compare optimization strategies | CompareStrategiesModal exists -- shows side-by-side | Good feature, well-implemented | -- |

**Verdict**: Studio is well-designed for the technical persona's workflow. Primary gaps are keyboard shortcuts, cross-project search, and WebSocket reliability feedback.

---

## Part 4: Cross-Cutting Issues

| # | Issue | Sev | Pages | File:Line |
|---|-------|-----|-------|-----------|
| X1 | **No offline indicator anywhere on /prompts page** -- features silently degrade or redirect | High | All segments | `PromptsWorkspace.tsx:17-38` |
| X2 | **"Keywords" vs "Tags" inconsistency** across drawer, sidebar, toolbar, table columns | High | Custom, Copilot | `PromptDrawer.tsx:1139`, `FacetedFilters.tsx:128` |
| X3 | **Three different label sets for the same concepts**: "System prompt"/"User prompt" (Inspector, Quick Test) vs "AI Instructions"/"Message Template" (Drawer) vs "System"/"Quick" (Filters) | High | All segments | Multiple files |
| X4 | **Zero help/documentation links in Studio** -- no "?" icons, no "Learn more", no docs | High | Studio | Entire Studio directory |
| X5 | **Generic "Something went wrong" errors** in 3+ locations with no actionable guidance | High | Custom, Studio | `ProjectSelector.tsx:86`, `hooks/usePromptSync.tsx:408,418` |
| X6 | **Missing ARIA attributes**: no `role="toolbar"` on bulk actions, no `aria-expanded` on collapsibles, no `aria-live` for selection counts | Med | Custom | `PromptBulkActionBar.tsx:56-58`, `PromptSidebar.tsx:93-180`, `PromptBulkActionBar.tsx:60` |
| X7 | **Mobile toolbar overflow** -- 10+ controls stack vertically with no progressive disclosure | Med | Custom | `PromptListToolbar.tsx:83` |

---

## Part 5: Priority Recommendations

### Critical (do first)

1. **Add offline banner** (X1, P1) -- "You are offline. Server features disabled." at page top. Prevent silent redirects.
   - File: `PromptsWorkspace.tsx`

2. **Add help links to Studio** (X4, S25, S26) -- "?" icon on each tab linking to docs. Inline descriptions for optimization strategies and evaluation metrics.
   - Files: `Studio/StudioTabContainer.tsx`, `Studio/Optimizations/CreateOptimizationWizard.tsx`, `Studio/Evaluations/EvaluationsTab.tsx`

3. **Replace "Something went wrong"** (X5, P18, P32) -- Use specific, actionable error messages per error type.
   - Files: `ProjectSelector.tsx`, `hooks/usePromptSync.tsx`, `hooks/usePromptImportExport.tsx`

### High Priority

4. **Standardize terminology** (X2, X3, P13-P16) -- "Tags" everywhere (not "Keywords"). "AI Instructions"/"Message Template" in Inspector and Quick Test modal. "Title" consistently.
   - Files: `PromptDrawer.tsx`, `FacetedFilters.tsx`, `PromptInspectorPanel.tsx`, `PromptListToolbar.tsx`, `prompt-table-columns.tsx`, `PromptFullPageEditor.tsx`

5. **Explain prompt types** (P6, P29) -- Add tooltips: "System: Sets AI behavior and persona", "Quick: Reusable message template", "Mixed: Has both AI instructions and a message template".
   - File: `FacetedFilters.tsx:20-22`

6. **Replace ML jargon** (P5, S4, S5, S6) -- "Few-shot examples" -> "Example input/output pairs". "MIPRO" -> "Advanced Optimizer (MIPRO)" with description. "Golden" -> "Reference answer".
   - Files: `PromptDrawer.tsx:634`, `Studio/Optimizations/CreateOptimizationWizard.tsx:86,95`, `Studio/TestCases/TestCasesTab.tsx:197`

7. **Add "What is a structured prompt?" help** (P7, P28) -- Help link when conversion is offered explaining benefits and trade-offs.
   - File: `PromptDrawer.tsx:961`

8. **Explain "Keep both" in conflict resolution** (P3) -- Add "(Creates a copy with your changes)" subtitle.
   - File: `ConflictResolutionModal.tsx`

### Medium Priority

9. **Mobile toolbar progressive disclosure** (P25, X7) -- Collapse secondary filters behind "Filters" button on mobile.
   - File: `PromptListToolbar.tsx`

10. **Studio project gate improvement** (S17) -- Auto-select last-used project. Add "Create project" shortcut on empty tabs.
    - File: `Studio/StudioTabContainer.tsx`

11. **Retry button for failed sync** (P33) -- Add inline retry on failed sync operations.
    - Files: `SyncStatusBadge.tsx`, `hooks/usePromptSync.tsx`

12. **Import error specificity** (P19, P34) -- Show "Invalid JSON format" or "Missing required field: title" instead of generic error.
    - File: `hooks/usePromptImportExport.tsx`

13. **Accessibility: ARIA attributes** (X6, P21, P22) -- `role="toolbar"`, `aria-expanded`, `aria-live`, `aria-invalid`.
    - Files: `PromptBulkActionBar.tsx`, `PromptSidebar.tsx`, `PromptListTable.tsx`, `PromptDrawer.tsx`

### Lower Priority

14. Studio keyboard shortcuts: Cmd+1-5 for tabs (S33)
15. Global search across workspaces (S19)
16. Breadcrumbs in Studio (S18)
17. Merge preview in conflict resolution (S15)
18. Name-typing confirmation for Empty Trash (P11)
19. Responsive table column collapsing on mobile (P25)
20. "Conflict -- click to resolve" hint on badge (P2)

---

## Part 6: Verification Plan

After implementing fixes:

1. **Heuristic re-evaluation**: Re-score each heuristic for both Main Page and Studio. Target: all scores >= 3.5/5.

2. **Journey walkthroughs** (manual):
   - Fresh localStorage, researcher persona: Create prompt -> organize with tags -> use in chat. Target: < 5 clicks.
   - Fresh localStorage, student persona: Find template -> customize -> save. Target: < 4 clicks.
   - Content creator persona: Import library -> organize collections -> version. Target: < 6 clicks.
   - Technical persona: Create structured prompt -> add test cases -> run evaluation. Target: < 8 clicks.

3. **Accessibility check**:
   - Tab navigation through all new tooltips and help elements
   - Screen reader testing for Studio output descriptions
   - Color contrast on new help text and warning states
   - Verify `aria-live`, `aria-expanded`, `role="toolbar"` additions

4. **Regression**:
   - All existing tests pass
   - Add tests for: offline banner rendering, terminology consistency (grep for "Keywords" in UI labels), ARIA attributes on bulk action bar
