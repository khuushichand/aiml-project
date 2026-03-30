# Integrations And Scheduled Tasks Control Plane Design

Date: 2026-03-20
Status: Approved

## Summary

This design adds two new management surfaces to the shared web UI and extension:

- personal integrations management
- workspace integrations management
- unified scheduled tasks management

The initial request combined Slack, Discord, Telegram, and scheduled-task management into a single UI initiative. Repo review showed that the current backend contracts are asymmetric:

- Slack and Discord already have OAuth and admin policy surfaces, but installation records are still effectively per-user.
- Telegram already has workspace bot configuration and pairing-code generation, but not a full admin inventory for linked actors.
- Scheduled tasks already exist as two separate primitives:
  - reminder tasks at `/api/v1/tasks`
  - watchlist jobs at `/api/v1/watchlists/jobs`

Because of that, the recommended direction is not a thin UI over existing endpoints. V1 should introduce a small control-plane backend with normalized read/write contracts that both the web UI and extension consume.

## Goals

- Give end users a dedicated personal integrations page to manage Slack and Discord connections.
- Give admins a dedicated workspace integrations page to manage Slack, Discord, and Telegram at the workspace level.
- Give users a single scheduled-tasks page that shows both reminder tasks and watchlist jobs.
- Keep reminder tasks fully manageable in the unified page.
- Keep watchlist jobs visible in the unified page but explicitly managed through the existing Watchlists UI.
- Preserve parity between the Next.js web UI and the extension by implementing shared routes and components in `apps/packages/ui/src/`.

## Non-Goals

- Do not collapse these surfaces into the existing `connectors` product area. In this repo, `connectors` already refers to content-sync providers like Drive, Notion, Gmail, and OneDrive.
- Do not make Telegram user-manageable in the personal integrations page in V1.
- Do not make watchlist jobs editable from the unified scheduled-tasks page in V1.
- Do not expose raw provider-specific payloads to the frontend as the primary contract.

## Product Decisions

### Information Architecture

Use a hybrid IA:

- `/integrations` for personal connection management
- `/admin/integrations` for workspace-level admin management
- `/scheduled-tasks` for unified task visibility and reminder CRUD

This keeps personal and admin responsibilities distinct while still giving each a first-class page.

Navigation exposure for V1:

- `/integrations` and `/scheduled-tasks` should be reachable from the shared options launcher/header shortcuts.
- `/admin/integrations` should remain a distinct admin-oriented route and shortcut rather than being folded into the general user workspace list.

### Platform Scope

Ship full parity in both:

- web UI
- extension options UI

These surfaces should be built as shared route components in `apps/packages/ui/src/routes/` and wrapped by both `apps/tldw-frontend/pages/` and the extension route system.

The sidepanel is not the primary target for V1 management flows. Full-page option routes are the baseline.

### Provider Scope

Personal integrations page:

- Slack: full connect/disconnect/enable/disable management
- Discord: full connect/disconnect/enable/disable management
- Telegram: omitted in V1

Workspace integrations page:

- Slack: workspace overview, workspace policy, workspace installation registry
- Discord: workspace overview, workspace policy, workspace installation registry
- Telegram: workspace bot config, enable/disable, pairing-code generation, linked-actor inventory, revoke/unlink controls

### Scheduled Tasks Scope

Expose both scheduled-task primitives in one place, but preserve their asymmetry:

- reminder tasks: native CRUD in the unified page
- watchlist jobs: read-only in the unified page, with deep links to `/watchlists`

The page must make this distinction explicit in the UI and contract so users do not assume all scheduled rows are editable in place.

## Why Not Reuse Existing Endpoints Directly

Existing repo seams are useful but not sufficient as the final product contract.

### Slack And Discord

Current admin routes support policy actions, but installation records are still read from the authenticated user's secret store. That means current admin inventory is not a true workspace-wide view.

V1 therefore needs a new workspace-scoped installation registry so an admin can:

- see installations relevant to the workspace
- know who installed them
- disable or remove them with clear audit ownership

### Telegram

Current Telegram admin support includes:

- bot config
- webhook handling
- pairing-code generation

That is not yet enough for a complete management overview. The workspace control plane should also expose:

- linked Telegram actor list
- revoke/unlink action
- pairing-code status summary

### Scheduled Tasks

Reminder tasks and watchlist jobs already exist, but they are modeled and owned by different backend domains. The unified page should consume a normalized read model while preserving their native ownership.

## Recommended Architecture

Introduce a new control-plane layer in the backend.

The control plane is responsible for:

- aggregating existing provider/task state
- normalizing it into product-facing models
- exposing typed admin and personal mutations
- hiding provider/task-specific inconsistencies from the clients

