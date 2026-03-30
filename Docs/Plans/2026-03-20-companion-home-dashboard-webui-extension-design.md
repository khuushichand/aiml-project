# Companion Home Dashboard WebUI + Extension Design

Date: 2026-03-20
Owner: Codex collaboration session
Status: Approved (design, revised after review)

## Context and Problem

The repo already has three adjacent concepts:

- A lightweight home landing at `/` in the WebUI that currently renders `LandingHub`.
- A richer `Companion` workspace that already shows activity, goals, knowledge, and reflection-linked inbox data.
- A sidepanel root that is currently chat-first and restores recent conversations.

The requested product direction is not another standalone dashboard. It is a central personal hub for the user that surfaces stats, notifications, current work, and follow-up items, with parity across WebUI and extension.

The first design draft exposed several repo-level constraints:

1. WebUI `/` currently owns hosted-mode and first-run onboarding behavior.
2. Sidepanel `/` currently owns chat-resume behavior.
3. `Companion` is capability-gated on personalization today, which conflicts with the desired hybrid home shell.
4. Notification triage behavior exists in WebUI-only code today rather than shared UI code.

The design therefore needs to make `Companion` the conceptual home without breaking onboarding, hosted mode, or sidepanel chat restore.

## Goals

1. Make the user’s home experience a real personal cockpit rather than a static landing screen.
2. Merge that home experience into the `Companion` product direction instead of creating another overlapping workspace.
3. Keep WebUI and extension on the same information architecture, with responsive density differences only.
4. Prioritize a balanced dashboard with visible notifications plus actionable personal work blocks.
5. Support modular cards from day one, with a shared default layout and per-surface overrides.

## Non-Goals

1. Replacing hosted-mode landing behavior with Companion.
2. Removing first-run onboarding from the options root route.
3. Replacing the sidepanel’s existing resumable-chat behavior with a blind dashboard redirect.
4. Building a freeform canvas layout editor with arbitrary pixel positioning.
5. Inventing a brand-new backend dashboard API before proving the shared UI aggregator pattern.

## User-Approved Product Decisions

- Product direction: merge the new hub into `Companion`.
- Product emphasis: personal work cockpit plus highly visible inbox/alerts.
- Page style: balanced dashboard.
- Cross-surface strategy: same hub in WebUI and extension.
- Fallback behavior: hybrid shell, with strong setup/enablement states instead of a hard gate.
- MVP cards:
  - Unread notifications/alerts with quick triage actions
  - Resume work
  - Goals / focus
  - Recent activity
  - Reading queue or saved-for-later
- Optional cards:
  - Personal stats
  - Reflections / insights
  - Quick actions launcher
  - Collections / watchlists summary
- Customization: modular dashboard from day one.
- Persistence shape: shared default plus per-surface overrides.
- Inbox model: canonical server inbox plus a separate derived `Needs Attention` strip.

## Review-Driven Corrections

The original design was revised in these ways after repo review:

### 1) `Companion` becomes the conceptual home, not a naive direct root swap

The current `Companion` page cannot simply replace `/` unchanged because:

- WebUI `/` owns hosted-mode and onboarding today.
- Sidepanel `/` owns resumable chat behavior today.
- `Companion` route capability gating currently hides the route when personalization is unavailable.

Revised decision:

- Keep wrapper/resolver routes at `/`.
- Move the new dashboard into a new shared `Companion Home` shell that can render useful fallback states even when personalization is unavailable.

### 2) Home capability gating moves from route-level to card-level

Current `Companion` behavior treats missing personalization as route unavailability or a full-page unavailable state.

Revised decision:

- `Companion Home` must always be reachable after onboarding in self-host mode.
- Personalized cards degrade individually.
- The home shell remains useful even when personalization is unavailable or not yet enabled.

### 3) Notification behavior must become shared UI infrastructure

The current full inbox experience is implemented in the Next.js layer, not shared UI.

Revised decision:

- Extract notifications into shared services and shared cards before using them as a parity-critical home surface.

### 4) Layout sync is constrained by current storage reality

The repo already supports local/chrome storage patterns, but not an existing server-backed dashboard preference model.

Revised decision for v1:

- Ship one product-defined shared default layout.
- Persist per-surface overrides locally in WebUI and extension.
- Treat true cross-surface user-synced preferences as later additive work unless a suitable personalization-backed setting store is added.

## Selected Approach

