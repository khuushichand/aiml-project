Date: 2026-03-10
Status: Implemented

# Companion Quality And Trust Controls Design

## Summary

This design defines the next companion milestone after the explicit-capture foundation merged to `dev`.

The foundation is now broad enough to support real user workflows:

- explicit activity ledger
- derived knowledge cards
- manual goals
- Jobs-backed reflections
- companion workspace
- dedicated companion conversation surface
- consent gating

The next gap is quality and trust, not breadth. The companion needs to become more relevant per query, more inspectable, and safer to manage when users want to review provenance or remove derived state.

## Implementation Notes

This design is now implemented on `codex/companion-explicit-capture-foundation`.

Delivered in this milestone:

- per-user companion reflection settings on the personalization profile
- explicit goal provenance and progress-mode fields
- bounded lexical-first companion context ranking with safe fallback behavior
- deterministic multi-family knowledge derivation
- richer reflection synthesis grounded in cards, goals, and stale follow-up signals
- dedicated provenance detail endpoints for activity, knowledge, and reflections
- workspace settings, provenance drill-down, and scoped purge/rebuild controls

Intentional limits that remain deferred:

- ranking is lexical-first and bounded, not semantic retrieval
- lifecycle controls only purge or rebuild derived state; explicit activity remains preserved
- reflection settings are limited to supported daily/weekly enable flags plus existing proactive and quiet-hours behavior
- destructive lifecycle controls remain option-surface only, not sidepanel actions

## Goal

Upgrade companion from a usable foundation into a trustworthy daily surface by improving:

- relevance of companion context used in conversation
- quality of derived knowledge and reflections
- inspectability of why the system produced a card or reflection
- user controls for settings, purge, and rebuild

## Non-Goals

This milestone does not include:

- passive or ambient capture
- new hidden or background tracking
- broad new extension capture families
- arbitrary user-defined reflection schedules
- full activity-ledger deletion from the companion workspace
- a second storage system outside personalization

## Reviewed Current State

The merged foundation already provides:

- companion activity, goals, and workspace APIs
- consent gating on companion read/write flows
- derived knowledge via `personalization_consolidation`
- companion context injection into persona retrieval
- Jobs-backed reflection generation and notification delivery
- workspace rendering for activity, knowledge, goals, reflections, and manual check-ins

Main quality limitations in the current implementation:

- knowledge derivation is too narrow and mostly top-tag driven
- companion context is bounded and safe, but not query-aware
- reflection synthesis is usable but shallow
- provenance is present in data, but not exposed through a dedicated UI drill-down flow
- purge/rebuild semantics are not defined at companion scope

## Design Review Adjustments

Before approving this milestone, the design was tightened in several places.

### Goal provenance must exist before destructive controls

Current goals do not cleanly distinguish:

- manual goals authored by the user
- derived goals created by the system
- manual goals with computed progress

This milestone therefore adds explicit goal metadata:

- `origin_kind`: `manual | derived | mixed`
- `progress_mode`: `manual | computed`
- optional `derivation_key`
- optional `evidence_json`

This prevents purge/rebuild actions from deleting or mutating user-authored goals incorrectly.

### Reflection settings must be honest about backend support

The current reflection scheduler is globally configured and only lightly gated per user by existing personalization fields such as `proactive_enabled` and quiet hours.

This milestone will not promise arbitrary cadence editing. It only adds simple per-user reflection flags:

- `companion_reflections_enabled`
- `companion_daily_reflections_enabled`
- `companion_weekly_reflections_enabled`

Quiet hours continue to reuse the existing personalization profile.

### Reflection purge must delete linked notifications too

Companion reflections are stored as companion activity events, but the inbox copy is stored in the notifications subsystem.

Reflection purge in this milestone is defined as:

- remove derived reflection activity rows
- remove linked `companion_reflection` notifications

This avoids ghost inbox entries or broken detail links.

### Query-aware ranking must stay bounded

Ranking against the entire activity ledger on every turn would create latency, noise, and failure modes that do not justify the gain.

This milestone limits query-aware ranking to a bounded candidate pool:

- active knowledge cards
- active or paused goals
- recent explicit activity window

Ranking uses deterministic lexical heuristics first, with fallback to the current bounded recent-summary behavior.

### Provenance UI needs detail endpoints

The existing workspace snapshot is fine for summary rendering, but not for drill-down views.

This milestone adds dedicated detail reads for:

- activity item provenance
- knowledge card provenance
- reflection provenance

The summary workspace remains lightweight.

### Rebuild must be Jobs-backed and per-user idempotent

Rebuild can race with background consolidation and reflection scheduling if it runs inline without coordination.

This milestone treats rebuild as a user-visible Jobs flow with:

- per-user idempotency
- explicit scope
- status surface
- safe coexistence with consolidation and reflection scheduling

## Recommended Product Direction

Recommended approach: `quality + trust-controls`

Upgrade companion usefulness and inspectability in the same milestone rather than growing capture breadth first.

Why this is the right next step:

- the current product already has enough capture sources to be useful
- more capture breadth would outrun the current quality layer
- trust features matter most once users begin depending on derived outputs
- provenance and destructive controls must arrive before the product gets more proactive

## User-Facing Scope

This milestone includes:

- better companion context selection in conversation
- richer knowledge cards
- better reflections grounded in goals and stale/open work
- companion settings panel
- provenance drill-down UI
- scoped purge/rebuild controls

This milestone explicitly does not include:

- new ambient monitoring
- new dashboard/tray/floating surfaces
- broad new explicit-capture adapters
- highly dynamic notification coaching

## Architecture

### Core principle

Keep companion state inside the personalization domain and keep persona as the conversation surface.

Companion remains:

- per-user for activity, derived knowledge, reflections, and goals

Persona remains:

- per-persona for profile, state docs, and live-session behavior

### New layers

The milestone adds four concrete layers:

1. `companion_relevance`
   - bounded lexical scoring of activity, cards, and goals against a live query
   - used by persona/companion conversation flows

2. richer deterministic derivations
   - multiple card families instead of only a single focus card
   - still evidence-backed and explainable

3. scoped companion lifecycle services
   - purge knowledge
   - purge reflections plus linked notifications
   - rebuild knowledge
   - rebuild reflections
   - recompute derived goal progress where allowed

4. companion detail/read models
   - summary workspace payload stays small
   - provenance drawers fetch dedicated detail payloads

## Data Model Changes

### Profile fields

Add companion-specific profile flags in the personalization profile:

- `companion_reflections_enabled`
- `companion_daily_reflections_enabled`
- `companion_weekly_reflections_enabled`

These are per-user controls, not global scheduler replacements.

### Goal fields

Add goal provenance and recomputation metadata:

- `origin_kind`
- `progress_mode`
- `derivation_key`
- `evidence_json`

Rules:

- manual goals are never deleted by derived-state rebuild
- derived goals may be purged and rebuilt
- computed progress on manual goals may be recomputed
- manual progress on manual goals is preserved

### Detail models

Add detail response models for:

- activity detail
- knowledge card detail
- reflection detail

Each detail payload must expose:

- timestamps
- source event IDs
- linked knowledge card IDs where applicable
- capture surface
- why-selected text

## Companion Context Design

### Current limitation

Current companion context loads a tiny bounded set of recent activity and active cards, which is safe but not very relevant to the live query.

### New behavior

On each companion/persona turn:

1. gather bounded candidates from:
   - active cards
   - goals
   - recent explicit activity
2. score them against the user message with deterministic lexical heuristics
3. build the prompt packet from the strongest matches
4. fall back to the current bounded recent-summary behavior when matches are weak

The scoring model should remain transparent and cheap in this milestone.

## Knowledge Derivation Design

The milestone expands derivation to a small, deterministic set of card families:

- `project_focus`
- `topic_focus`
- `stale_followup`
- `source_focus`
- `active_goal_signal`

Each card must be:

- explainable
- evidence-backed
- bounded in evidence size
- user-inspectable through provenance detail

This milestone is not trying to build a general inference engine.

## Reflection Design

Reflections should use:

- current focus cards
- unresolved or stale explicit work
- active goals and recent progress
- meaningful check-ins and persona/tool outcomes

Reflections remain:

- compact
- inspectable
- provenance-backed
- subject to quiet hours and per-user reflection enable flags

Reflection creation continues to run through Jobs.

## Settings Design

The companion settings surface should expose only controls the backend can honor truthfully now:

- companion reflections enabled
- daily reflections enabled
- weekly reflections enabled
- proactive companion behavior enabled
- existing quiet hours

This milestone does not include cron-like cadence editing.

## Provenance UI Design

The workspace adds drill-down affordances from:

- activity items
- knowledge cards
- reflections

Each drawer or detail panel should show:

- summary and title
- source IDs
- surfaces
- timestamps
- linked evidence items
- why-selected or why-derived explanations

The summary workspace should not preload all detail data.

## Purge And Rebuild Design

### Scope model

This milestone supports scoped actions, not an undifferentiated “reset companion” button.

Supported purge scopes:

- derived knowledge cards
- derived reflections plus linked inbox notifications
- derived goals only

Supported rebuild scopes:

- rebuild knowledge cards from preserved activity
- rebuild reflections from preserved activity and current knowledge/goals
- recompute derived goal progress where allowed

### Explicit exclusions

The companion workspace must not offer routine purge of the raw explicit activity ledger in this milestone.

That is a stronger destructive action and should remain separate from derived-state maintenance.

### Execution model

- purge may be synchronous if the scope is small and bounded
- rebuild must enqueue Jobs for durability and progress reporting
- rebuild operations must use per-user idempotency and locking

## Testing Strategy

Backend tests:

- bounded relevance ranking
- derivation families and evidence rules
- goal provenance semantics
- purge scope correctness
- rebuild job idempotency
- reflection purge removing linked notifications

Integration tests:

- persona/companion query-aware context selection
- settings persistence
- provenance detail endpoints
- purge/rebuild endpoints

UI tests:

- settings panel behavior
- provenance drawer rendering
- destructive confirmation flows
- rebuild status presentation

## Rollout Strategy

Recommended implementation order:

1. data model and profile/goal semantics
2. purge/rebuild backend services
3. relevance and richer derivations
4. reflection improvements
5. detail endpoints
6. workspace settings/provenance/purge UI

## Placeholder Follow-Ons

The following work is intentionally deferred but must remain visible:

1. `Companion Capture Expansion`
   - add more explicit capture adapters and extension actions

2. `Companion Proactive Polish`
   - improve notification quality, proactive delivery tuning, and coaching loops

## Recommendation

Build this milestone next.

It addresses the two real product gaps after the merged foundation:

- usefulness
- trust

It does so without broadening capture scope or violating the explicit local-first model.
