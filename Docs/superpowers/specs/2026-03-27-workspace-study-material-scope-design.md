# Workspace Study Materials Scope Design

## Summary

This design introduces a workspace-level study-materials policy that controls where newly generated quizzes and flashcards live by default:

- `general`: generated study materials join the general Quiz and Flashcards collections
- `workspace`: generated study materials belong to one workspace and are hidden by default on the main Quiz and Flashcards pages unless the user enables workspace visibility filters

The design keeps Quiz and Flashcards as the canonical storage locations. Workspace generation creates real persisted records in those modules rather than temporary workspace-only copies. Users can later move a quiz or flashcard deck between general scope and a single workspace.

## Goals

- Make workspace-generated quizzes and flashcards real server-side objects in their native modules.
- Ensure workspace-generated quizzes are persisted as one quiz record per generation run, even when built from multiple selected sources.
- Let users open generated quizzes and flashcards from both the workspace page and their native Quiz or Flashcards pages.
- Keep workspace-owned materials isolated by default on main pages while still discoverable through filters.
- Allow users to change scope after creation.

## Non-Goals

- Supporting one quiz or deck in multiple workspaces at the same time.
- Creating a second storage namespace for workspace study materials.
- Adding workspace ownership to individual flashcards independent of their deck.

## Current State

- Workspace quiz generation persists one quiz per selected media item and merges the questions into a single workspace artifact.
- Workspace flashcard generation persists cards into a deck, but deck ownership is not modeled as workspace-specific.
- Quizzes already support `workspace_tag` and mixed-source metadata through `source_bundle_json`.
- Flashcards and decks do not currently have a first-class workspace-scoping model in the UI flow.

## Requirements Confirmed With User

- Workspace should define the default study-materials policy.
- Workspace-only materials should be hidden by default on the main Quiz and Flashcards pages, but visible behind filters.
- Flashcard isolation should be deck-level.
- Workspace-only quizzes should be one persisted quiz record attributable to a workspace, while existing `workspace_tag` support can remain as a compatibility layer during migration.
- Users should be able to change scope after creation.
- A quiz or deck belongs to at most one workspace at a time.

## Approaches Considered

### Approach 1: First-Class Workspace Ownership On Existing Records

Add explicit workspace-ownership metadata to quizzes and flashcard decks. Keep the existing Quiz and Flashcards modules as the only canonical storage. Main pages remain unified and filterable.

Pros:

- Single source of truth
- Minimal duplication
- Straightforward move-to-workspace and move-to-general behavior
- Fits existing `workspace_tag` support in quizzes

Cons:

- Requires coordinated changes across workspace generation and the main Quiz and Flashcards views

### Approach 2: Separate Workspace Collections With Promotion

Store workspace-owned quizzes and flashcards separately, then let users promote them into the general collection later.

Pros:

- Strong separation

Cons:

- Higher complexity
- Duplication and sync problems
- Harder cross-page navigation and ownership transitions

### Approach 3: Tag-Only Ownership

Represent scope using only tags or naming conventions.

Pros:

- Fastest to add

Cons:

- Weak invariants
- Easy for users and code paths to drift out of consistency
- Hard to enforce deck-level ownership rules

## Recommendation

Use Approach 1.

Add canonical workspace ownership to quizzes and flashcard decks, keep native modules canonical, and make main-page filtering responsible for default visibility.

## Proposed Data Model

### Workspace

Add a workspace-level `studyMaterialsPolicy`:

- `general`
- `workspace`

This policy is inherited automatically by workspace generation flows.

### Quiz

Use one canonical ownership field:

- `workspace_id`: nullable stable workspace identifier

General scope is derived from `workspace_id = null`.

Compatibility and display metadata:

- `workspace_tag`: optional derived label or compatibility field
- if retained, it must not be the canonical ownership field

Quizzes remain single records. A workspace-generated multi-source quiz is stored as one persisted quiz with:

- one `quiz.id`
- `source_bundle_json` referencing the selected source bundle
- `workspace_id` populated only when workspace-owned
- `workspace_tag` populated only as a derived display or compatibility value when needed

### Flashcard Deck

Add deck-level ownership metadata with the same model:

- `workspace_id`: nullable stable workspace identifier
- optional derived `workspace_tag` only if needed for compatibility or display

Cards inherit effective ownership from the deck.

### Flashcard Card

Do not add separate workspace ownership fields. Cards continue to reference:

- `deck_id`
- `source_ref_type`
- `source_ref_id`

Deck ownership determines visibility and movement behavior.

## UX And Behavior

### Workspace Settings

Each workspace exposes a default study-materials policy:

- Save generated study materials to the general collection
- Keep generated study materials owned by this workspace

### Workspace Quiz Generation

Workspace quiz generation should:

- create exactly one persisted quiz record for the full selected-source bundle
- store mixed-source provenance in `source_bundle_json`
- apply `workspace_id` based on the workspace policy
- optionally populate a derived `workspace_tag` for compatibility with existing quiz flows
- return a workspace artifact that links to the real quiz record

### Workspace Flashcard Generation

Workspace flashcard generation should:

- generate a real persisted deck and cards
- create a workspace-owned deck when the workspace policy is `workspace`
- create or target a general deck when the policy is `general`
- return a workspace artifact that links to the real deck

Default behavior for workspace-owned flashcards should be:

- create a fresh workspace-owned deck per generation run unless the user explicitly selected an existing target deck
- assign a legible default name such as `<workspace name> - Flashcards - <source bundle title/date>`
- prefer bulk card creation when the API supports it

