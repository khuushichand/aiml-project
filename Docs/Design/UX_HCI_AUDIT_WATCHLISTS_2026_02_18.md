# UX/HCI Audit: Watchlists Page

**Date**: 2026-02-18
**Scope**: `/watchlists` page — all 7 tabs, backend API coverage, competitive analysis
**Methodology**: Nielsen's 10 heuristics, Shneiderman's 8 golden rules, code-level component review

---

## 1. Executive Summary — Top 5 Highest-Impact Findings

| # | Finding | Severity | Heuristic |
|---|---------|----------|-----------|
| 1 | **No onboarding wizard or pipeline explanation** — A first-time user sees "Sources" tab with no guidance on the Sources → Jobs → Runs → Items → Outputs workflow. The 7-tab structure exposes implementation internals instead of user goals. | **Catastrophic** | H2: Match between system and real world |
| 2 | **No dashboard/overview tab** — There is no "at a glance" view showing aggregate health: total sources, active jobs, recent failures, unread items count, next scheduled run. Users must click through 5+ tabs to answer "is everything working?" | **Major** | H1: Visibility of system status |
| 3 | **Critical API data not surfaced in Sources tab** — The backend tracks `consec_not_modified` (consecutive failures), `defer_until` (backoff), `status` field, error counts, and dedup stats, but these are hidden behind a "Seen" drawer that most users won't discover. A source silently backing off after repeated failures is invisible. | **Major** | H1: Visibility of system status |
| 4 | **Job form is overwhelming** — The JobFormModal (847 lines) packs scope, schedule, filters, templates, email delivery, chatbook delivery, retention TTL, and guided presets into a single collapsible modal with raw cron expressions and TTL-in-seconds inputs. Non-technical users will struggle. | **Major** | H6: Recognition rather than recall |
| 5 | **Items tab lacks batch operations** — Users can only mark items as reviewed one at a time. With 100+ items from a run, there's no "mark all as reviewed", no batch select, no keyboard shortcuts (j/k navigation, space to toggle). | **Major** | H7: Flexibility and efficiency of use |

---

## 2. Heuristic Violations

### H1: Visibility of System Status

| ID | Violation | Severity | Location |
|----|-----------|----------|----------|
| H1.1 | No global health dashboard — users can't see at a glance whether the system is healthy | **Major** | Missing tab |
| H1.2 | Source error status hidden in "Seen" drawer — `consec_not_modified`, `defer_until`, and `status` fields exist in API but aren't visible in the sources table | **Major** | `SourcesTab.tsx:484-638` |
| H1.3 | Job `next_run_at` field exists in the type (`WatchlistJob.next_run_at`) but is not displayed anywhere in the Jobs table | **Minor** | `JobsTab.tsx:144-276` |
| H1.4 | Polling indicator ("Auto-refreshing") is subtle — just a small animated dot. No indication of _when_ data was last refreshed | **Minor** | `RunsTab.tsx:536-543` |
| H1.5 | Output delivery status (email sent, chatbook created) is shown as small Tags — easy to miss in a data-dense table | **Minor** | `OutputsTab.tsx:253-270` |
| H1.6 | No notification when a scheduled job completes or fails — user must manually check the Runs tab | **Major** | Missing feature |
| H1.7 | WebSocket stream endpoint exists (`/runs/{run_id}/stream`) but the UI doesn't use it — RunDetailDrawer fetches once, no live log tailing | **Minor** | `RunDetailDrawer.tsx:63-82` |

### H2: Match Between System and Real World

