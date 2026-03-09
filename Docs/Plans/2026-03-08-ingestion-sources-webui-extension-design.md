# Ingestion Sources WebUI and Extension Design

## Date
2026-03-08

## Owner
Shared full-page WebUI and extension surface for ingestion-source management

## Goal
Design a shared full-page UI for ingestion sources that works in both the WebUI and the browser extension options app, with a user-facing route and an admin-mounted mirror for future expansion.

## Scope

In scope:
- Shared full-page routes for ingestion-source management in WebUI and extension options
- User-facing routes:
  - `/sources`
  - `/sources/new`
  - `/sources/:sourceId`
- Admin-mounted mirror route:
  - `/admin/sources`
- Full management surface for the current backend-supported source operations:
  - create source
  - update mutable fields
  - run manual sync
  - upload archive refreshes
  - inspect items
  - reattach detached notes items
- Archive upload and manual sync actions from the UI
- Source item inspection and notes-item reattach actions
- Shared data hooks and components in `apps/packages/ui`
- Web and extension route wiring
- Frontend tests for shared components and route coverage

Out of scope for v1:
- Sidebar-only or popup-only ingestion-source flows
- Cross-user admin management
- Dedicated admin-only backend APIs
- Source deletion/removal until the backend exposes a delete endpoint and lifecycle policy
- Advanced per-run job inspection beyond the existing source/item status data
- A separate extension-specific UI implementation

## Problem Statement

The backend now exposes a usable ingestion-source API for local directories and archive snapshots, but there is no product surface for people to actually manage those sources. The repo already supports a shared options-style full-page UI across WebUI and extension, but ingestion sources are not yet represented there.

The requested product shape is:

- available in both WebUI and extension
- full page, not sidebar
- regular user route plus admin-mounted route
- same workspace in both places, with admin route mainly reserved for future expansion
- hybrid navigation model:
  - a list workspace for discovery and quick actions
  - dedicated create/detail routes for deeper editing and inspection

## Current Verified Constraints

### Shared WebUI and extension pages already exist

The repo uses shared route and page components from `apps/packages/ui` for full-page options surfaces, which are then mounted in:

- WebUI pages under `apps/tldw-frontend/pages`
- extension options app under `apps/extension/entrypoints/options/main.tsx`

Relevant files:

- `apps/packages/ui/src/routes/route-registry.tsx`
- `apps/packages/ui/src/entries/options/main.tsx`
- `apps/extension/entrypoints/options/main.tsx`

This means ingestion sources should be built once in shared UI code and mounted into both app shells.

### There is already a placeholder route family for connectors

The WebUI currently has placeholder pages for:

- `/connectors`
- `/connectors/sources`
- `/connectors/jobs`

These are placeholders, not mature product surfaces:

- `apps/tldw-frontend/pages/connectors/index.tsx`
- `apps/tldw-frontend/pages/connectors/sources.tsx`

That gives freedom to introduce a better-named route family instead of forcing ingestion sources into the remote-connector concept.

### Admin pages already use shared route wrappers

Admin pages in the shared UI are mounted by route wrappers such as:

- `apps/packages/ui/src/routes/option-admin-server.tsx`

This confirms the right admin pattern for v1 is a shared page with different route mounting, not a second copy of the UI.

### Backend scope is still per-user

The ingestion-source backend currently exposes per-user source management:

- `POST /api/v1/ingestion-sources`
- `GET /api/v1/ingestion-sources`
- `GET /api/v1/ingestion-sources/{source_id}`
- `PATCH /api/v1/ingestion-sources/{source_id}`
- `POST /api/v1/ingestion-sources/{source_id}/sync`
- `POST /api/v1/ingestion-sources/{source_id}/archive`
- `GET /api/v1/ingestion-sources/{source_id}/items`
- `POST /api/v1/ingestion-sources/{source_id}/items/{item_id}/reattach`

There is no admin cross-user source API yet, so the admin route in v1 must still operate on the signed-in user’s sources.

