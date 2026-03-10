# Companion Explicit-Capture Roadmap Design

Date: 2026-03-10
Status: Approved

## Summary

This design reviews the Echo concept described in the external article and repo, compares it against the existing `tldw_server` persona and adjacent systems, and proposes a local-first roadmap that stays inside explicit-capture boundaries.

The recommendation is to build a `Companion` product layer on top of the existing persona, personalization, collections, notifications, and jobs infrastructure rather than copying Echo's ambient desktop-monitoring model.

## Reviewed Sources

- Medium article: <https://kotrotsos.medium.com/claude-desktop-has-a-hidden-feature-6322a22ab625>
- `claude_echo` repo: <https://github.com/Kotrotsos/claude_echo>
- Echo notes: <https://raw.githubusercontent.com/Kotrotsos/claude_echo/main/docs/09-ECHO-FEATURE.md>

## Investigated Internal Context

- Persona design and APIs:
  - `Docs/Design/Personas.md`
  - `Docs/Product/Persona_Agent_Design.md`
  - `tldw_Server_API/app/api/v1/endpoints/persona.py`
  - `tldw_Server_API/app/api/v1/schemas/persona.py`
  - `tldw_Server_API/app/core/Persona/memory_integration.py`
  - `tldw_Server_API/app/core/Persona/policy_evaluator.py`
  - `tldw_Server_API/app/core/Persona/session_manager.py`
- Persona WebUI:
  - `apps/packages/ui/src/routes/sidepanel-persona.tsx`
  - `Docs/Plans/2026-03-08-persona-garden-design.md`
- Personalization:
  - `Docs/Product/Personalization_Design.md`
  - `tldw_Server_API/app/core/DB_Management/Personalization_DB.py`
  - `tldw_Server_API/app/services/personalization_consolidation.py`
- Notifications and reminders:
  - `Docs/API-related/Reminder_Notifications_API.md`
- Self-monitoring:
  - `Docs/Design/Guardian_Self_Monitoring.md`
- Collections, reading, extension, and digests:
  - `Docs/Product/Completed/Content_Collections_PRD.md`
  - `tldw_Server_API/app/core/Collections/reading_digest_jobs.py`
  - `tldw_Server_API/app/services/reading_digest_scheduler.py`

## Problem Statement

The external Echo material suggests a useful product pattern:

- maintain an activity timeline
- derive knowledge from activity
- support a dedicated companion conversation surface
- generate reflections, goals, and proactive notifications

`tldw_server` already has much of the upper-layer substrate for this pattern, but it does not yet have a first-class unified activity model for explicit user captures and actions. Without that shared activity layer, the existing persona, personalization, notifications, and reading/watchlist systems remain useful but fragmented.

## Scope Decision

Approved scope:

- local-first
- explicit capture only
- broader roadmap across persona plus adjacent systems

Explicitly out of scope for this design:

- passive desktop monitoring
- ambient screen capture
- arbitrary window observation
- hidden or non-provenanced behavioral inference from non-explicit OS activity

## What Echo Does

Based on the external material, Echo appears to combine:

- a capture engine with configurable cadence and privacy controls
- an activity feed
- a knowledge base derived from observed behavior
- reflections and behavioral goals
- proactive notifications
- a dedicated conversational interface
- dashboard, tray, and bubble surfaces

The most relevant product pattern is not the screen capture itself. It is the stack above capture: activity normalization, derived knowledge, coaching/reflection, and a conversational companion.

## Current tldw_server Overlap

### Strong overlap

- Persona already provides:
  - catalog, session, and session history endpoints
  - live WS streaming
  - tool-plan confirmation
  - policy and scope rules
  - persona state docs and restore history
  - persona memory retrieval and persistence hooks
- Personalization already provides:
  - per-user profile/preferences
  - per-user usage events
  - semantic memories
  - topic profiles
  - proactive preference fields and quiet hours
- Notifications and reminders already provide:
  - inbox model
  - SSE stream
  - reminders
  - Jobs bridge patterns for user-facing background outcomes
