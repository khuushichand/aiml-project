# Moderation Playground UX Redesign

**Date:** 2026-03-07
**Status:** Approved
**Scope:** Frontend only (no backend changes required)

## Problem

The current `/moderation-playground` page is a 1,918-line monolithic component with UX issues:

- Missing backend feature parity (server-level enabled/action toggles, full category taxonomy, performance tuning, export/import)
- Information architecture relies on a single scrollable page with an "Advanced" toggle that hides key features
- Dense layout mixes server-wide and per-user concerns
- No inline help for blocklist syntax
- Test results are minimal (no before/after, no history)
- Category picker uses 7 hardcoded suggestions vs 8+ backend categories with metadata

## Design Decisions

- **Architecture:** Tabbed sub-pages within a single route, not separate routes
- **Both personas:** Admin (server config) and guardian (per-user rules) served equally
- **Full backend parity:** All configurable features exposed (A-H)
- **Guardian UI deferred:** Supervised policy engine (schedules, chat-type scoping, notifications) is a future effort
- **Fully responsive:** Equal attention to mobile, tablet, desktop
- **Component library:** Shift toward custom Tailwind components, reduce antd dependency

## Page Structure

### Hero Banner
- Keeps gradient + grid aesthetic
- Simplified: title, subtitle, server status tag, reload button
- Scope selector and user ID input move to Context Bar

### Context Bar (new, sticky)
- **Left:** Scope dropdown (Server/User) + user ID input (when scope=user) + "Configuring: {userId}" badge
- **Center:** Policy status badges (enabled/disabled, input action, output action, rule count)
- **Right:** Unsaved changes indicator + Quick Test button
- **Mobile:** Collapses to single row; status badges in collapsible row below

### Tab Bar
5 tabs: Policy & Settings | Blocklist Studio | User Overrides | Test Sandbox | Advanced

Custom Tailwind tab bar (not antd Tabs). Horizontally scrollable on mobile. State preserved across tab switches via shared hooks.

## Tab 1: Policy & Settings

Server-wide moderation configuration.

- **Master toggle** (new) — `enabled` config, not previously exposed in UI
- **Input/Output split controls** — Two-column layout. Each has: enabled toggle, action selector (block/redact/warn with descriptions). Redact replacement text under output column.
- **PII Detection toggle** — Same as current, with description
- **Category picker** (improved) — Visual grid from backend `get_all_categories()`. Each card: name, description, severity, keyword/pattern count. Checkbox to enable. Custom category input below. Replaces hardcoded 7-item Select.
- **Per-user overrides toggle** (new) — Enables/disables the entire override system
- **Persist toggle** — Warning-styled, confirmation modal when enabling
- **Save / Reset buttons** — With active policy summary banner below

**Mobile:** Input/Output columns stack. Category grid to 2-col then 1-col. Buttons full-width.

## Tab 2: Blocklist Studio

Rule authoring with two sub-views: Managed Rules (default) and Raw Editor.

### Managed Rules
- **Add-rule form** (improved) — Structured fields: pattern input, action dropdown, categories multi-select, phase selector. Replaces single text input.
- **Inline validation** — Lint result shows below form after "Validate" click. Green/red status with parsed details.
- **Rules table** (improved) — Columns: #, pattern, type (literal/regex tag), action (color-coded), categories (chips), delete. Version footer. Auto-loads on tab activation.

### Raw Editor
- Warning banner about full replacement
- Monospace textarea with line numbers (CSS-only)
- Placeholder with real syntax examples
- Load / Validate all / Save buttons
- Lint results table

### Syntax Reference (new)
- Collapsible panel visible in both sub-views
- Documents full grammar: literals, regex, actions, redact substitution, categories, comments
- Notes ReDoS safety (nested quantifiers rejected, >2000 char limit)

**Mobile:** Add-rule fields stack. Table scrolls horizontally. Syntax ref full-width.

## Tab 3: User Overrides

Per-user moderation settings. Consolidates current hero user-picker, Per-User Safety Rules card, and Advanced-mode overrides table.

### User Picker (improved)
- Searchable combobox showing existing override user IDs as suggestions
- "No override found — create new?" prompt for unknown IDs
- Replaces plain text input + "Load user" button

### Two-Column Editor
- **Left column:** Presets (Strict/Balanced/Monitor as compact buttons), enabled toggle, input settings (enabled + action), output settings (enabled + action + redact replacement), category picker
- **Right column:** Phrase list builder with add form (pattern, ban/notify, phase, regex checkbox), banned phrases list, notify phrases list. Counts in section headers.

### All Overrides Table (always visible)
- Search filter, row selection, bulk delete
- Summary column: active/disabled, input/output actions, rule count
- Edit button switches to that user in the editor above

### Actions
- Save, Reset changes, Delete override (with confirmation)

**Mobile:** Editor columns stack. Table shows user ID + summary only, actions behind "..." menu. Presets horizontal scroll.

## Tab 4: Test Sandbox

Verify-your-work surface for testing moderation rules.