| ID | Violation | Severity | Location |
|----|-----------|----------|----------|
| H2.1 | Tab names use implementation vocabulary ("Sources", "Jobs", "Runs", "Items", "Outputs") instead of user-centric language. "Feeds", "Monitors", "Activity", "Articles", "Reports" would be clearer | **Major** | `WatchlistsPlaygroundPage.tsx:49-120` |
| H2.2 | "Scope" in job creation is jargon — users think "which feeds to include", not "scope" | **Minor** | `JobFormModal.tsx:488-496` |
| H2.3 | Cron expressions shown raw in tooltips (e.g., "Cron: 0 8 * * MON") — meaningless to non-technical users | **Minor** | `CronDisplay.tsx:118-124` |
| H2.4 | "MECE variants" and "MECE review" in output presets are HCI jargon — no explanation of what MECE means | **Minor** | `JobFormModal.tsx:553-555` |
| H2.5 | "Claim Clusters" in Settings tab is unexplained domain jargon | **Minor** | `SettingsTab.tsx:295-355` |
| H2.6 | TTL input is in raw seconds — 86400 is not meaningful; should be "1 day" or provide a duration picker | **Minor** | `JobFormModal.tsx:640-680` |

### H3: User Control and Freedom

| ID | Violation | Severity | Location |
|----|-----------|----------|----------|
| H3.1 | No undo for source/job deletion — Popconfirm is the only guard, no soft-delete or undo toast | **Major** | `SourcesTab.tsx:260-270` |
| H3.2 | No undo for bulk operations (bulk delete, bulk disable) | **Major** | `SourcesTab.tsx:304-332` |
| H3.3 | Bulk import has no dry-run preview — OPML is imported immediately | **Minor** | `SourcesBulkImport.tsx` |
| H3.4 | Cannot cancel a running job from the UI — no cancel/abort button on active runs | **Major** | `RunsTab.tsx` (missing) |
| H3.5 | Template deletion has no versioning safety net — deleting a template used by active jobs has no warning | **Minor** | `TemplatesTab.tsx:74-83` |

### H4: Consistency and Standards

| ID | Violation | Severity | Location |
|----|-----------|----------|----------|
| H4.1 | Sources tab has a left sidebar (GroupsTree) but no other tab has this pattern | **Cosmetic** | `SourcesTab.tsx:781-790` |
| H4.2 | Items tab has 3-pane layout unique to this page — inconsistent with the table-based pattern of all other tabs | **Cosmetic** | `ItemsTab.tsx:376-731` |
| H4.3 | Delete button placement varies — sometimes in action column, sometimes in bulk bar | **Cosmetic** | Various |
| H4.4 | Forum type is shown in source type dropdown but is `disabled: true` with no explanation | **Minor** | `SourceFormModal.tsx:168-170` |
| H4.5 | Run detail drawer uses hardcoded English labels ("Status", "Duration", "Items Found") instead of i18n keys | **Minor** | `RunDetailDrawer.tsx:265-289` |

### H5: Error Prevention

| ID | Violation | Severity | Location |
|----|-----------|----------|----------|
| H5.1 | No validation that a source URL is reachable before saving (though API has `/sources/{id}/test`) | **Minor** | `SourceFormModal.tsx` |
| H5.2 | No warning when deleting a source that is referenced by active jobs | **Major** | `SourcesTab.tsx:260-270` |
| H5.3 | No guard against scheduling jobs too frequently (e.g., `* * * * *` every minute) | **Minor** | `SchedulePicker.tsx` |
| H5.4 | No circular group hierarchy detection in the UI (groups can have parent_group_id) | **Minor** | `GroupsTree.tsx` |
| H5.5 | Email recipients field (`Select mode="tags"`) accepts any text without email format validation | **Minor** | `JobFormModal.tsx:694-700` |

### H6: Recognition Rather Than Recall

| ID | Violation | Severity | Location |
|----|-----------|----------|----------|
| H6.1 | Job scope shows "3 sources, 2 groups" but not _which_ sources — user must open the edit modal to see details | **Major** | `JobsTab.tsx:129-141` |
| H6.2 | Filter count column shows just a number (e.g., "3") — no indication of what the filters do | **Minor** | `JobsTab.tsx:178-190` |
| H6.3 | Run source column shows `#123` (numeric ID) instead of source name | **Minor** | `RunDetailDrawer.tsx:228-229` |
| H6.4 | No contextual help or tooltips explaining concepts like "OPML", "Jinja2", "cron", "TTL" | **Major** | Various |