- Collections already provide:
  - explicit reading capture
  - watchlists
  - notes/highlights substrate
  - scheduled digests and suggestion logic
- Self-monitoring already provides:
  - awareness-rule concepts
  - escalation and cooldown ideas
  - notification-oriented reflective workflows

### Partial overlap

- reflections and suggestions exist as design direction across personalization, digests, and self-monitoring, but are not yet unified
- extension capture surfaces exist, but not as a generalized companion-ingestion adapter

### Main gap

The biggest missing primitive is a unified explicit-capture activity ledger that can power:

- activity timeline UX
- knowledge derivation
- reflection generation
- goal progress tracking
- proactive suggestions with provenance

## Recommended Product Direction

Recommended approach: `Persona-first companion`

Use the existing persona system as the interactive companion surface and build the missing activity/knowledge/reflection layer around it.

Rejected alternatives:

- `Personalization-first life log`
  - cleaner from a data-model perspective, but delays value and duplicates existing persona surface area
- `Digest/monitoring-first coach`
  - useful for scheduled summaries, but weaker for conversational continuity and less aligned with current persona investment

## Product Model

Use only one new top-level user-facing workspace:

- `Companion`

`Persona Garden` remains separate and continues to own:

- persona profile editing
- persona state docs
- scope rules
- policy rules
- live persona sessions

`Companion` owns:

- Activity
- Knowledge
- Reflections
- Goals
- Conversations

This keeps persona configuration distinct from the user-facing companion experience.

## Recommended Roadmap

### Phase 1: Explicit Activity Ledger

Create a first-class explicit activity model for:

- reading-item saves
- reading status changes
- highlights and note edits
- watchlist item additions
- persona session summaries
- important persona tool outcomes
- reminder completions
- optional manual user check-ins
- extension-driven explicit captures such as page summary, save selection, and ask-about-page

This phase is the core missing primitive.

### Phase 2: Activity-Derived Knowledge

Derive compact, user-editable knowledge from the activity ledger:

- active topics
- recurring projects
- repeated research themes
- stale or unfinished reading queues
- source/domain focus areas
- working preferences inferred from explicit behavior

This phase should extend the personalization domain rather than create an unrelated memory system.

### Phase 3: Reflections, Digests, and Goals

Add inspectable, user-visible outputs:

- daily/weekly reflections
- saved-but-unrevisited suggestions
- backlog summaries
- project-focused summaries
- lightweight goals tied to explicit activity
- reminders and follow-ups

These are user-facing and should run on the Jobs backend, with APScheduler only used to enqueue recurring work.

### Phase 4: Companion Workspace

Expose the system through a dedicated workspace:

- activity timeline
- knowledge cards
- goals
- reflection history
- conversations with the companion persona
- notification/inbox integration
- provenance details for every suggestion or reflection

## Feature Mapping

### Adopt soon

- activity timeline
- knowledge base from activity
- reflections
- behavioral goals tied to explicit events
- prompt/profile customization through persona profiles, state docs, and prompt library

### Adopt later

- proactive notifications
- dedicated companion dashboard
- browser-side quick capture actions for companion workflows

### Do not copy directly

- ambient screen capture
- always-visible floating bubble
- separate auth/product key model
- Slack-style ambient communication monitoring

## Architecture

### Core principle

Do not create a second parallel event system unless the existing personalization schema proves insufficient.

Default architecture:

- extend the personalization domain to hold the normalized explicit-capture activity ledger
- let persona consume that context
- keep persona state/memory separate from per-user companion knowledge

### Proposed layers

- `Companion Activity Adapter Layer`
  - normalizes events from reading, highlights, notes, watchlists, reminders, and persona sessions
- `Personalization Activity Store`
  - stores normalized explicit activity events inside the personalization domain
- `Companion Consolidation`
  - derives knowledge cards, reflection inputs, and goal-progress signals
- `Companion Orchestrator`
  - prepares companion context for persona conversations and dashboard views
- `Companion Workspace`
  - renders Activity, Knowledge, Reflections, Goals, and Conversations

### Ownership rules