The existing provider/task endpoints remain in place for:

- webhook ingestion
- OAuth callbacks
- Telegram webhook handling
- watchlist execution and management
- reminder execution

The web UI and extension should use the new control-plane endpoints rather than calling legacy provider endpoints directly for management.

## Normalized Domain Model

### IntegrationConnection

Represents one visible connection or installation summary.

Fields:

- `id`
- `provider`: `slack | discord | telegram`
- `scope`: `personal | workspace`
- `display_name`
- `status`: `connected | disconnected | disabled | degraded | needs_config`
- `enabled`
- `connected_at`
- `updated_at`
- `health`
- `metadata`
- `actions`

### IntegrationPolicy

Represents workspace policy/configuration for Slack and Discord, plus workspace bot config for Telegram.

V1 must use typed schemas rather than free-form JSON payloads.

### ScheduledTask

Represents a normalized task row in the unified scheduled-tasks page.

Fields:

- `id`
- `primitive`: `reminder_task | watchlist_job`
- `title`
- `description`
- `status`
- `enabled`
- `schedule_summary`
- `timezone`
- `next_run_at`
- `last_run_at`
- `edit_mode`: `native | external`
- `manage_url`
- `source_ref`

Capability rules:

- reminder tasks use `edit_mode: native`
- watchlist jobs use `edit_mode: external`

## Backend Control Plane

### Personal Integrations Endpoints

- `GET /api/v1/integrations/personal`
- `POST /api/v1/integrations/personal/{provider}/connect`
- `PATCH /api/v1/integrations/personal/{provider}/{connection_id}`
- `DELETE /api/v1/integrations/personal/{provider}/{connection_id}`

These endpoints should cover Slack and Discord only in V1.

### Workspace Integrations Endpoints

- `GET /api/v1/integrations/workspace`
- `GET /api/v1/integrations/workspace/{provider}`
- `PUT /api/v1/integrations/workspace/{provider}/policy`
- `POST /api/v1/integrations/workspace/telegram/bot`
- `POST /api/v1/integrations/workspace/telegram/pairing-code`
- `GET /api/v1/integrations/workspace/telegram/linked-actors`
- `DELETE /api/v1/integrations/workspace/telegram/linked-actors/{actor_id}`

Slack and Discord workspace pages also require registry-backed installation inventory. That implies backend support for persisting a workspace-visible installation summary in addition to the user-owned secret/token material.

### Scheduled Tasks Endpoints

- `GET /api/v1/scheduled-tasks`
- `GET /api/v1/scheduled-tasks/{task_id}`
- `POST /api/v1/scheduled-tasks/reminders`
- `PATCH /api/v1/scheduled-tasks/reminders/{task_id}`
- `DELETE /api/v1/scheduled-tasks/reminders/{task_id}`

The scheduled-tasks list endpoint should return a combined read model over:

- `/api/v1/tasks`
- `/api/v1/watchlists/jobs`

It should support partial-success aggregation so one primitive failing does not blank the whole page.

## Workspace Installation Registry

This is the main correction identified during design review.

Slack and Discord need a workspace-scoped installation registry that stores non-secret operational metadata such as:

- provider
- workspace identifier
- external installation identifier
- installer user id
- installed at
- disabled state
- last health status
- last sync/check timestamp if applicable

Secrets and access tokens should remain in user-owned secret storage, but the admin UI must read from the workspace registry rather than attempting to infer workspace state from whichever admin is currently logged in.

Admin action policy should be explicit:

- any workspace admin may disable or remove a workspace installation unless product rules later narrow that
- all such actions should be auditable
- UI must display installer ownership and last-updated metadata

## Frontend Routes And Components

### Routes

Shared routes:

- `apps/packages/ui/src/routes/option-integrations.tsx`
- `apps/packages/ui/src/routes/option-admin-integrations.tsx`
- `apps/packages/ui/src/routes/option-scheduled-tasks.tsx`

Wrapper pages:

- `apps/tldw-frontend/pages/integrations.tsx`
- `apps/tldw-frontend/pages/admin/integrations.tsx`
- `apps/tldw-frontend/pages/scheduled-tasks.tsx`

Equivalent extension route wiring should point at the shared option routes.

### Shared Components

- `IntegrationManagementPage`
- `ScheduledTasksPage`
- `IntegrationProviderCard`
- `IntegrationConnectionDrawer`
- `IntegrationPolicyPanel`
- `ScheduledTaskTable`
- `ReminderTaskEditor`
- `WatchlistJobReadOnlyPanel`

## Page Design

### `/integrations`

Purpose:

- personal connection management for Slack and Discord