### H7: Flexibility and Efficiency of Use

| ID | Violation | Severity | Location |
|----|-----------|----------|----------|
| H7.1 | No keyboard shortcuts for common actions (j/k item navigation, r to refresh, n to create) | **Minor** | Global |
| H7.2 | Items tab has no "mark all as reviewed" or batch review | **Major** | `ItemsTab.tsx` |
| H7.3 | No saved/pinned filters or search presets | **Minor** | All tabs |
| H7.4 | Can't drag-and-drop sources between groups | **Cosmetic** | `GroupsTree.tsx` |
| H7.5 | No "quick create" flow — adding a first source + creating a job + running it requires navigating 3+ tabs | **Major** | Cross-tab |

### H8: Aesthetic and Minimalist Design

| ID | Violation | Severity | Location |
|----|-----------|----------|----------|
| H8.1 | 7 tabs is too many — Settings tab content (2 read-only cards + cluster management) could be folded into a gear icon popover | **Minor** | `WatchlistsPlaygroundPage.tsx:49-120` |
| H8.2 | Runs tab toolbar has both a CSV export mode dropdown AND an export button — could combine into a split button | **Cosmetic** | `RunsTab.tsx:552-573` |
| H8.3 | Settings tab shows "Phase 3 Readiness" card — internal development status exposed to end users | **Minor** | `SettingsTab.tsx:265-292` |

### H9: Help Users Recognize, Diagnose, and Recover from Errors

| ID | Violation | Severity | Location |
|----|-----------|----------|----------|
| H9.1 | Error messages are generic ("Failed to load sources") — no guidance on what went wrong or how to fix it | **Minor** | All tabs |
| H9.2 | Run error_msg is shown but no suggested remediation ("This source returned 403 — check if the feed requires authentication") | **Minor** | `RunDetailDrawer.tsx:293-300` |
| H9.3 | OPML import errors show per-item status but no "retry failed" option | **Minor** | `SourcesBulkImport.tsx` |

### H10: Help and Documentation

| ID | Violation | Severity | Location |
|----|-----------|----------|----------|
| H10.1 | No inline help, tutorial, or guided tour for first-time users | **Major** | Global |
| H10.2 | No link to documentation from the page | **Minor** | `WatchlistsPlaygroundPage.tsx` |
| H10.3 | Beta notice is dismissible but provides no link to report issues or read docs | **Minor** | `WatchlistsPlaygroundPage.tsx:149-157` |

---

## 3. Per-Tab Findings

### 3A. Sources Tab

**Strengths**:
- Good empty state with dual CTA (Add Source + Import OPML)
- Bulk operations with confirmation dialogs
- Group sidebar for hierarchical navigation
- "Check Now" with inline feedback linking to Runs tab
- Tag filtering and search

**Issues**:
1. **Source health invisible** — `status`, `consec_not_modified`, `defer_until` are in the API/types but not shown. A failing source looks identical to a healthy one in the table.
2. **Group filtering uses OPML export as a proxy** (`SourcesTab.tsx:167-181`) — this is fragile and slow. The API supports `groups` query parameter but it's not used.
3. **Client-side filtering loads up to 1000 items** (`CLIENT_FILTER_MAX_ITEMS = 1000`) — doesn't scale to users with many sources.
4. **"Seen" button (Eye icon)** is cryptic — users won't understand "Dedup / Seen" without context.
5. **No source error indicator** (red dot, warning icon) in the table.
6. **No "Test Source" button** — the API has `/sources/{id}/test` but the UI doesn't expose it during creation.

### 3B. Jobs Tab

**Strengths**:
- Clean table layout with meaningful columns
- Schedule displayed in human-readable format
- "Run Now" button per job
- Preview modal for dry-run testing