There is also no delete endpoint in the current ingestion-source backend surface, so the first UI slice cannot promise delete/remove operations yet.

### Shared capability detection does not cover ingestion sources yet

The shared UI already uses a capability model for feature availability, but ingestion sources are not represented there today.

Relevant files:

- `apps/packages/ui/src/services/tldw/server-capabilities.ts`
- `apps/packages/ui/src/hooks/useServerCapabilities.ts`

That means the ingestion-sources route should add a capability flag such as `hasIngestionSources` before shipping, so older servers render a clear “feature unavailable” state instead of a raw failing page.

## Evaluated Approaches

### Approach 1: Dedicated `Sources` workspace

Add a new top-level route family for ingestion sources:

- `/sources`
- `/sources/new`
- `/sources/:sourceId`
- `/admin/sources`

Pros:
- best semantic fit
- keeps local/archive sync separate from OAuth/cloud connectors
- matches the requested “top-level content/storage” placement
- clear future room for source-specific status and maintenance UI

Cons:
- introduces a new top-level IA area

### Approach 2: Reuse `connectors`

Replace the connector placeholder routes with the ingestion-source workspace.

Pros:
- lower route-count churn
- existing placeholder pages already exist

Cons:
- local/archive ingestion sources are not the same concept as provider connectors
- likely to create long-term IA confusion

### Approach 3: Fold sources into an existing content workspace

Add ingestion sources as a tab under Collections, Items, or Settings.

Pros:
- fewer top-level destinations

Cons:
- poor conceptual fit
- sources are operational sync objects, not just another content tab
- harder to scale into richer diagnostics later

## Selected Approach

Use a dedicated `Sources` workspace with shared full-page UI and an admin-mounted mirror.

Routes:
- user:
  - `/sources`
  - `/sources/new`
  - `/sources/:sourceId`
- admin:
  - `/admin/sources`

Optional later:
- `/admin/sources/:sourceId`

This gives the best product semantics, fits the repo’s shared route architecture, and avoids overloading the connectors concept with a different class of sync source.

## Information Architecture

### User route model

`/sources`
- discovery and operations workspace
- list of the signed-in user’s ingestion sources
- quick actions such as sync, enable/disable, and open detail

`/sources/new`
- full-page creation flow
- local directory and archive source modes

`/sources/:sourceId`
- full-page detail/edit/inspect route
- source metadata
- mutable settings
- item table
- run summary
- action surface for sync, archive upload, and item reattach

### Admin route model

`/admin/sources`
- same core workspace
- mounted with admin page chrome and route identity
- same per-user behavior in v1
- `New source` and `Open detail` route into `/sources/new` and `/sources/:sourceId` until dedicated admin subroutes exist
- reserved for future admin-only expansion once cross-user APIs exist

## UX Behavior

### `/sources`

This should behave like an operations workspace, not a settings page.

Show:
- source label or path summary
- source type
- sink type
- lifecycle policy
- enabled state
- last sync status
- last successful sync counters:
  - degraded items
  - sink failures
  - ingestion failures
  - detached conflicts

Quick actions:
- sync now
- open detail
- enable/disable
- create new source

### `/sources/new`

Full-page source creation flow with source-type-aware fields.

`local_directory` mode:
- server directory path
- sink type
- policy
- schedule controls
- advanced/self-hosted warning explaining that this path is on the tldw server host, not the browser or extension device

`archive_snapshot` mode:
- sink type
- policy
- create logical source first
- upload first archive after creation

Validation requirements:
- render backend `400` path/archive validation errors inline
- render immutable/unsupported field errors as user-facing form messages

### `/sources/:sourceId`

Top section:
- source identity
- enabled/disabled state
- source type and sink
- last sync status and timestamps
- manual sync button
- archive upload action for `archive_snapshot`

Middle section:
- last successful sync summary panel
- last error or degraded-state banner
- clear distinction between:
  - total source failure
  - degraded success
  - notes conflict/detached state

