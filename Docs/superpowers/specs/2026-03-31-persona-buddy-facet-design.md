# Persona Buddy Facet Design

**Date:** 2026-03-31

## Goal

Define a persona-owned buddy system that gives every persona a persistent visual face and an interaction shell that can appear consistently across Persona Garden, persona-related cards and headers, and active persona chat surfaces.

The buddy is not a separate pet, character, or assistant. It is the persona's visible representation and shortest interaction path.

## Context

Relevant existing repo context:

- `Docs/Plans/2026-03-08-persona-garden-design.md`
- `Docs/Plans/2026-03-13-persona-companion-connection-ux-design.md`
- `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- `apps/packages/ui/src/components/Option/Companion/CompanionPage.tsx`

The existing product model already establishes:

- `My Chat Identity` is distinct from persona
- persona is a first-class assistant artifact, not a user avatar
- `/persona` is already a live workflow, not only a settings page

This feature should extend that model rather than introduce a second independent identity system.

## Problem

Personas currently have rich configuration and live-session behavior, but they do not yet have a first-class, recognizable face that follows them across the product. Existing persona surfaces can feel structurally rich but visually anonymous.

The user intent is stronger than "add an icon":

- every persona should have a visual representation by default
- that visual should be tied to the persona itself
- it should appear wherever the persona appears
- it should later support Clippy-like interaction, not only static display

If this is implemented as a decorative avatar or a separate companion entity, the product will split the persona into multiple identities and weaken the mental model established by Persona Garden.

## User-Confirmed Product Rules

1. The buddy is tied to each persona.
2. The buddy should behave more like a Clippy-style presence than a plain icon.
3. The buddy is the persona's visual representation and a means of interaction.
4. Planning and rollout should proceed in this order:
   - `A)` identity model
   - `B)` cross-surface rendering
   - `C)` interaction model
5. Every persona gets a buddy automatically.
6. The buddy is the "face" of the persona, so core identity should remain persona-derived.
7. User customization is allowed, but only as presentation overlays rather than total replacement of the core derived identity.

## Scope And Decomposition

This feature is too large to treat as a single implementation pass. It should be decomposed into three linked tracks with clear dependency order.

### Track A: Persona Buddy Identity Facet

Create the server-backed persona-owned buddy facet and the resolved buddy payload consumed by clients.

### Track B: Cross-Surface Rendering System

Introduce shared rendering primitives and render-mode rules so the same buddy can appear consistently in persona lists, cards, headers, and active persona surfaces.

### Track C: Buddy Interaction Shell

Introduce the Clippy-style interaction layer, including reactive bubbles, direct buddy invocation, and persona-aligned micro-interactions.

Planning should start with Track A. Tracks B and C should be planned after the identity facet is stable enough to support a shared resolved payload.

## Non-Goals

- Do not create a second independent pet entity with its own canonical identity separate from persona.
- Do not redefine the buddy as the user's chat identity.
- Do not require the initial implementation to ship a large asset catalog before the data model is sound.
- Do not allow core buddy identity to drift independently from persona state.
- Do not make the buddy a mandatory interruption layer on every surface.
- Do not silently let buddy interactions mutate persona settings without explicit user action.

## Recommended Approach

Model the buddy as a `persona-owned facet` with four layers:

1. `Persona signals`
   - existing persona fields and future explicit appearance hints
2. `Derived core buddy identity`
   - persona-authoritative visual and behavioral foundation
3. `User-selected overlay preferences`
   - accessory and presentation choices that decorate the derived core
4. `Resolved buddy payload`
   - the merged payload every surface consumes

This keeps the source of truth singular:

- persona remains canonical
- the buddy remains visibly and behaviorally anchored to persona
- clients render a shared resolved output instead of recomputing divergent buddy variants locally

## Track A Planning Contract

Track A is the next planning target and should stay narrowly scoped.

### In Scope

- extend persona persistence with a buddy facet contract
- derive the core buddy identity from stable persona signals
- support existing personas as well as newly created personas
- persist and serve a canonical resolved buddy profile
- store and normalize overlay preferences when present
- expose backend read contracts required for later rendering work through a dedicated persona buddy sub-resource

### Out Of Scope

- shared rendering primitives and tier-specific UI placement
- animation systems, idle-motion behavior, or bubble choreography
- buddy micro-chat or direct buddy interaction flows
- user-facing overlay editing UI
- public overlay mutation workflows unless a later plan explicitly adds them

Track A may define reserved extension points needed by Tracks B and C, but it should not require Track B or C implementation work in the first plan.

### Track A API Contract

Track A should expose buddy data through a dedicated persona-scoped sub-resource rather than by overloading every existing persona payload immediately.

Recommended day-one read contract:

- `GET /api/v1/persona/profiles/{persona_id}/buddy`

Optional follow-on reads may project a buddy summary into other persona surfaces later, but Track A should treat the buddy as a dedicated sub-resource owned by persona.

## Design

### 1. Domain Model

Each persona owns exactly one buddy facet.

The buddy facet should be treated as a stable sub-resource of the persona profile rather than as a free-floating object in its own right. The facet should be stored in the persona domain, not in the separate personalization or companion domain.

Implementation constraint:

- Track A should persist buddy state in the persona storage layer, keyed by `persona_id`
- Track A should not store canonical buddy identity in `PersonalizationDB`
- a dedicated persona-buddy table or equivalent persona-scoped storage contract is preferred over mutating unrelated personalization records

The facet should distinguish between:

- `derived_core`
- `overlay_preferences`
- `resolved_profile`

#### Derived Core

The derived core is always computed from persona-authoritative state.

Day-one derived-core outputs should include:

- `species_id`
- `silhouette_id`
- `palette_id`
- `behavior_family`
- `expression_profile`

Day-one derivation inputs should prefer stable persona signals, such as:

- persona id
- persona name
- source-character lineage
- origin-character snapshot metadata
- explicit appearance hints when they exist in a future schema

Day-one derivation should not use highly mutable fields such as freeform `system_prompt`, setup progress, or live-tuned voice defaults as primary identity inputs. Those fields may inform future presentation refinements, but they should not cause the persona's core buddy identity to churn during normal editing.

The exact derivation heuristic is an implementation detail, but the contract is not: identical persona inputs should produce a stable derived core unless the derivation version changes intentionally.

#### Overlay Preferences

Overlay preferences are user-controlled but bounded.

Day-one overlays may include:

- accessory or hat selection
- eye style
- alternate compatible expression set

Overlay preferences must not replace:

- species
- base silhouette
- core behavior family
- canonical visual identity

For Track A, overlay preferences are a persistence and normalization concern, not yet a full end-user editing feature. Track A should support reading, storing, and compatibility-checking overlay preferences if present, but buddy overlay editing UI and public mutation flows are deferred to later plans.

#### Resolved Profile

The resolved profile is the only payload surfaces should render against.

It merges:

- current derived core
- compatible overlay preferences
- derived or computed fallbacks when overlays are invalid

The resolved profile should also expose compatibility metadata so the UI can explain when a chosen overlay had to be downgraded or replaced.

Track A's required resolved-profile contract should stay limited to identity and compatibility fields needed for consistent rendering:

- `species_id`
- `silhouette_id`
- `palette_id`
- `behavior_family`
- `expression_profile`
- `accessory_id`
- `eye_style`
- `compatibility_status`

Fields needed mainly for Track B or C, such as display modes, bubble behavior, motion profiles, or proactive interaction hints, should be treated as reserved extension points rather than mandatory Track A payload requirements.

The resolved profile should be fetched through the dedicated buddy sub-resource. Existing `PersonaProfileResponse` payloads may later include summary pointers or cached fields if useful, but Track A should not require widening the current persona profile response contract to land the buddy system.

### 2. Lifecycle Rules

Buddy lifecycle is persona lifecycle, not pet lifecycle.

#### Create

When a persona is created, the system automatically derives and stores its buddy facet. No separate creation ceremony is required.

#### Existing Personas

Track A must also cover personas that already exist before the buddy facet ships.

The required behavior is lazy initialization on read or update:

- if the buddy sub-resource is requested for an existing persona and no buddy facet exists, the system derives and persists one before returning the resolved profile
- if an existing persona is updated and no buddy facet exists, the same derivation path applies

An optional background repair or backfill job may be added later for hardening, but Track A must not rely on a separate migration-only pass to satisfy the "every persona gets a buddy" rule.

#### Versioning Constraint

Lazy initialization must not create surprising optimistic-concurrency churn for the main persona profile.

Track A should therefore treat buddy persistence as independent from the current `PersonaProfileResponse.version` flow:

- lazy buddy initialization should not bump the main persona profile version
- fetching the buddy sub-resource may create or repair buddy state
- normal persona profile reads should not require write-back solely to surface buddy data

If Track A needs write-on-read behavior for buddy creation, that write should occur in buddy-specific storage rather than through the existing persona profile update path.

#### Update

When persona state changes in a way that affects the buddy, the buddy re-derives automatically.

This must be deterministic from persona state plus derivation version. The system should not leave stale buddy identity in place after relevant persona changes.

#### Overlay Preservation

When re-derivation occurs:

- compatible overlays should be preserved
- incompatible overlays should be replaced with the nearest valid default
- the UI should be able to communicate that a fallback occurred

#### Regeneration Semantics

There is no user-facing "invent a brand-new different buddy" action in the core model. Any future regenerate action should mean "recompute from current persona state," not "replace with an unrelated design."

### 3. Rendering Model

This section defines Track B direction only. It is included to constrain later planning and to make Track A extension points explicit. It is not part of the Track A implementation scope.

The product should render the same buddy across surfaces with mode-specific density rather than inventing separate persona images for each context.

#### Tier 1: Persistent Identity Surfaces

Examples:

- persona cards
- list rows
- headers
- selectors
- summary chips

Behavior:

- compact render
- minimal animation
- optimized for recognition and status
- click target may open buddy details or persona destination depending on context

#### Tier 2: Active Workspace Surfaces

Examples:

- Persona Garden
- companion/persona dashboards
- setup surfaces
- persona management panels

Behavior:

- larger anchored render
- limited idle animation
- contextual status cues
- optional proactive bubble hints

#### Tier 3: Direct Interaction Surfaces

Examples:

- active persona chat or live-session input areas
- focused persona control surfaces

Behavior:

- anchored near the interaction locus
- capable of reactive expression changes
- acts as entry point into the buddy interaction shell
- must remain minimizeable and dismissible

#### Cross-Surface Rules

- every tier must render the same resolved buddy identity
- animation intensity scales by tier
- offline or degraded states should fall back to a static or low-motion representation, not disappearance
- non-persona chat should not automatically receive buddy presence unless a real persona context is active

#### Coexistence With Existing Avatar Paths

Track B should coexist with the repo's existing `avatar_url`-based persona and assistant rendering paths rather than attempting an all-at-once replacement.

Rules:

- buddy-aware persona surfaces should prefer the resolved buddy profile for buddy rendering
- existing `avatar_url` fields may remain in place for legacy or non-buddy consumers
- Track B should not require immediate removal of `avatar_url` from existing persona summaries or assistant-selection flows
- when both exist, the buddy render is the canonical persona-face treatment, while `avatar_url` remains a compatibility path until later cleanup work chooses otherwise

### 4. Interaction Model

This section defines Track C direction only. It is included so Track A and Track B do not paint the product into the wrong corner. It is not part of the Track A implementation scope.

The buddy is an interaction shell for persona, not a separate conversational product.

#### Layer 1: Ambient Presence

The buddy can express:

- idle state
- mood or tone shifts
- presence or availability
- lightweight reactive emotes

These behaviors should be deterministic and cheap.

#### Layer 2: Guided Assistance

The buddy can surface short, state-aware prompts such as:

- setup guidance
- missing-connection explanations
- suggested next actions
- contextual reminders

These prompts should be driven primarily by product state and policy, not by open-ended generation.

#### Layer 3: Direct Buddy Interaction

The buddy should support an explicit interaction affordance, such as:

- expandable speech bubble
- micro-chat panel
- compact action sheet

This layer allows users to ask the persona quick questions through its buddy shell, for example:

- who this persona is
- what it can do
- what it remembers
- what it recommends next

Longer or more capable operations may delegate into persona behavior, but only after explicit user engagement.

#### Behavior Constraints

- buddy copy should match persona tone, but remain shorter and more UI-native than full chat
- unsolicited buddy prompts must be rate-limited
- prompts must be easy to dismiss, mute, or minimize
- the buddy may recommend actions but must not silently execute persona mutations

### 5. Derivation And Data Flow

The canonical flow should be:

1. Persona is created or updated.
2. Buddy derivation evaluates stable persona signals.
3. The system computes the `derived_core`.
4. The system merges stored `overlay_preferences`.
5. Invalid overlays are normalized to supported defaults.
6. The system publishes a `resolved_profile`.
7. All persona-facing surfaces render from the resolved profile.

This design intentionally avoids local client recomputation as the primary source of truth. Clients may compute transient animation state, but they should not independently decide species, silhouette, or canonical display profile.

### 6. Asset And Catalog Strategy

The user-supplied companion-pet suggestions are useful inspiration for the derivation taxonomy, but the initial design should not commit the first implementation plan to a giant fixed catalog.

Recommended day-one content strategy:

- define a small canonical species or silhouette taxonomy first
- ensure the taxonomy can expand without schema redesign
- treat hats, eyes, and display styles as overlay catalogs
- keep rendering contracts stable even if the art system changes from ASCII-inspired, vector, sprite, or hybrid forms later

This preserves room for the more playful direction without turning Track A into an asset-production project.

## Error Handling And Degradation

- If buddy derivation fails, the persona should fall back to a deterministic neutral default rather than showing no identity.
- If a requested overlay is incompatible, the resolved profile should fall back predictably and expose a compatibility note.
- If persona data is unavailable or the connection state is degraded, the UI should show a static buddy placeholder or last-known resolved form where safe.
- If interactive buddy features are unavailable, the buddy should remain usable as a visual identity marker.

## Testing

### Track A

Write tests for:

1. persona creation auto-generates a buddy facet
2. existing personas lazily receive a buddy facet on first eligible read or update
3. persona updates re-derive the core buddy identity
4. identical persona inputs yield stable derived output
5. compatible stored overlays are preserved across re-derivation
6. incompatible stored overlays fall back to supported defaults
7. resolved profile payloads are identical across fetches for the same persona state

### Track B

Write tests for:

1. compact and expanded render modes preserve recognizable identity
2. all persona-facing surfaces consume the same resolved payload shape
3. offline and degraded states fall back without layout breakage
4. non-persona chat does not render the buddy unintentionally

### Track C

Write tests for:

1. buddy prompts are rate-limited and dismissible
2. state-driven prompts render the expected guidance
3. direct buddy invocation opens the intended interaction shell
4. buddy actions do not silently mutate persona settings

Regression verification should include existing persona and companion route coverage so the buddy system does not destabilize current Persona Garden behavior.

## Risks

- If clients derive buddy identity locally, surfaces will drift and the persona will stop feeling canonical.
- If overlay scope is too permissive, users will effectively replace the buddy and break the "face of the persona" rule.
- If proactive buddy behavior ships before mute or minimize controls, the experience will feel intrusive.
- If the first implementation plan mixes identity, rendering, and interaction into one pass, the project will accumulate avoidable UI and state coupling.

## Recommendation

Proceed in three separate implementation plans:

1. establish the persona-owned buddy facet and resolved payload
2. build the shared cross-surface rendering system
3. add the buddy interaction shell on top of the stabilized rendering contract

The next implementation-planning step should target Track A only while preserving explicit extension points for Tracks B and C.