This avoids accidental mixing across unrelated study sets.

### Main Quiz Page

Default listing behavior:

- show general quizzes by default
- hide workspace-owned quizzes by default

Controls:

- `Show workspace quizzes`
- workspace filter dropdown

Management actions:

- `Move to general collection`
- `Assign to workspace`

### Main Flashcards Page

Default listing behavior:

- show general decks by default
- hide workspace-owned decks by default

Controls:

- `Show workspace decks`
- workspace filter dropdown

Management actions on decks:

- `Move to general collection`
- `Assign to workspace`

### Cross-Page Navigation

Users should be able to:

- generate a quiz or flashcard deck in a workspace
- open that real persisted quiz from the Quiz page
- open that real persisted deck from the Flashcards page
- continue to access the same persisted item even if its scope changes later

Workspace artifacts should retain stable links to the persisted quiz or deck IDs.

Direct-link rule:

- if navigation includes a concrete `quizId` or `deckId`, the destination page must fetch and show that item even when hidden-by-default workspace filters are off
- the page can indicate that the item is workspace-owned and currently outside the default collection filter

## API And Query Changes

### Quiz APIs

Extend create, update, list, and generate flows to support:

- canonical `workspace_id`
- optional derived `workspace_tag` only if backward compatibility still requires it

List filtering should support:

- `workspace_id`
- optional inclusion of workspace-owned items

Workspace generation should use one `generateQuiz(...)` request with a mixed `sources` payload instead of one request per media item.

### Flashcard Deck APIs

Extend create, update, and list flows to support:

- canonical `workspace_id`
- optional derived `workspace_tag` only if needed for compatibility or display

List filtering should support:

- `workspace_id`
- optional inclusion of workspace-owned decks

### Flashcard Card, Review, And Document APIs

Flashcard visibility cannot be enforced only at the deck-list level.

Any flashcard endpoint that reads cards, review queues, due counts, analytics, or document/search results must either:

- accept the same workspace visibility filters as deck listing
- or enforce deck ownership internally by joining through the owning deck

At minimum this applies to flows equivalent to:

- card listing and search
- next-review card selection
- due-count and analytics summaries
- document/query views built from card collections

### Workspace Artifact State

Generated artifacts should store stable server identifiers:

- quiz artifact: persisted `quiz.id`
- flashcard artifact: persisted `deck.id`

## Scope Changes After Creation

Users can change scope after creation.

Rules:

- A quiz or deck can belong to general scope or one workspace scope.
- Moving from workspace to general clears canonical workspace ownership metadata.
- Moving from general to workspace assigns one `workspace_id`.
- No cloning is required; ownership changes happen in place.

## Edge Cases

### Workspace Rename

Preferred behavior:

- no ownership migration is required when canonical ownership uses a stable `workspace_id`
- refresh any derived `workspace_tag` or display labels as a secondary compatibility concern

### Workspace Deletion

Recommended fallback:

- move owned quizzes and decks to general scope with a warning/confirmation flow

This preserves user data and avoids orphaned hidden records.

### Existing Artifacts After Scope Changes

Workspace-generated artifact links should still open the same quiz or deck after scope changes. The artifact can show current scope state rather than assuming the original scope remains unchanged.

## Migration Strategy

- Existing quizzes default to `workspace_id = null`
- Existing decks default to `workspace_id = null`
- existing `workspace_tag` values can remain temporarily for compatibility while ownership is normalized onto `workspace_id`
- No content cloning or bulk backfill is required beyond setting defaults

## Testing Strategy

### Workspace Tests

Add or update tests to verify:

- one persisted quiz is created for multi-source workspace quiz generation
- workspace policy is inherited automatically
- workspace-generated flashcards land in a correctly scoped deck
- generated artifacts link to persisted quiz/deck records

### Quiz Page Tests

Verify:

- workspace-owned quizzes are hidden by default
- they appear when `Show workspace quizzes` is enabled
- workspace filtering works
- move-to-general and assign-to-workspace work in place
- direct `quizId` links force-show the referenced quiz even when workspace filters are off

### Flashcards Page Tests

Verify:

- workspace-owned decks are hidden by default
- they appear when `Show workspace decks` is enabled
- workspace filtering works
- deck scope changes work in place
- direct `deckId` links force-show the referenced deck even when workspace filters are off
- card/review/document flows do not leak workspace-owned cards when workspace visibility is off

### Service And API Tests

Verify:

- quiz generate accepts mixed-source bundles and returns one persisted quiz
- quiz list filters honor workspace ownership fields
- deck list filters honor workspace ownership fields
- flashcard card/review/document endpoints honor workspace visibility rules
- scope updates preserve IDs and content

## Implementation Notes

- Rework workspace quiz generation so the workspace artifact is not an aggregate over multiple persisted quizzes.
- Rework workspace flashcard target-deck selection so workspace-owned runs default to a new workspace-owned deck unless the user selected an existing destination.
- Treat `workspace_id` as canonical ownership and keep any `workspace_tag` usage transitional or derived.
- Keep main Quiz and Flashcards pages unified rather than adding a separate workspace-only study-materials surface.

## Open Product Choice Already Resolved

The user chose:

- workspace default policy over per-generation selection
- hidden-by-default with filters over complete invisibility on main pages
- deck-level flashcard ownership
- one persisted quiz per workspace generation run
- mutable scope after creation
- single-workspace ownership only

## Recommended Next Step

Write an implementation plan that breaks this into:

1. data/service shape updates
2. workspace generation flow changes
3. main Quiz and Flashcards filter and move-scope UX
4. end-to-end verification
