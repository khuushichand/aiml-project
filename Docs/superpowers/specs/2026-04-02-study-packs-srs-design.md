# Study Packs And SRS Design

## Summary

This design adds a native `tldw` study workflow that turns source-backed workspace material into provenance-rich flashcard study packs with spaced repetition and contextual remediation.

V1 is intentionally focused on two outcomes:

- source-to-flashcards generation with exact evidence provenance
- due-review and remediation on top of the existing flashcards scheduler stack

The design does not treat Google Calendar or NotebookLM as product dependencies. Calendar support is provider-neutral and phased. NotebookLM is only conceptual inspiration, not an integration target.

## Goals

- Let users select supported workspace-backed sources and generate a study pack on demand.
- Reuse the existing flashcards and `SM-2`/`FSRS` review stack instead of building a second scheduler.
- Persist citation-grade provenance for generated flashcards so remediation can jump back to exact supporting evidence.
- Keep remediation on the same card rather than automatically creating new cards after a failed review.
- Support mixed-source study generation when all selected inputs can be resolved into durable evidence and locators.
- Leave room for later calendar adapters without making external calendar sync part of the V1 critical path.

## Non-Goals

- Literal integration with Google NotebookLM.
- Automatic background generation of study material when sources change.
- Automatic remediation-card creation when a learner answers incorrectly.
- A second independent review scheduler outside the existing flashcards system.
- Provider-synced free/busy placement into external calendars in V1.
- Universal support for every workspace object regardless of provenance quality.

## Requirements Confirmed With User

- This should be a native `tldw` feature, not a direct NotebookLM product integration.
- The first product slice should prioritize:
  - source-to-flashcards generation with contextual remediation
  - due-review behavior and SRS inside `tldw`
- Calendar support should be generic and not tied exclusively to Google Calendar.
- V1 source support should include any workspace object only when provenance can be preserved.
- Study generation should be user-triggered, not automatic.
- Failed reviews should keep the same card set and attach remediation behavior instead of auto-creating new cards.

## Current State

- The repo already has mature flashcard review primitives, including `SM-2` and `FSRS` scheduler helpers.
- Flashcards already support due reviews, next-card selection, study-assistant interactions, and deck-level scheduler configuration.
- Flashcards currently store only coarse source linkage through `source_ref_type` and `source_ref_id`.
- Quizzes already have a richer citation model with `source_citations` and a `source_bundle_json` concept.
- The current `flashcard_generate` workflow adapter is permissive and text-only. It does not require provenance or citation-safe outputs.
- The repo already has reminders, APScheduler-based services, Jobs infrastructure, and some provider OAuth/connector patterns.
- The repo can already emit calendar-compatible files such as `ics`, but there is no generic provider-neutral calendar abstraction for free/busy placement yet.

## Design Constraints Discovered During Review

### Pack Membership Constraint

`deck_id` alone is not enough to identify study-pack membership.

If packs append to existing decks, or if users manually edit deck contents later, then pack-scoped regeneration, analytics, delete behavior, and review summaries become ambiguous. V1 therefore needs explicit pack-to-card membership.

### Provenance Vocabulary Constraint

The existing flashcard provenance fields are too coarse for exact remediation links.

Current flashcard linkage is limited to `media`, `message`, `note`, or `manual`, while the user wants source support that can include derived workspace artifacts when provenance exists. V1 needs a shared study-provenance contract that is broader than the current flashcard enum and more flexible than the quiz-specific enum.

### Generation Safety Constraint

The current flashcard generator cannot be reused as-is for source-backed study packs.

It generates cards from free text and expects only a basic array of `front`/`back` pairs. That is acceptable for generic drafting, but not for citation-safe study generation where every card must be traceable back to allowed evidence.

### Sync And Restore Constraint

New persistence units must follow the existing sync/version conventions used by flashcards and other user data.

This repo expects `client_id`, `version`, `last_modified`, and sync-log participation for collaborative or multi-client safety. New tables that skip those conventions will drift from existing data flows immediately.

### Calendar Scope Constraint

Generic calendar support and provider-specific free/busy scheduling are not the same feature.

Provider-neutral support is realistic in V1 through internal study-session suggestions plus `ICS` export. Actual availability scanning requires provider-specific read/write integrations and must be phased separately.

## Approaches Considered

### Approach 1: Flashcards-First Extension

Extend the existing flashcards system with richer provenance, a study-pack orchestration layer, and remediation-aware study assistant behavior.

Pros:

- Reuses mature scheduler and review infrastructure
- Directly supports the user's `A+B` priorities
- Minimizes reinvention and keeps the review unit canonical
- Fits existing frontend and backend shapes