Use a new shared `Companion Home` shell as the post-onboarding home experience, and render it from both the options root and the Companion route.

This is better than creating a new `/dashboard` route because:

- it aligns with the approved product direction to merge into Companion,
- it reuses the existing Companion data foundations,
- it avoids a third overlapping “home” concept,
- and it keeps the change additive to the current route architecture.

## Route Architecture

## WebUI

- `/`
  - remains a wrapper route
  - preserves hosted-mode landing behavior
  - preserves first-run onboarding behavior
  - renders `Companion Home` after onboarding in self-host mode
- `/companion`
  - renders the same `Companion Home` shell directly
- `/companion/conversation`
  - remains the focused companion conversation surface

### WebUI route behavior

`OptionIndex` should continue to own:

1. hosted-mode landing
2. onboarding wizard for first-run self-host
3. post-onboarding transition into home

Only the final branch changes from `LandingHub` to `Companion Home`.

## Extension / Sidepanel

- `/`
  - becomes a resolver route rather than a blind chat route
- `/companion`
  - renders the same `Companion Home` shell directly
- `/companion/conversation`
  - remains the focused companion conversation route

### Sidepanel resolver behavior

The sidepanel root must preserve current value:

1. if resumable chat state exists, render chat
2. otherwise render `Companion Home`

This keeps current chat restore behavior while still making the hub the default empty-state destination.

### Route and copy implications

Because `/` stops meaning “chat-only” in some contexts, copy and recovery affordances that implicitly assume `/ == chat` should be audited during implementation.

Examples include:

- not-found recovery CTA labels
- sidepanel first-run copy
- any explicit “go straight to chat” home-copy assumptions

## Capability Model

## Home shell availability

`Companion Home` should not be route-disabled when `hasPersonalization` is false.

Instead:

- the home shell is always accessible after onboarding in self-host mode
- personalized modules degrade individually
- setup and enablement states become first-class content

## Conversation route availability

`/companion/conversation` remains capability-gated:

- requires personalization
- requires persona support

## Card-level gating

Each card declares its dependencies.

Examples:

- `Inbox Preview`
  - depends on notifications availability
- `Goals / Focus`
  - can show setup or unavailable state when personalization is absent
- `Reading Queue`
  - depends on reading endpoints
- `Resume Work`
  - can mix server-backed and client-derived entries

## Page Architecture

The page is a balanced dashboard with two urgency layers followed by modular work blocks.

## Top header band

The header should include:

- page identity: `Companion` or `Companion Home`
- refresh action
- primary action: `Open conversation` when available
- setup/status message when the shell is degraded

When personalization is unavailable or disabled, this header expands into a strong setup band rather than disappearing.

## Attention layer

Directly below the header:

- `Inbox Preview`
  - canonical notifications from the server inbox
- `Needs Attention`
  - derived, ephemeral reminders from goals, reading, and unfinished note/document work

These are intentionally separate:

- inbox is authoritative and triageable
- attention is computed and non-durable

## Summary layer

A compact summary strip remains near the top with lightweight counts:

- unread inbox
- active goals
- reading queue
- unfinished note/document work

This supports the chosen balanced dashboard without forcing a dedicated deep-stats card into MVP.

## Main modular grid

Default MVP cards:

1. `Resume Work`
2. `Goals / Focus`
3. `Recent Activity`
4. `Reading Queue`

Optional catalog cards:

1. `Personal Stats`
2. `Reflections`
3. `Quick Actions`
4. `Collections / Watchlists`

## Card Model

Use a constrained typed card registry, not bespoke page sections.

Each card should define:

- `id`
- `title`
- `default position`
- `allowed spans`
- `required capabilities`
- `removable` vs `collapsible only`
- `surface availability`

### System cards

Pinned but collapsible:

- Setup / status band
- Inbox Preview
- Needs Attention

These establish the page as “home” and should not be fully removable.

### Core and optional cards

Movable and configurable:

- Resume Work
- Goals / Focus
- Recent Activity
- Reading Queue
- all optional add-on cards

## Customization Model

Customization is supported in v1, but within a constrained responsive grid.

Users can:

- reorder cards
- hide/show removable cards
- change size presets within allowed spans
- reset a surface layout
- reset all layouts to shared default

Users cannot:

- place cards with arbitrary pixel coordinates
- create overlapping freeform canvases

## Layout Persistence

