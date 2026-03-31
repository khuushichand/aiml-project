# Reference Manager Import Sync Design

## Summary

This design adds a generic reference-manager integration layer to `tldw_server2` so users can link a scholarly library account, choose collections or folders as sources, and continuously import newly added papers into a NotebookLM-style workspace.

The approved v1 scope is intentionally narrow:

- generic abstraction first, not a Zotero-only one-off
- import mode, not mirror mode
- reliable one-way sync from linked collections or folders into local workspaces
- strong dedupe so repeated sync runs and multi-collection overlap do not create noisy duplicates
- metadata fidelity so imported items carry DOI, authors, dates, and related bibliographic context cleanly
- background live sync driven by the existing scheduler and job infrastructure

This design explicitly excludes bidirectional repair, upstream delete propagation, and full annotation parity in the first slice.

## Feasibility Verdict

This feature is feasible in the current codebase and fits the existing architecture better than it would have a month earlier.

The main reason it is feasible now is that the repo already has the hard operational primitives needed for a serious connector feature:

- OAuth-capable account and source plumbing in `tldw_Server_API/app/api/v1/endpoints/connectors.py`
- persistent connector account, source, and sync-state storage in `tldw_Server_API/app/core/External_Sources/connectors_service.py`
- a recurring scheduler bridge in `tldw_Server_API/app/services/connectors_sync_scheduler.py`
- async job workers for connector sync execution in `tldw_Server_API/app/services/connectors_worker.py`
- DOI-aware scholarly ingestion and normalized `safe_metadata` handling in `tldw_Server_API/app/api/v1/endpoints/paper_search.py`

The main reason it is not trivial is that the current connector framework is optimized for file-hosting providers. Scholarly libraries behave differently:

- the primary entity is a reference item, not a file
- bibliographic identity and attachment identity are related but not the same
- sync must tolerate items with strong metadata but no retrievable attachment
- dedupe decisions must prefer false negatives over false merges

That means v1 should reuse the existing connector control plane and job model, but it should not pretend a Zotero library item is just another Drive file.

## Goals

- Let users link a reference-manager account through the existing connectors model.
- Let users choose one or more collections or folders as linked import sources.
- Automatically import newly discovered papers from those linked sources on a schedule.
- Preserve bibliographic fidelity in local `safe_metadata` fields.
- Prevent duplicate local imports across repeated syncs and overlapping collections.
- Keep the reference manager as the source of discovery without making upstream edits or deletes destructive to local workspace content.
- Surface clear per-source sync status, counts, and failure reasons in the existing connector UX.
- Design the provider abstraction so Zotero can ship first while Mendeley can follow without redesigning the storage or worker contract.

## Non-Goals

- Propagating local edits back to Zotero, Mendeley, or another provider.
- Rewriting or deleting local media because an upstream record changed or disappeared.
- Full synchronization of annotations, highlights, or notes from the provider into first-class local annotation objects.
- Building a generic citation-writing or bibliography-editing interface in v1.
- Supporting every scholarly provider in the first delivery.
- Replacing the existing file-sync connector architecture.

## Requirements Confirmed With User

- The feature is for `tldw_server2`'s own NotebookLM-style workspace, not for Google NotebookLM.
- The abstraction should be generic from the start, even if that slows initial delivery.
- The v1 non-negotiable outcomes are:
  - reliable one-way sync into a workspace with dedupe
  - metadata fidelity for DOI, authors, and date
  - background live sync from linked collections or folders
- The source-of-truth model for v1 is import mode:
  - new items flow in automatically
  - upstream edits or deletes do not rewrite or remove local items by default

## Current State

### What Already Exists

- External accounts and sources for connectors
- OAuth start and callback flows
- provider registry and provider-specific source configuration
- scheduler-driven sync job submission
- worker execution for connector jobs
- local media ingest and update paths
- DOI-aware search and ingest endpoints
- normalized `safe_metadata` storage and search in Media DB

### What Does Not Exist Yet

- a scholarly-library provider contract distinct from file-sync adapters
- source models centered on collection and reference-item semantics
- dedupe ranking specialized for bibliographic imports
- source sync status that distinguishes metadata-only records from attachment-importable records
- a linked-library UX in the connectors or workspace surfaces
- provider-contract tests for scholarly library payloads

## Problems To Solve

