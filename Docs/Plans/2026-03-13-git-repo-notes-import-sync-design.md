# Git Repo Notes Import and Sync Design

Date: 2026-03-13
Status: Approved
Scope: Add git-repository-backed import and sync for Notes, with folder-aware organization

## 1. Summary

Extend the existing `ingestion_sources` subsystem with a new `git_repository` source type so users can:

- point at a local checked-out git repository and import or sync notes
- connect a remote GitHub repository and import or sync notes
- map repository files into Notes
- organize imported notes using dedicated Notes folder support

This is not a Notes-only one-shot importer bolted onto `POST /api/v1/notes/import`.
The design intentionally reuses the existing source tracking, diffing, job execution, and notes sync behaviors where they fit, then adds missing Notes folder primitives where the current model is insufficient.

## 2. User-Approved Product Decisions

1. The feature should support both one-time import and ongoing sync.
2. The feature should support both local repositories and remote repositories.
3. Folder structure should become a first-class Notes organization concept.
4. Repo-derived folders should be user-editable after import or sync.
5. Sync should be additive for folder membership:
   - preserve extra user-added folders
   - continue managing repo-derived folder memberships owned by the sync source
6. Design review corrections were accepted before documentation:
   - do not overload existing Notes smart collections for repo folders
   - narrow V1 remote support to GitHub
   - make V1 rename semantics explicit instead of implying path continuity

## 3. Current Verified State

### 3.1 Existing Notes import is batch import, not source sync

`POST /api/v1/notes/import` already accepts JSON and Markdown batch imports with duplicate strategies in:

- `tldw_Server_API/app/api/v1/endpoints/notes.py`
- `tldw_Server_API/app/api/v1/schemas/notes_schemas.py`

This endpoint is import-only. It does not persist source identity, diff later refreshes, or track sync ownership.

### 3.2 Existing ingestion sources already sync local directories into Notes

The repository already has a reusable `ingestion_sources` subsystem with:

- source records
- source item bindings
- snapshots and diffing
- notes/media sink selection
- job-backed sync
- conflict detach and reattach behaviors for synced notes

Relevant files:

- `tldw_Server_API/app/api/v1/endpoints/ingestion_sources.py`
- `tldw_Server_API/app/core/Ingestion_Sources/service.py`
- `tldw_Server_API/app/services/ingestion_sources_worker.py`
- `tldw_Server_API/app/core/Ingestion_Sources/sinks/notes_sink.py`

### 3.3 Existing Notes collections are not note folders

Current Notes organization primitives are:

- `keywords`
- `keyword_collections`
- `note_keywords`
- `collection_keywords`

Important constraint:

- `keyword_collections` group keywords, not notes
- notes do not directly belong to collections
- `keyword_collections.name` is globally unique

Relevant files:

- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- `apps/packages/ui/src/components/Notes/NotesSidebar.tsx`
- `apps/packages/ui/src/components/Notes/NotesManagerPage.tsx`

This means repo folder support cannot safely be implemented by simply reusing current smart collections.

### 3.4 Existing notes do not have general metadata storage

The current Notes table stores:

- `id`
- `title`
- `content`
- timestamps
- deletion/version/client metadata
- backlinks added later for conversation/message references

There is no generic note metadata column that could safely hold repo folder identity or provenance.

### 3.5 Existing notes sync is path-bound and detach-aware

The Notes sink currently:

- derives note title from file content or filename
- updates an existing note only when the current source item binding already exists
- marks locally edited synced notes as detached by leaving them out of overwrite flow

The current ingestion item identity is `source_id + normalized_relative_path`.
As implemented today, path moves are naturally modeled as delete plus create.

### 3.6 Existing remote account/OAuth patterns are real, but not git-specific

The repository already has remote account and OAuth patterns under `External_Sources`, but those connectors are designed around provider file APIs and media/document sync. They are useful precedents for account binding and token storage, but they are not a drop-in git transport layer.

## 4. Goals and Non-Goals

### 4.1 Goals

- Support repo-backed Notes import and sync using the existing source-sync architecture.
- Support both local repositories and remote GitHub repositories in V1.
- Add true Notes folder support needed for repo path organization.
- Preserve user freedom to edit repo-derived folders while keeping source-owned folder reconciliation reliable.
- Keep source status, partial failures, and detach behavior visible through existing source management surfaces.

### 4.2 Non-Goals

- Generic git transport support for all providers in V1.
- GitLab, Bitbucket, or arbitrary SSH remotes in V1.
- Full rename continuity for moved files in V1.
- Three-way merge for note content conflicts.
- Reusing current Notes smart collections as filesystem folders.
- Broad document conversion for repo sync in V1 beyond text-first note files.

## 5. Approaches Considered

### Approach A (Rejected): Extend `/api/v1/notes/import` with repo inputs

Pros:

- smaller immediate API surface
- faster demo path for one-time imports

Cons:

- duplicates logic that already belongs in `ingestion_sources`
- creates drift between import and sync behavior
- makes item tracking, diagnostics, and conflict handling worse

