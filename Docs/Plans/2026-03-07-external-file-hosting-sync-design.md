# External File Hosting Sync Design

Date: 2026-03-07
Status: Approved

## Summary

Add version-aware import and sync support for external file-hosting providers, starting with Google Drive and Microsoft OneDrive, while designing the system so Dropbox, Box, and SharePoint can be added later without schema churn.

The system should reconcile upstream file state with existing local media items, create new `DocumentVersions` when remote content changes, preserve the last good local version if a new upstream revision fails ingestion, and archive local items when the upstream file is removed or access is revoked.

## Product Decisions (Approved)

- Local update model: versioned
- Initial provider scope: Google Drive and OneDrive, with Dropbox/Box/SharePoint-ready abstractions
- Trigger model: hybrid event-driven, using provider webhooks/subscriptions with polling fallback
- Source types in v1: folders/libraries, individual files, and shared links
- Failed new upstream revision policy: keep the last good local version active
- Upstream removal policy: archive locally but keep searchable history and versions

## Goals

- Reuse the existing connectors stack instead of building a parallel integration subsystem.
- Support one-time bootstrap import plus ongoing sync for Google Drive and OneDrive.
- Maintain a stable mapping from a remote object to a local `Media` item.
- Create new `DocumentVersions` when remote content changes.
- Distinguish content changes from metadata-only changes such as rename or move.
- Archive local items when the upstream object is removed or becomes inaccessible.
- Keep sync execution visible in the existing Jobs system.
- Support webhook-first freshness without depending on webhooks for correctness.

## Non-Goals

- Shipping Dropbox, Box, or SharePoint as first-class UI options in the initial release.
- Replacing the existing connectors API surface.
- Introducing a separate version store outside `Media` and `DocumentVersions`.
- Performing heavy sync work directly in webhook handlers.
- Full enterprise admin UX for every provider-specific source type in v1.

## Existing Repo Anchors

The design extends existing code instead of replacing it:

- Connectors API and CRUD:
  - `tldw_Server_API/app/api/v1/endpoints/connectors.py`
- Connectors service and provider registry:
  - `tldw_Server_API/app/core/External_Sources/connectors_service.py`
  - `tldw_Server_API/app/core/External_Sources/google_drive.py`
  - `tldw_Server_API/app/core/External_Sources/notion.py`
  - `tldw_Server_API/app/core/External_Sources/gmail.py`
- Existing async worker patterns:
  - `tldw_Server_API/app/services/connectors_worker.py`
- Existing media update and versioning primitives:
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/Media_Update_lib.py`
  - `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Existing Jobs system:
  - `Docs/Code_Documentation/Jobs_Module.md`

## Recommended Architecture

### 1. Provider Sync Adapters

Add a provider sync adapter contract under `External_Sources/` for file-hosting providers. Each adapter should isolate provider-specific behavior:

- `browse_source`
- `resolve_shared_link`
- `list_children`
- `list_changes`
- `get_item_metadata`
- `download_or_export`
- `subscribe_webhook`
- `renew_webhook`
- `revoke_webhook`

This keeps Drive-, Graph-, Dropbox-, or Box-specific logic out of the shared reconciliation path.

### 2. Shared Sync Coordinator

Add one shared sync coordinator service that owns the generic lifecycle:

- source loading
- token refresh
- cursor and webhook bookkeeping
- dedupe
- retry and backoff
- change normalization
- remote-to-local reconciliation
- version creation
- archive-on-removal behavior
- degraded-state handling when the latest remote revision fails

The current Gmail sync code in `connectors_worker.py` is the strongest behavioral precedent for cursor handling, retry state, and run finalization.

### 3. Jobs as the Execution Backbone

Use the existing Jobs system for all user-visible or admin-visible async work. Planned job types:

- `bootstrap_scan`
- `incremental_sync`
- `manual_resync`
- `subscription_renewal`
- `repair_rescan`

APScheduler should only enqueue work. It should not own sync state or replace Jobs.

### 4. Webhooks as Triggers Only

Webhook endpoints should:

- validate the provider request
- dedupe provider events
- mark the relevant source as needing sync
- enqueue an `incremental_sync` job
- return immediately

Webhook handlers must not download files or ingest content inline.

## Data Model

Keep the existing connector tables:

- `external_accounts`
- `external_sources`

Evolve `external_items` into the canonical remote-object binding table instead of adding a second item-mapping table. The current connectors implementation already uses `external_items` for dedupe and ingest state, so v1 should extend that table in place rather than create a competing source of truth.

Add purpose-specific sync tables alongside it.

### `external_source_sync_state`

One row per source. Tracks source-level sync health and cursors.

Suggested fields:

- `source_id`
- `sync_mode` (`manual`, `poll`, `hybrid`)
- `cursor`
- `cursor_kind`
- `last_bootstrap_at`
- `last_sync_started_at`
- `last_sync_succeeded_at`
- `last_sync_failed_at`
- `last_error`
- `retry_backoff_count`
- `webhook_status`
- `webhook_subscription_id`
- `webhook_expires_at`
- `needs_full_rescan`
- `consecutive_failures`
- `active_job_id`
- `active_run_token`
- `active_lease_expires_at`