**Issues**:
1. **No `next_run_at` column** — users can't see when the next execution will happen.
2. **Scope summary is too terse** — "3 sources, 1 tag" doesn't help identify which sources.
3. **No filter summary** — just a count. Hover or expand to see filter rules would help.
4. **No empty state** — an empty table with no description.
5. **"Run Now" disabled when job is inactive** but no tooltip explaining why.
6. **No duplicate/clone job action**.

### 3C. Runs Tab

**Strengths**:
- Auto-polling with visual indicator when runs are active
- Progress bar for running jobs
- Filter by job + status
- CSV export with multiple modes (standard, per-run tallies, aggregate)
- Run detail drawer with stats, logs, and items

**Issues**:
1. **No timeline/gantt visualization** — just a flat table. Can't see run overlap or patterns.
2. **No log streaming** — WebSocket endpoint exists (`/runs/{run_id}/stream`) but is unused.
3. **No "cancel run" action**.
4. **Duplicate "Found"/"Processed"/"Filtered"/"Errors" stats** — shown in both table and detail drawer without additional context.
5. **No "Why was this filtered?" explanation** — `filtered_sample` field exists in `RunDetailResponse` but is not rendered in the drawer.
6. **CSV export mode dropdown is confusing** — "Standard CSV" vs "Per-run tallies" vs "Global tallies summary" needs explanation.

### 3D. Items Tab

**Strengths**:
- Best-designed tab — the 3-pane reader layout is excellent
- Smart feed filters (Today, Unread, Reviewed, All) with live counts
- Source sidebar with search
- HTML content rendering with DOMPurify sanitization
- Image extraction from content
- Read/unread indicator dots
- "Open Original" button

**Issues**:
1. **No batch review operations** — can only toggle reviewed one item at a time.
2. **No keyboard navigation** — j/k to move between items, space to toggle read, o to open original.
3. **No "mark all as reviewed" or "mark page as reviewed"**.
4. **No content search** — search only queries titles, not body content.
5. **Fixed 20 items per page** (`showSizeChanger={false}`) — no way to change page size.
6. **Left pane loads all sources** (up to 1000) — could be slow with many sources.
7. **No item star/favorite/save-for-later**.
8. **"All Unread" label used for both the smart filter button AND the tag in the reader** — confusing.

### 3E. Outputs Tab

**Strengths**:
- Delivery status shown with color-coded tags
- Regenerate modal preserves original settings
- Download action for offline access
- Expiration tracking

**Issues**:
1. **No inline content preview** — must open a drawer to see output.
2. **No "create new output" from scratch** — can only regenerate from existing.
3. **No TTS/audio output management** — the API supports `generate_tts` and `generate_audio` but the UI has no audio player.
4. **Template version selection is unintuitive** — switches between a Select and InputNumber based on available versions.
5. **No delete output action**.
6. **No share/public-link action**.

### 3F. Templates Tab

**Strengths**:
- Clean CRUD interface
- Empty state with "Create your first template" CTA
- Versioning support

**Issues**:
1. **No template preview** — can't see rendered output without creating an actual output.
2. **No syntax highlighting** — unclear if TemplateEditor uses a code editor.
3. **No variable documentation** — Jinja2 templates need to know available variables (`items`, `job`, `run`, etc.) but there's no reference.
4. **No template duplication/fork**.
5. **No version history viewer** — `available_versions` field exists but no UI to browse previous versions.

### 3G. Settings Tab

**Strengths**:
- Shows server configuration in a clear card layout
- Cluster subscription toggle per job

**Issues**:
1. **Read-only settings** — TTL, forums_enabled, sharing_mode are display-only. Can't change anything.
2. **"Phase 3 Readiness" card** exposes internal development metadata to end users.
3. **Cluster management is deeply buried** — probably deserves its own UI location.
4. **No "apply" or "save" button** — unclear if settings changes are possible.
5. **"Claim Clusters" concept is unexplained** — no help text or documentation.