Behavior:

- render one provider card per supported provider
- show connection state, display name, connected time, status, and allowed actions
- primary actions:
  - connect
  - reconnect
  - disable/enable
  - remove

Telegram does not appear here in V1.

### `/admin/integrations`

Purpose:

- workspace-level management for Slack, Discord, and Telegram

Suggested sections:

- overview
- Slack
- Discord
- Telegram

Slack and Discord sections:

- workspace status summary
- typed policy editor
- workspace installation registry table
- disable/remove actions
- ownership and audit metadata

Telegram section:

- bot config form
- enabled/disabled state
- bot username
- pairing-code generation
- linked actor inventory
- revoke/unlink action

### `/scheduled-tasks`

Purpose:

- one place to review all scheduled automation visible to the user

Sections:

- overview cards
- reminder tasks
- watchlist jobs

Reminder tasks section:

- full CRUD
- create/edit in drawer or modal
- status and schedule summary

Watchlist jobs section:

- read-only rows/cards
- filters and drill-in details
- “Manage in Watchlists” deep link

The watchlist rows should use current deep-link conventions already established in the watchlists route/store.

## Extension OAuth Flow

This is another correction from design review.

The extension should not become its own OAuth callback target in V1.

Recommended V1 flow:

1. extension calls `POST /api/v1/integrations/personal/{provider}/connect`
2. backend returns the auth URL
3. extension opens the auth URL in a browser tab/window
4. backend handles the callback using the existing server callback route
5. extension polls or refetches normalized control-plane state

This keeps OAuth ownership on the server and avoids extension-specific callback complexity.

## Error Handling

### Integrations

- provider failures degrade only that provider card/section
- page-level loading should not be all-or-nothing
- show actionable states:
  - not configured
  - needs reconnect
  - permission denied
  - unavailable
  - degraded

### Scheduled Tasks

- reminder CRUD errors stay local to the reminder editor
- watchlist aggregation failures degrade only the watchlist section
- partial failures in `/api/v1/scheduled-tasks` should still render available primitives

### Admin Policy Editing

- prefer typed field-level validation
- do not default to a raw JSON editor as the main UX
- a raw JSON debug escape hatch is acceptable later, but not the primary control surface

## Testing Strategy

### Backend

- unit tests for Slack, Discord, Telegram, reminders, and watchlists normalization
- tests for workspace installation registry behavior
- endpoint tests for:
  - personal integrations
  - workspace integrations
  - scheduled tasks aggregation
- permission tests for personal and admin scopes
- partial-aggregation failure tests
- Telegram linked-actor list/revoke tests

### Frontend Shared UI

- route tests for:
  - `/integrations`
  - `/admin/integrations`
  - `/scheduled-tasks`
- component tests for provider cards, policy panels, reminder editor, and read-only watchlist rows
- tests that capability flags drive action visibility correctly
- responsive tests for extension-sized layouts

### End-To-End

- Slack personal connect flow with mocked auth start
- Discord personal connect flow with mocked auth start
- Telegram admin bot config plus pairing-code generation
- Telegram linked-actor revoke flow
- reminder create/edit/delete from scheduled tasks
- watchlist row deep-link to watchlists

## Risks And Mitigations

### Risk: Workspace Visibility Is Misleading

Mitigation:

- make workspace registry part of the backend control-plane scope
- do not ship an admin inventory that is secretly tied to the current admin account

### Risk: `connectors` IA Becomes Confused

Mitigation:

- keep messaging integrations out of `/connectors`
- label these surfaces consistently as `Integrations`

### Risk: Unified Scheduled Tasks Feels Inconsistent

Mitigation:

- use explicit capability labels and `Manage in Watchlists` actions
- distinguish native reminder management from external watchlist management in copy and layout

### Risk: Telegram Section Feels Half-Built

Mitigation:

- require linked-actor inventory and revoke support as part of the admin control-plane slice

## Recommended Delivery Sequence

1. Introduce typed control-plane schemas and service layer.
2. Add workspace installation registry for Slack and Discord.
3. Add Telegram admin linked-actor inventory and revoke support.
4. Add normalized integrations endpoints.
5. Add normalized scheduled-tasks endpoints.
6. Build shared UI routes/components in `packages/ui`.
7. Add web UI wrappers and extension route wiring.

## Final Recommendation

Proceed with option 3, but only in its corrected form:

- new control-plane backend
- real workspace installation registry for Slack and Discord
- stronger Telegram admin management support
- explicit separation from `connectors`
- unified scheduled-tasks read model with reminder-native CRUD and watchlist external management

That is the smallest design that satisfies the product request without baking backend inconsistencies directly into two clients.
