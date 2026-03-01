# Watchlists UX Review - Dual Perspective Analysis

## Your Role

Conduct a thorough UX review of the Watchlists feature from two distinct perspectives, clearly separating your findings for each:

**Perspective A — Senior HCI/UX Designer (15 years designing complex information systems, medical device UIs, and safety-critical dashboards)**
Evaluate with the rigor you'd apply to a clinical monitoring dashboard: information hierarchy, cognitive load, error prevention, learnability, accessibility, and design system consistency. You understand that dense, multi-signal interfaces can be done well (Bloomberg Terminal, Grafana) or poorly — the question is whether complexity serves the user or overwhelms them.

**Perspective B — Target End User (a knowledge worker / analyst / researcher who tracks 10-50 information sources daily)**
This person is technically literate but not a developer. They want to set up their feeds, get their briefings, and move on. They should not need to understand cron syntax, Jinja2 templates, or XPath selectors to accomplish their core tasks. Evaluate how intuitive, discoverable, and frustration-free the experience is for this person from first launch through daily use.

---

## Product Context

### What This Is
A Watchlists module within a larger research assistant platform (tldw_server). Think of it as a power-user RSS/feed reader + automated content synthesis engine.

### Primary Use Cases (in priority order)

**UC1 — Feed Aggregation & Triage**
A user collects 10-50 information sources (news sites, RSS feeds, forums) into a single place. Sources are polled on a schedule. The user reviews collected items, marks them as read/reviewed, and filters noise. The core value: "I check one place instead of 50."

**UC2 — Automated Content Synthesis & Delivery**
After items are collected, the system uses LLM + templates to generate derivative content:
- A daily news briefing (text summary)
- A MECE analytical report on developments in area X from sources A, B, C
- An audio "newscast" — a spoken-word briefing file (multi-voice TTS) the user can listen to instead of reading

**Example scenario:** A user has 10 news sites polled twice daily. After each poll, collected stories + a prompt generate a briefing-style verbal presentation. The user receives: (1) a text briefing, and (2) an audio file in their chosen voice. They can read or listen.

**UC3 (Planned) — Push-based updates via WebSub**
Real-time feed updates without polling. Already partially implemented but not yet exposed in the UI.

### Current Architecture (8-tab interface)

| Tab | Purpose | Complexity |
|-----|---------|------------|
| **Overview** | Dashboard with health indicators, stats cards, quick-setup wizard | Low |
| **Feeds** | CRUD for sources (RSS, website, forum). Groups, tags, OPML import/export, bulk ops, health stats | High |
| **Monitors** | Job definitions: scope (which feeds), schedule (cron), filters (keyword/regex/date/author), output prefs (template, email, chatbook, audio), retention | Very High |
| **Activity** | Run history with status, logs, streaming, cancel, CSV export | Medium |
| **Articles** | Feed reader view — per-source item list, status filters, batch review, keyboard shortcuts | Medium |
| **Reports** | Generated outputs — preview, download, regenerate with different template/settings | Medium |
| **Templates** | Jinja2 template editor with live preview, variable palette, snippet insertion | High |
| **Settings** | Workspace config — TTLs, forum toggle, backend selection, claim cluster subscriptions | Low |

---

## What to Read

Start by reading these files to understand the full UX surface:

### Frontend (UI components & flow)
1. `apps/packages/ui/src/components/Option/Watchlists/WatchlistsPlaygroundPage.tsx` — Main container, tab structure
2. `apps/packages/ui/src/components/Option/Watchlists/OverviewTab/OverviewTab.tsx` — Dashboard & quick-setup wizard
3. `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/SourcesTab.tsx` — Feed management list
4. `apps/packages/ui/src/components/Option/Watchlists/SourcesTab/SourceFormModal.tsx` — Feed create/edit form
5. `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobsTab.tsx` — Monitor list
6. `apps/packages/ui/src/components/Option/Watchlists/JobsTab/JobFormModal.tsx` — Monitor creation form (most complex UI element)
7. `apps/packages/ui/src/components/Option/Watchlists/RunsTab/RunsTab.tsx` — Activity/run history
8. `apps/packages/ui/src/components/Option/Watchlists/ItemsTab/ItemsTab.tsx` — Article reader
9. `apps/packages/ui/src/components/Option/Watchlists/OutputsTab/OutputsTab.tsx` — Reports list
10. `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplatesTab.tsx` — Template management
11. `apps/packages/ui/src/components/Option/Watchlists/TemplatesTab/TemplateEditor.tsx` — Template code editor
12. `apps/packages/ui/src/components/Option/Watchlists/SettingsTab/SettingsTab.tsx` — Configuration

### State & API
13. `apps/packages/ui/src/store/watchlists.tsx` — Zustand store (all client state)
14. `apps/packages/ui/src/services/watchlists.ts` — API service layer (50+ endpoints)
15. `apps/packages/ui/src/assets/locale/en/watchlists.json` — All UI copy/labels

### Backend (for understanding data model & capabilities)
16. `tldw_Server_API/app/api/v1/schemas/watchlists_schemas.py` — Pydantic schemas (reveals what the UI must handle)
17. `tldw_Server_API/app/core/Watchlists/audio_briefing_workflow.py` — Audio generation pipeline

---

## Review Dimensions

For each dimension below, provide findings from BOTH perspectives (Designer + User). Use severity ratings: **Critical** (blocks core use cases), **Major** (significant friction), **Minor** (polish), **Observation** (not a problem, but worth noting).