---

## 4. Missing Information Inventory

| API Field | Where Available | Shown in UI? | Impact |
|-----------|----------------|--------------|--------|
| `WatchlistSource.status` | GET `/sources` | No (type defined but not rendered) | Users can't see if a source is erroring |
| `WatchlistSource.settings` | GET `/sources` | No | Source-specific config not viewable |
| `SourceSeenStats.consec_not_modified` | GET `/sources/{id}/seen-stats` | Only in Seen drawer | Backoff status invisible in table |
| `SourceSeenStats.defer_until` | GET `/sources/{id}/seen-stats` | Only in Seen drawer | Backoff expiry invisible |
| `WatchlistJob.next_run_at` | GET `/jobs` | **No** | Users can't see next scheduled run |
| `WatchlistJob.wf_schedule_id` | GET `/jobs` | No | Schedule linkage not visible |
| `WatchlistJob.max_concurrency` | GET `/jobs` | No (only in edit modal) | Concurrency limits not visible |
| `WatchlistJob.per_host_delay_ms` | GET `/jobs` | No (only in edit modal) | Rate limiting config not visible |
| `WatchlistJob.retry_policy` | GET `/jobs` | No | Retry behavior invisible |
| `RunDetailResponse.filtered_sample` | GET `/runs/{id}/details` | **No** | Can't see why items were filtered |
| `ScrapedItem.media_id` / `media_uuid` | GET `/items` | No | No link to Media DB |
| `WatchlistOutput.storage_path` | GET `/outputs` | No | Storage location not shown |
| `WatchlistOutput.chatbook_path` | GET `/outputs` | No | Chatbook link not shown |
| `WatchlistOutput.media_item_id` | GET `/outputs` | No | No link back to ingested media |
| `WatchlistTemplate.history_count` | GET `/templates` | No | Version count not shown |
| `WatchlistTemplate.available_versions` | GET `/templates` | No (only in regenerate modal) | Can't browse version history |
| `WatchlistSettings.sources_count` etc. | (WatchlistSettingsStats type exists) | **No** | Aggregate counts not shown anywhere |
| WebSocket `/runs/{run_id}/stream` | Endpoint exists | **Not used** | No live log streaming |
| POST `/sources/{id}/test` | Endpoint exists | **Not used** | Can't test a source before committing |
| TTS/audio fields in output create | API supports `generate_tts`, `tts_model`, etc. | **Not exposed** | Audio briefing feature invisible |

---

## 5. Workflow Friction Map

### Workflow 1: Adding a First RSS Feed and Getting Results

| Step | Action | Clicks | Friction |
|------|--------|--------|----------|
| 1 | Land on `/watchlists` | 0 | See empty state with "Add Source" button — good |
| 2 | Click "Add Source" | 1 | Modal opens — clear and simple |
| 3 | Fill form (name, URL, type, tags) | 4 fields | **No URL validation or test** — user doesn't know if URL works |
| 4 | Click "Create" | 1 | Source created — success toast shown |
| 5 | Realize nothing happens automatically | - | **No guidance**: user must now create a Job |
| 6 | Navigate to Jobs tab | 1 | Tab click |
| 7 | Click "Add Job" | 1 | **847-line modal** opens with 4 collapsed sections |
| 8 | Fill name, expand Scope, select the source | 3+ | Scope selector requires finding the source just created |
| 9 | Expand Schedule, set a schedule | 2+ | **Raw cron input** — "0 8 * * *" is unintelligible |
| 10 | Click "Create" | 1 | Job created |
| 11 | Click "Run Now" on the job row | 1 | Run triggered — success toast |
| 12 | Navigate to Runs tab | 1 | Tab click |
| 13 | Wait for run to complete, click refresh or wait for polling | 1+ | No push notification |
| 14 | Navigate to Items tab | 1 | Tab click |
| 15 | Find and read results | 2+ | Select source, select item |