Lower section:
- tracked source items table
- filters for degraded and detached states
- reattach action for `conflict_detached` notes items
- editable form for mutable fields only

### Extension

This must live in the full options-page experience, not in the sidepanel. The layout should remain the same shared page structure as the WebUI, while collapsing appropriately for narrower widths.

## Component Architecture

Create a shared ingestion-sources module under `apps/packages/ui`.

Recommended structure:

- `components/Option/Sources/SourcesWorkspacePage.tsx`
- `components/Option/Sources/SourceDetailPage.tsx`
- `components/Option/Sources/SourceForm.tsx`
- `components/Option/Sources/SourceListTable.tsx`
- `components/Option/Sources/SourceItemsTable.tsx`
- `components/Option/Sources/SourceStatusPanels.tsx`
- `components/Option/Sources/index.ts`

Route wrappers in shared UI:

- `routes/option-sources.tsx`
- `routes/option-sources-new.tsx`
- `routes/option-sources-detail.tsx`
- `routes/option-admin-sources.tsx`

Web page mounts:

- `apps/tldw-frontend/pages/sources.tsx`
- `apps/tldw-frontend/pages/sources/new.tsx`
- `apps/tldw-frontend/pages/sources/[sourceId].tsx`
- `apps/tldw-frontend/pages/admin/sources.tsx`

### Admin-mode handling

Use one shared component tree with an `adminMode` or equivalent route-context prop. In v1 this mainly affects page title, breadcrumbs, and future expansion hooks, not the data scope.

## Data Flow

Use shared React Query hooks for server state and keep local UI state separate.

### Shared client operations

Required queries:
- list sources
- get source detail
- list source items
- get server capabilities for route availability and unsupported-state handling

Required mutations:
- create source
- patch source
- sync source
- upload archive
- reattach item

### State split

Server state:
- React Query cached API data

Local UI state:
- filters and search
- create/edit draft values
- upload state
- dialogs and confirmations

This avoids forking extension-specific state unnecessarily.

## Error Handling

### Source-level errors

Show clear distinction between:
- sync failed
- sync succeeded with degraded items
- sync requires user attention because notes items detached

### Form-level errors

Map backend responses into actionable copy:
- `409` immutable field edits:
  - “This field can’t be changed after the first successful sync.”
- `400` path validation:
  - inline under local-directory path input
- `400` archive validation:
  - inline in archive upload section

### Connection state

Reuse the repo’s existing server offline/unreachable patterns. The sources workspace should degrade like other full-page options surfaces instead of inventing its own connection model.

### Feature availability state

If the connected server does not advertise ingestion-source support, the page should render the project’s normal “feature unavailable” treatment rather than attempting live source calls and surfacing raw API errors.

## Testing Strategy

### Shared component tests

- sources list rendering
- create form mode switching between local directory and archive
- detail page status-summary rendering
- degraded/conflict state badges and banners
- reattach action visibility and success invalidation behavior

### Route tests

- shared route-registry entries for user and admin routes
- WebUI page mounts render the shared route
- extension options route navigation reaches the new workspace

### E2E / smoke coverage

- WebUI route smoke for `/sources`
- extension options route smoke for `/sources`
- basic create/list/detail navigation flow with mocked API responses

### Recommended first test

Start with a shared list-page test rendering mocked sources and `last_successful_sync_summary` badges. That validates the most visible backend/frontend contract first.

## Implementation Order

1. Shared ingestion-sources API client and query hooks
2. `/sources` list workspace
3. `/sources/new` creation flow
4. `/sources/:sourceId` detail/edit route
5. `/admin/sources` mirror route
6. WebUI/extension route wiring and tests

## Known Follow-On Work

- Cross-user admin source management once backend APIs exist
- Dedicated sync-job history views
- Richer archive/source diagnostics panels for admin routes
- Navigation polish and discoverability work once the first shared page lands
