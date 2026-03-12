Date: 2026-03-12
Status: Designed

# Companion Capture Expansion Design

## Summary

This design activates the deferred companion capture-expansion slice after the foundation, quality/trust-controls, and proactive-polish milestones.

The goal is not to broaden companion in every direction. It is to extend the existing explicit-capture model into a small set of lower-risk bulk and import flows that already map well onto the current companion activity ledger.

This milestone stays intentionally narrow:

- `notes/import`
- `notes/bulk`
- `watchlists/sources/import`
- `watchlists/sources/bulk`

## Goal

Extend explicit companion capture into selected bulk/import flows so that successful imported or bulk-created user content becomes usable by existing companion derivations, reflections, and conversation context.

## Non-Goals

This milestone does not include:

- `chatbooks/import`
- restore semantics beyond what endpoints already do today
- ledger entries for duplicates, skips, validation failures, or row-level errors
- new import-specific event families
- passive or hidden capture
- a new storage path outside personalization

## Product Rules

The user already approved these rules during design review:

- capture stays explicit and per-item
- only rows that actually changed state are eligible for companion activity
- existing event families are reused
- import and bulk origins are distinguished through provenance and surface metadata
- restore semantics remain out of scope for this slice unless the endpoint already restores

## Reviewed Current State

The current companion system already has:

- per-user consent gating through personalization profiles
- an explicit companion activity ledger in `PersonalizationDB`
- existing event families for notes and watchlist sources
- downstream consumers that already understand those event families

The current import and bulk flows already exist:

- notes import supports create, skip, overwrite, and create-copy flows
- notes bulk creates notes and returns hydrated created-note payloads
- watchlists OPML import creates or skips sources
- watchlists bulk create creates rows or returns per-entry errors

These flows are explicit user actions already, so they fit the companion model.

## Design Review Adjustments

Before approving this milestone, the design was tightened around several real implementation risks found in the current code.

### Bulk companion insert must be conflict-tolerant

`PersonalizationDB.insert_companion_activity_events_bulk(...)` currently inserts the whole batch in one transaction without duplicate handling.

That is too brittle for this slice because a single dedupe conflict can invalidate the whole companion write batch.

This milestone therefore requires either:

- conflict-tolerant bulk insert behavior, or
- prefiltering against existing dedupe keys before insert

The behavioral requirement is fixed even if the implementation choice varies:

- companion capture remains best-effort
- one duplicate must not fail the whole bulk/import companion write

### `watchlists/sources/bulk` must prove that a row was newly created

The current watchlists DB helper is idempotent on unique URL conflict and can return an existing row from `create_source(...)`.

That means the endpoint's current `status="created"` response is not strong enough to drive companion capture by itself.

This milestone therefore requires explicit actual-change detection for `watchlists/sources/bulk`.

Valid options:

- extend the DB helper to report whether the insert was new
- add a conservative pre-check that only emits companion activity when a create is known to have changed state

The design requirement is:

- no `watchlist_source_created` companion event may be emitted unless the code can prove the row was newly created

### `notes/import` must reread the final note row

The current notes import path does not end with a hydrated post-write note object in either create or overwrite mode.

That is not sufficient for reliable companion event construction because existing note companion events use:

- final version
- final timestamps
- final compact metadata
- keyword/tag state where available

This milestone therefore requires a post-write reread for successful `notes/import` create and overwrite rows before building companion events.

### Capture must be success-branch local

Companion writes must happen inside the actual success branches that performed the create or update, not from the final response summary.

This avoids mapping drift where:

- a route reports `created` for an idempotent no-op
- a route classifies a failure as `skipped`
- future response formats stop matching actual DB effects

### Shared adapter should batch payloads, not loop over single-event helpers

The existing `record_*` helpers open personalization storage and check consent one event at a time.

That is fine for single-resource CRUD routes, but not ideal for bulk/import flows.

This milestone therefore introduces a shared adapter layer that:

- builds normalized event payloads
- performs consent gating once
- writes through a conflict-tolerant bulk path

## Recommended Approach

Recommended approach: shared bulk/import companion adapter.

Why this is the right fit:

- it keeps the milestone low-risk
- it avoids four one-off endpoint-specific companion implementations
- it preserves the existing companion activity model
- it keeps provenance and metadata normalization in one place

Rejected alternatives:

- endpoint-local hand-written capture logic in all four handlers
  - simpler to start, but more drift and duplication
- post-import reconciliation from response payloads
  - too easy to mismatch actual DB changes

## Architecture

### Core principle

Do not introduce a second bulk-import-specific companion pipeline.

Bulk/import routes should continue to:

- perform parsing
- perform validation
- perform DB writes
- build their normal API responses

The companion system should continue to:

- reuse existing event families
- write into personalization storage
- honor existing per-user consent gates

### New layer

Add a shared companion bulk/import adapter in the personalization layer.

Responsibilities:

- map successful row outcomes to existing event families
- attach import-specific provenance and surfaces
- build compact metadata payloads
- perform a single consent check per request
- execute conflict-tolerant bulk writes

Endpoints remain responsible for:

- identifying successful create/update branches
- rereading final objects where needed
- passing normalized row outcomes into the adapter

## Event Model

### Event families

Reuse existing families:

- `note_created`
- `note_updated`
- `watchlist_source_created`
- `watchlist_source_updated` only if a current in-scope flow already performs a real update

This milestone does not add:

- `note_imported`
- `bulk_note_created`
- `watchlist_source_imported`
- any other import-specific event family

### Provenance and surfaces

Differentiate origin through surface and provenance instead of event type.

Surfaces:

- `api.notes.import`
- `api.notes.bulk`
- `api.watchlists.sources.import`
- `api.watchlists.sources.bulk`

Provenance routes:

- `/api/v1/notes/import`
- `/api/v1/notes/bulk`
- `/api/v1/watchlists/sources/import`
- `/api/v1/watchlists/sources/bulk`

Provenance actions should reflect origin-specific behavior while preserving the existing event families:

- `import_create`
- `import_overwrite`
- `bulk_create`

If a future in-scope route performs a real update rather than a create, its provenance action should be similarly explicit.

## Per-Surface Behavior

### `notes/import`

Successful outcomes:

- imported new note -> emit `note_created`
- overwrite of existing note -> emit `note_updated`
- create-copy retry that succeeds -> emit `note_created`

No companion activity for:

- skipped duplicates
- parse failures
- validation failures
- row-level exceptions

Implementation rule:

- reread the final note row after successful create or overwrite before building companion activity

### `notes/bulk`

Successful outcomes:

- created note -> emit `note_created`

No companion activity for:

- per-row failures
- rejected rows

Implementation note:

- this route already rereads the created note row, so it can pass hydrated notes into the shared adapter

### `watchlists/sources/import`

Successful outcomes:

- newly created source -> emit `watchlist_source_created`

No companion activity for:

- duplicate-source skips
- missing URL rows
- invalid YouTube RSS rows
- create failures

Implementation note:

- capture must happen only in the actual create branch

### `watchlists/sources/bulk`

Successful outcomes:

- newly created source -> emit `watchlist_source_created`

No companion activity for:

- per-entry validation errors
- create failures
- idempotent returns of existing sources

Implementation rule:

- this route must establish whether the row was newly created before emitting any companion event

## Metadata Rules

### Note metadata

Imported and bulk note metadata should stay consistent with current note activity:

- `title`
- `content_preview`
- `version`
- `conversation_id`
- `message_id`

Where available after reread or existing hydration:

- keyword-derived tags
- import-relevant `changed_fields` for overwrite paths

### Watchlist source metadata

Imported and bulk source metadata should stay consistent with current watchlist source activity:

- `name`
- `url`
- `source_type`
- `active`
- `status`
- `group_ids`
- `settings_keys`

Where available:

- normalized tags

## Consent And Failure Policy

Consent behavior remains unchanged:

- if personalization/companion is not enabled for the user, import and bulk actions still succeed
- companion activity is simply not recorded

Failure behavior for this milestone:

- companion capture is best-effort
- companion write failure must not fail the import or bulk operation
- failures should be logged at debug or warning level with enough context to diagnose drift

This is the right tradeoff for this slice because the import/bulk action is the primary user intent, while companion capture is secondary enrichment.

## Testing Strategy

Backend coverage should include:

- adapter unit tests for event payload construction
- adapter tests for conflict-tolerant duplicate handling
- notes import integration tests covering:
  - create -> `note_created`
  - overwrite -> `note_updated`
  - skip -> no event
  - consent-disabled import -> no companion event and unchanged response counts
- notes bulk integration tests covering:
  - success row -> `note_created`
  - failed row -> no event
- watchlists OPML import integration tests covering:
  - create -> `watchlist_source_created`
  - duplicate skip -> no event
- watchlists bulk integration tests covering:
  - real create -> `watchlist_source_created`
  - duplicate/idempotent existing-row case -> no event
  - validation error -> no event

Verification should also include:

- targeted existing regression tests for notes and watchlists bulk/import responses
- Bandit on touched backend scope
- `git diff --check`

## Milestone Outcome

When this milestone is complete:

- explicit bulk/import actions feed the existing companion system
- companion derivations and reflections gain more useful raw activity without new hidden capture
- provenance remains clear about where each event came from
- the ledger stays cleaner because duplicates, skips, and errors are excluded

This keeps the companion system broader, but still disciplined.