**Total: 15+ steps across 4 tabs. A "Quick Setup" wizard could reduce this to 3 steps.**

### Workflow 2: Setting Up a Daily News Briefing with Email Delivery

| Step | Action | Clicks | Friction |
|------|--------|--------|----------|
| 1-4 | Add sources | 4+ | Same as Workflow 1 |
| 5 | Create job with schedule | 5+ | Must navigate to Jobs tab |
| 6 | Expand "Output & Delivery" in job form | 1 | Collapsible section |
| 7 | Select preset or configure template | 2+ | **Preset system is two-step**: select preset, then click "Apply" |
| 8 | Enable email delivery, add recipients | 3+ | **No email validation** |
| 9 | Set schedule (e.g., daily 8am) | 2+ | Raw cron or SchedulePicker |
| 10 | Create job | 1 | Job created |
| 11 | Wait for first scheduled run | - | **No confirmation of when it will run** |

**Friction point: The "Output & Delivery" section has 5 subsections (presets, template, retention, email, chatbook) crammed into one collapsible panel. Should be a step-by-step wizard.**

### Workflow 3: Investigating Why Specific Items Were Filtered

| Step | Action | Clicks | Friction |
|------|--------|--------|----------|
| 1 | Navigate to Runs tab | 1 | |
| 2 | Find the relevant run | 1+ | May need to filter by job |
| 3 | Click eye icon to open detail drawer | 1 | |
| 4 | Look at stats — see "Items Filtered: 5" | 0 | Number is shown |
| 5 | **Dead end** — `filtered_sample` exists in API but is NOT rendered | - | **Cannot see which items were filtered or why** |
| 6 | Navigate to Items tab | 1 | |
| 7 | Filter by "Filtered" status | 1 | Segmented control |
| 8 | See filtered items, but no reason displayed | - | **No `matched_filter_key` or `matched_action` shown** |

**This workflow is essentially broken.** The data exists in the API (`filtered_sample`, `filter_tallies`) but the UI doesn't render it in a way that explains _why_ each item was filtered.

### Workflow 4: Reviewing and Triaging New Items

| Step | Action | Clicks | Friction |
|------|--------|--------|----------|
| 1 | Navigate to Items tab | 1 | |
| 2 | Click "All Unread" smart filter | 1 | Good — shows count |
| 3 | Click first item | 1 | Opens in reader pane |
| 4 | Read content | 0 | Good reading experience |
| 5 | Click "Mark as reviewed" | 1 | Toast shown |
| 6 | Click next item | 1 | |
| 7 | Repeat steps 4-6 for each item | N*2 clicks | **No keyboard shortcuts, no batch review** |

**For 50 items: 100+ clicks. With keyboard shortcuts (j/k/space): 50 keypresses. With "mark all": 1 click.**

### Workflow 5: Creating a Custom Output Template

| Step | Action | Clicks | Friction |
|------|--------|--------|----------|
| 1 | Navigate to Templates tab | 1 | |
| 2 | Click "Create Template" | 1 | |
| 3 | Fill name, description, content, format | 4+ | |
| 4 | Write Jinja2 template | Many | **No variable reference**, no syntax docs, unclear what variables are available |
| 5 | Save | 1 | |
| 6 | **No preview** — must create an actual output to test | 5+ | Navigate to Outputs, regenerate with new template, open preview |

**The template authoring experience lacks a preview/test mode.** Users write blind, save, then must go through the full output generation pipeline to see results.

---

## 6. Prioritized Recommendations

### Quick Wins (Low effort, High impact)

