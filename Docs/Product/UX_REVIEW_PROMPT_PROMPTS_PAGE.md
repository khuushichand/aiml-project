# UX/HCI Review Prompt for the `/prompts` Page

> **Usage**: Paste this entire file as a prompt to a UX/HCI reviewer (human or AI) to guide a comprehensive audit of the Prompts page. The prompt provides a detailed inventory of what exists today so the reviewer can focus on analysis rather than discovery.

**Scope**: `/prompts` page — four tabs (Custom, Copilot, Studio, Trash), CRUD operations, search/filtering, import/export, server sync, and a full Prompt Studio sub-app
**Date**: 2026-02-17
**Codebase version**: `dev` branch

---

## Review Prompt

You are an HCI/UX design expert and also a power user of prompt management tools
(e.g., PromptLayer, LangSmith Prompt Hub, Anthropic's prompt workbench, OpenAI Playground).
Review the `/prompts` page of our application from both perspectives.

### Page Overview (What Exists Today)

The page has four tabs:

1. **Custom** — User-created local prompts stored in IndexedDB. Features:
   - Table with columns: favorite star, name, type badge (System/Quick), keywords, sync status, actions menu
   - Create/Edit via a slide-in drawer (fields: name, author, system_prompt, user_prompt, keywords, details/notes)
   - Search bar (client-side, across name/content/author/keywords/details)
   - Filters: type (All/System/Quick), keyword multi-select
   - Sorting: favorites first, then by creation date descending
   - Bulk operations: select rows → bulk export or bulk delete
   - Import/Export: JSON file (merge or replace-with-backup modes)
   - "Use in Chat" action: sets system prompt and/or user message template, then navigates to chat
   - Duplicate, soft-delete to trash
   - Server sync: push/pull/link/unlink to Prompt Studio; auto-sync option; conflict detection & resolution
   - Draft auto-save (every 30s to localStorage, recovery banner on reopen)
   - Keyboard shortcuts: N (new), / (search), Esc (close drawer)

2. **Copilot** — Server-provided predefined prompts (read-only except one editable field)

3. **Studio** — Full Prompt Studio sub-app (server-backed, feature-gated) with sub-tabs:
   - Projects, Prompts (versioned, with few-shot examples & module config), Test Cases, Evaluations, Optimizations
   - Execute Playground, Version History, auto-generate test cases, 9 optimization strategies

4. **Trash** — Soft-deleted prompts with restore and permanent delete; 30-day auto-purge warning

### Backend Capabilities NOT Surfaced in the UI

- Prompt Collections API (create named groups of prompts) — no UI
- Prompt comparison / diff between versions — backend schema exists, no UI
- Prompt generation from description — backend endpoint, no UI
- Prompt improvement suggestions — backend endpoint, no UI
- Server-side full-text search (the Custom tab only uses client-side filtering)
- CSV/Markdown export formats (backend supports them; UI only offers JSON)
- Template variable extraction and rendering endpoints
- Studio project import/export

### Your Review Should Cover These Dimensions

#### 1. Information Architecture & Navigation

- Is the four-tab structure (Custom/Copilot/Studio/Trash) intuitive? Would a user understand the distinction between Custom and Studio prompts?
- Is the relationship between "Custom prompts" and "Studio prompts" clear, or is sync confusing?
- Should Trash be a top-level tab or accessible differently (e.g., filter toggle, secondary menu)?
- Is the Copilot tab's purpose and value clear to a first-time user?
- How discoverable are the Studio sub-tabs (Projects → Prompts → Test Cases → Evaluations → Optimizations)?

#### 2. Prompt Browsing & Discovery

- Is the table the right primary view? Should there be alternative views (card/grid, grouped by project/category)?
- Is the information density appropriate? What columns are missing that users would expect (e.g., last modified date, usage count, character count, version number)?
- How effective is the current search? Should it support advanced queries (field-specific, regex, date ranges)?
- Is the keyword/tag system sufficient, or should there be hierarchical categories, folders, or collections?
- Can users quickly find "the prompt I used yesterday" or "my best-performing prompt"?

#### 3. Prompt Creation & Editing

- Is the slide-in drawer the right pattern, or would a full-page editor be better for long prompts?
- Are the form fields sufficient? What's missing? Consider:
  - Description/purpose field (distinct from "details")
  - Model recommendations or constraints (e.g., "designed for GPT-4")
  - Temperature/parameter suggestions
  - Input/output format specification
  - Usage instructions or examples
  - Preview / dry-run capability
- Is the system_prompt vs user_prompt distinction clear to non-technical users?
- How is prompt quality feedback captured? (ratings, effectiveness tracking, A/B results)

#### 4. Prompt Organization & Management

- The backend supports Collections but there's no UI — should there be? How would users organize dozens or hundreds of prompts?
- Are keywords/tags powerful enough, or do users need folders, workspaces, or hierarchical organization?
- Is there a way to see prompt relationships (versions, forks, derivatives)?
- How do users manage prompt lifecycle (draft → testing → production → deprecated)?

#### 5. Collaboration & Sharing

- How would a team share prompts? The sync mechanism exists but is it intuitive?
- Is there a way to share a single prompt via link?
- Can users see who created or last modified a prompt?
- Is there a concept of prompt visibility (private/team/public)?

#### 6. Version Control & History

- Version history exists in Studio but not in the Custom tab — is this a gap?
- Can users compare versions side-by-side (diff view)?
- Is rollback/restore intuitive?
- Are change descriptions (commit messages for prompts) encouraged or required?

#### 7. Testing & Evaluation

- The Studio has test cases and evaluations, but they're deeply nested — should testing be more accessible?
- Can a user quickly test a prompt from the Custom tab without entering Studio?
- Is there a way to see prompt performance metrics (latency, token usage, quality scores)?
- How visible are optimization suggestions?

#### 8. Import/Export & Interoperability

- JSON-only export in the UI (backend supports CSV/Markdown) — is this sufficient?
- Can users import from other tools (LangChain Hub, PromptLayer, etc.)?
- Is the import/replace flow safe enough? (backup is auto-downloaded, but is this clear?)
- Should there be a clipboard "copy prompt" one-click action?

#### 9. Empty States, Onboarding & Learnability

- What does a new user see with zero prompts? Is there guidance on getting started?
- Are there example/template prompts to learn from?
- Is the Copilot tab a form of onboarding, and if so, is it effective?
- Are tooltips, help text, or documentation links present where needed?
- Is the sync concept explained anywhere?

#### 10. Accessibility & Responsiveness

- Are keyboard shortcuts discoverable (is there a shortcut legend)?
- How does the page work on mobile/tablet?
- Are screen reader announcements meaningful?
- Is color contrast sufficient for sync status badges and type badges?

#### 11. Missing Functionality (Competitive Analysis)

Compare against prompt management in tools like:
- LangSmith / LangChain Hub (prompt versioning, playground, dataset testing)
- PromptLayer (usage tracking, scoring, A/B testing, request logs)
- Anthropic Console (prompt workbench, variable slots, streaming preview)
- OpenAI Playground (model selection, parameter tuning, conversation mode)

What standard features are missing that users of these tools would expect?

### Deliverable Format

Structure your report as:

1. **Executive Summary** — Top 5 most impactful findings
2. **Strengths** — What the page does well (acknowledge good design)
3. **Critical Issues** — Problems that likely cause user frustration or task failure
4. **Improvement Opportunities** — Enhancements ranked by impact vs effort
5. **Missing Functionality** — Features users would expect but don't find, with priority ratings (Must-Have / Should-Have / Nice-to-Have)
6. **Information Gaps** — Data the system has (or could have) but doesn't expose to the user
7. **Recommendations** — Concrete, actionable improvements with rough scope estimates (S/M/L)

For each finding, include:
- **What**: Description of the issue or opportunity
- **Why it matters**: Impact on user experience (use specific HCI principles: recognition over recall, error prevention, flexibility, etc.)
- **Recommendation**: Specific solution proposal
- **Priority**: Critical / High / Medium / Low
