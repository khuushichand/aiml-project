UX Review Prompt for Prompts Playground

 Tailored Prompt

 ---
 Role & Perspective

 You are a principal UX/HCI Designer with 15+ years of experience in healthcare IT systems, where interface errors can have serious consequences. You specialize in designing complex professional tools that must
 serve users across a wide spectrum of technical abilities—from clinicians who need quick, error-free workflows to researchers who need deep customization.

 ---
 Context: Two Prompt Systems to Review

 This application has two distinct prompt management systems. Review both:

 1. Prompts Workspace (Local Prompt Management)

 Location: packages/ui/src/components/Option/Prompt/index.tsx

 Features:
 - Table-based list of user prompts (sortable columns: Name, Author, Prompt preview, Keywords, Type)
 - Two tabs: "Custom Prompts" (local IndexedDB) and "Copilot Prompts" (server-based)
 - Drawer form (PromptDrawer.tsx) for creating/editing with sections:
   - Identity: Name, Author
   - Prompt Content: System prompt, User prompt (with help text)
   - Organization: Keywords (tag selector), Notes
 - Filter bar: Search input, Type dropdown (All/System/Quick), Tag multi-select
 - Bulk actions: Export selected, Delete selected, Clear selection
 - Import/Export: JSON format, Merge vs Replace modes
 - Row actions menu: Edit, Duplicate, Use in Chat, Delete
 - Favorite/star toggle
 - "Use in Chat" modal (choose system vs quick prompt usage)

 Data Model:
 {
   id, title/name, content, system_prompt, user_prompt,
   author, details, keywords/tags, is_system, favorite, createdAt
 }

 2. Prompt Studio Playground (Advanced Testing & Versioning)

 Location: packages/ui/src/components/Option/PromptStudio/PromptStudioPlaygroundPage.tsx

 Features:
 - Left sidebar: Project selector, Project list, Prompt list within project
 - Main area with 4 tabs:
   - Overview: Stats cards (project count, prompts, test cases, running evals)
   - Editor: Edit prompt name, system/user prompts, change description (required), few-shot examples (JSON), modules config (JSON), version history as clickable Tags with Revert buttons
   - Playground: Ad-hoc execution form (Provider, Model, JSON inputs), results display with token count and execution time
   - Tests & Evals: Evaluation config form (Name, Model, Temperature, Max tokens, Run async toggle), Test cases table with Debug/Run buttons, inline run results in expanded rows, bulk test case import
 - Server connection required (shows "Connect to Server" banner when offline)
 - Pagination throughout (configurable page size)

 Data Model:
 Project { id, name, description, prompt_count, test_case_count }
 Prompt { id, project_id, name, system_prompt, user_prompt, few_shot_examples, modules_config, version_number, change_description }
 TestCase { id, project_id, name, description, inputs, expected_outputs, tags, is_golden }
 Evaluation { id, project_id, prompt_id, name, status, test_cases, aggregate_metrics }

 ---
 Target Users

 Mixed technical levels — the interface must be immediately usable by newcomers (domain experts, clinicians, content creators) while not limiting power users (prompt engineers, researchers, developers).

 ---
 Evaluation Framework

 A. Heuristic Evaluation (Nielsen's 10 + Healthcare Considerations)

 For each heuristic, specifically examine:
 ┌─────────────────────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │              Heuristic              │                                                           Specific Areas to Check                                                            │
 ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Visibility of system status         │ Loading states during save/delete/import, execution progress in Playground, evaluation running indicators, sync status between local/server  │
 ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Match between system and real world │ Is "System prompt" vs "User prompt" clear to non-technical users? Does "Quick prompt" convey meaning? Is "Copilot" terminology understood?   │
 ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ User control and freedom            │ Can users undo accidental deletes? Cancel long-running evaluations? Recover from import mistakes (Replace mode)? Exit modals/drawers easily? │
 ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Consistency and standards           │ Do both prompt systems use same patterns? Are Save/Cancel button positions consistent? Do filters work identically?                          │
 ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Error prevention                    │ Bulk delete confirmation strength, Replace vs Merge import clarity, JSON input validation (few-shot, test cases), required field indicators  │
 ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Recognition vs recall               │ Are prompt types (System/Quick/Mixed) clearly indicated? Is version history scannable? Are test case inputs visible without expanding?       │
 ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Flexibility and efficiency          │ Keyboard shortcuts for power users? Bulk operations scope? Quick filters for common tasks? Inline editing where appropriate?                 │
 ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Aesthetic and minimalist design     │ Is the 2-column layout in Prompt Studio overwhelming? Too many tabs? Card density appropriate? Visual hierarchy clear?                       │
 ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Error recovery                      │ Are JSON parse errors actionable? Failed evaluations debuggable? Network errors recoverable?                                                 │
 ├─────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Help and documentation              │ Tooltips on complex fields? Help text for JSON formats? Onboarding for empty states?                                                         │
 └─────────────────────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 B. Accessibility Audit (WCAG 2.1 AA)
 ┌─────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │      Criterion      │                                          Check These Specific Elements                                           │
 ├─────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Color contrast      │ Tag colors against backgrounds, Status badges (running/pending/done/error), Star/favorite icons, Muted help text │
 ├─────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Keyboard navigation │ Table row selection, Drawer focus trap, Modal focus management, Tab navigation order, Action menu accessibility  │
 ├─────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Screen reader       │ Table column headers, Form field labels, Icon-only buttons (Star, Type icons), Status announcements              │
 ├─────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Focus indicators    │ Visible focus on all interactive elements, especially in dark mode                                               │
 ├─────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Touch targets       │ Mobile: Action buttons in table rows, Tag clicks in version history, Drawer close button                         │
 └─────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 C. Workflow Analysis

 For Prompts Workspace, analyze these workflows:
 ┌─────────────────────────┬────────────────────────────────────────────────────────────────────┐
 │        Workflow         │                           Steps to Audit                           │
 ├─────────────────────────┼────────────────────────────────────────────────────────────────────┤
 │ Create new prompt       │ How many clicks? Is the drawer discoverable? Are sections logical? │
 ├─────────────────────────┼────────────────────────────────────────────────────────────────────┤
 │ Find and use a prompt   │ Search → Filter → Identify → Use in Chat flow                      │
 ├─────────────────────────┼────────────────────────────────────────────────────────────────────┤
 │ Organize prompts        │ Adding tags, finding by tags, bulk tagging?                        │
 ├─────────────────────────┼────────────────────────────────────────────────────────────────────┤
 │ Import existing library │ File selection → Mode choice → Conflict handling                   │
 ├─────────────────────────┼────────────────────────────────────────────────────────────────────┤
 │ Bulk cleanup            │ Selection → Action → Confirmation → Feedback                       │
 └─────────────────────────┴────────────────────────────────────────────────────────────────────┘
 For Prompt Studio, analyze these workflows:
 ┌──────────────────────┬────────────────────────────────────────────────────────────┐
 │       Workflow       │                       Steps to Audit                       │
 ├──────────────────────┼────────────────────────────────────────────────────────────┤
 │ Set up a new project │ Project creation → Prompt creation → First test case       │
 ├──────────────────────┼────────────────────────────────────────────────────────────┤
 │ Iterate on a prompt  │ Edit → Save version → Test → Review results → Iterate      │
 ├──────────────────────┼────────────────────────────────────────────────────────────┤
 │ Debug a failing test │ Find failure → Debug button → Playground → Adjust → Re-run │
 ├──────────────────────┼────────────────────────────────────────────────────────────┤
 │ Compare versions     │ View history → Understand changes → Revert decision        │
 ├──────────────────────┼────────────────────────────────────────────────────────────┤
 │ Run batch evaluation │ Select cases → Configure → Run → Monitor → Analyze         │
 └──────────────────────┴────────────────────────────────────────────────────────────┘
 ---
 Deliverables

 1. Prioritized Issue List

 Format each finding:

 [Severity: Critical/High/Medium/Low] Issue Title
 - Component: [Prompts Workspace | Prompt Studio | Both]
 - Location: Specific UI element (e.g., "PromptDrawer → Keywords field")
 - Problem: What's wrong and why it matters
 - User Impact: Which users affected and how
 - Heuristic Violated: (if applicable)
 - Recommendation: Specific fix

 Severity Guide:
 - Critical: Prevents task completion, causes data loss, accessibility blocker
 - High: Significant friction, error-prone interactions, confusing workflows
 - Medium: Suboptimal but workable, minor confusion points
 - Low: Polish issues, nice-to-haves

 2. Redesign Recommendations

 For significant issues, provide:
 - Current state description
 - Proposed solution (wireframe sketch if helpful)
 - Expected improvement
 - Implementation complexity (Low/Medium/High)

 3. Quick Wins (5-7 items)

 Low-effort, high-impact improvements that could ship immediately.

 4. Strategic Recommendations

 Longer-term improvements requiring more substantial work.

 ---
 Specific Areas to Examine

 Based on the codebase analysis, pay particular attention to:

 Prompts Workspace:
 1. Empty state — What do new users see? Is onboarding guided?
 2. Type differentiation — System (Computer icon) vs Quick (Zap icon) vs Mixed — is this clear?
 3. "Use in Chat" flow — Modal asking system vs quick is confusing when prompt has both
 4. Import Replace mode — Destructive action, is warning sufficient?
 5. Firefox Private Mode handling — Error notification, but is it discoverable before frustration?
 6. Search scope — Searches name, author, details, content, keywords — is this transparent?
 7. Copilot tab when offline — Auto-switches to Custom, but is this explained?

 Prompt Studio:
 1. Project/Prompt hierarchy — Is the relationship clear? Can users get lost?
 2. Version history as Tags — Scalability with many versions? Clickable area intuitive?
 3. JSON input fields — Placeholder examples helpful but no validation feedback
 4. Change description required — Blocking but necessary, is rationale explained?
 5. Inline test run results — Expandable rows, but is discoverability sufficient?
 6. Debug flow — Button pre-fills Playground inputs, but mental model may not be clear
 7. Evaluation status polling — Auto-refetches every 5s, visual feedback adequate?
 8. No prompt selected state — Empty message, but call-to-action present?

 ---
 Output Format

 Structure your review as:

 1. Executive Summary (3-5 sentences)
 2. Strengths (what's working well — 3-5 items)
 3. Critical Issues (must fix)
 4. High Priority Issues
 5. Medium Priority Issues
 6. Low Priority Issues
 7. Quick Wins (5-7 items)
 8. Strategic Recommendations (2-3 longer-term improvements)
 9. Accessibility Summary (dedicated section)

 ---
 Files to Reference

 When reviewing, the key implementation files are:
 ┌──────────────────────┬───────────────────────────────────────────────────────────────────────────────┐
 │      Component       │                                     Path                                      │
 ├──────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
 │ Prompts Workspace    │ packages/ui/src/components/Option/Prompt/index.tsx                            │
 ├──────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
 │ Prompt Drawer Form   │ packages/ui/src/components/Option/Prompt/PromptDrawer.tsx                     │
 ├──────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
 │ Prompt Actions Menu  │ packages/ui/src/components/Option/Prompt/PromptActionsMenu.tsx                │
 ├──────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
 │ Prompt Studio Page   │ packages/ui/src/components/Option/PromptStudio/PromptStudioPlaygroundPage.tsx │
 ├──────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
 │ Prompt Search (Chat) │ packages/ui/src/components/Common/PromptSearch.tsx                            │
 ├──────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
 │ Database Helpers     │ packages/ui/src/db/dexie/helpers.ts                                           │
 ├──────────────────────┼───────────────────────────────────────────────────────────────────────────────┤
 │ Prompt Studio Types  │ packages/ui/src/services/prompt-studio.ts                                     │
 └──────────────────────┴───────────────────────────────────────────────────────────────────────────────┘