| # | Recommendation | Resolves |
|---|----------------|----------|
| QW1 | **Add `next_run_at` column to Jobs table** — data already in the type, just not rendered | H1.3 |
| QW2 | **Add source health indicator** — show a colored dot (green/yellow/red) based on `status` field in the sources table | H1.2 |
| QW3 | **Replace "Seen" eye icon with a health/status icon** and rename tooltip to "Source Health & Dedup Stats" | H6.4 |
| QW4 | **Show `filtered_sample` in RunDetailDrawer** — the data is already fetched, just not rendered | H6.2, Workflow 3 |
| QW5 | **Add "Mark page as reviewed" button** to Items tab | H7.2 |
| QW6 | **Change TTL input from seconds to duration picker** (or at least show "= X days" helper text) | H2.6 |
| QW7 | **Remove "Phase 3 Readiness" card** from user-facing Settings tab | H8.3 |
| QW8 | **Add "Test Source" button** to SourceFormModal — API exists, just wire it up | H5.1 |
| QW9 | **Use API `groups` query param** instead of OPML export hack for group filtering in SourcesTab | Performance |
| QW10 | **Fix hardcoded English in RunDetailDrawer** stats labels — use i18n keys | H4.5 |

### Medium-Term (Moderate effort, High impact)

| # | Recommendation | Resolves |
|---|----------------|----------|
| MT1 | **Add "Quick Setup" wizard** — on first visit with 0 sources, offer a guided flow: "Add Feed → Configure Schedule → Done" that creates both a source and a job in 3 steps | H10.1, Workflow 1 |
| MT2 | **Add Dashboard/Overview tab** (or make it the default) — show: total sources (healthy/erroring), active jobs with next run times, last 5 runs with status, unread items count, failed runs alert | H1.1, H1.6 |
| MT3 | **Split Job form into a step-by-step wizard** — Step 1: Name + Scope, Step 2: Schedule, Step 3: Filters, Step 4: Output & Delivery. Use Ant Design's Steps component | H6.1, Workflow 2 |
| MT4 | **Add keyboard navigation to Items tab** — j/k for next/previous item, space to toggle reviewed, o to open original, r to refresh | H7.1, Workflow 4 |
| MT5 | **Add batch item operations** — checkbox selection on items list, "Mark N as reviewed" action bar | H7.2 |
| MT6 | **Wire up WebSocket log streaming** in RunDetailDrawer — the endpoint exists, add a streaming log viewer | H1.7 |
| MT7 | **Add "Cancel Run" button** to active runs in the Runs table and detail drawer | H3.4 |
| MT8 | **Show scope preview** in Jobs table — expandable row or tooltip showing actual source/group/tag names, not just counts | H6.1 |
| MT9 | **Add deletion safety check** — when deleting a source, warn if it's referenced by active jobs and list them | H5.2 |
| MT10 | **Add template preview** — "Render Preview" button in TemplateEditor that applies the template to sample data | Workflow 5 |

### Strategic (High effort, Transformative impact)

| # | Recommendation | Resolves |
|---|----------------|----------|
| S1 | **Rethink tab structure** — Consider: "Dashboard" (overview), "Feeds" (sources + items merged), "Monitors" (jobs + runs merged), "Reports" (outputs + templates merged), "Settings". Reduce from 7 tabs to 5. | H2.1, H8.1 |
| S2 | **Add notification system** — in-app toast/badge when: job completes, job fails, new items arrive, source errors. Optional email/webhook notifications beyond the per-job email delivery. | H1.6 |
| S3 | **Add analytics dashboard** — source reliability scores (success rate over time), trending topics (word frequency in titles), read/unread tracking over time, items per day chart | Competitive gap |
| S4 | **Add undo system** — after delete operations, show a toast with "Undo" button that restores within 10 seconds (soft delete on backend) | H3.1, H3.2 |
| S5 | **Add collaborative features** — share watchlists between users, public/team feeds, shared annotations on items | Competitive gap |
| S6 | **Mobile-optimized reader** — the 3-pane Items layout should collapse to a slide-over navigation pattern on mobile, not just stack vertically | H4.2 |
| S7 | **Add TTS/audio briefing player** — the API supports `generate_tts` and `generate_audio` but the UI has no audio output management. Add an audio player for briefing playback. | Missing feature |