### Approach B (Recommended): Add `git_repository` as a first-class ingestion source

Pros:

- reuses existing source lifecycle, diffing, and job patterns
- keeps one-time import and ongoing sync on the same engine
- aligns with the current local-directory-to-notes sync model

Cons:

- requires additional source configuration and Notes folder schema work
- remote GitHub support still needs explicit fetch/cache handling

### Approach C (Rejected): Fake git repos as `local_directory` sources

Pros:

- minimal schema change
- maximum reuse of current code

Cons:

- remote repositories become awkward and under-specified
- repo-specific diagnostics and settings have nowhere good to live
- source identity becomes muddy

## 6. Selected Architecture

Proceed with **Approach B**.

Add `git_repository` as a new `ingestion_sources.source_type`, then implement:

- local repository scanning
- remote GitHub repository materialization
- repo-aware Notes mapping
- dedicated Notes folder primitives

One-time import remains a product mode, not a separate backend subsystem.

## 7. Source Model

### 7.1 New source type

Add:

- `git_repository`

to the allowed ingestion source types in:

- backend schemas
- normalization helpers
- frontend types
- source-creation UI

### 7.2 Source configuration

Proposed config fields:

- `mode`: `local_repo` | `remote_github_repo`
- `label`: optional display label
- `path`: local repository path when `mode=local_repo`
- `repo_url`: GitHub repository URL when `mode=remote_github_repo`
- `account_id`: linked remote account identifier for private GitHub access
- `ref`: branch, tag, or commit-ish to sync
- `root_subpath`: optional subdirectory inside the repo to treat as the notes root
- `include_globs`: optional allowlist patterns
- `exclude_globs`: optional denylist patterns
- `respect_gitignore`: boolean, default true for local repos
- `import_mode`: `one_time` | `ongoing`

### 7.3 One-time import behavior

One-time import should:

1. create a `git_repository` source
2. run the initial sync
3. leave the source with `policy=import_only`
4. hide completed import-only sources from the default Sources list unless the user opts to show them

This preserves future convert-to-sync potential without cluttering the main source-management experience.

## 8. Remote Scope and Fetch Strategy

### 8.1 Remote provider scope

V1 remote support is intentionally narrow:

- GitHub only

This includes:

- public repositories
- private repositories via linked GitHub account

### 8.2 Auth model

Reuse the project’s existing account-binding and OAuth storage patterns conceptually, but do not claim current file connectors can be reused unchanged for git sync. This feature needs a GitHub-specific repo access flow built on the same AuthNZ/account primitives.

### 8.3 Materialization strategy

Remote GitHub repositories should be materialized into a managed local cache before snapshotting.

Preferred V1 strategy:

- fetch repository archive or file-tree contents from GitHub for the requested ref
- unpack into a source-managed cache directory
- scan the materialized tree using the same snapshot pipeline as local repos

This keeps local and remote scanning behavior aligned while avoiding generic git transport complexity in V1.

## 9. Notes Folder Model

### 9.1 Why current collections are insufficient

The current Notes smart collections are keyword groups, not note containers. Repo folders need:

- stable folder identity
- parent-child hierarchy
- direct note membership
- provenance to distinguish repo-managed memberships from user-managed ones

### 9.2 Required schema expansion

Add dedicated Notes folder primitives rather than overloading `keyword_collections`.

Proposed new tables:

- `note_folders`
  - stable folder row per user
  - `id`
  - `name`
  - `parent_id`
  - standard timestamps/version/client metadata
  - `provenance_json` or equivalent structured repo provenance
- `note_folder_memberships`
  - direct note-to-folder links
  - `note_id`
  - `folder_id`
  - provenance or ownership flags if needed

Provenance should record enough information to answer:

- which source owns this folder node
- which repo-relative path segment chain created it
- whether this membership was repo-managed or user-added

### 9.3 User-editable repo folders

Because the approved UX requires repo-derived folders to remain user-editable:

- sync must track ownership by stable IDs and provenance, not folder names
- user rename of a repo-derived folder must not force the system to recreate a new folder under the old path name
- extra user-created folder memberships must survive sync

### 9.4 Additive reconciliation

For each synced note, the source binding should track the set of repo-managed folder memberships it owns.

Sync may:

- add missing repo-managed memberships
- remove stale repo-managed memberships for this source

Sync may not:

- remove extra user-added memberships not owned by the source

## 10. Content Mapping

### 10.1 Supported repo note files in V1

Keep V1 text-first and intentionally narrow:

- `.md`
- `.markdown`
- `.txt`

Defer broader format support such as `.html`, `.docx`, or `.rtf` until repo sync behavior is stable.

### 10.2 Title and body derivation

Use the same general title heuristics already present in notes import and notes sync:

- front matter `title`
- first Markdown heading
- first non-empty line
- filename stem fallback

Store:

- Markdown files as Markdown content
- plain text files as plain text content

### 10.3 Provenance

Each synced note binding should retain repo provenance in `ingestion_source_items.binding_json`, including:

- `note_id`
- `sync_status`
- `current_version`
- repo-relative path
- repo-managed folder membership IDs
- source ref or revision metadata as helpful diagnostics

