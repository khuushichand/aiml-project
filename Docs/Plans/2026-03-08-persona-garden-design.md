# Persona Garden Design

Date: 2026-03-08
Status: Approved

## Summary

Design a first-class `Persona Garden` page for the WebUI and extension that exposes persona configuration and customization without conflating persona with either the user's chat identity or standard character chat.

The approved model is:

- `My Chat Identity` is the user's self-representation in chat.
- `Character` is the base assistant definition used in normal chat.
- `Persona` is a derived, advanced assistant artifact created from a character and then evolved independently with its own state, memory, policies, and media.

## Investigated Context

- The WebUI and extension already expose a shared `/persona` route:
  - `apps/tldw-frontend/pages/persona.tsx`
  - `apps/tldw-frontend/extension/routes/sidepanel-persona.tsx`
  - `apps/packages/ui/src/routes/sidepanel-persona.tsx`
- The existing `/persona` route is a live persona workflow, not only a settings page:
  - persona catalog selection
  - session creation/resume
  - memory and state-context toggles
  - live websocket messaging
  - tool-plan confirmation
  - state-doc editing and history restore
- Normal chat currently uses:
  - `selectedCharacter` for assistant selection
  - local user display name, avatar, and prompt-template settings for user-side identity
- Backend persona profiles already support a link to a source character via `character_card_id`, but normal chat does not currently consume persona profiles as first-class chat startup state.

## User-Confirmed Product Rules

1. Persona is not the user.
2. The user's chat identity is separate from persona.
3. Persona is conceptually `character++`, but not as a permanent live dependency.
4. A persona is created from a character, then becomes its own thing.
5. Once created, a persona should not continue to rely on the source character.
6. Persona-owned memories and state must be able to evolve independently.
7. The UI/page name should be `Persona Garden`.

## Problem Statement

The repo already contains persona capabilities, but the current UX does not explain the relationship between user identity, characters, and personas clearly enough. The existing `/persona` route also behaves more like a live agent console than a branded configuration workspace, while normal chat still stores user-side identity settings locally and separately.

Without a clearer information architecture, users are likely to confuse:

- the user identity they present in chat,
- the character they are chatting with,
- and the persona profiles used for advanced scoped/live assistant behavior.

## Design Goals

- Establish a clear mental model for `My Chat Identity`, `Characters`, and `Persona Garden`.
- Preserve the current live persona-session workflow instead of regressing it.
- Reframe personas as advanced derived artifacts seeded from characters.
- Expose persona configuration and customization in a dedicated branded workspace.
- Support WebUI and extension parity through shared UI components and shared route behavior.

## Non-Goals

- Do not redefine persona as the user's self-identity.
- Do not make persona the same thing as standard character chat.
- Do not imply that ordinary chat already runs through persona profiles automatically.
- Do not add whimsical garden-themed microcopy that obscures function.
- Do not silently sync local user-identity settings to the server without explicit backend support.

## Key Constraints Discovered During Review

### 1. Persona is not wired into standard chat today

In normal chat, `persona_id` is only a deprecated alias for `character_id`; it is not the new persona profile system. That means the design cannot claim that persona presets already drive ordinary chat startup.

### 2. User chat identity is local today

Display name, user avatar, and user-side prompt templates currently live in client storage, not in persona profile storage.

### 3. `/persona` is already a live workflow

The shared route already supports session selection, websocket streaming, memory toggles, state-context toggles, pending tool-plan approval, state docs, and state history. Any redesign must preserve that behavior.

### 4. Persona creation can reference characters, but persona must become independent

Persona profiles can reference `character_card_id`, which supports a `created from character` flow. However, the approved product rule is that personas should fork from their source character rather than remain live-bound to it.

## Approved Domain Model

### My Chat Identity

Represents the user in standard chat.

Owns:

- user display name
- user avatar/image
- user-side prompt templates such as continue-as-user / impersonate-user / force-narrate

Does not own:

- character definitions
- persona profiles
- persona memory/state/policy data

### Character

Represents the base assistant definition used in standard chat.

Owns:

- reusable assistant identity
- greeting/personality/system prompt
- base images and related metadata

### Persona

Represents an advanced assistant artifact derived from a character snapshot and then evolved independently.

Owns:

- persona-specific system/state overlays
- persona state docs
- persona policy rules
- persona scope rules
- persona-owned long-term/session memory
- persona-specific media/voice additions
- persona live sessions

### Persona Lifecycle

The approved lifecycle is:

1. User creates or selects a character.
2. User creates a persona from that character.
3. Character fields are copied or snapshotted into the persona seed.
4. Persona evolves independently afterward.

Implications:

- editing the source character does not automatically mutate existing personas
- editing a persona does not mutate the source character
- persona memory belongs to the persona
- any future `refresh from source` behavior must be explicit, manual, and diff-based

## Naming And Framing

### UX Name

Use `Persona Garden` as the user-facing page/workspace name.

### Technical Naming

Keep backend and code terminology as `persona`, `persona profile`, and `persona session`.

### Recommended Header Copy

- Title: `Persona Garden`
- Subtitle: `Grow advanced personas from base characters.`
- Explanatory helper text: `A persona is a character-derived assistant with its own memory, state, and scoped behavior.`

### Copy Constraints

Use the garden metaphor for page framing only. Avoid themed action labels that reduce clarity.

Good:

- `Persona Garden`
- `Create Persona from Character`
- `Origin: created from ...`

Avoid:

- `Plant persona`
- `Water memory`
- `Harvest session`

## Information Architecture

The approved top-level product split is:

- `My Chat Identity`
- `Characters`
- `Persona Garden`

These must remain separate concepts in both WebUI and extension.