---

## 7. Competitive Gap Analysis

### Compared Tools: Miniflux, Feedly Pro, Huginn

| Feature | tldw Watchlists | Miniflux | Feedly Pro | Huginn |
|---------|-----------------|----------|------------|--------|
| **Feed reader (3-pane)** | Yes (Items tab) | Yes (native) | Yes (native) | No |
| **RSS auto-discovery** | No — user must provide feed URL | Yes | Yes | No |
| **OPML import/export** | Yes | Yes | Yes | No |
| **Scheduled scraping** | Yes (cron jobs) | Yes (per-feed interval) | Automatic | Yes (agents) |
| **Content filters** | Yes (keyword/author/date/regex) | No | Yes (AI-based) | Yes (custom code) |
| **Email digest** | Yes (per-job) | No | Yes | Yes |
| **Full-text search** | Partial (title search only) | Yes | Yes | No |
| **Keyboard shortcuts** | **No** | Yes (comprehensive) | Yes | No |
| **Mark all as read** | **No** | Yes | Yes | N/A |
| **Starred/saved items** | **No** | Yes | Yes (boards) | No |
| **Categories/folders** | Yes (groups) | Yes (categories) | Yes (folders) | No |
| **Source health monitoring** | Hidden in drawer | Shown per-feed | Shown per-feed | Manual |
| **Dashboard/overview** | **No** | Yes (unread counts) | Yes (Today view) | Yes (events log) |
| **Mobile responsiveness** | Partial | Yes | Yes (native app) | No |
| **Notification on new items** | **No** | No | Yes (push, email) | Yes (webhooks) |
| **Analytics/trends** | **No** | No | Yes (AI insights) | No |
| **API for integrations** | Yes (full REST) | Yes | Limited | Yes |
| **Template-based outputs** | **Yes (unique strength)** | No | No | Partial |
| **TTS audio briefings** | API only (not in UI) | No | No | No |
| **Chatbook export** | **Yes (unique strength)** | No | No | No |

### Key Gaps vs Competitors:
1. **Keyboard shortcuts** — Miniflux and Feedly both have comprehensive shortcut systems; Watchlists has none
2. **Feed auto-discovery** — paste a blog URL and auto-detect the RSS feed
3. **Mark all as read** — fundamental feature in every feed reader
4. **Starred/saved items** — ability to bookmark items for later
5. **Full-text content search** — search within article bodies, not just titles
6. **Dashboard view** — aggregate "what's new" overview

### Unique Strengths vs Competitors:
1. **Template-based output generation** — no competitor offers Jinja2 template-driven briefings
2. **Chatbook export** — unique integration with the chatbook system
3. **Audio briefing potential** — TTS API support (when UI is built)
4. **Advanced filter system** — include/exclude/flag with priority and regex support
5. **CSV export with tallies** — detailed analytics export

---

## 8. Accessibility Notes

| Issue | WCAG Level | Location |
|-------|------------|----------|
| Status badges use color alone (no icon/text for colorblind users) | AA | `StatusTag.tsx` |
| Source type badges (blue/green/purple) rely on color | AA | `SourcesTab.tsx:48-52` |
| Read/unread indicator is a small colored dot only | AA | `ItemsTab.tsx:553-557` |
| Smart feed sidebar buttons lack `aria-current` for active state | A | `ItemsTab.tsx:390-408` |
| Keyboard focus not trapped in modals/drawers | A | Various modals |
| Item reader pane uses `dangerouslySetInnerHTML` — external content may lack alt text | AA | `ItemsTab.tsx:701-704` |
| Tooltip-only actions (icon buttons without visible labels) | A | Action columns in all tables |
| No skip-to-content link for 3-pane layout | A | `ItemsTab.tsx:376` |

---

*End of audit. This document should be tracked alongside implementation plans and updated as recommendations are implemented.*