### 1. The current connector model is file-centric

Drive and OneDrive sync are built around remote files and file revisions. A scholarly library item may have:

- metadata and an attachment
- metadata but no attachment
- multiple attachments
- multiple collections pointing at the same item

The first slice needs a dedicated abstraction that represents a reference item as the primary record and treats attachments as secondary import candidates.

### 2. Dedupe must work across provider boundaries and collection overlap

The same paper can appear:

- in the same collection across multiple sync runs
- in multiple linked collections in one provider account
- in two different providers
- as two local files with the same DOI but different filenames

If dedupe is weak, the feature becomes a duplicate factory. If dedupe is too aggressive, it collapses distinct records and damages trust.

### 3. Metadata quality is as important as file ingest

Users are asking for this feature partly to avoid manual metadata cleanup. If a sync imports a PDF but drops DOI, authors, or publication date, the feature misses the core user value.

### 4. Live sync must be reliable without requiring mirror semantics

The user wants background import of new upstream items, not a full mirrored library. That means the system must reliably discover and ingest new items while intentionally refusing to treat local state as a mirror of the upstream library.

### 5. Annotation retention is valuable but not affordable in v1

The current product already has annotation-related scope boundaries in workspace flows. Pulling third-party annotations into a stable, user-trustworthy local model would materially expand the first slice and should remain out of scope.

## Approaches Considered

### Approach 1: Add a research-specific import feature outside the connectors framework

Build a custom scholarly-library import surface under the research module and bypass the general connector machinery.

Pros:

- faster initial implementation
- fewer constraints from existing connector contracts

Cons:

- duplicates account linking, source state, scheduling, and job status
- makes later Mendeley support messier
- creates another sync system in a codebase that already has one

### Approach 2: Extend the connector framework with a new reference-manager adapter family

Reuse accounts, sources, scheduler, and jobs, but add a separate provider contract for scholarly libraries.

Pros:

- strongest fit with current architecture
- keeps OAuth, scheduling, status, and operations in one system
- supports a generic abstraction without pretending everything is a file
- makes phased provider rollout practical

Cons:

- requires more upfront design than a one-off Zotero integration
- forces some connector storage and worker paths to become slightly more general

### Approach 3: Build a full mirror-sync platform from the start

Import, update, delete, annotation sync, and optional write-back all in one system.

Pros:

- richest end-state
- avoids later architectural expansion

Cons:

- too broad for the approved v1
- highest risk surface
- likely to stall on edge cases around annotation fidelity and destructive sync behavior

## Recommendation

Use Approach 2.

The first delivery should extend the connector architecture with a dedicated `ReferenceManagerAdapter` family while keeping the operational model identical to the rest of the connector system:

- OAuth-based linked account
- source rows for linked collections or folders
- scheduled sync jobs
- per-source status and counts
- worker-owned import execution

The feature should remain intentionally import-only in v1. The reference manager is a discovery source for new papers, not a mirrored authority that can rewrite or delete local workspace content.

## Proposed Architecture

### High-Level Shape

Add a second connector family beside the current file-sync providers:

- `FileSyncAdapter`
  - current model for Drive and OneDrive
- `ReferenceManagerAdapter`
  - new model for Zotero, Mendeley, and future scholarly library providers

Both families reuse:

- account linking
- external source creation
- scheduler integration
- job execution
- sync status APIs

They differ in how they enumerate remote entities, choose import candidates, persist remote identity, and decide dedupe.

### New Provider Contract

`ReferenceManagerAdapter` should define a minimal provider contract centered on collections and items rather than files.

Expected capabilities:

- `list_collections(account_tokens, cursor=None)`
- `get_collection(account_tokens, collection_key)`
- `list_items(account_tokens, collection_key, cursor=None, updated_after=None)`
- `get_item_metadata(account_tokens, item_key)`
- `list_item_attachments(account_tokens, item_key)`
- `resolve_attachment_download(account_tokens, attachment_descriptor)`
- `normalize_reference_item(raw_item, raw_attachments) -> NormalizedReferenceItem`
- optional push-friendly methods later, but not required in v1

The normalized item should include:

- provider item key
- provider library id or account-scoped remote namespace
- collection keys
- provider version or updated timestamp
- item type
- title
- authors
- publication date or year
- DOI
- journal or venue
- abstract if available
- source URL
- attachment descriptors

