# Enhanced UX Review Prompt for Multi-Item Review Playground

## Original Request

Help craft a better prompt for reviewing the Multi-Item Review playground page from a hospital UX/HCI designer perspective.

---

## Recommended Prompt

```
You are a Principal UX/HCI Designer with 15+ years of experience designing clinical applications for hospital environments. Your expertise includes:
- High-stakes decision support interfaces
- Accessibility compliance (WCAG 2.1 AA)
- Cognitive load management for fatigued users
- Error prevention in time-pressured contexts

## Context

Review the Multi-Item Review playground page for the tldw extension/WebUI. This page allows users to search, filter, select, and compare multiple media items (transcripts, notes, documents) simultaneously.

## Core Features to Evaluate

### 1. Search & Filtering System
- Free-text search with content toggle (searches title/content)
- Multi-select media type filter (dropdown with available types)
- Keyword/tag filtering with autocomplete suggestions
- "Include Content" checkbox for deep content search
- Collapsible filter panel with active count badge
- Clear filters button when filters active

### 2. Selection Mechanics
- Click to select/deselect individual items
- Shift+click for range selection across visible results
- 30-item selection limit with warning messages
- Visual selection indicators (ring highlight, checkbox state)
- Selection count display with proximity warning (changes color near limit)
- Clear selection button in sidebar header

### 3. View Modes (Evaluate discoverability and switching)
- **Compare/Spread**: Side-by-side view of all selected items
- **Focus/List**: Single item with dropdown picker for navigation
- **Stack/All**: Vertical scroll of all selected items with position badges
- Auto-select mode based on selection count (configurable):
  - 1 item → Focus mode
  - 2-4 items → Compare mode
  - 5+ items → Stack mode

### 4. Navigation
- Prev/Next buttons with keyboard shortcuts (j/k)
- Item position indicator ("Item 2 of 5")
- Mini-map button bar showing all open items with quick-jump
- Escape key to clear selection entirely
- "o" key to toggle expand on focused card
- Tab navigation into results list, Enter/Space to select

### 5. Content Display
- Expandable content sections with truncation (2000 chars)
- Expandable analysis/summary sections (1600 chars)
- Copy-to-clipboard buttons for content and analysis separately
- "Collapse others on expand" toggle in settings dropdown
- Expand all / Collapse all controls in dropdown menu
- Loading skeleton states during detail fetch

### 6. Layout Options
- Vertical orientation (full-width cards)
- Horizontal orientation (~48% width side-by-side)
- Settings dropdown with toggleable options:
  - Auto-select view mode
  - Collapse others on expand
  - Review all on page action

### 7. Onboarding
- First-use 3-step tooltip guide (dismissible, persisted)
- Keyboard shortcuts help button ("?" icon with tooltip)
- Contextual hints ("Click to stack, Shift+click for range")
- Empty state with guidance when no items selected

### 8. Accessibility Features Present
- aria-live region for selection count announcements
- aria-selected states on result items
- aria-expanded on collapsible sections
- Screen reader labels on icon-only buttons
- prefers-reduced-motion detection for animations
- Focus trap and tabIndex management

## Evaluation Criteria

For each criterion, provide:
- Current state assessment (1-5 scale)
- Specific issues identified
- Recommended improvements with rationale

### A. Discoverability & Learnability
1. Can a first-time user understand the three view modes without documentation?
2. Are keyboard shortcuts discoverable before users need them?
3. Is the 30-item selection limit communicated proactively (not just on error)?
4. Are collapsed filters too hidden (filter state visibility)?
5. Is the relationship between sidebar selection and viewer display clear?

### B. Cognitive Load (Critical for hospital context)
1. Does the sidebar/viewer split create unnecessary eye movement?
2. Is the mini-map button bar helpful or visual noise when many items selected?
3. How many actions are needed for the most common task flow (compare 3 items)?
4. Are expand/collapse states predictable and consistent across cards?
5. Is there too much visual density in the viewer header rows?

### C. Error Prevention & Recovery
1. What happens when users exceed the selection limit? (Currently: warning toast)
2. Can users accidentally lose their selection? How to recover?
3. Is it clear which items are currently visible vs. selected but scrolled?
4. Are destructive actions (clear all) sufficiently guarded?
5. What happens on network errors during detail fetch?

### D. Efficiency for Expert Users
1. Is keyboard navigation sufficient for power users (j/k/o/Escape)?
2. Can common workflows be completed without mouse?
3. Are there unnecessary confirmation steps?
4. Does the auto-select view mode help or hinder experienced users?
5. Is the mini-map useful for navigation or redundant with dropdown picker?

### E. Accessibility
1. Screen reader compatibility for selection state changes (aria-live present)
2. Keyboard focus indicators visibility
3. Color contrast for selection states (ring highlight)
4. Motion preferences respected (prefers-reduced-motion checked)
5. Touch targets adequate for tablet use?

### F. Information Architecture
1. Is the content/analysis separation logical?
2. Does metadata placement support scanning (type tag, date, duration)?
3. Are timestamps and durations formatted appropriately?
4. Is pagination vs. virtualized scrolling the right choice for results?
5. Is the "Open items" mini-map placement logical?

### G. Responsive Design
1. How does the interface adapt to smaller viewports?
2. Does sidebar collapse appropriately (toggle bar present)?
3. Are touch targets adequate for tablet use?
4. Does horizontal orientation work on narrower screens?

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
```