Cons:

- Requires provenance expansion beyond current flashcard fields
- Needs a stricter study-pack generation path than the current flashcard generator

### Approach 2: Quiz-First Study Workflow

Use quiz generation and quiz citations as the primary learning flow, then derive flashcards from incorrect or selected quiz questions.

Pros:

- Quizzes already have stronger citation modeling
- Incorrect-answer remediation is a natural fit for quiz flows

Cons:

- Spaced repetition becomes secondary instead of primary
- Duplicates functionality already owned by flashcards
- Moves the main experience away from the user's requested center of gravity

### Approach 3: New Standalone Revision Domain

Create a new review-item model, new scheduler state, and separate study-session product independent from flashcards.

Pros:

- Cleanest long-term domain model
- Maximum flexibility for future learning features

Cons:

- Highest scope and migration cost
- Unnecessary given the maturity of the existing flashcards stack
- Risks introducing parallel review systems

## Recommendation

Use Approach 1.

Build this as a flashcards-first study workflow with explicit study-pack orchestration and citation-grade provenance. Reuse the existing scheduler and review surfaces, but add new persistence and generation layers where the current flashcard model is too coarse.

## Proposed Architecture

### Product Shape

V1 adds a user-triggered `Generate Study Pack` workflow from supported workspace-backed material.

The system should create:

- a flashcard deck or append into an existing deck
- a study-pack record that captures the originating source bundle and generation options
- provenance-rich flashcards whose citations point back to supporting evidence
- remediation actions on reviewed cards that stay attached to the same card

Flashcards remain the canonical review unit. Study packs are orchestration and provenance containers, not a second scheduler.

### V1 Entry Points And Default Deck Policy

V1 should define one primary launcher and a small set of prefilled entry points.

Primary launcher:

- add a `Generate Study Pack` flow in the Flashcards workspace
- the launcher presents a supported-source picker limited to the V1 source classes defined below
- the launcher supports one or more selected supported sources so mixed-source bundles remain possible

Prefilled entry points:

- Notes: launch the study-pack flow from a note or selected excerpt
- Media: launch the study-pack flow from a media detail or source context
- Chat: launch the study-pack flow from a conversation or message action when stable source context exists

Default deck policy:

- default to `create new deck`
- offer `append to existing deck` as an explicit opt-in
- default deck title should derive from the study-pack title with collision-safe suffixing

This keeps V1 predictable, avoids accidental mixing of unrelated material, and still leaves room for advanced deck reuse.

### Core Components

Recommended units:

- `StudySourceResolver`
- `StudyPackGenerationService`
- `FlashcardProvenanceStore`
- `StudyPackCalendarService`

Responsibilities:

- `StudySourceResolver`
  - accepts selected workspace objects
  - resolves only supported objects into a canonical source bundle
  - rejects objects that cannot provide stable evidence and locators

- `StudyPackGenerationService`
  - creates or selects the destination deck
  - performs strict citation-safe card generation
  - validates and persists cards, pack metadata, membership, and citations

- `FlashcardProvenanceStore`
  - owns flashcard citation read/write behavior
  - resolves deep-dive targets from locators and workspace routes

- `StudyPackCalendarService`
  - computes internal study-session suggestions from due workload
  - emits `ICS` outputs in V1
  - defines provider-neutral interfaces for later adapters without implementing free/busy scanning yet

## Data Model

### Shared Provenance Contract

Introduce a shared study provenance contract rather than reusing the flashcard coarse fields or the quiz enum directly.

Recommended conceptual models:

- `StudySourceType`
- `StudyCitation`
- `StudySourceBundleItem`

Suggested `StudyCitation` shape:

- `source_type`
- `source_id`
- `label`
- `quote`
- `chunk_id`
- `timestamp_seconds`
- `source_url`
- `locator_json`

The contract should be broad enough to describe supported source-backed workspace objects, but V1 eligibility remains capability-based.

### New Tables

Recommended new persistence units:

- `study_packs`
  - `id`
  - `workspace_id`
  - `title`
  - `deck_id`
  - `source_bundle_json`
  - `generation_options_json`
  - `status`
  - `created_at`
  - `last_modified`
  - `deleted`
  - `client_id`
  - `version`

- `study_pack_cards`
  - `study_pack_id`
  - `flashcard_uuid`
  - `created_at`
  - `last_modified`
  - `deleted`
  - `client_id`
  - `version`