### 1. Information Architecture & Navigation
- Does the 8-tab structure map to the user's mental model, or to the system's data model?
- Can a user who just wants UC1 (feed reader) ignore the tabs they don't need, or does the UI force them through complexity?
- Is the progression Overview → Feeds → Monitors → Activity → Articles → Reports → Templates → Settings a natural workflow, or are there missing/misplaced steps?
- Would a user looking for "my generated briefings" intuitively go to "Reports" or "Outputs"?
- Is the vocabulary consistent? (Sources vs Feeds, Monitors vs Jobs, Activity vs Runs, Reports vs Outputs — the UI uses different terms in different places)

### 2. First-Run Experience & Learnability
- Evaluate the Quick Setup Wizard (3-step: Add Feed → Create Monitor → Review Results). Does it adequately bootstrap a new user?
- How many concepts must a user understand before they can accomplish UC1? UC2?
- Is there progressive disclosure, or is the full complexity visible from the start?
- What happens when a user encounters cron expressions, Jinja2 syntax, XPath selectors, or regex filters for the first time? Is there adequate scaffolding?
- Evaluate the guided tour system (5-step tour). Does it cover the right things?

### 3. Core Workflow: Feed Setup → Briefing Delivery (UC2 end-to-end)
Walk through the complete flow for: "I want 10 news sites scraped twice daily, generating a text + audio briefing each time."
- How many screens/modals/forms does this require?
- Where are the decision points that might confuse a non-technical user?
- Is the relationship between Sources, Monitors, Templates, and Outputs clear?
- Can the user preview what they'll get before committing to a configuration?
- How does the user discover that audio briefings are possible?

### 4. Information Density & Cognitive Load
- Are the list views (Sources, Monitors, Runs, Items, Outputs) appropriately dense, or do they show too much/too little by default?
- Evaluate the Monitor creation form (JobFormModal) — it has 10+ configuration sections including scope, schedule, filters, output template, retention, email delivery, chatbook delivery, and audio settings. Is this manageable?
- Do the dashboard stats cards (Overview tab) surface the right metrics?
- Is the use of advanced/collapsible sections effective for managing complexity?

### 5. Error Prevention, Recovery & Feedback
- Evaluate the delete-with-undo pattern (configurable undo window). Is this discoverable?
- How does the system handle: a feed URL that doesn't work? A template with syntax errors? A failed run?
- Are error messages actionable (do they tell the user what to do, not just what went wrong)?
- Evaluate the "test feed" and "preview monitor" features — do they adequately prevent configuration mistakes?
- What happens when a scheduled run fails silently? How does the user find out?

### 6. Content Consumption (Articles Tab / Feed Reader)
- Compare the Articles tab to established feed readers (Feedly, Inoreader, NetNewsWire). What's missing? What's better?
- Is the read/reviewed/filtered status model intuitive?
- Evaluate keyboard shortcuts — are they discoverable? Do they match conventions?
- How well does batch review work at scale (100+ items)?
- Is the article preview sufficient, or does the user need to click through to get value?

### 7. Output Generation & Audio Briefing UX
- How discoverable is the audio briefing feature? Can a user find it without being told it exists?
- Evaluate the output regeneration flow — selecting a different template/version for existing items.
- Is the relationship between Runs → Outputs → Downloads clear?
- For audio: voice selection, speed, background audio, target duration — are these settings approachable?
- How does the user preview/test an audio configuration before committing to a full generation?

### 8. Template System Usability
- Jinja2 templates require developer knowledge. Is this the right abstraction for the target user?
- Evaluate the template editor: code editor + live preview + variable palette + snippet insertion. Is this sufficient scaffolding?
- Are the preset templates (briefing_md, newsletter_html, mece_md) useful starting points?
- Would a WYSIWYG or block-based editor be more appropriate for non-technical users?

### 9. Accessibility & Inclusivity
- Keyboard navigation completeness across all tabs
- Screen reader compatibility (ARIA labels, roles, live regions for status updates)
- Color contrast and color-as-sole-indicator issues (status tags, health indicators)
- Touch/mobile considerations (responsive layout behavior)
- Cognitive accessibility (plain language, consistent patterns, predictable interactions)

### 10. Scalability of the UX
- How does the UI behave with 5 feeds vs 50 feeds vs 200 feeds?
- What about 10 monitors vs 50 monitors?
- Does the Articles tab handle thousands of items gracefully?
- Are there performance or usability cliffs as data volume grows?

---

## Output Format

Structure your response as:

### Executive Summary
2-3 paragraphs: Overall UX health, biggest strengths, biggest risks.

### Top 10 Findings (ranked by impact)
For each: Severity | Perspective(s) | Dimension | Finding | Recommendation

### Detailed Analysis by Dimension
For each of the 10 dimensions above, provide:
- **Designer Perspective**: Technical UX analysis with specific references to components/code
- **User Perspective**: Narrative walkthrough of the experience, pain points, moments of delight
- **Recommendations**: Concrete, prioritized improvements (not vague "make it better" — specify what to change and why)

### Quick Wins (< 1 day effort each)
5-10 small changes that would noticeably improve the experience.

### Strategic Recommendations
2-3 larger UX initiatives that would transform the experience for UC1 and UC2.

### Competitive Comparison
Brief comparison to: Feedly, Inoreader, Mailbrew/Refind (for feed aggregation); Notebook LM (for audio synthesis); Morning Brew/The Skimm (for curated briefings). Where does this product sit, and what can it learn from each?