### Test Form
- Phase selector (User message / AI response) + optional user ID input
- Sample text textarea
- **Quick sample buttons** (new) — Pre-filled test strings from category taxonomy keywords (PII email, phone, profanity, etc.)
- Run Test button

### Results (improved)
- Prominent color-coded status badge (red=block, orange=redact, yellow=warn, green=pass)
- Two-column layout: match details (category, pattern, action, phase) on left, before/after comparison on right
- **Before/After** (new) — Original text with highlighted match span, redacted text with replacement inline
- **Effective policy viewer** (new) — Collapsible JSON of applied policy

### Test History (new)
- Session-only list of recent tests (capped at ~20)
- Each entry: truncated input, phase, result badge
- Actions: Rerun (re-execute with current policy), Load (populate form)
- Clear history button

### Quick Test (Context Bar)
- Compact inline form: text input + phase dropdown + run button
- Slides below context bar, usable from any tab
- Single-line result summary with "Open full results" link to Test Sandbox
- Inherits user ID from context bar scope
- Close with x or Escape

**Mobile:** Phase/user stack. Quick samples scrollable pills. Before/After stacks vertically. History compact.

## Tab 5: Advanced

Power-user surface for performance tuning and system operations.

### Performance Tuning (read-only display)
- `max_scan_chars` (default 200000)
- `max_replacements_per_pattern` (default 1000)
- `match_window_chars` (default 4096)
- `blocklist_write_debounce_ms` (default 0)
- Each with description. Info note: values from server config, requires config file edit + reload.

### Export / Import (new)
- Download blocklist.txt / Upload & replace
- Download overrides.json / Upload & replace
- Warning about full replacement + backup recommendation

### System Operations
- Reload from disk button with description
- Per-user overrides master toggle

### Server Configuration (read-only)
- Collapsible view of file paths, auth mode, config values from effective policy snapshot

**Mobile:** Single column. Number inputs full-width. Export/Import buttons stack.

## Shared State Architecture

```
useModerationContext() -> { scope, activeUserId, setScope, setActiveUserId }
useModerationSettings() -> { settings, updateSettings, isDirty, reset, ... }
useModerationPolicy() -> { policy, refetch }
useUserOverrides() -> { overrides, setOverride, deleteOverride, bulkDelete, ... }
useBlocklist() -> { items, append, delete, lint, managedItems, rawText, ... }
useModerationTest() -> { runTest, result, history, clearHistory }
```

Each hook manages its own react-query state. Context bar reads `isDirty` from each hook for unsaved indicator.

## Component File Structure

```
ModerationPlayground/
  index.tsx                    # Route entry, lazy loads shell
  ModerationPlaygroundShell.tsx  # Hero + context bar + tab router (~150 lines)
  ModerationContextBar.tsx       # Sticky status bar + quick test (~80 lines)
  PolicySettingsPanel.tsx        # Tab 1 (~250 lines)
  BlocklistStudioPanel.tsx       # Tab 2 (~300 lines)
  UserOverridesPanel.tsx         # Tab 3 (~300 lines)
  TestSandboxPanel.tsx           # Tab 4 (~200 lines)
  AdvancedPanel.tsx              # Tab 5 (~150 lines)
  hooks/
    useModerationContext.ts
    useModerationSettings.ts
    useBlocklist.ts
    useUserOverrides.ts
    useModerationTest.ts
  components/
    CategoryPicker.tsx           # Grid with taxonomy metadata
    BlocklistSyntaxRef.tsx       # Collapsible syntax reference
    PolicyStatusBadges.tsx       # Reusable status tag row
    QuickTestInline.tsx          # Context bar mini-tester
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+S / Cmd+S | Save current tab's pending changes |
| Ctrl+T / Cmd+T | Toggle Quick Test open/closed |
| Escape | Close Quick Test if open |

## Antd vs Custom Tailwind

**Keep antd:** Modal (confirm dialogs), Tooltip, message (toast), Select mode="tags" (complex multi-select)
**Replace with custom Tailwind:** Cards, Tables (simple cases), Switches/toggles, Segmented controls, Tabs, Badges/Tags, basic Selects

## Nielsen Heuristic Coverage

| Heuristic | How addressed |
|-----------|---------------|
| 1. Visibility of system status | Context bar with live policy badges, unsaved indicator, server status |
| 2. Match real world | "User message"/"AI response" instead of "input"/"output" phase throughout |
| 3. User control & freedom | Reset changes on every tab, test history rerun/load, undo via baseline comparison |
| 4. Consistency | Shared hooks, consistent save/reset pattern across tabs, uniform action selectors |
| 5. Error prevention | Persist confirmation modal, blocklist replace warning, delete confirmations, inline lint |
| 6. Recognition over recall | Category grid with descriptions, syntax reference, quick samples, structured add-rule form |
| 7. Flexibility & efficiency | Quick Test from any tab, keyboard shortcuts, presets, bulk operations |
| 8. Aesthetic & minimalist | Tab separation reduces cognitive load, progressive disclosure within tabs |
| 9. Help recognize errors | Inline lint with actionable messages, color-coded test results, before/after comparison |
| 10. Help & documentation | Syntax reference panel, tooltips on every control, category metadata display |
