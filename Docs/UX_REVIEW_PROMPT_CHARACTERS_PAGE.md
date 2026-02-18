# UX Review Prompt: `/characters` Page

> **Usage**: Paste this prompt to a UX-capable LLM (Claude, GPT-4, etc.) along with
> screenshots of the `/characters` page in all four viewport/theme combinations
> (desktop-light, desktop-dark, mobile-light, mobile-dark), plus screenshots of key
> modals (create, edit, import, AI generate, conversations list). The model will
> produce a structured heuristic evaluation.

---

You are a senior UX researcher and HCI expert conducting a heuristic evaluation of a
"/characters" page in a research-assistant / AI-chat application (tldw_server). This
page lets users create, manage, and chat with reusable AI character personas (similar
to SillyTavern character cards). Put yourself in the shoes of three user archetypes:

1. **Newcomer** - first time on the page, no characters yet, unfamiliar with the
   concept of "character cards" or prompt engineering.
2. **Power user** - 50+ characters, uses tags/search heavily, imports/exports between
   tools (SillyTavern, Chub, etc.), cares about prompt format control.
3. **Accessibility-conscious user** - relies on keyboard navigation, screen readers,
   or reduced-motion preferences.

## Current page capabilities (for context)

**Listing & views:** table view (avatar, name, description, tags, conversation count,
action buttons) and gallery view (avatar grid cards). Paginated (10/page). Sortable
columns. Persisted view preference.

**Search & filter:** debounced text search, multi-tag filter with "match all" toggle,
tag usage counts shown.

**CRUD:** create (form with core + collapsible advanced fields), inline-edit
(name/description double-click in table), edit (full form), duplicate, soft-delete
with 10s undo toast, restore.

**Import/export:** file import (JSON, YAML, TXT, MD, PNG with embedded metadata),
export as JSON or PNG (SillyTavern V3 spec), bulk export to single JSON.

**Bulk operations:** multi-select in table view, bulk delete, bulk export, bulk add tags.

**AI generation:** full-character generation from a concept prompt (with model selector,
progress steps, preview-before-apply), per-field sparkle buttons, AI avatar generation
via image backends.

**Keyboard shortcuts:** N (new), / (search), Escape (close modal), G (gallery), T (table).

**Draft auto-save:** form drafts saved to browser storage every 30s with restoration banner.

**Character data model:** name, description, avatar, system_prompt, greeting,
alternate_greetings, personality, scenario, post_history_instructions, message_example,
creator_notes, creator, character_version, tags, prompt_preset (default/st_default),
author_note, generation settings (temp, top_p, rep_penalty, stop sequences), mood images.

**Chat integration:** "Chat" button sets character and navigates to chat; "View
conversations" modal lists all chats for that character.

---

## Evaluation dimensions

For each dimension below, identify specific issues, rate severity
(Critical / Major / Minor / Enhancement), and propose concrete improvements.

### 1. First-use experience & onboarding
- Is it clear what characters are and why you'd create one?
- Does the empty state guide the user effectively?
- Are templates discoverable enough? Do they help newcomers understand the concept?
- Is the relationship between characters and chat sessions obvious?

### 2. Information architecture & discoverability
- Are all character fields visible/accessible at the right time?
- Is the "advanced fields" collapse hiding important information?
- Can users quickly understand what a character "does" from the list view alone?
- Are the prompt_preset, generation settings, and author_note discoverable?
- Is the mood images feature discoverable and understandable?

### 3. Search, filtering & organization
- Is tag management (create, rename, merge, delete tags) sufficient?
- Can users find characters efficiently at scale (50-100+ characters)?
- Are there missing filter dimensions (e.g., by creator, last-used, has-conversations)?
- Is sorting flexible enough (e.g., sort by last-used, most-conversations)?

### 4. Character creation & editing workflow
- Is the form layout logical? Are fields grouped well?
- Is the system_prompt field given enough guidance (what makes a good one)?
- Are alternate_greetings easy to manage (add, reorder, preview)?
- Is the difference between "personality" vs "description" vs "system_prompt" clear?
- Does the AI generation workflow feel trustworthy and controllable?

### 5. Import/export & interoperability
- Is the import flow intuitive for users coming from SillyTavern, Chub, or other tools?
- Are format compatibility issues surfaced clearly?
- Is bulk import supported (multiple files at once)?
- Can users preview what they're importing before committing?

### 6. Conversation integration
- Is the link between characters and their conversations clear?
- Can users see conversation history/stats from the character page?
- Is it obvious how to start a new chat vs resume an existing one?
- Can users set a "default" character for new conversations?

### 7. Visual design & information density
- Is the table view making good use of space?
- Does the gallery view convey enough information per card?
- Are avatars handled well (missing avatar state, aspect ratios, loading)?
- Is the page visually scannable when there are many characters?

### 8. Error handling & edge cases
- What happens with very long names, descriptions, or system prompts?
- How are API errors (generation failures, import errors) communicated?
- What about duplicate character names?
- Is the soft-delete/undo pattern discoverable?

### 9. Accessibility & keyboard interaction
- Can all actions be performed via keyboard alone?
- Is focus management correct (modal open/close, inline edit, bulk select)?
- Are ARIA labels present on icon-only buttons?
- Does the page respect prefers-reduced-motion?
- Are color contrasts sufficient for all interactive elements?

### 10. Missing features a user would expect
Think about comparable tools (SillyTavern, Character.AI, Janitor.AI, OpenAI GPTs)
and identify features users would reasonably expect but that are missing, such as:
- Character versioning / revision history
- Character sharing / community gallery
- Character analytics (usage stats, popular greetings, avg conversation length)
- Character grouping / folders / collections
- Character cloning across accounts
- Lorebook / world-info integration on the character page
- Quick-test / preview chat without leaving the page
- Character comparison view

---

## Output format

Produce a structured report with:

1. **Executive summary** (3-5 sentences on overall UX quality)
2. **Findings table** (columns: ID, Dimension, Finding, Severity, Recommendation)
3. **Top 5 quick wins** (high-impact, low-effort improvements)
4. **Top 5 strategic improvements** (higher-effort but significant UX gains)
5. **Missing functionality matrix** (feature, user archetype who needs it, priority)