- Companion knowledge is per-user, source-linked, and editable.
- Persona memory/state is per-persona, scoped, and not silently rewritten by companion inference.
- Persona may read companion context during responses.
- Companion reflections/goals may reference persona sessions, but they do not mutate persona state docs automatically.

## Data Contract

Every normalized activity event should include at minimum:

- `event_type`
- `source_type`
- `source_id`
- `surface`
- `timestamp`
- `tags`
- `provenance`
- `dedupe_key`

Derived outputs should carry evidence links back to their source events/items.

## Provenance Requirements

Provenance is mandatory.

Every reflection, suggestion, and goal-progress explanation must expose:

- which source records were used
- why they were selected
- when they were captured
- how many signals were involved

This must be part of the API contract, not just UI copy.

## Jobs and Scheduling

User-visible durable work should use Jobs:

- scheduled reflections
- proactive summaries
- goal progress evaluations
- companion digest generation

Recurring schedules should use APScheduler only to enqueue Jobs, following existing reading-digest and reminders patterns.

## Notification Policy

To avoid notification fatigue:

- respect quiet hours and proactive preferences already present in personalization
- enforce minimum evidence thresholds for proactive outputs
- cap proactive reflection frequency
- rank notifications before delivery
- make all proactive outputs inspectable in the inbox and companion workspace

## Relationship To Existing Systems

### Persona

Use persona as the conversation/action surface, not as the single storage layer for companion state.

### Personalization

Extend personalization for activity events and user-level derived knowledge. Avoid creating a separate user-modeling database unless forced by schema limitations.

### Collections

Use reading/watchlists/highlights/notes as primary explicit-capture inputs for the activity ledger.

### Self-Monitoring

Reuse notification, escalation, cooldown, and awareness ideas where useful, but keep productivity goals separate from guardian/self-monitoring rule models.

### Notifications

Use existing inbox/SSE/reminder infrastructure for delivery and acknowledgement flows.

## Purge and Export Semantics

Because this system models user behavior, purge/export semantics are part of v1:

- derived knowledge, reflections, and goals must be purgeable
- derivations should be reconstructible from source records where possible
- the system should prefer references and compact summaries over large duplicated content copies

## Testing Strategy

### Unit

- event normalization
- dedupe behavior
- consolidation logic
- provenance assembly
- goal-progress calculations
- notification ranking/throttling

### Integration

- reading save/highlight/note to activity event
- watchlist additions to activity event
- persona session/tool outcome to activity event
- reflection job to notification output
- persona companion retrieval with activity and derived knowledge context

### UX/behavioral

- provenance visibility
- quiet-hours enforcement
- opt-in and opt-out behavior
- purge behavior
- web and extension parity for explicit capture entry points

## Risks

### Risk: duplicate storage semantics

Mitigation:

- keep source systems canonical
- store activity rows as references plus compact metadata
- keep derivations compact and rebuildable

### Risk: persona sprawl

Mitigation:

- keep `Companion` separate from `Persona Garden`
- do not overload persona endpoints with every companion concern

### Risk: noisy proactive output

Mitigation:

- add evidence thresholds
- rank and throttle suggestions
- make every suggestion inspectable and dismissible

### Risk: privacy confusion

Mitigation:

- use strict explicit-capture language everywhere
- avoid ambient-monitoring language and product claims

## Suggested v1 Deliverables

1. Extend personalization event capture with a normalized explicit activity envelope.
2. Build activity adapters for reading, highlights, notes, watchlists, reminders, and persona sessions.
3. Add companion derivation logic for knowledge cards and reflections.
4. Create Jobs-backed reflection generation and delivery.
5. Add a `Companion` workspace with Activity, Knowledge, Reflections, Goals, and Conversations.
6. Wire persona companion retrieval to the per-user companion knowledge layer.

## Final Recommendation

The best path for `tldw_server` is not to imitate Echo's hidden ambient-capture model.

The best path is to turn the repo's existing persona, personalization, collections, notifications, and jobs infrastructure into a transparent, local-first `Companion` built from explicit user captures and actions. That produces most of Echo's useful value while staying consistent with `tldw_server`'s architecture, privacy posture, and existing product direction.
