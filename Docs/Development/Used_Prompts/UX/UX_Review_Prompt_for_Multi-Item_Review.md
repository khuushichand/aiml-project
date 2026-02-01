Enhanced UX Review Prompt for Multi-Item Review Playground

 Original Request

 Help craft a better prompt for reviewing the Multi-Item Review playground page from a hospital UX/HCI designer perspective.

 ---
 Recommended Prompt

 You are a Principal UX/HCI Designer with 15+ years of experience designing clinical applications for hospital environments. Your expertise includes:
 - High-stakes decision support interfaces
 - Accessibility compliance (WCAG 2.1 AA)
 - Cognitive load management for fatigued users
 - Error prevention in time-pressured contexts

 ## Context
 Review the Multi-Item Review playground page for the tldw extension/WebUI. This page allows users to search, filter, select, and compare multiple media items (transcripts, notes, documents) simultaneously.

 ## Core Features to Evaluate

 ### 1. Search & Filtering System
 - Free-text search with content toggle
 - Multi-select media type filter
 - Keyword/tag filtering with suggestions
 - Favorites filter
 - Collapsible filter panel with active count badge

 ### 2. Selection Mechanics
 - Click and Shift+click range selection
 - 30-item selection limit
 - Visual selection indicators in sidebar
 - Selection count display and clear button

 ### 3. View Modes (Evaluate discoverability and switching)
 - **Compare/Spread**: Side-by-side view (2-4 items)
 - **Focus/List**: Single item with prev/next navigation
 - **Stack/All**: Vertical scroll of all selected items
 - Auto-select mode based on selection count

 ### 4. Navigation
 - Prev/Next buttons and keyboard shortcuts (j/k)
 - Mini-map quick-jump buttons
 - Position indicator (e.g., "2 of 5")
 - Escape key to clear selection

 ### 5. Content Display
 - Expandable content sections with truncation (2000 chars)
 - Expandable analysis/summary sections (1600 chars)
 - Copy-to-clipboard buttons
 - "Collapse others on expand" toggle
 - Expand all / Collapse all controls

 ### 6. Layout Options
 - Vertical orientation (full-width cards)
 - Horizontal orientation (~48% width side-by-side)
 - Settings dropdown for preferences

 ### 7. Onboarding
 - First-use 3-step tooltip guide
 - Keyboard shortcuts help button

 ## Evaluation Criteria

 For each criterion, provide:
 - Current state assessment (1-5 scale)
 - Specific issues identified
 - Recommended improvements with rationale

 ### A. Discoverability & Learnability
 1. Can a first-time user understand the three view modes without documentation?
 2. Are keyboard shortcuts discoverable before users need them?
 3. Is the 30-item selection limit communicated proactively?
 4. Are collapsed filters too hidden (filter state visibility)?

 ### B. Cognitive Load (Critical for hospital context)
 1. Does the sidebar/viewer split create unnecessary eye movement?
 2. Is the mini-map button bar helpful or visual noise?
 3. How many actions are needed for the most common task flow?
 4. Are expand/collapse states predictable and consistent?

 ### C. Error Prevention & Recovery
 1. What happens when users exceed the selection limit?
 2. Can users accidentally lose their selection? How to recover?
 3. Is it clear which items are currently visible vs. selected?
 4. Are destructive actions (clear all) sufficiently guarded?

 ### D. Efficiency for Expert Users
 1. Is keyboard navigation sufficient for power users?
 2. Can common workflows be completed without mouse?
 3. Are there unnecessary confirmation steps?
 4. Does the auto-select view mode help or hinder experienced users?

 ### E. Accessibility
 1. Screen reader compatibility for selection state changes
 2. Keyboard focus indicators visibility
 3. Color contrast for selection states
 4. Motion preferences respected (prefers-reduced-motion)

 ### F. Information Architecture
 1. Is the content/analysis separation logical?
 2. Does metadata placement support scanning?
 3. Are timestamps and durations formatted appropriately?
 4. Is pagination vs. infinite scroll the right choice?

 ### G. Responsive Design
 1. How does the interface adapt to smaller viewports?
 2. Does sidebar collapse appropriately?
 3. Are touch targets adequate for tablet use?

 ## Deliverables Requested

 1. **Priority Matrix**: Plot issues on Severity (1-4) vs. Effort (1-4) grid
 2. **Top 5 Quick Wins**: High-impact, low-effort improvements
 3. **Top 3 Critical Issues**: Must-fix before release
 4. **Interaction Flow Diagram**: Annotate the ideal task flow for "compare 3 items"
 5. **Specific Recommendations**: For each issue, provide:
    - Current behavior
    - Problem it causes
    - Proposed solution
    - Expected impact

 ## Hospital Environment Considerations

 Apply your clinical UX expertise to specifically address:
 - **Interruption recovery**: Can users resume after being pulled away?
 - **Glanceability**: Can status be understood in <2 seconds?
 - **Fatigue tolerance**: Does the UI work after a 12-hour shift?
 - **Shared workstation use**: Does the UI leak context between users?
 - **Low-light environments**: Color/contrast in dimmed settings

 ---
 Why This Prompt is Better
 ┌─────────────────────┬────────────────────────────────┬───────────────────────────────────────────┐
 │       Aspect        │            Original            │                 Enhanced                  │
 ├─────────────────────┼────────────────────────────────┼───────────────────────────────────────────┤
 │ Reviewer context    │ Brief mention                  │ Detailed expertise framing                │
 ├─────────────────────┼────────────────────────────────┼───────────────────────────────────────────┤
 │ Features to review  │ Implicit                       │ Explicit enumeration                      │
 ├─────────────────────┼────────────────────────────────┼───────────────────────────────────────────┤
 │ Evaluation criteria │ None                           │ 7 categories with sub-questions           │
 ├─────────────────────┼────────────────────────────────┼───────────────────────────────────────────┤
 │ Deliverables        │ Vague ("expose functionality") │ 5 specific outputs requested              │
 ├─────────────────────┼────────────────────────────────┼───────────────────────────────────────────┤
 │ Domain context      │ "hospital" mentioned           │ Hospital-specific UX concerns detailed    │
 ├─────────────────────┼────────────────────────────────┼───────────────────────────────────────────┤
 │ Actionability       │ Low                            │ High (severity/effort matrix, quick wins) │
 └─────────────────────┴────────────────────────────────┴───────────────────────────────────────────┘
 Alternative Shorter Version

 If you need a more concise prompt:

 As a Principal UX/HCI Designer specializing in clinical applications, review the Multi-Item Review playground for usability and ergonomics.

 **Key areas**: Search/filtering, selection mechanics (click, shift-click, 30-item limit), three view modes (Compare/Focus/Stack), keyboard navigation (j/k/o/Escape), content expand/collapse, and onboarding.

 **Evaluate against**:
 1. Discoverability without documentation
 2. Cognitive load for fatigued users
 3. Error prevention and recovery
 4. Expert user efficiency
 5. Accessibility (WCAG 2.1 AA)

 **Deliverables**:
 - Top 7 quick wins (high impact, low effort)
 - Top 10 critical issues
 - Specific recommendations with current state → proposed solution format

 **Hospital context**: Address interruption recovery, glanceability (<2s), 12-hour shift fatigue tolerance, and shared workstation privacy.