Because there is no existing verified server-backed dashboard preference model in scope today, v1 layout persistence should be:

- `shared product default`
- `webui local override`
- `extension local override`

This still satisfies the approved “shared default plus per-surface overrides” direction, but does not claim cross-surface user-synced custom layouts before the underlying storage exists.

## Data Aggregation

Introduce a new shared aggregator, for example:

- `fetchCompanionHomeSnapshot(surface)`

This should compose existing services rather than require a new backend dashboard endpoint for v1.

## Inputs

### Companion snapshot

Reuse the existing shared Companion snapshot for:

- activity
- goals
- knowledge/reflection counts
- reflection-linked inbox data

### Notifications

Use `/api/v1/notifications` as the canonical inbox source.

Shared UI work is required to support:

- list
- unread count
- stream subscription
- mark read
- dismiss
- snooze

The current WebUI-only notifications page should become a thin consumer of shared notification infrastructure.

### Reading queue

Use existing shared reading item endpoints to populate a queue-like subset such as:

- saved
- unread
- recently updated but unresolved

Do not invent a new backend queue model for v1.

### Notes and document work

Use:

- existing notes list/search endpoints for recent note work
- local document workspace state for resumable reading/document context

Do not invent a new note-draft backend contract for MVP unless implementation discovers one already exists and stable.

## `Resume Work` model

Use a merged typed list of resumable entries:

- `goal_followup`
- `reading_item`
- `note_or_document`

Each entry should include:

- title
- reason it is resumable
- last activity timestamp
- target route
- target id
- optional secondary action

### Scope note

Chat resume is not a required MVP card source, because the approved MVP sources are goals, reading items, and note/document work.

However, the sidepanel root resolver must still preserve resumable chat behavior for backwards compatibility.

## `Needs Attention` derivation

This strip is client-derived and ephemeral.

Candidate sources:

- active goals with stale or missing progress
- reading items saved but not revisited
- unfinished note/document work

### Dedupe rule

If a canonical inbox item already represents the same entity or follow-up, the derived reminder should not also appear in `Needs Attention`.

The canonical inbox wins.

## Error Handling and Degraded States

The page should degrade by card, not fail as a whole surface.

## Missing personalization capability

Show:

- home shell
- setup/status band
- non-personalized cards that can still function

Do not show:

- a full-route dead end

## Personalization available but not enabled

Show:

- consent/setup band prominently
- inbox and other non-personalized modules when available
- disabled or setup states for personalized cards

## Server unavailable or auth failure

Show:

- reconnect/setup guidance
- locally derivable resume signals where possible
- clear per-card unavailable states

Do not:

- blank the entire home shell

## Notification action failures

Notification triage should be optimistic with rollback, and failures should stay local to the inbox card.

## Testing Strategy

## Service tests

- companion home snapshot aggregation
- needs-attention derivation
- inbox dedupe logic
- resume-work ranking
- layout preference merge logic

## Component tests

- setup/status band
- inbox preview triage flows
- card empty/unavailable/error states
- customize mode
- add/remove/reorder/reset behavior

## Route tests

- options `/` preserves hosted mode
- options `/` preserves onboarding
- options `/` renders Companion Home after onboarding
- sidepanel `/` preserves resumable chat behavior
- sidepanel `/` falls back to Companion Home when no resumable chat exists
- `/companion/conversation` remains separate and capability-gated

## Parity tests

Add shared WebUI + extension parity coverage for:

- card inventory
- setup-band behavior
- inbox preview behavior
- core dashboard rendering
- customization affordances

Responsive differences are allowed, but information architecture drift is not.

## Success Criteria

1. The user lands on a useful personal hub after onboarding instead of a shallow static landing screen.
2. Hosted mode and first-run onboarding remain intact.
3. Sidepanel chat restore behavior remains intact.
4. The home shell remains useful when personalization is missing or disabled.
5. Notifications become a shared cross-surface capability rather than a WebUI-only page.
6. Users can resume real work from goals, reading, and note/document state.
7. WebUI and extension stay aligned on the same hub architecture.

## Proposed Deliverables

1. Shared `Companion Home` shell in `apps/packages/ui`
2. Shared notifications domain and inbox preview card
3. Shared home snapshot aggregator
4. Options root migration from `LandingHub` to `Companion Home`
5. Sidepanel root resolver preserving chat resume
6. Modular card registry and layout persistence
7. WebUI + extension parity tests for the new home surface