### Quick Surface In Chat And Extension

The chat-level quick surface should expose `My Chat Identity`, not persona.

Recommended contents:

- `Your name`
- `Your image`
- `Prompt style templates`

The chat UI may still provide links to:

- `Characters`
- `Persona Garden`

But those are separate destinations, not nested identity settings.

### Characters Workspace

Characters remain the place to define and manage the base assistant identity used for standard chat.

Recommended additions:

- `Create Persona from Character`
- `Open in Persona Garden`

### Persona Garden

Persona Garden remains the dedicated advanced workspace and should preserve current live persona behavior while improving organization.

Recommended top-level sections:

1. `Live Session`
2. `Profiles`
3. `State Docs`
4. `Scopes`
5. `Policies`

Optional overview elements may summarize provenance and active status, but they should not displace the current live-session workflow.

## Persona Garden Structure

### Live Session

Preserve the current route's operational workflow:

- persona selection
- connect/disconnect
- resume session
- memory toggle for the current persona session
- memory top-k for the current persona session
- state-context toggle for the current persona session
- websocket chat log
- pending tool-plan review and confirmation
- session history loading

This is not optional. The redesign must keep `Persona Garden` useful as a live workflow surface, not only a settings page.

### Profiles

Manage persona profile records:

- list personas
- create persona
- rename persona
- archive/delete persona
- activate/deactivate persona if applicable
- show origin/provenance

Recommended provenance labels:

- `Origin: created from <character>`
- `Created from character: <name>`

Avoid labels that imply live inheritance, such as `currently based on`.

### State Docs

Expose and preserve the current persona-owned state-doc functionality:

- soul
- identity
- heartbeat
- version history
- restore flow

### Scopes

Manage persona-specific access boundaries and scoped data rules.

This must remain an advanced surface and should not appear in quick chat identity controls.

### Policies

Manage persona-specific tool/skill policies, confirmations, and allowed capabilities.

This also remains an advanced surface and should not appear in quick chat identity controls.

## Persona Creation Flow

### Recommended Primary Flow

`Create Persona from Character`

The preferred user flow is:

1. User opens Characters.
2. User chooses an existing character or creates one.
3. User creates a new persona from that character.
4. Persona Garden opens with the newly created independent persona.

### Independence Rules

At creation time, persona should be seeded from a snapshot of the source character rather than stay live-bound to it.

That means implementation should prefer:

- copied seed fields
- provenance metadata
- explicit source reference for history/audit

Rather than:

- automatic live inheritance
- silent synchronization from character to persona

### Future-Safe Optional Behavior

If the product later wants a `Refresh from source character` action, it must:

- be explicit
- show field-level diffs
- never run automatically

## WebUI And Extension Parity

The same conceptual structure should apply to both surfaces:

- separate user identity from persona
- expose `Persona Garden` as its own destination
- preserve the shared `/persona` route contract

Recommended parity behavior:

- WebUI page label: `Persona Garden`
- Extension route label can be `Persona` when space is tight, but the page header should read `Persona Garden`
- Shared route/component structure should remain the source of truth for persona workspace behavior

## Rollout Strategy

### Phase 1: Clarify Existing Concepts

- Make `My Chat Identity` explicit in chat/extension UI.
- Keep it separate from Characters and Persona Garden.
- Rename/reframe `/persona` as `Persona Garden`.
- Reorganize Persona Garden IA while preserving live-session behavior.

### Phase 2: Character To Persona Workflow

- Add `Create Persona from Character` and `Open in Persona Garden` flows from Characters.
- Surface origin/provenance clearly in Persona Garden.
- Establish persona independence semantics at creation time.

### Phase 3: Optional Deeper Integration

Only if product later decides that ordinary chat should launch with persona-derived state.

This requires explicit backend and chat integration work and is not assumed by this design.

## Error Handling

- If persona capability is unavailable, keep Persona Garden hidden or capability-gated using the existing capability checks.
- If live session connect fails, Persona Garden configuration sections should still work when their APIs are available.
- If a persona lacks source-character provenance, treat it as a standalone legacy persona and allow it to continue functioning.
- If a source character is later deleted, the persona remains valid because it is an independent derivative.
- If a future manual refresh-from-source feature exists, it must block destructive overwrites behind confirmation and diff review.

## Testing Strategy

### Unit And Component Tests

- Verify separation between `My Chat Identity`, `Characters`, and `Persona Garden`.
- Verify Persona Garden preserves live-session controls after IA refactor.
- Verify persona provenance is displayed correctly.
- Verify legacy personas without source-character metadata still render safely.

### Integration Tests

- Create persona from character flow
- Persona Garden IA sections/tabs
- State-doc edit/history/restore
- Scope and policy editing
- Live session connect/resume behavior after refactor

### End-To-End Tests

- WebUI exposes `Persona Garden`
- extension exposes `Persona Garden` or `Persona` route with `Persona Garden` header
- persona creation from character leads to an independent persona record
- editing user identity does not modify persona
- editing persona does not modify source character
- standard chat identity and standard character chat remain unaffected by persona-session actions

## Acceptance Criteria

- Users can clearly distinguish `My Chat Identity`, `Characters`, and `Persona Garden`.
- `Persona Garden` is the branded page name for the advanced persona workspace in WebUI and extension.
- The current `/persona` live workflow remains functional after IA improvements.
- Personas are created from characters through an explicit user flow.
- Personas are treated as independent derivatives after creation.
- Persona-owned memory, state, policy, and media are not modeled as live inherited character state.
- No part of the UX implies that persona is the user.
- No part of the UX implies that ordinary chat already runs through persona profiles automatically.
