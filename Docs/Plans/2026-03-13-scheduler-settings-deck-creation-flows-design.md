# Scheduler Settings In Deck Creation Flows Design

Date: 2026-03-13  
Status: Approved

## Summary

This slice extends scheduler configuration from the dedicated `Scheduler` tab into deck-creation flows.

The goal is to let users choose scheduler behavior when they create new flashcard decks, instead of creating decks with implicit defaults and fixing them later.

The design covers:

- explicit inline deck creation in the flashcard create drawer
- flashcards import/generate/image-occlusion deck creation from the target-deck selector
- quiz remediation deck creation when converting missed questions into flashcards

It does not replace the existing `Scheduler` tab. That tab remains the full editor for existing decks.

## Current Baseline

The backend already supports scheduler settings on deck create and deck update.

The current UI gap is that most deck-creation flows either:

- create a deck with name only, or
- silently auto-create a deck with backend defaults

Relevant code anchors:

- `apps/packages/ui/src/services/flashcards.ts`
- `apps/packages/ui/src/components/Flashcards/hooks/useFlashcardQueries.ts`
- `apps/packages/ui/src/components/Flashcards/utils/scheduler-settings.ts`
- `apps/packages/ui/src/components/Flashcards/tabs/SchedulerTab.tsx`
- `apps/packages/ui/src/components/Flashcards/components/FlashcardCreateDrawer.tsx`
- `apps/packages/ui/src/components/Flashcards/tabs/ImportExportTab.tsx`
- `apps/packages/ui/src/components/Flashcards/tabs/ImageOcclusionTransferPanel.tsx`
- `apps/packages/ui/src/components/Quiz/tabs/ResultsTab.tsx`
- `apps/packages/ui/src/services/quizzes.ts`
- `tldw_Server_API/app/api/v1/schemas/flashcards.py`
- `tldw_Server_API/app/api/v1/endpoints/flashcards.py`
- `tldw_Server_API/app/api/v1/schemas/quizzes.py`
- `tldw_Server_API/app/api/v1/endpoints/quizzes.py`
- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`

## Product Decision

Use one shared scheduler-creation editor across deck-creation flows.

Do not embed the full `Scheduler` tab in each creation surface.

Do not limit creation-time scheduler control to presets only.

Do not leave quiz remediation as a default-only exception.

This gives users the best outcome because:

- new decks can start with the right scheduler immediately
- all major deck-creation surfaces behave consistently
- the existing `Scheduler` tab remains the one place for deep edits after creation

## Recommended Approach

Add a shared compact scheduler editor for creation flows and reuse the existing scheduler draft utilities.

The creation flows should all support:

- deck name
- preset selection
- scheduler summary
- optional advanced custom settings

The shared editor should be used by:

- flashcard create drawer inline new-deck flow
- structured import target deck selector
- generated-cards target deck selector
- image-occlusion target deck selector
- quiz remediation "create new deck" modal path

The `Scheduler` tab remains the edit surface for existing decks.

## Scope Clarification

This slice includes both flashcards and quiz remediation deck creation.

It does not add a new standalone deck-management modal.

It does not add scheduler editing for already-selected decks inside each flow. Existing decks stay read-only in these surfaces, with a visible scheduler summary and a pointer to the `Scheduler` tab.

## Shared Scheduler Editor

Extract a reusable embeddable scheduler editor instead of reusing `SchedulerTab` directly.

New shared pieces:

- `DeckSchedulerSettingsEditor`
- `useDeckSchedulerDraft`

The shared hook should wrap:

- `createSchedulerDraft`
- `validateSchedulerDraft`
- preset application
- reset-to-defaults
- draft/error state

The shared component should support a compact creation mode:

- preset selector
- summary preview
- optional advanced editor accordion

It should reuse the same field labels, validation rules, and preset behavior as the existing `Scheduler` tab so the UI cannot drift.

## Create-Deck Contract

The frontend create-deck contract should be tightened to use a full scheduler settings object when the field is present.

V1 decision:

- `useCreateDeckMutation()` accepts `scheduler_settings?: DeckSchedulerSettings`
- creation flows must submit fully validated scheduler settings
- do not send partial scheduler payloads from create flows

This matches the backend model more closely and removes ambiguity about which side is responsible for default-filling.

## Flashcards Create Drawer

The inline `Create new deck` path in `FlashcardCreateDrawer.tsx` should expand from name-only creation to:

- deck name
- scheduler preset selector
- compact scheduler summary
- advanced scheduler settings when expanded

Behavior:

- validation must happen before calling create
- successful create selects the new deck in the flashcard form
- cancel must clear both deck-name and scheduler draft state

## Import, Generate, And Image-Occlusion Flows

The current import/generate/image-occlusion tabs only auto-create a deck when no decks exist.

That is not enough for this slice.

V1 decision:

- add a `__new__` option to target-deck selectors in:
  - structured import
  - generated cards
  - image occlusion
- when `__new__` is selected, render a new-deck configuration block inline
- the configuration block contains:
  - deck name
  - preset selector
  - scheduler summary
  - optional advanced scheduler editor

This lets users create a new deck with scheduler settings even when other decks already exist.

### Selector State Rules

The existing "default to first deck" effects must become sentinel-aware.

Rules:

- initial default may still select the first existing deck
- once the user chooses `__new__`, the selector state must not be overwritten by the auto-default effect
- deck creation block state must persist while `__new__` remains selected
- switching back to an existing deck hides the creation block without mutating the chosen existing deck

These rules are required to avoid clobbering user intent.

## Quiz Remediation Deck Creation

Quiz remediation already supports `target_deck_id` or `create_deck_name`.

This slice extends that creation path so a new remediation deck can also receive scheduler settings.

Request extension:

- `create_deck_scheduler_settings?: DeckSchedulerSettings | null`

Rules:

- only valid when `create_deck_name` is provided
- ignored or rejected when `target_deck_id` is used
- create-deck scheduler settings are applied only to the newly created deck

UI behavior in `ResultsTab.tsx`:

- when the user chooses `Create new deck`, render the same shared scheduler creation block below the deck-name input
- when an existing deck is selected, show a read-only scheduler summary for that deck

This keeps remediation deck creation consistent with the flashcards surfaces.

## Existing Deck Visibility

When an existing deck is selected in any creation surface, show:

- a short scheduler summary
- lightweight text pointing to the `Scheduler` tab for edits

V1 should not allow inline editing of existing deck scheduler settings in these creation flows.

That keeps the scope focused and avoids mixing create-time and edit-time concerns.

## Validation And Error Handling

Validation should remain local to the creation surface until the user submits.

Behavior:

- invalid scheduler drafts block deck creation
- create-flow validation errors stay local to that flow
- deck-create request errors still use the existing mutation error path
- remediation create-deck errors should stay in the remediation modal and not clear selection state

## Backend Changes

Flashcards create-deck backend already supports scheduler settings, so no flashcards API change is required.

Quiz remediation does require a small backend extension:

- add `create_deck_scheduler_settings` to the remediation convert request schema
- thread it through the remediation convert endpoint and DB helper
- pass those settings into the deck creation call when `create_deck_name` is used

No other scheduler backend behavior changes are needed in this slice.

## Testing Strategy

Frontend tests should cover:

- `useCreateDeckMutation` forwarding full scheduler settings
- flashcard create drawer inline deck creation with scheduler settings
- structured import `__new__` deck creation with scheduler settings
- generated cards `__new__` deck creation with scheduler settings
- image occlusion `__new__` deck creation with scheduler settings
- quiz remediation `Create new deck` with scheduler settings
- selector sentinel state not being overwritten by default-deck effects
- existing deck scheduler summary rendering in each creation surface

Backend tests should cover:

- remediation convert request accepting `create_deck_scheduler_settings`
- remediation-created decks storing the provided scheduler settings
- rejecting invalid create-deck scheduler payloads through existing schema validation

## Non-Goals

This slice does not include:

- inline editing of existing deck scheduler settings in create/import flows
- a new dedicated deck-management modal
- changing deck scheduler settings from the quiz side after deck creation
- changing flashcards routing or the `Scheduler` tab architecture

## Success Criteria

This slice is complete when:

- all supported new-deck flows can create a deck with explicit scheduler settings
- import/generate/image-occlusion flows support `Create new deck` even when decks already exist
- quiz remediation can create a new deck with scheduler settings
- existing selected decks show a scheduler summary without becoming editable in-place
- the UI submits full validated scheduler settings instead of partial create payloads