## 11. Sync Semantics

### 11.1 Baseline identity

The baseline tracked item identity remains:

- `source_id + normalized_relative_path`

This matches the current ingestion source model and keeps V1 diffing straightforward.

### 11.2 Change handling

For unchanged paths:

- do nothing

For changed paths:

- update note content unless detached
- reconcile repo-managed folder memberships

For deleted paths:

- apply existing policy behavior
- `canonical`: archive or soft-delete bound note
- `import_only`: leave note in place

### 11.3 Rename and move semantics

V1 must state this explicitly:

- path rename or move is treated as `delete old path` plus `create new path`

Do not promise note continuity on rename in V1.

Possible follow-on:

- content-hash-assisted rename detection

### 11.4 Content detach vs folder management

Split detach behavior into two concerns:

- `content_detached`
  - stop overwriting title/body
- `folders_managed`
  - continue reconciling repo-managed folder memberships

This preserves user content edits without freezing repo-path-based organization.

## 12. Local Repository Rules

### 12.1 Allowed roots

Local repositories must:

- resolve under configured allowed roots
- be revalidated at sync time

### 12.2 Scan behavior

Local sync should:

- ignore `.git/`
- respect `gitignore` by default
- ignore unsupported file suffixes
- record useful diagnostics such as current `HEAD` and dirty-state summary

Local dirty working tree state should be surfaced as informational status, not treated as a fatal error by default.

## 13. API and UI Shape

### 13.1 Backend API

Reuse the current ingestion source endpoints and extend them for `git_repository`.

No new repo-specific Notes import endpoint is required for V1.

Additional Notes folder endpoints will be required for:

- folder CRUD
- note-folder membership CRUD
- listing hierarchy for UI use

### 13.2 Sources UI

Extend the existing Sources workspace with:

- `Git repository` as a source type
- local vs remote GitHub selection
- repo/ref/path/glob configuration
- one-time import vs keep synced choice
- repo-specific diagnostics on the detail page

### 13.3 Notes UI

Add a convenience action such as:

- `Import from repo`

This should deep-link into the Sources creation flow with sensible defaults, rather than creating a parallel feature surface.

## 14. Error Handling

### 14.1 Local repository errors

- path outside allowed roots
- path exists but is not a git repository
- path disappears between creation and sync

Result:

- reject create/update or fail sync with actionable error text

### 14.2 Remote GitHub errors

- missing linked account
- expired or revoked token
- repo not found
- ref not found
- fetch/materialization failure

Result:

- preserve last successful snapshot
- do not mutate prior good bindings
- surface reconnect or retry guidance

### 14.3 Item-level failures

- parse failure for one file
- sink write failure for one note
- folder reconciliation failure for one note

Result:

- continue best-effort for other items
- record per-item failure/degraded state

## 15. Testing Strategy

### 15.1 Unit tests

- `git_repository` config normalization
- local repo path validation
- local repo snapshot builder
- GitHub remote materialization state transitions
- file suffix filtering and `gitignore` handling
- Notes folder hierarchy and membership helpers
- additive repo-managed folder reconciliation
- content-detached plus folders-managed behavior

### 15.2 Integration tests

- local repo one-time import
- local repo ongoing sync with create/update/delete
- remote GitHub public repo sync
- remote GitHub private repo sync with linked account
- repo-managed folder creation and reuse
- user-added extra folders survive sync
- content detach prevents overwrite but still allows folder updates
- import-only source stays hidden from default list surfaces after completion

### 15.3 UI tests

- Sources form supports `git_repository`
- Git repository detail page renders diagnostics
- Notes shortcut deep-links correctly
- folder tree or folder selectors render new dedicated Notes folders, not smart collections

### 15.4 Security tests

- local path escape rejection
- `.git` internals excluded from ingestion
- remote account scoping per user
- managed cache paths cannot escape configured storage roots

## 16. Recommended Implementation Sequence

1. Add `git_repository` source type to backend and frontend source schemas.
2. Add dedicated Notes folder schema and DB helpers.
3. Add Notes folder API surface and basic UI read/write plumbing.
4. Implement local repo snapshot builder with text-first suffix filtering.
5. Extend notes sink and source bindings for repo provenance plus folder ownership tracking.
6. Implement one-time import UX mode on top of the same source engine.
7. Implement remote GitHub account binding and materialization flow.
8. Add repo diagnostics to Sources detail pages.
9. Add Notes shortcut entry point and folder-aware Notes UI updates.
10. Add verification coverage, then follow-on rename detection only if still needed.

## 17. Final Decisions Captured

- Repo import and sync belong in `ingestion_sources`, not in a new Notes-only importer.
- V1 supports:
  - local git repositories
  - remote GitHub repositories
  - one-time import
  - ongoing sync
- Existing Notes smart collections are not used for repo folders.
- Dedicated Notes folder primitives are required.
- Repo-derived folders remain user-editable.
- Sync remains additive for folder memberships.
- Remote V1 scope is GitHub-only.
- V1 path rename semantics are delete plus create.
