Date: 2026-03-10
Status: Approved

# Companion Proactive Polish Design

## Summary

This design activates the next companion roadmap slice after the quality and trust-controls milestone.

Companion now has:

- explicit capture
- bounded relevance
- richer derived knowledge
- provenance inspection
- scoped purge and rebuild
- dedicated companion conversation

The next gap is not more capture breadth. The next gap is whether companion can surface useful next-step guidance without becoming noisy, opaque, or ambient.

This milestone improves proactive behavior conservatively:

- better reflection delivery quality
- better suppression and prioritization
- explicit follow-up prompts only after a reflection is opened
- explicit follow-up prompts inside `/companion/conversation`

## Goal

Make companion proactively useful while preserving the existing local-first, explicit, and inspectable trust model.

## Non-Goals

This milestone does not include:

- passive or hidden capture
- standalone prompts on the workspace landing surface
- standalone prompts in the inbox list
- chat popups or ambient interruptions
- broad new capture adapters
- semantic ranking or opaque delivery models
- full inbox redesign

## Reviewed Current State

The current implementation already provides:

- Jobs-backed reflection generation
- inbox delivery through `companion_reflection` notifications
- per-user proactive and reflection settings
- provenance-backed reflection detail
- a dedicated companion conversation route

Current limitations:

- reflection generation is better than the original foundation but still shallow for delivery decisions
- every generated reflection is still too close to an all-or-nothing notification path
- there is no persisted delivery classification on the reflection itself
- follow-up prompts are not generated as first-class companion outputs
- companion conversation can use context, but not proactive prompt suggestions

## Product Direction

Recommended approach: `curated proactive layer`

Companion should stay explicit and user-controlled:

- reflections remain the primary proactive object
- follow-up prompts are secondary actions attached to reflection detail or companion conversation
- users can always inspect why a suggestion exists
- prompt insertion is not itself treated as captured activity

## Design Review Adjustments

Before approving this milestone, the design was tightened in several places.

### Reflection delivery classification must be persisted

Delivery policy should not exist only as inline branching inside the job runner.

Each reflection activity record should persist:

- `delivery_decision`: `delivered | low_priority | suppressed`
- `delivery_reason`
- `theme_key`
- `signal_strength`

This keeps the system auditable even when no notification is emitted.

### Suppressed reflections remain auditable but not primary

Suppressed reflections should still be persisted for provenance and review, but they should not clutter the default reflection list.

Default behavior for this milestone:

- delivered reflections appear normally
- low-priority reflections appear but carry explicit metadata/badging
- suppressed reflections remain available through detail/provenance paths and future admin-style views, but are not shown in the default workspace reflection list

### Companion conversation prompt sourcing must be deterministic

Conversation suggestions should not come from a fuzzy mix of “whatever seems relevant.”

Prompt precedence for `/companion/conversation`:

1. most relevant delivered reflection tied to current ranked companion context
2. if none, most relevant suppressed reflection with strong signal
3. if none, direct context-derived prompts from top-ranked card, goal, or activity

The response should include:

- `prompt_source_kind`
- `prompt_source_id`

so the UI can explain where the chips came from.

### Low-priority is metadata first, not a full inbox redesign

This milestone does not rework the inbox list UI. Low-priority should be represented as persisted reflection metadata plus detail/workspace badging first.

### Prompt repetition suppression must be theme-local

Repeated prompt families should only be suppressed when the theme is effectively unchanged and the signal delta is weak.

Suppression should reset when:

- the theme key changes
- signal strength meaningfully increases
- linked goal state changes
- new stale-followup evidence appears

### Prompt insertion must remain non-capturing

Clicking a suggested prompt should only insert draft text.

It should not create companion activity on its own. Capture still happens only when the user sends a conversation turn or explicitly saves/checks in.

## Architecture

### Core split

This milestone separates proactive behavior into three explicit layers:

1. `reflection generation`
   - summarize meaningful themes and evidence into a reflection artifact

