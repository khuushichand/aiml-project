# Persona Garden Phase 3 Chat Integration Design

Date: 2026-03-08
Status: Approved

## Summary

Design Phase 3 of Persona Garden so personas become first-class assistant identities in ordinary chat anywhere users can currently start a character chat.

The approved model is:

- ordinary chat can start with either a `Character` or a `Persona`
- persona-backed chats persist and display only the persona as the assistant identity
- existing character chats remain character-based when reopened
- Phase 3 persona-backed ordinary chat is single-assistant first, not a full replacement for every character-only group/diagnostic feature
- persona-backed ordinary chats use a mixed memory model:
  - read persona memory/state by default
  - only write back durable persona memory when the user explicitly enables it

## User-Confirmed Product Rules

1. Persona-backed chat should be available everywhere a user can currently start a normal character chat.
2. A persona-backed ordinary chat should store and display only the persona, not the originating character.
3. The chat assistant picker should become a tabbed surface with `Characters` and `Personas`.
4. Existing character-based chats should remain character-based when reopened.
5. Persona-backed ordinary chat should use mixed memory behavior:
   - read persona memory/state by default
   - only write persona memory when the user explicitly enables it

## Investigated Context

- The current ordinary chat stack is still keyed off `selectedCharacter` in:
  - `apps/packages/ui/src/routes/sidepanel-chat.tsx`
  - `apps/packages/ui/src/hooks/useSelectedCharacter.ts`
  - `apps/packages/ui/src/hooks/chat/useChatActions.ts`
- The current assistant picker is character-only in:
  - `apps/packages/ui/src/components/Common/CharacterSelect.tsx`
- Chat request schemas still model `persona_id` only as a deprecated alias to `character_id` in:
  - `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py`