---

## Why This Prompt is Better

| Aspect | Original | Enhanced |
|--------|----------|----------|
| Reviewer context | Brief mention | Detailed expertise framing |
| Features to review | Implicit | Explicit enumeration with implementation details |
| Evaluation criteria | None | 7 categories with sub-questions |
| Deliverables | Vague | 5 specific outputs requested |
| Domain context | "hospital" mentioned | Hospital-specific UX concerns detailed |
| Actionability | Low | High (severity/effort matrix, quick wins) |
| Accessibility | Not mentioned | Dedicated criteria section |

---

## Alternative Shorter Version

If you need a more concise prompt:

```
As a Principal UX/HCI Designer specializing in clinical applications, review the Multi-Item Review playground for usability and ergonomics.

**Key areas**: Search/filtering (free-text, type filter, keywords, content toggle), selection mechanics (click, shift-click, 30-item limit), three view modes (Compare/Focus/Stack with auto-select), keyboard navigation (j/k/o/Escape), content expand/collapse, and onboarding.

**Evaluate against**:
1. Discoverability without documentation
2. Cognitive load for fatigued users
3. Error prevention and recovery
4. Expert user efficiency
5. Accessibility (WCAG 2.1 AA)

**Deliverables**:
- Top 5 quick wins (high impact, low effort)
- Top 3 critical issues
- Specific recommendations with current state → proposed solution format

**Hospital context**: Address interruption recovery, glanceability (<2s), 12-hour shift fatigue tolerance, and shared workstation privacy.
```

---

## Files to Reference

When reviewing, the key implementation files are:

| Component | Path |
|-----------|------|
| Media Review Page | `packages/ui/src/components/Review/MediaReviewPage.tsx` |
| UI Settings | `packages/ui/src/services/settings/ui-settings.ts` |
| Note Keywords | `packages/ui/src/services/note-keywords.ts` |
| Background Request | `packages/ui/src/services/background-proxy.ts` |

---

## Key Implementation Details

### State Management
- Selection state: `selectedIds` array with 30-item limit (`openAllLimit`)
- View mode: `viewModeState` with persistence via `useSetting` hook
- Expand states: Separate `contentExpandedIds` and `analysisExpandedIds` Sets
- Filter state: Collapsible via `filtersCollapsed` with persistence

### Virtualization
- Uses `@tanstack/react-virtual` for both results list and viewer
- Results list: `estimateSize: 110px`, overscan: 8
- Viewer: `estimateSize: 520px`, overscan: 6, dynamic measurement enabled

### Keyboard Shortcuts
```
j      - Navigate to next item
k      - Navigate to previous item
o      - Toggle expand on focused card
Escape - Clear selection
Enter/Space - Select item (when focused in results list)
```

### Selection Limit Handling
- Warning shown when limit reached
- Shift+click range selection respects limit (adds partial range if needed)
- Selection count display changes color when approaching limit