### `external_items`

One row per remote object bound to one local `Media` item. This table replaces the “dedupe only” role it has today and becomes the single source of truth for remote identity, local binding, and item-level sync state.

Suggested fields:

- `id`
- `source_id`
- `provider`
- `external_id`
- `remote_parent_id`
- `remote_path`
- `remote_name`
- `remote_etag`
- `remote_revision`
- `remote_hash`
- `remote_modified_at`
- `remote_deleted_at`
- `access_revoked_at`
- `media_id`
- `current_version_number`
- `last_seen_at`
- `last_content_sync_at`
- `last_metadata_sync_at`
- `sync_status` (`active`, `degraded`, `archived_upstream_removed`, `orphaned`)

Constraints:

- unique key on `(source_id, provider, external_id)`

### `external_item_events`

Append-only audit trail for per-item state transitions.

Suggested fields:

- `external_item_id`
- `event_type` (`created`, `content_updated`, `metadata_updated`, `deleted_upstream`, `restored_upstream`, `access_revoked`, `ingest_failed`, `archived`)
- `job_id`
- `occurred_at`
- `payload_json`

## Local Persistence Model

Do not create a separate content version subsystem. Use the existing Media DB model:

- One stable `Media` row per bound remote object
- One new `DocumentVersion` per upstream content revision

This aligns with existing helpers such as:

- `create_document_version(...)`
- `add_media_with_keywords(..., overwrite=True)`
- `get_all_document_versions(...)`

Provider metadata should be persisted in two places:

1. Stable operational mapping in `external_items`
2. Per-revision provider snapshot in `DocumentVersions.safe_metadata`

### Migration and Backfill

Existing connector imports may already have rows in `external_items` that contain only dedupe fields. Before incremental sync is enabled for an existing source:

- backfill the new binding columns in `external_items`
- resolve or infer the bound `media_id` where possible
- if a binding cannot be safely inferred, mark the source `needs_full_rescan = true` and require a bounded repair bootstrap before enabling incremental sync

The rollout must not allow two parallel sources of truth for remote object state.

Suggested `safe_metadata` payload on each synced version:

- `provider`
- `source_id`
- `remote_id`
- `remote_revision`
- `remote_etag`
- `remote_hash`
- `remote_path`
- `remote_url`
- `sync_job_id`
- `sync_kind`
- `upstream_deleted`
- `export_mime`
- `provider_metadata`

## Sync Lifecycle

### 1. Bootstrap Import

When a source is first connected:

1. enqueue `bootstrap_scan`
2. enumerate the source recursively
3. resolve shared links to canonical remote IDs when possible
4. create or backfill `external_items` bindings for discovered files
5. ingest supported items into `Media`
6. create initial `DocumentVersions`
7. persist the initial cursor or delta token
8. create and store webhook subscription state if supported

### 2. Incremental Sync

Triggered by polling, manual run, or webhook:

1. load source state from `external_source_sync_state`
2. if `needs_full_rescan` is true, run a bounded repair rescan instead of delta
3. call the provider adapter for `list_changes(cursor)`
4. normalize provider responses into shared change types
5. reconcile each normalized change against `external_items`
6. persist updated cursor or delta token
7. finalize job result and source sync health

### 3. Normalized Change Types

Provider-specific events should be normalized into:

- `created`
- `content_updated`
- `metadata_updated`
- `deleted`
- `restored`
- `permission_lost`

### 4. Reconciliation Rules

#### `created`

- If no binding exists, ingest and bind.
- If a binding exists but is archived, restore it and refresh metadata.

#### `content_updated`

- Download or export the latest content.
- Compare provider revision and content hash.
- If unchanged, no-op.
- If changed, update the existing `Media` row and create a new `DocumentVersion` in the same transaction.
- The content-update path must atomically update:
  - `Media.content`
  - `Media.content_hash`
  - `Media.last_modified`
  - `Media.version`
  - `media_fts`
  - the new `DocumentVersion`
- Update binding fields including revision, hash, modification time, and current version number.
- Do not use `process_media_update()` as-is for this path, because it only appends a document version and does not refresh the canonical `Media` content or FTS state.

#### `metadata_updated`

- Update binding metadata only.
- Do not create a new `DocumentVersion` for rename, move, or path-only changes.

#### `deleted` or `permission_lost`

- Mark the binding as `archived_upstream_removed` or `orphaned`.
- Archive the local media item from default active views using the existing trash semantics (`mark_as_trash`), not hard delete.
- Preserve version history and audit trail.

#### `restored`

- Unarchive the local media item using the existing restore semantics (`restore_from_trash`).
- Refresh metadata.
- Optionally force a content refresh if the provider cannot prove the latest content hash or revision.

## Failure and Recovery Rules

### Keep the Last Good Version Active

If the newest remote revision fails download, conversion, or ingestion:

- leave the current local media item and latest good `DocumentVersion` active
- mark the binding `degraded`
- record an `ingest_failed` event
- surface the failure at source and job level

