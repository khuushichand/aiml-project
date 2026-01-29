# Watchlists Playground Implementation Plan

## Overview
Create a full-featured tabbed playground page for the watchlists module, exposing all tldw_server2 watchlists functionality for both developer testing and end-user production use.

## Target Structure

```
Tabs: Sources | Jobs | Runs | Outputs | Templates | Settings
```

## File Structure

### New Files to Create
```
src/routes/option-watchlists.tsx                    # Route entry point
src/types/watchlists.ts                             # TypeScript types
src/services/watchlists.ts                          # API service layer
src/store/watchlists.tsx                            # Zustand store
src/assets/locale/en/watchlists.json                # i18n translations

src/components/Option/Watchlists/
├── WatchlistsPlaygroundPage.tsx                    # Main container
├── WatchlistsTabs.tsx                              # Tab navigation
├── SourcesTab/
│   ├── SourcesTab.tsx                              # Sources list view
│   ├── SourcesTable.tsx                            # Ant Design Table
│   ├── SourceFormModal.tsx                         # Create/Edit modal
│   ├── SourcesBulkImport.tsx                       # OPML import UI
│   └── GroupsTree.tsx                              # Hierarchical groups sidebar
├── JobsTab/
│   ├── JobsTab.tsx                                 # Jobs list view
│   ├── JobsTable.tsx                               # Jobs table
│   ├── JobFormModal.tsx                            # Create/Edit with nested components
│   ├── FilterBuilder.tsx                           # Visual filter builder
│   ├── ScopeSelector.tsx                           # Sources/Groups/Tags picker
│   └── SchedulePicker.tsx                          # Cron UI with presets
├── RunsTab/
│   ├── RunsTab.tsx                                 # Execution history view
│   ├── RunsTable.tsx                               # Runs list with status
│   └── RunDetailDrawer.tsx                         # Log viewer, stats panel
├── OutputsTab/
│   ├── OutputsTab.tsx                              # Generated briefings
│   ├── OutputsTable.tsx                            # Outputs list
│   └── OutputPreviewDrawer.tsx                     # Preview rendered output
├── TemplatesTab/
│   ├── TemplatesTab.tsx                            # Template management
│   ├── TemplatesTable.tsx                          # Templates list
│   └── TemplateEditor.tsx                          # Jinja2 editor with preview
├── SettingsTab/
│   └── SettingsTab.tsx                             # TTL config, claim clusters
└── shared/
    ├── TagsInput.tsx                               # Reusable tags input
    ├── SourceTypeIcon.tsx                          # RSS/Site/Forum icons
    ├── CronDisplay.tsx                             # Human-readable cron
    └── StatusTag.tsx                               # Job/Run status badges
```

### Files to Modify
- `src/routes/route-registry.tsx` - Add watchlists route

## API Service Layer (`src/services/watchlists.ts`)

### Sources API
- `fetchWatchlistSources(params)` → GET /api/v1/watchlists/sources
- `createWatchlistSource(source)` → POST /api/v1/watchlists/sources
- `updateWatchlistSource(id, updates)` → PATCH /api/v1/watchlists/sources/{id}
- `deleteWatchlistSource(id)` → DELETE /api/v1/watchlists/sources/{id}
- `bulkCreateSources(sources)` → POST /api/v1/watchlists/sources/bulk
- `importOpml(file)` → POST /api/v1/watchlists/sources/import
- `exportOpml()` → GET /api/v1/watchlists/sources/export

### Groups/Tags API
- `fetchWatchlistGroups()` → GET /api/v1/watchlists/groups
- `createWatchlistGroup(group)` → POST /api/v1/watchlists/groups
- `fetchWatchlistTags()` → GET /api/v1/watchlists/tags

### Jobs API
- `fetchWatchlistJobs(params)` → GET /api/v1/watchlists/jobs
- `createWatchlistJob(job)` → POST /api/v1/watchlists/jobs
- `updateWatchlistJob(id, updates)` → PATCH /api/v1/watchlists/jobs/{id}
- `deleteWatchlistJob(id)` → DELETE /api/v1/watchlists/jobs/{id}
- `previewJob(id)` → GET /api/v1/watchlists/jobs/{id}/preview

### Runs API
- `fetchWatchlistRuns(params)` → GET /api/v1/watchlists/runs
- `triggerWatchlistRun(jobId)` → POST /api/v1/watchlists/jobs/{id}/run
- `getRunDetails(runId)` → GET /api/v1/watchlists/runs/{id}/details
- `cancelRun(runId)` → POST /api/v1/watchlists/runs/{id}/cancel

### Outputs API
- `fetchWatchlistOutputs(params)` → GET /api/v1/watchlists/outputs
- `downloadOutput(outputId)` → GET /api/v1/watchlists/outputs/{id}/download
- `createOutput(runId, templateId)` → POST /api/v1/watchlists/outputs

### Templates API
- `fetchWatchlistTemplates()` → GET /api/v1/watchlists/templates
- `createWatchlistTemplate(template)` → POST /api/v1/watchlists/templates
- `deleteWatchlistTemplate(name)` → DELETE /api/v1/watchlists/templates/{name}

