# Ingestion Source Sync Design

## Date
2026-03-08

## Owner
Generic document/file ingestion sync for local directories and archive snapshots

## Goal
Design a reusable sync/import system for document and file ingestion that supports local directories and uploaded archive refreshes, with selectable destination sinks for Media/Documents or Notes.

## Scope

In scope:
- Generic syncable ingestion sources for:
  - local directories on disk
  - uploaded archive snapshots (`.zip`, later `.tar`/`.tar.gz` if supported by the same safety model)
- Manual sync plus optional scheduled rescans for local-directory sources
- UI and API refresh of archive-backed sources by replacing the payload for the same logical source
- Selectable sink per source:
  - `media`
  - `notes`
- Per-source lifecycle policy:
  - `canonical`
  - `import_only`
- Source-scoped job execution, status, history, and conflict/degraded reporting

Out of scope for v1:
- Continuous filesystem watching
- Git repository sync
- Cloud provider/OAuth connectors
- Three-way merge for synced note conflicts
- Changing `sink_type` or source identity after the first successful sync
- Full note revision-history storage
- Generic binary ingestion into Notes

## Problem Statement

Current ingestion supports upload/import, but not durable source tracking and resynchronization. Users who keep notes or document collections in a folder or exported archive must re-upload everything when files change. Existing Notes import handles JSON/Markdown batches, and existing External Sources sync handles cloud providers for Media, but there is no reusable local/archive sync system that:

- remembers a source over time
- detects per-file adds/changes/deletes
- updates existing destination content instead of blindly duplicating
- supports both Media and Notes as destinations

## Current Verified Constraints

### Notes import/export exists, but not sync

`POST /api/v1/notes/import` already supports JSON and Markdown batch import with duplicate strategies in:

- `tldw_Server_API/app/api/v1/endpoints/notes.py`
- `tldw_Server_API/app/api/v1/schemas/notes_schemas.py`

This is import-only behavior. It does not persist source identity, track source items, or diff later refreshes.

### Notes do not have recoverable content history today

`CharactersRAGDB.update_note()` updates the current row in place and increments the optimistic-lock version:

- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`

That is not the same as preserving historical note bodies. Therefore the Notes sink in v1 must be defined as latest-state sync, not durable note revision history.

### A stronger sync model already exists for cloud file sources

The repo already has good patterns for source sync state, reconciliation, job fencing, and scheduled enqueue in:

- `tldw_Server_API/app/core/External_Sources/README.md`
- `tldw_Server_API/app/core/External_Sources/connectors_service.py`
- `tldw_Server_API/app/services/connectors_sync_scheduler.py`
- `tldw_Server_API/app/services/connectors_worker.py`

That system is currently provider-centric and Media-centric. It should inform the design, but local folders and uploaded archives should not be modeled as fake OAuth providers.

### Safe local path handling and allowed-root validation already matter in this repo

Relevant existing patterns:

- `tldw_Server_API/app/core/Ingestion_Media_Processing/path_utils.py`
- `tldw_Server_API/app/core/Setup/setup_manager.py`

These confirm that local-path sync must be explicitly constrained to allowed roots and revalidated at runtime.

### Existing ingestion coverage is broader for Media than for Notes

The document/media ingestion pipeline already handles text-first documents and richer document formats:

- `tldw_Server_API/app/api/v1/endpoints/media/process_documents.py`
- `tldw_Server_API/app/core/Ingestion_Media_Processing/Plaintext/Plaintext_Files.py`
- `tldw_Server_API/app/api/v1/endpoints/media/process_pdfs.py`
- `tldw_Server_API/app/api/v1/endpoints/media/process_ebooks.py`

Notes should therefore have a narrower v1 sink scope than Media.

## Selected Architecture

Create a new generic `ingestion_sources` subsystem for syncable inputs. Reuse the successful ideas from the existing External Sources and Jobs architecture, but keep this system independent from OAuth accounts and remote-provider assumptions.

### Core flow

1. User creates an ingestion source.
2. A source adapter scans the source and emits a normalized snapshot of items.
3. A diff/reconciliation layer compares the candidate snapshot to the last successful snapshot.
4. A sink adapter applies creates/updates/deletes according to the source policy.
5. Jobs own execution; APIs only create/update sources and enqueue work.
6. Scheduled rescans use APScheduler to enqueue Jobs, not to process content inline.

### Why this approach

- Matches the repo’s existing preference for Jobs for user-visible work
- Reuses proven sync-state and fencing concepts
- Avoids building another one-shot import endpoint that cannot evolve
- Leaves room for future source types such as git repos or more connectors

## Data Model

### Core tables

`ingestion_sources`
- one logical source per user
- fields:
  - `id`
  - `user_id`
  - `source_type` (`local_directory`, `archive_snapshot`)
  - `sink_type` (`media`, `notes`)
  - `policy` (`canonical`, `import_only`)
  - `enabled`
  - `schedule_enabled`
  - `schedule_interval_sec` or equivalent schedule config
  - source config payload
  - created/updated timestamps

`ingestion_source_state`
- mutable runtime state per source
- fields:
  - `source_id`
  - `active_job_id`
  - `last_successful_snapshot_id`
  - `last_sync_started_at`
  - `last_sync_completed_at`
  - `last_sync_status`
  - `last_error`
  - counts/summary fields

`ingestion_source_snapshots`
- one row per scan or archive refresh attempt
- fields:
  - `id`
  - `source_id`
  - `snapshot_kind` (`scan`, `archive_refresh`)
  - `status` (`candidate`, `active`, `failed`, `superseded`)
  - snapshot metadata and summary
  - created timestamps

`ingestion_source_items`
- canonical per-item binding for the latest known source state
- canonical identity in v1:
  - `source_id + normalized_relative_path`
- fields:
  - source item path identity
  - content fingerprint/hash
  - file size / modified time metadata
  - current sync status
  - bound destination id and destination metadata
  - item-level error/degraded/conflict state

`ingestion_item_events`
- append-only audit trail for item-level create/update/delete/archive/conflict events

`ingestion_source_artifacts`
- staged archive file metadata and extracted snapshot metadata
- supports retention and cleanup of old uploaded payloads and extracted candidate trees

## Source Semantics

### `local_directory`

- Stores a validated absolute source path under configured allowed roots
- Supports:
  - manual sync
  - optional scheduled rescans
- Does not support:
  - filesystem watch in v1
- Operational constraint:
  - only safe in deployments where the worker that runs sync can access the same path later
  - should be treated as self-hosted/admin-controlled unless shared storage guarantees exist

### `archive_snapshot`

- Represents one logical source whose payload is replaced over time by new uploaded archives
- Refresh paths:
  - UI re-upload to the same source
  - API archive replacement for the same source
- Every refresh creates a candidate snapshot
- Candidate snapshot becomes authoritative only after successful extraction, normalization, diffing, and sink application
- If refresh fails, the previous successful snapshot remains current

## Normalization Rules

For both source types, adapters emit normalized items with:

- normalized relative path
- display path
- content fingerprint
- size
- modified time when available
- parseable media/document hint

### Archive normalization

If an uploaded archive contains a single common top-level directory, strip that root during normalization so timestamped export wrappers do not cause a full delete/create churn every refresh.

### Rename semantics

In v1, rename is explicitly modeled as:

- old path deleted
- new path created

No rename continuity is attempted in v1.

## Reconciliation Contract

Candidate snapshot vs last successful snapshot yields:

- `created`
- `changed`
- `unchanged`
- `deleted`

Fingerprinting rule:
- content hash is authoritative
- file size and modified time may be used as scan shortcuts, but not as the final truth when content is available

This is especially important for archive refreshes, where filename reuse is common.

## Lifecycle Policies

### `canonical`

- one destination object per source item
- content changes update that same bound destination object
- removed source items archive or soft-delete the destination object

### `import_only`

- one destination object per source item
- content changes update that same bound destination object
- removed source items do not trigger automatic archival/deletion

### Deferred from v1

`append_only`
- every change creates a new destination object
- excluded from v1 to keep binding semantics simple

## Sink Semantics

### `media` sink

- Broadest v1 sink
- Reuses the document/media ingestion pipeline
- Appropriate for mixed source collections containing text documents, PDFs, DOCX, EPUB, HTML, Markdown, plain text, and other supported document types
- On change:
  - update the same logical bound item where supported
  - create a new document/media version instead of duplicating when the existing Media model allows it
- On failed revision ingest:
  - preserve the last good active version
  - mark item degraded instead of destroying continuity

### `notes` sink

- Narrower by design in v1
- Supported input classes for direct Notes sync:
  - `.md`
  - `.markdown`
  - `.txt`
  - `.html`
  - `.htm`
  - `.xml`
  - `.json`
  - `.docx`
  - `.rtf`
- Not supported for direct Notes sync in v1:
  - PDFs
  - ebooks
  - generic binaries

Reason:
- Notes are text-first
- existing note import behavior is oriented around structured text
- Media already owns the richer document extraction path

### Notes sink content contract

- V1 Notes sync is latest-state sync only
- It does not promise durable historical note body preservation
- Title/body derivation:
  - front matter title when available
  - Markdown heading fallback
  - filename fallback
- Keywords/tags may be mapped where the parsed content exposes them cleanly

## Synced Notes Conflict Policy

This is required to avoid silent user-data loss.

### Recommended v1 rule

- Synced notes are marked `sync_managed`
- User edits are allowed
- Once a sync-managed note is manually edited locally, it becomes `detached`
- Detached note behavior:
  - future source syncs do not overwrite that note
  - the source item is marked `conflict_detached`
  - source status surfaces that conflict for user resolution

### Why this rule

- Safer than overwriting user edits
- Simpler than read-only synced notes
- Much simpler than three-way merge

### Deferred from v1

- automatic merge
- inline conflict editing UI
- true bidirectional sync

## API Shape

### Endpoints

`POST /api/v1/ingestion-sources`
- create a source

`GET /api/v1/ingestion-sources`
- list sources with current status

`GET /api/v1/ingestion-sources/{id}`
- source detail, last run summary, last error, counts

`PATCH /api/v1/ingestion-sources/{id}`
- mutable fields only:
  - enabled flag
  - schedule
  - lifecycle policy
  - parser/filter options

Immutable after first successful sync:
- `source_type`
- source identity
- `sink_type`

`POST /api/v1/ingestion-sources/{id}/sync`
- enqueue a manual sync

`POST /api/v1/ingestion-sources/{id}/archive`
- replace payload for an archive-backed source
- create a candidate snapshot
- enqueue a sync for that candidate snapshot

`GET /api/v1/ingestion-sources/{id}/items`
- inspect bound items and sync states

Optional useful follow-up, but not required for first backend checkpoint:
- `POST /api/v1/ingestion-sources/{id}/items/{item_id}/reattach`

## Jobs and Scheduling

Use Jobs for execution because this is user-visible work with status and admin visibility requirements.

Use APScheduler only to enqueue recurring sync jobs, consistent with repo guidance and existing patterns such as:

- `tldw_Server_API/app/services/connectors_sync_scheduler.py`

Execution requirements:
- source-scoped active job fencing
- lease renewal for long syncs
- no inline processing in request handlers

## Error Handling

### Source validation failures

- invalid local path
- path escape
- path outside allowed roots
- unsupported source configuration

Result:
- reject creation/update or fail the queued job with actionable error text

### Archive failures

- invalid archive
- encrypted archive
- unsafe member path
- unsupported archive member handling

Result:
- reject candidate snapshot
- preserve last successful snapshot as current

### Item-level processing failures

- parse/extract failure on one file
- sink write failure on one file

Result:
- keep partial progress for other items
- mark item failed or degraded
- retain the previous good bound state where applicable

### Notes conflicts

- detached synced note

Result:
- do not overwrite
- mark `conflict_detached`

### Sink mutation attempts

- changing `sink_type` or source identity after first success

Result:
- reject with 400/409
- never migrate implicitly

## Security and Deployment Constraints

### Local directory roots

Add a dedicated allowlist such as:

- `INGESTION_SOURCE_ALLOWED_ROOTS`

Behavior:
- create/update validates configured path against the allowlist
- runtime scan revalidates actual resolved path containment before reading
- symlink and traversal escapes must be treated as unsafe

### Archive safety

Follow the same archive-member safety posture already used in other parts of the repo:

- reject zip-slip and unsafe member names
- reject unsupported encrypted archives
- never extract blindly into uncontrolled paths

## Retention and Cleanup

Staged uploads and extracted candidate snapshots need explicit cleanup rules.

Defaults:
- keep current successful snapshot
- keep a bounded number of previous successful snapshots
- keep failed candidate snapshots only briefly for debugging
- remove expired staged artifacts with a cleanup job/service

This prevents archive-backed sync sources from becoming unbounded storage leaks.

## Testing Strategy

### Unit tests

- path normalization and allowed-root enforcement
- archive root stripping
- snapshot diffing
- lifecycle policy behavior
- sink selection and routing
- detached-note conflict handling

### Integration tests

- local directory initial sync
- local directory rescan with add/change/delete
- archive source initial upload
- archive source successful re-upload diff
- archive source failed re-upload rollback
- media sink version update behavior
- notes sink latest-state update behavior
- detached note not overwritten on later sync
- scheduled enqueue without inline processing

### Security tests

- path traversal via local path input
- unsafe archive member names
- symlink/path escape attempts

### Verification

- targeted pytest scope for new backend paths
- Bandit on touched Python scope before completion

## Recommended Implementation Sequence

1. Add generic source tables and source-state invariants
2. Add snapshot builder and diff engine
3. Add local-directory source adapter
4. Add archive candidate snapshot flow
5. Add media sink adapter
6. Add notes sink adapter with `sync_managed` / `detached` semantics
7. Add Jobs worker and scheduled enqueue
8. Add source CRUD/status APIs
9. Add UI after backend behavior is stable

## Final Decisions Captured

- The solution is a general sync/import system for document/file ingestion, not a Notes-only feature
- v1 source types:
  - local directory
  - uploaded archive snapshot
- local-directory refresh:
  - manual sync
  - optional scheduled rescans
- archive refresh:
  - UI/manual re-upload
  - API refresh for the same source
- destination model:
  - selectable sink per source (`media` or `notes`)
- lifecycle:
  - per-source policy
- Notes sink:
  - latest-state sync only
  - detached conflict semantics
- sink/source identity:
  - immutable after first successful sync