2. `delivery policy`
   - decide whether that reflection is delivered, low-priority, or suppressed

3. `follow-up prompt generation`
   - create a small set of concrete, provenance-backed next-question prompts

The existing Jobs-backed reflection flow remains intact. This milestone adds a policy layer around it rather than replacing it.

### New backend layers

#### 1. Companion proactive policy

Add a deterministic policy helper, likely in a new `companion_proactive.py` or similarly scoped module, to:

- compute `theme_key`
- compute `signal_strength`
- classify `delivery_decision`
- explain `delivery_reason`
- decide whether a notification should be emitted

#### 2. Companion follow-up prompt generation

Add a dedicated prompt-generation helper that builds short prompt suggestions from:

- reflection evidence
- goal state
- stale/open follow-up signals
- ranked companion context

Each prompt should include:

- `prompt_id`
- `label`
- `prompt_text`
- `prompt_type`
- `source_reflection_id`
- `source_evidence_ids`

#### 3. Companion conversation prompt sourcing

Add a lightweight companion read path for `/companion/conversation` so the UI can request prompt chips before sending a message.

This should apply the explicit source hierarchy:

- delivered reflection
- suppressed reflection with high signal
- direct ranked context fallback

## Data Model And Read Model Changes

### Reflection metadata

Reflection activity metadata should now include:

- `title`
- `summary`
- `cadence`
- `evidence`
- `theme_key`
- `signal_strength`
- `delivery_decision`
- `delivery_reason`
- `follow_up_prompts`
- prompt-source metadata where relevant

### Reflection detail payload

Companion reflection detail should expose:

- delivery decision fields
- follow-up prompt list
- evidence-backed source ids

### Conversation prompt payload

Add a dedicated response model for companion conversation prompt suggestions:

- prompt chips
- source kind
- source id
- optional explanation text

## User-Facing Behavior

### Reflection detail behavior

When a reflection is opened:

- show its summary and delivery status
- show up to 3 follow-up prompts
- allow one-click prompt insertion into companion conversation or the current draft flow
- provide a clear explanation path for why each prompt exists

The prompts should be available directly on the reflection surface, not hidden behind provenance alone.

### Companion conversation behavior

Inside `/companion/conversation`:

- show prompt chips only when companion context is enabled and meaningful
- insert prompt text into the draft instead of auto-sending
- show at most 3 suggestions
- keep the chips tied to an explicit source

### Inbox and workspace behavior

For this milestone:

- delivered reflections keep their existing inbox path
- low-priority reflections carry metadata or detail badging
- suppressed reflections do not produce notifications
- suppressed reflections are not shown in the default workspace reflection list

## Delivery Policy Heuristics

First-pass heuristics should remain deterministic and explainable.

Good initial rules:

- suppress when recent activity is below a meaningful threshold
- suppress when the theme matches a recent delivered reflection and signal delta is weak
- suppress repeated prompt families within the same theme and weak-delta window
- de-emphasize repetitive maintenance-only reflection output
- promote reflections that combine active-goal pressure with stale or newly changed evidence

## Trust And Auditability Rules

- no prompt is shown without a traceable source reflection or context source
- prompt insertion is not logged as activity
- sending a prompt as a conversation turn follows existing persona/companion capture behavior
- suppression and low-priority classification remain inspectable through detail payloads

## Testing Strategy

Backend tests:

- delivery classification and suppression rules
- prompt generation families and source ids
- reflection detail payload exposure
- conversation prompt source precedence

Frontend tests:

- reflection follow-up prompt rendering
- prompt draft insertion
- companion conversation prompt chips
- no standalone prompt rendering on workspace home or inbox list

Operational tests:

- scheduler/job flow still respects consent, proactive toggles, cadence toggles, and quiet hours
- low-priority and suppressed paths do not regress notification behavior

## Deferred Follow-Ons

Still deferred after this milestone:

- broader proactive coaching loops
- dynamic inbox prioritization redesign
- stronger notification tuning beyond deterministic heuristics
- broader capture expansion