### Items API
- `fetchScrapedItems(params)` → GET /api/v1/watchlists/items
- `markItemReviewed(itemId, reviewed)` → PATCH /api/v1/watchlists/items/{id}

### Settings API
- `getWatchlistSettings()` → GET /api/v1/watchlists/settings

## Zustand Store Slices

```typescript
// Key state structure
interface WatchlistsState {
  // Tab state
  activeTab: 'sources' | 'jobs' | 'runs' | 'outputs' | 'templates' | 'settings'

  // Sources slice
  sources: WatchlistSource[]
  sourcesLoading: boolean
  groups: WatchlistGroup[]
  selectedGroupId: string | null

  // Jobs slice
  jobs: WatchlistJob[]
  jobsLoading: boolean
  selectedJobId: string | null

  // Runs slice
  runs: WatchlistRun[]
  runsLoading: boolean
  pollingActive: boolean

  // Outputs slice
  outputs: WatchlistOutput[]
  outputsLoading: boolean

  // Templates slice
  templates: WatchlistTemplate[]
  templatesLoading: boolean

  // Settings slice
  settings: WatchlistSettings | null
}
```

## Key UI Features by Tab

### Sources Tab
- Table with columns: Name, URL, Type, Tags, Enabled, Actions
- Left sidebar: GroupsTree for hierarchical filtering
- OPML import via drag-drop zone
- OPML export button
- Bulk operations (select all, delete, enable/disable)

### Jobs Tab
- Table with columns: Name, Schedule, Scope, Filters, Status, Last Run, Actions
- JobFormModal with:
  - ScopeSelector: Multi-select for sources/groups/tags
  - FilterBuilder: Add/remove filters (keyword, author, date_range, regex)
  - SchedulePicker: Preset buttons (hourly, daily, weekly) + custom cron
- Manual run trigger button per job

### Runs Tab
- Table with columns: Job, Status, Started, Duration, Items Found/Processed, Actions
- Filter by job, status
- RunDetailDrawer showing:
  - Progress bar (if running)
  - Stats summary
  - Scrollable log viewer
  - List of scraped items with reviewed toggle

### Outputs Tab
- Table with columns: Title, Job, Run, Format, Created, Actions
- OutputPreviewDrawer with rendered content
- Download button (markdown/HTML)
- Regenerate with different template

### Templates Tab
- Table with columns: Name, Description, Updated, Actions
- TemplateEditor with:
  - Code editor (syntax highlighting for Jinja2)
  - Live preview panel
  - Variable documentation

### Settings Tab
- TTL configuration (items, runs, outputs)
- Claim clusters subscription management

## Implementation Phases

### Phase 1: Foundation
1. Create route and register in route-registry
2. Create types file with all interfaces
3. Create service layer (Sources API only)
4. Create Zustand store skeleton
5. Create WatchlistsPlaygroundPage with tabs
6. Implement SourcesTab with basic CRUD

### Phase 2: Sources Complete
1. Add GroupsTree sidebar
2. Implement OPML import/export
3. Add bulk operations
4. Add tags filtering

### Phase 3: Jobs Tab
1. Add Jobs API to service layer
2. Implement JobsTable and JobFormModal
3. Build FilterBuilder component
4. Build ScopeSelector component
5. Build SchedulePicker with presets

### Phase 4: Runs Tab
1. Add Runs API to service layer
2. Implement RunsTable with status badges
3. Implement RunDetailDrawer with log viewer
4. Add polling for active runs
5. Add manual trigger and cancel actions

### Phase 5: Outputs Tab
1. Add Outputs API to service layer
2. Implement OutputsTable
3. Implement OutputPreviewDrawer
4. Add download functionality

### Phase 6: Templates Tab
1. Add Templates API to service layer
2. Implement TemplatesTable
3. Implement TemplateEditor with preview

### Phase 7: Settings & Polish
1. Implement SettingsTab
2. Add claim clusters integration
3. Complete i18n translations
4. Add loading skeletons and empty states
5. Error handling throughout

## Reference Files
- `src/components/Option/Chatbooks/ChatbooksPlaygroundPage.tsx` - Main playground pattern
- `src/components/Knowledge/KnowledgePanel.tsx` - Tab architecture
- `src/store/option.tsx` - Zustand store pattern
- `src/services/background-proxy.ts` - API service pattern
- `src/routes/route-registry.tsx` - Route registration

## Verification Steps

1. **Build check**: `bun run compile` - verify no TypeScript errors
2. **Dev server**: `bun dev` - load extension in Chrome
3. **Navigate**: Go to Options page → Watchlists tab
4. **Test Sources CRUD**:
   - Create a new RSS source
   - Edit the source
   - Toggle enable/disable
   - Delete the source
5. **Test Jobs**:
   - Create a job with filters and schedule
   - Trigger manual run
   - View run details and logs
6. **Test Outputs**:
   - View generated output
   - Download as markdown
   - Preview with different template
7. **E2E tests**: Add test file `tests/e2e/watchlists.spec.ts`