- `flashcard_citations`
  - `id`
  - `flashcard_uuid`
  - `ordinal`
  - `source_type`
  - `source_id`
  - `label`
  - `quote`
  - `chunk_id`
  - `timestamp_seconds`
  - `source_url`
  - `locator_json`
  - `created_at`
  - `last_modified`
  - `deleted`
  - `client_id`
  - `version`

### Why A Membership Table Is Required

Explicit `study_pack_cards` membership is required because:

- packs may append into an existing deck
- users may manually add, edit, move, or remove cards after generation
- future regeneration or pack deletion must act on the intended card set only

Without explicit membership, `study_pack.deck_id` becomes unreliable as soon as a deck contains cards from more than one generation event.

### Pack Lifecycle Rules

V1 should prefer retention-safe behavior over destructive cleanup.

Delete behavior:

- deleting a study pack should soft-delete the `study_pack` row and its `study_pack_cards` membership rows
- deleting a study pack should not automatically delete underlying flashcards, review history, or citations
- this avoids accidental data loss when cards were appended into an existing deck or already reviewed and edited

Regenerate behavior:

- regenerating a study pack should create a new pack record and a new generated card set
- the prior pack should be marked superseded, not mutated in place
- prior flashcards should remain intact unless a later explicit cleanup action is introduced

Append behavior:

- appending into an existing deck should still create a distinct `study_pack`
- `study_pack_cards` should contain only the cards created by that append run
- pack membership must remain stable even if the destination deck contains cards from other packs or manual edits

This keeps deletion, regeneration, and deck reuse deterministic without conflating pack lifecycle with card lifecycle.

### Backward Compatibility

The existing `flashcards.source_ref_type/source_ref_id` fields should remain as a backward-compatible summary only. They are not authoritative once multi-citation cards exist.

Primary citation rule:

- citations must be stored with an explicit `ordinal`
- `ordinal = 0` is the primary citation
- the generation and persistence layer should choose the primary citation deterministically using:
  - exact locator available
  - otherwise richest routeable source identifier
  - otherwise first valid citation returned after normalization

Legacy summary fields should mirror only the primary citation. Deep-dive routing and remediation should always read from `flashcard_citations`, not from legacy summary fields.

The new citation rows become canonical for deep-dive remediation and exact evidence rendering.

## Supported V1 Sources

V1 source support should be capability-based, not universal.

A source is eligible only if it can be resolved into:

- stable `source_type`
- stable `source_id`
- bounded evidence text
- at least one durable locator or graceful route fallback

Recommended initial V1 source classes:

- notes from the Notes system, including selected excerpts when available
- ingested media records with chunk, transcript, or timestamp locators
- chat conversations or individual chat messages with stable `conversation_id` and `message_id`

Selection surfaces for V1 should map directly to those entities:

- Notes surface selects note or excerpt inputs
- Media surface selects ingested media inputs
- Chat surface selects conversation or message inputs

No generic catch-all workspace artifact adapter should ship in V1.

Additional source classes should only be added later after their provenance and locator behavior are proven equivalent.

Examples that should remain unsupported until better provenance exists:

- ephemeral or synthesized outputs without durable evidence references
- arbitrary aggregated views that cannot map generated claims back to evidence

## Generation Flow

### Strict Study-Pack Generation Path

Do not reuse the current permissive `flashcard_generate` adapter directly.

Study-pack generation should be Jobs-backed in V1.

Reasoning:

- the feature is user-visible and potentially long-running
- mixed-source resolution plus LLM generation and validation can exceed comfortable synchronous request times
- the repo already treats user-visible longer-running work as a good fit for Jobs-backed execution
- Jobs-backed execution gives cleaner retry, progress, cancellation, and partial-failure handling than a blocking request

Recommended API shape:

- create study-pack generation job
- stream or poll job status
- persist the final `study_pack` only after validation succeeds
- expose failure state and repair diagnostics without partial visible data

Instead, add a new strict study-pack generation flow:

1. resolve selected sources into a canonical `source_bundle`
2. gather bounded evidence snippets and locator metadata
3. call a provenance-aware generation adapter that returns cards plus citations
4. validate every card before persistence
5. attempt one repair pass for malformed but salvageable outputs
6. reject the pack if citation safety cannot be restored
7. persist:
   - deck
   - flashcards
   - `study_packs`
   - `study_pack_cards`
   - `flashcard_citations`

### Validation Rules

Each generated card must satisfy:

- non-empty `front`
- non-empty `back`
- at least one citation
- citations reference only allowed bundle items
- citation rows contain enough information for a deep-dive route or graceful fallback

### Deck Policy

V1 should support both:

- `create new deck`
- `append to existing deck`

Because deck names are currently globally unique, the service must own a deterministic naming policy for auto-created decks. Suggested behavior:

- use a requested title when unique
- otherwise suffix with a collision-safe variant

Do not rely on workspace-local uniqueness because the underlying schema does not provide it today.

## Review And Remediation

### Scheduler Authority

The existing flashcard scheduler remains authoritative.

`FSRS` or `SM-2` continues to determine:

- queue state
- due timing
- interval previews
- review history

This design does not create a second scheduler or review-state system.

### Remediation Behavior

When a learner marks a card wrong or hard:

- the normal flashcard review transition runs first
- the system does not create new cards automatically
- the card exposes contextual remediation actions instead

Recommended remediation actions:

- `Explain from another angle`
- `Show supporting quote`
- `Deep dive to source`

### Study Assistant Integration

Extend the existing flashcard study-assistant context to include:

- citation rows for the card
- primary citation summary
- source-bundle context when the card belongs to a study pack

This lets remediation stay attached to the same card and use evidence-backed prompts rather than freeform assistant behavior.

### Deep-Dive Resolution

Preferred locator order:

1. exact locator such as `chunk_id`, anchor, or timestamp
2. direct workspace route using source identity
3. pack-level source detail or citation-only fallback

Deep dive should degrade gracefully if the underlying source moved or was deleted. The system should preserve citation text even when routing is no longer exact.

## Calendar And Scheduling

### V1 Scope

Provider-neutral calendar support in V1 means:

- internal study-session suggestions inside `tldw`
- `ICS` export or feed

It does not mean provider-synced free/busy placement.

### V1 Non-Goal

Do not promise automatic free-block scanning across external calendars in V1.

That requires provider-specific read/write integrations and availability APIs. It cannot be satisfied by `ICS` alone.

### Provider-Neutral Interface

Do not make provider adapter interfaces part of the V1 implementation plan if calendar sync is out of scope.

Instead, record the later expansion point here so Phase 3 can add interfaces such as:

- `CalendarScheduleAdapter.create_or_update_session(...)`
- `CalendarScheduleAdapter.delete_session(...)`
- `CalendarAvailabilityAdapter.find_candidate_slots(...)`

Only internal study-session suggestions and `ICS` export need implementation in V1. Availability scanning and provider adapters remain deferred until a real provider integration milestone exists.

### Provider Strategy

Later phases can implement:

- Google Calendar first
- Microsoft/Outlook or CalDAV-style adapters later

Google can be the first full adapter because the repo already has OAuth and connector precedents, but Google must not become the product model.

## Error Handling

### Generation Errors

- uncited or invalid cards
  - reject or repair before persistence
- unsupported source bundle item
  - fail fast with explicit source eligibility messaging
- provider or LLM failure
  - surface generation failure without partially-persisted packs

### Provenance And Routing Errors

- source moved or deleted
  - keep citation text and degrade link routing gracefully
- locator missing
  - route to the closest source detail page instead of failing hard

### Scheduler Errors

- invalid deck scheduler settings
  - reuse existing scheduler validation and error responses

### Calendar Errors

- `ICS` generation failure
  - keep internal schedule authoritative and report export failure
- future provider adapter failure
  - mark external sync degraded without corrupting the internal schedule

## Testing Strategy

### Unit Tests

- source resolution for each supported source class
- citation validation and repair behavior
- deep-dive locator resolution order
- pack membership semantics when appending to existing decks
- deck auto-naming and collision handling
- `ICS` session rendering

### Integration Tests

- generate a study pack from supported mixed sources
- verify persisted flashcards, pack membership, and citation rows
- review a card and request remediation actions
- deep-dive fallback when an exact locator is unavailable
- append a second pack into an existing deck without corrupting membership

### Regression Tests

- existing flashcard review endpoints still function for legacy cards without citation rows
- legacy `source_ref_type/source_ref_id` behavior remains intact
- sync/version behavior for new tables matches repository expectations

## Phased Delivery

### Phase 1

- strict source resolver
- study-pack persistence
- citation-grade flashcard generation
- flashcard remediation backed by stored citations

The first implementation plan should cover Phase 1 only.

### Phase 2

- internal study-session suggestion layer
- `ICS` export for generic calendar interoperability

### Phase 3

- provider-specific calendar adapters
- free/busy-aware slot suggestions

## Open Product Decisions For Later Planning

- how aggressively remediation actions should appear in the review UI
- whether pack analytics should be per-pack only or also per-source

These are implementation-planning details, not blockers for the current architecture.
