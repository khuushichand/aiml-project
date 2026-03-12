# Workspace Source Folders + Workspace Collections Design

Date: 2026-03-11
Owner: Codex collaboration session
Status: Approved (revised after design review)

## Context and Problem

`/workspace-playground` currently has two organization gaps:

- Sources inside a workspace live in one flat `WorkspaceSource[]` list.
- Saved workspaces are presented as a flat browser with search, pinning, and archive, but no true topical grouping.

This prevents two common research workflows:

1. Organizing sources inside a workspace by nested themes, evidence buckets, or modality-specific subtopics.
2. Organizing multiple related workspaces under a broader topic while keeping each workspace focused on a narrower question.

The current implementation is also local-first and persistence-heavy, so any design must respect the existing Zustand workspace store, split storage/indexed DB offload, and workspace import/export bundle flow.

## Goals

1. Add nested source folders inside a workspace.
2. Allow a source to belong to multiple source folders in the same workspace.
3. Make source folders selectable for grounded chat/output scope, with recursive inclusion of descendant folders.
4. Add flat workspace collections across saved workspaces.
5. Allow exactly one collection per workspace in v1.
6. Keep the design local-first for v1, but shape it so future server-backed sync is straightforward.

## Non-Goals

1. Server-backed sync/storage for folders or collections in v1.
2. Shared collection overview pages, shared notes, or collection-level RAG behavior.
3. Collection nesting in v1.
4. Folder-level exclusion rules in v1.
5. Auto-generating folders from source type or collections from workspace name/tag.
6. Sharing, permissions, color systems, or collaborative editing.

## Current Constraints

### Workspace sources are flat

The current workspace state stores:

- `sources: WorkspaceSource[]`
- `selectedSourceIds: string[]`

There is no existing folder or membership model for workspace sources.

### Saved workspaces are flat and capped

Saved workspaces currently store only:

- `id`
- `name`
- `tag`
- `createdAt`
- `lastAccessedAt`
- `sourceCount`

The current store truncates `savedWorkspaces` to `MAX_SAVED_WORKSPACES = 10`. That cap is incompatible with meaningful collection browsing and must change as part of this work.

### Persistence is local-first

Workspace persistence already uses:

- persisted Zustand state
- split-key storage/indexed DB offload for large payloads
- quota recovery that evicts heavy snapshot/session payloads

The design should preserve those mechanisms instead of replacing them.

## Design Decision

Use two independent organization systems:

1. **Source folders**
   - Scoped to a single workspace snapshot.
   - Nested.
   - Many-to-many with sources.
   - Selectable as recursive grounded context.

2. **Workspace collections**
   - Scoped to the global saved-workspace browser.
   - Flat in v1.
   - Exactly one collection per workspace.
   - Organizational container only.

Use a **local-first, server-ready entity/link model** for both systems so a future backend API can adopt the same shapes without rewriting the client semantics.

## Proposed Data Model

### 1) Source folders

Add two new entities to the workspace snapshot.

#### `WorkspaceSourceFolder`

- `id: string`
- `workspaceId: string`
- `name: string`
- `parentFolderId: string | null`
- `createdAt: Date`
- `updatedAt: Date`

#### `WorkspaceSourceFolderMembership`

- `folderId: string`
- `sourceId: string`

### 2) Workspace collections

Add one global entity plus a collection reference on saved workspace metadata.

#### `WorkspaceCollection`

- `id: string`
- `name: string`
- `description: string | null`
- `createdAt: Date`
- `updatedAt: Date`

#### `SavedWorkspace` extension

Add:

- `collectionId: string | null`

### 3) Workspace state additions

Add to current workspace snapshot/state:

- `sourceFolders: WorkspaceSourceFolder[]`
- `sourceFolderMemberships: WorkspaceSourceFolderMembership[]`
- `selectedSourceFolderIds: string[]`
- `activeFolderId: string | null`

Add to global workspace list state:

- `workspaceCollections: WorkspaceCollection[]`

## Validation Rules

### Source folders

1. Folder IDs must be unique within the workspace.
2. A folder cannot parent itself.
3. A folder cannot move under one of its descendants.
4. Sibling folder names must be unique under the same parent.
5. Duplicate `folderId + sourceId` memberships are not allowed.

### Workspace collections

1. Collection IDs must be unique.
2. Collection names must be unique after trim/case-normalization.
3. A workspace may reference at most one collection ID.

## Selection Model

The existing direct source selection remains in place. Folder selection is additive, not a replacement.

### State

- `selectedSourceIds`
  - direct source picks
- `selectedSourceFolderIds`
  - folder picks for grounded context
- `activeFolderId`
  - browse/filter focus only; does not affect grounded context by itself

### Derived selection

Add a derived selector:

- `effectiveSelectedSourceIds: string[]`

It is the unique set of ready source IDs from:

1. directly selected ready sources
2. all ready sources reachable from selected folders
3. all ready sources reachable from descendant folders of selected folders

### Folder recursion rules

Selecting a parent folder includes:

1. sources directly assigned to the folder
2. sources assigned to every descendant folder at any depth

No exclusion model is included in v1.

### Source selection origin

Each source row should derive one of:

- `direct`
- `folder`
- `both`
- `none`

This is required because a source can be selected through a folder even if its direct checkbox was never toggled.

### Source row interaction rules

1. If a source is `none`, clicking selects it directly.
2. If a source is `direct`, clicking deselects it directly.
3. If a source is `folder`, clicking does not remove it from effective context; the UI should make clear it is included via folder.
4. If a source is `both`, clicking removes only the direct selection; the source remains included via folder.

### Folder checkbox state

Folder checkboxes must be tri-state:

- `unchecked`
- `checked`
- `indeterminate`

Tri-state calculations must be based on **unique descendant ready source IDs**, not raw membership row counts, because a source can belong to multiple folders.

## Source Folder UI

### Placement

Add a collapsible source-folder tree above the source list in the Sources pane.

### Folder row behavior

Each folder row should expose:

- expand/collapse
- context checkbox
- folder name
- descendant ready-source count
- actions:
  - new subfolder
  - rename
  - move
  - delete

### Folder focus vs context selection

Separate two concepts:

1. **Focus/filter**
   - clicking the folder name sets `activeFolderId`
   - source list filters to the focused subtree

2. **Context selection**
   - clicking the folder checkbox toggles `selectedSourceFolderIds`
   - grounded chat/output uses `effectiveSelectedSourceIds`

### Membership management

Support both:

1. drag/drop source rows onto folders
2. source-row and bulk "Add to folders" action

Because membership is many-to-many, users must be able to add a source to several folders without moving it out of previous folders.

### Folder deletion

Deleting a folder:

1. never deletes sources
2. deletes memberships attached to that folder
3. reparents child folders to the deleted folder's parent
4. removes the folder from `selectedSourceFolderIds`
5. clears `activeFolderId` if that folder was focused

## Workspace Collection UI

### Placement

Collections belong in the workspace browser/header flow, not inside the current workspace panes.

### Browser behavior

The workspace browser should support:

1. create collection
2. rename collection
3. delete collection
4. filter workspaces by collection
5. grouped display by collection
6. an `Unassigned` bucket
7. assign/reassign a workspace to exactly one collection

### Collection deletion

Deleting a collection:

1. never deletes workspaces
2. sets member workspaces to `collectionId = null`
3. moves those workspaces into `Unassigned`

### Duplicate/import behavior

1. Duplicated workspaces inherit `collectionId`.
2. Imported workspaces are placed in `Unassigned`.

Imported workspace bundles must not blindly recreate global collection membership because collections are library-level organization, not intrinsic workspace content.

## Persistence and Migration

### Migration defaults

Existing persisted workspaces must load with:

- `sourceFolders = []`
- `sourceFolderMemberships = []`
- `selectedSourceFolderIds = []`
- `activeFolderId = null`
- `workspaceCollections = []`
- `collectionId = null` on all saved workspaces

### Import/export rules

Single-workspace bundle export/import should include:

- source folders
- source folder memberships
- selected source folder IDs

Single-workspace bundle export/import should not restore:

- global workspace collection assignments
- collection definitions

If import data is inconsistent:

1. memberships pointing to missing sources or folders are dropped
2. folders pointing to missing parents are reparented to root
3. selected folder IDs pointing to missing folders are dropped

### Saved workspace cap

Replace the current 10-item truncation for saved workspaces in any collection-aware release.

Recommended v1 rule:

- do not truncate saved workspace metadata
- rely on existing split storage and quota recovery to evict heavy snapshots/chat sessions instead of deleting workspace metadata

## Performance and Selector Architecture

Do not bury all recursive logic inside React components or the giant workspace store body.

Create pure selector/helper utilities for:

- `childrenByFolderId`
- `sourceIdsByFolderId`
- `folderIdsBySourceId`
- descendant folder resolution
- unique descendant source resolution
- effective selected source IDs
- folder tri-state status
- source selection origin

These selectors should be memoized at the component/store boundary and tested independently.

This is necessary to avoid:

1. duplicate counting bugs
2. tri-state inconsistencies
3. unreadable store logic
4. performance cliffs on medium/large folder trees

## Error Handling and Edge Cases

1. Folders may contain processing/error sources, but only ready sources participate in `effectiveSelectedSourceIds`.
2. If a selected folder currently resolves to zero ready sources, show that clearly in the UI.
3. Reject invalid moves that would create cycles.
4. Reject duplicate memberships silently at the store layer and explicitly in the UI.
5. Keep undo for folder/collection delete and move operations, consistent with existing source/workspace undo patterns.

## Risks and Mitigations

### Risk: inherited selection feels broken

If a source is selected via folder and the user clicks its checkbox, they may expect it to disappear from context.

Mitigation:

- explicit `direct/folder/both` origin state
- source-row UI copy that distinguishes direct selection from inherited inclusion

### Risk: collections do not scale

If the 10-workspace cap remains, collections become misleading and lossy.

Mitigation:

- remove saved-workspace truncation as part of this design

### Risk: import/export pollutes library-level organization

If single-workspace bundles restore global collection membership, imports can create invalid or surprising browser organization.

Mitigation:

- do not restore collection membership from workspace bundles

### Risk: duplicate counts and incorrect tri-state

Many-to-many memberships make naive subtree counting wrong.

Mitigation:

- all subtree counts and states must use unique source IDs

## Delivery Staging

Recommended delivery sequence:

1. workspace type/store migration and saved-workspace cap fix
2. workspace collections in the workspace browser
3. source-folder data model and pure selectors
4. source-folder UI and membership editing
5. effective selection integration with chat/output
6. import/export updates and regression coverage

This sequence delivers the simpler collection feature first while isolating the higher-risk recursive selection work.

## Success Criteria

1. Users can create nested source folders inside a workspace.
2. A source can belong to multiple folders.
3. Selecting a parent folder includes every ready source in descendant folders.
4. Direct source selection continues to work and is clearly distinguished from folder-derived inclusion.
5. Users can create flat workspace collections and assign each workspace to exactly one collection.
6. Workspace collections remain accurate beyond 10 saved workspaces.
7. Persistence/import/export behaves predictably without corrupting organization metadata.