### Cursor Recovery

If a provider cursor or delta token becomes invalid or expires:

- mark `needs_full_rescan = true`
- record source-level failure state
- enqueue or allow a bounded repair rescan

### Partial Failures

If a source sync partially succeeds:

- persist successfully processed item updates
- keep the job result explicit about processed, skipped, and failed counts
- do not roll back already-ingested items

## Source-Scoped Concurrency and Idempotency

Hybrid triggering means polling, manual sync, and webhook-triggered sync can all target the same source. The system must therefore enforce source-scoped fencing:

- at most one active processing sync run per source
- every enqueued sync job uses a Jobs `idempotency_key` derived from `source_id`, `sync_kind`, and the strongest available cursor or event identity
- `external_source_sync_state` tracks `active_job_id`, `active_run_token`, and lease expiry so stale or duplicated jobs can no-op safely
- webhook retries or duplicate poll submissions must converge on the same queued job whenever possible

Correctness must not depend on provider-side event uniqueness.

## API and Worker Additions

The existing connectors API should remain the entry point. Additive endpoints or behaviors may include:

- source sync trigger for file-hosting sources
- source sync status fields
- webhook callback endpoints per provider
- subscription status and expiry visibility

The connector schema surface must also expand early enough to represent the approved v1 scope:

- add provider `onedrive`
- add source type `file`
- keep existing Notion types (`page`, `database`) for backward compatibility
- represent Microsoft library or site context through source `options` metadata until a distinct `library` type is justified

Jobs should remain queryable through the existing Jobs surfaces rather than a connectors-specific status system.

## Provider Notes

### Google Drive

- Use IDs as canonical identity, not paths.
- Prefer `changes.getStartPageToken` and `changes.list` for incremental sync.
- Support Google-native exports:
  - Docs -> text or markdown-oriented export
  - Sheets -> CSV
  - Slides -> PDF plus existing PDF text extraction path
- Shared drives should be supported at the adapter layer from the start.

### OneDrive

- Build on Microsoft Graph delta APIs.
- Treat personal and business drives through the same adapter contract.
- Preserve `drive_id` and related Graph identity metadata in binding or provider metadata, not just item ID.
- Subscription renewal must be a first-class recurring job because Graph subscriptions expire.

### SharePoint

- Not a first-class v1 UI target.
- Design the OneDrive or Graph adapter so SharePoint document libraries are source variants without schema changes.
- Source metadata must be able to carry `site_id`, `drive_id`, and library context.

### Dropbox and Box

- Both should fit the same binding and shared coordinator model later.
- No schema redesign should be required when they are added.

## Security and Governance

- Reuse existing OAuth account and policy enforcement in the connectors module.
- Encrypt tokens at rest and never log them.
- Keep provider accounts and sources scoped to the authenticated user or tenant.
- Validate webhook signatures and dedupe provider events.
- Respect existing org policy controls for enabled providers, file types, and size limits.

## Observability

Track at minimum:

- source sync runs by provider and outcome
- item reconciliation counts by event type
- degraded item count
- webhook delivery or renewal failures
- cursor invalidation or full rescan occurrences
- subscription expiry proximity for providers that require renewal

The Gmail sync metrics model is a useful precedent for per-source health and recovery instrumentation.

## Testing Strategy

### Unit Tests

- provider change normalization
- reconciliation decisions
- archive and restore transitions
- degraded-state handling
- cursor invalidation and fallback to rescan
- shared-link resolution

### Integration Tests

- bootstrap scan creates bindings, media items, and document versions
- content update creates a new `DocumentVersion` on the same `media_id`
- rename or move updates metadata without creating a content version
- upstream deletion archives the local item
- webhook requests enqueue sync jobs but do not execute heavy work inline

### Property-Based Tests

- idempotent repeated delta application
- duplicate webhook delivery
- out-of-order metadata and content events

### Regression Tests

- existing connectors import behavior remains intact
- Gmail and email sync behavior remains isolated from file-hosting sync semantics
- media versioning endpoints continue to work with synced items

## Rollout Plan

### Phase 1

- Add sync state and binding tables
- Add provider sync adapter contract
- Implement Drive and OneDrive bootstrap import plus manual or scheduled sync
- Create new `DocumentVersions` for remote content changes
- Archive-on-removal behavior

### Phase 2

- Add webhook ingress and subscription renewal flows
- Add degraded-item repair and cursor-rescan flows
- Improve source and job observability

### Phase 3

- Add SharePoint-oriented source UX
- Add Dropbox and Box adapters
- Add richer admin and conflict tooling

## Acceptance Criteria

- A Drive or OneDrive source can bootstrap import into local `Media`.
- Subsequent upstream content changes create new `DocumentVersions` on the same `media_id`.
- Metadata-only changes do not create extra content versions.
- Failed latest upstream revisions do not replace the last good local version.
- Upstream deletions or permission loss archive local items while preserving history.
- Sync runs are visible in the existing Jobs system.
- Provider webhook support improves freshness but polling fallback preserves correctness.