### Source Types

The existing `external_sources` concept should be reused, but source options must support reference-manager semantics.

New source option shape should allow:

- `remote_source_type: "reference_collection"`
- `collection_key`
- `collection_name`
- `import_attachments: true | false`
- `sync_mode: "poll"`
- optional future provider-specific knobs

For v1, the linked source should be a collection or folder, not an entire account library by default. That keeps sync scope understandable and aligned with the user's request.

### Storage Model

Reuse the current external account and source tables, but add a dedicated reference-item sync storage layer instead of forcing everything into file-binding columns.

Add a new table, or equivalent storage abstraction, conceptually shaped like:

- `external_reference_items`
  - `source_id`
  - `provider`
  - `provider_item_key`
  - `provider_parent_key`
  - `provider_version`
  - `provider_updated_at`
  - `attachment_status`
  - `attachment_source_url`
  - `media_id`
  - `dedupe_match_reason`
  - `raw_reference_metadata`
  - `last_seen_at`
  - `last_imported_at`
  - `last_metadata_sync_at`

This should be separate from file-centric binding state because one reference item may represent:

- no file
- one importable file
- multiple candidate files
- a duplicate of an already imported local media item

### Local Metadata Contract

When a media item is imported or linked by dedupe hit, the local active version should carry normalized scholarly metadata in `safe_metadata`.

The normalized scholarly block should include:

- `provider`
- `provider_item_key`
- `provider_library_id`
- `collection_key`
- `source_url`
- `doi`
- `title`
- `authors`
- `publication_date`
- `journal`
- `abstract`
- `import_mode: "reference_manager"`

The first delivery should normalize field names aggressively so downstream search, RAG, and workspace UI do not need provider-specific branching for basic bibliographic display.

## Data Flow

### Link Flow

1. User starts OAuth flow for a reference-manager provider.
2. OAuth callback stores account tokens in the same external-account system used by current connectors.
3. User browses available collections or folders.
4. User links one or more collections as import sources.
5. Source options persist collection identity and sync configuration.

### Scheduled Sync Flow

1. The scheduler scans linked sources.
2. For each eligible reference-manager source, it enqueues a sync job.
3. The worker reserves the source and loads account tokens.
4. The provider adapter enumerates new or updated items using cursor or updated-since semantics.
5. Each remote item is normalized into a provider-neutral bibliographic shape.
6. The worker resolves attachment candidates only when needed for import.
7. The worker runs dedupe ranking.
8. If no match exists:
   - import the best attachment into Media DB when available
   - or record a metadata-only skip state if the provider has no retrievable attachment
9. If a match exists:
   - record the remote binding against the local media item
   - optionally fill missing normalized metadata fields
   - do not overwrite local content, local notes, or local versions in v1
10. Persist item-level results and advance the source cursor.

### Import-Mode Semantics

V1 must keep import mode explicit:

- newly discovered upstream items can create or attach to local records
- upstream edits do not automatically rewrite local records
- upstream deletes do not remove local records
- local users remain free to continue working on imported content without destructive upstream replay

## Dedupe Strategy

### Ranking Order

Dedupe should be strict-first and fuzzy-last:

1. existing binding on the same `provider + provider_item_key`
2. DOI match
3. normalized attachment hash match
4. conservative metadata fingerprint match:
   - normalized title
   - first author
   - year or publication date

### Why This Order

- provider item keys are best for idempotence within one provider account
- DOI is the strongest cross-provider scholarly identity
- attachment hash catches local duplicates where metadata differs slightly
- title-author-year fallback is necessary, but dangerous enough that it must remain conservative

### Match Outcomes

Each dedupe decision should persist a match reason:

- `same_provider_item`
- `doi`
- `file_hash`
- `metadata_fingerprint`
- `none`

This gives the UI and debugging surfaces enough information to explain why an item was skipped or linked.

### Overwrite Policy

On dedupe hit, v1 may enrich missing local metadata fields if the incoming provider metadata is stronger and the local field is currently missing. It must not:

- overwrite user-edited titles by default
- replace local extracted text
- create a new content version solely because provider metadata changed

That boundary keeps v1 import-safe.

## Background Live Sync

The approved live-sync requirement should be implemented as scheduled polling first.

Why polling first:

- it matches the current scheduler and jobs model
- it is provider-agnostic
- it avoids making v1 dependent on webhook parity across scholarly providers

Future push or streaming provider features can be layered in later where they exist, but they should feed the same source sync job path instead of creating a second execution model.

## UX and Control Plane

### User-Facing Shape

Present the feature as a linked-library workflow inside the existing connectors and workspace surfaces, not as a one-off import wizard.

The user flow should be:

- connect provider
- pick collections
- enable background import
- review sync status and imported items

### Per-Source Status

Each linked source should surface:

- provider
- collection name
- last successful sync
- last failed sync
- imported count
- skipped duplicate count
- metadata-only or attachment-missing count
- current state:
  - idle
  - queued
  - running
  - failed
  - auth_expired

### Failure Categories

The first delivery should distinguish:

- auth expired
- rate limited
- collection unavailable
- item metadata incomplete
- attachment missing
- duplicate skipped
- import failed

These are operationally and user-meaningfully different. The UI should not collapse them into a single generic failure string.

## Error Handling

### Principles

- keep sync jobs idempotent
- never delete local content during v1 sync
- preserve partial progress where possible
- record item-level outcomes for observability

### Item-Level Failures

If one item fails, the job should continue unless the provider session is irrecoverable. Common per-item failures include:

- malformed provider payload
- unsupported attachment type
- attachment download failure
- metadata normalization failure
- ingest failure

Each failure should be recorded against the item result rather than aborting the whole collection sync immediately.

### Source-Level Failures

Source-level failures include:

- revoked or expired OAuth credentials
- provider API outage
- invalid collection id
- unrecoverable cursor corruption

These should mark the source status clearly and halt further incremental advancement until the error is resolved.

## Testing Strategy

### Unit Tests

- metadata normalization from raw provider payloads into normalized scholarly metadata
- dedupe ranking and tie-breaking
- source option validation
- import-mode overwrite guards

### Integration Tests

- OAuth account linking and source creation through the connector API
- scheduler enqueue of reference-manager sync jobs
- worker execution for collection sync
- cursor persistence and incremental replay behavior
- duplicate handling across overlapping linked collections
- metadata enrichment of missing local fields without destructive overwrite

### Provider-Contract Tests

Define provider-agnostic contract fixtures so each provider proves:

- collection listing works
- item normalization returns required fields
- attachment resolution behavior is explicit
- pagination or cursor advancement is correct

The first provider should be Zotero, but the tests should be written against the generic contract from day one so Mendeley support does not require a design reset.

## Rollout Strategy

### Phase 1

- add `ReferenceManagerAdapter`
- add source options and storage for collection-linked sources
- implement Zotero provider
- implement scheduled import-mode sync
- implement dedupe and normalized metadata persistence
- surface basic linked-source status

### Phase 2

- add Mendeley provider against the same contract
- improve observability and source diagnostics
- add workspace affordances for imported scholarly metadata

### Future Phases, Not V1

- metadata write-back
- annotation import and mapping
- mirror-mode sync
- provider push notifications where they offer real value

## Risks and Mitigations

### Risk: Generic abstraction becomes over-engineered before the first provider ships

Mitigation:

- keep the adapter contract small
- build only the methods needed for collection-linked import mode
- let Zotero drive the first real shape of the abstraction

### Risk: Dedupe false positives merge distinct papers

Mitigation:

- use conservative fallback matching
- prioritize DOI and provider item identity
- store dedupe match reason
- prefer duplicate leakage over destructive merge

### Risk: Metadata-only items confuse users

Mitigation:

- record and surface attachment-missing outcomes explicitly
- do not silently present metadata-only references as successful content imports

### Risk: Mendeley parity diverges from Zotero assumptions

Mitigation:

- define provider-contract tests
- keep provider-specific fields inside normalized item conversion
- avoid embedding Zotero-specific collection or attachment assumptions into shared storage

## Decision Summary

The correct v1 is a generic reference-manager connector family built on the existing connector control plane and job model, with these fixed boundaries:

- import mode only
- collection-linked sources
- polling-based live sync first
- strict metadata normalization
- strict-first dedupe
- no upstream destructive replay
- no annotation sync
- no write-back

That slice is large enough to deliver meaningful user value and small enough to plan and implement without turning into a full scholarly-library platform rewrite.