- Conversation persistence is still character-shaped:
  - `conversations.character_id` is the persisted assistant relationship in
    `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Conversation list and metadata schemas currently expose `character_id`, not a normalized assistant identity, in:
  - `tldw_Server_API/app/api/v1/schemas/chat_conversation_schemas.py`

## Problem Statement

Persona Garden Phase 1 and Phase 2 made persona management and persona creation from characters explicit, but ordinary chat still assumes all assistant selection is character-based. That means the UI, request schemas, and persisted conversation model all treat characters as the only first-class assistant identity.

To make personas usable as ordinary chat assistants everywhere character chat starts, the system needs an explicit assistant identity model that can represent either a character or a persona without pretending persona chat is a disguised character chat.

## Goals

- Make personas first-class assistant identities in ordinary chat.
- Preserve existing character chat behavior for legacy conversations.
- Expose persona selection anywhere character chat can be launched today.
- Keep persona-backed ordinary chat separate from Persona Garden live-session mode.
- Support explicit per-conversation persona memory writeback control.

## Non-Goals

- Do not silently convert existing character chats into persona chats.
- Do not surface the originating character as the primary assistant identity in persona-backed chats.
- Do not overload the deprecated `persona_id` chat alias to mean full persona-backed ordinary chat.
- Do not make ordinary persona chat depend on Persona Garden websocket/live-session infrastructure.

## Evaluated Approaches

### Option 1: Explicit assistant identity model

Add a normalized assistant identity to chat persistence and chat APIs so a conversation can be either character-backed or persona-backed.

Pros:

- matches the approved product semantics exactly
- keeps reopen behavior deterministic
- keeps persona-backed chat independent from character-shaped persistence

Cons:

- requires schema, API, and UI state changes

### Option 2: Character compatibility bridge

Keep persisting ordinary chats as character chats and stash persona details in metadata.

Pros:

- smaller short-term change

Cons:

- violates the approved rule that persona-backed chats store and display only the persona
- creates immediate migration debt
- makes restore/history logic brittle

### Option 3: Route ordinary persona chat through Persona Garden live sessions

Treat persona-backed ordinary chat as a special case of the existing live persona session workflow.

Pros:

- strong persona semantics

Cons:

- over-couples ordinary chat to the live persona runtime
- much higher regression risk

## Approved Approach

Use Option 1: introduce an explicit assistant identity model for ordinary chat.

This allows:

- character chats to remain character chats
- persona chats to be persona chats
- reopen behavior to restore the correct assistant type
- mixed persona memory behavior to be stored at the conversation level

## Approved Assistant Identity Model

Ordinary chat conversations should persist a normalized assistant identity:

- `assistant_kind`: `character` or `persona`
- `assistant_id`: the selected character ID or persona profile ID

Compatibility rules:

- existing `character_id` remains temporarily during migration and rollout
- legacy conversations that only have `character_id` are treated as character chats
- new persona-backed chats persist as `assistant_kind=persona`
- new character-backed chats persist as `assistant_kind=character`

Persona-backed ordinary chats do not persist or display the source character as the active assistant identity.

## Minimum Persona Chat Projection

Phase 3 ordinary chat cannot assume the full character card shape exists on persona profiles. The current persona profile model does not include character-style greeting, alternate greetings, avatar/image, or extension payloads, while the existing ordinary-chat UI and runtime frequently assume those fields exist.

Because of that, Phase 3 needs an explicit assistant-facing persona chat projection.

Required projection fields:

- `id`
- `kind = persona`
- `display_name`
- prompt/state inputs required to build the assistant system layer

Optional projection fields:

- `avatar_url`
- `greeting`
- `extensions`

Fallback rules for the initial rollout:

- if a persona has no avatar, use the generic assistant avatar path
- if a persona has no greeting, ordinary chat does not inject a greeting
- if a persona has no character-style extensions payload, character-only extension features stay disabled

Important constraint:

- persona-backed ordinary chat must not require a live lookup of the mutable source character row in order to function
- if future richer persona fields are added, they should attach to persona-owned data or persona-owned snapshots, not recreate live source-character dependence

## Picker And Entry Point UX

The ordinary chat assistant picker should become a tabbed surface:

1. `Characters`
2. `Personas`

This model should apply anywhere the user can currently start a normal character chat.

Behavior:

- selecting a character starts a character-backed chat
- selecting a persona starts a persona-backed chat
- the selected assistant state in the UI becomes a generalized assistant selection, not character-only state

Reopen behavior:

- reopening an existing character chat restores the character selection and `Characters` tab
- reopening an existing persona chat restores the persona selection and `Personas` tab
- existing character chats are never silently converted

Primary assistant display:

- persona-backed chats show only the persona in normal chat chrome
- source-character provenance, if shown at all, belongs in deeper metadata rather than the main assistant identity

## Runtime Behavior

Persona-backed ordinary chat should use the persona as the assistant definition for prompt assembly and response generation, but it should not be implemented as a Persona Garden live session.

Character-backed chat:

- keeps current behavior

Persona-backed chat:

- loads the persona chat projection as the assistant definition
- applies persona-owned overlays and state where relevant
- does not require Persona Garden websocket/live-session behavior

This preserves Persona Garden live sessions as the richer operational workspace while allowing ordinary chat to use personas as first-class assistants.

## Character-Specific Feature Boundary For Initial Rollout

The current ordinary chat stack contains multiple behaviors that are explicitly character-shaped. Phase 3 should not silently inherit all of them for persona chats without defining how each one maps.

Phase 3 initial rollout should support:

- single-assistant ordinary persona chat
- ordinary chat persistence and restore
- prompt assembly using persona-owned state/system layers
- explicit persona memory mode

Phase 3 initial rollout should treat the following as character-only until explicit persona-aware mappings are added:

- directed-character and participant-routing behavior
- `speaker_character_id` assistant metadata and related mood/speaker persistence
- character greeting selection workflows
- character/world-book and lorebook diagnostics that require a character ID
- character-preset or character-fallback editor workflows that assume `selectedCharacter`

Implementation rule:

- where a character-only feature has no persona-safe mapping, the UI must hide or disable it for persona-backed chats rather than silently falling back to the source character

## Persona Memory Modes

Persona-backed ordinary chats store a per-conversation memory mode:

- `read_only`
- `read_write`

Default:

- new persona-backed ordinary chats start as `read_only`

Semantics:

- `read_only`
  - the chat may read persona memory/state for context
  - ordinary chat turns do not write durable persona memory
- `read_write`
  - the chat may read persona memory/state for context
  - ordinary chat turns may write durable persona memory back to the persona

The transition from `read_only` to `read_write` must be explicit in the chat UI.

Character-backed chats do not use persona memory mode.

## Migration Strategy

- add new conversation persistence fields for assistant identity and persona memory mode
- backfill existing conversations as character-backed conversations
- keep `character_id` temporarily for compatibility
- chat read paths should prefer normalized assistant identity fields when present
- persona-backed chats should write the new fields from day one

## Compatibility Rules

- old clients continue to function for legacy character conversations
- persona-backed ordinary chat UI should be capability-gated if backend support is absent
- the deprecated `persona_id` alias should stay deprecated and should not be repurposed as the new assistant identity contract

## Rollout Strategy

### Slice 1: Backend identity and persistence contract

- add assistant identity fields and persona memory mode
- backfill legacy character chats
- expose normalized assistant identity through read/write APIs

### Slice 2: Persona chat projection and compatibility boundary

- define the minimum persona chat projection ordinary chat can rely on
- add explicit fallback behavior for avatar/greeting/media gaps
- define which character-only runtime features stay disabled in the initial rollout

### Slice 3: Shared assistant selection abstraction

- replace character-only selection state with assistant selection state that can represent either characters or personas

### Slice 4: Tabbed picker rollout

- adapt the current character picker into the `Characters` tab
- add a `Personas` tab
- expose persona-backed chat start wherever character-backed chat start exists

### Slice 5: Persona memory mode controls

- default new persona chats to `read_only`
- add explicit opt-in for `read_write`

### Slice 6: Compatibility cleanup

- reduce legacy `character_id` dependence after rollout proves stable

## Testing Strategy

### Backend

- validate `assistant_kind`, `assistant_id`, and `persona_memory_mode`
- test conversation migration/backfill for legacy character chats
- test persona-backed prompt assembly
- test read-only vs read-write persona memory behavior

### Frontend

- assistant picker tabs render and restore correctly
- starting a persona-backed chat persists and restores persona selection
- reopening legacy character chats keeps them character-based
- persona memory writeback remains explicit
- character-only settings and diagnostics surfaces are either migrated or intentionally hidden for persona-backed chats

### Integration And E2E

- start persona-backed chats from every existing character-chat entry surface
- reopen persona-backed chats and restore the persona
- reopen old character chats and keep them character-based
- verify ordinary persona chat does not require Persona Garden live-session UI

## Risks And Mitigations

### Risk: hidden character-shaped compatibility leaks into persona chat

Mitigation:

- persist normalized assistant identity explicitly
- avoid treating the deprecated `persona_id` alias as the new feature

### Risk: existing conversation reopen behavior regresses

Mitigation:

- preserve legacy character chat backfill rules
- add restore-path tests for both assistant kinds

### Risk: persona memory writes happen implicitly

Mitigation:

- default persona ordinary chat to `read_only`
- require explicit opt-in before durable writeback

## Approved Outcome

Phase 3 should make personas first-class assistant identities in ordinary chat through an explicit assistant identity model, a tabbed `Characters | Personas` picker, and per-conversation persona memory modes, while preserving legacy character chat behavior and keeping Persona Garden live sessions as a separate advanced mode.
