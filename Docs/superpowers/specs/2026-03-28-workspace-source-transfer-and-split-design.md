# Workspace Source Transfer And Split Design

Date: 2026-03-28
Owner: Codex collaboration session
Status: Reviewed with user, pending implementation planning

## Summary

This design adds a first-class way to reorganize large research workspaces by moving or copying selected sources into another workspace, including the ability to create a new workspace from the current selection.

The feature is built on the current local-first Workspace Playground store model:

- `WorkspaceSource.id` remains a workspace-local wrapper ID.
- `WorkspaceSource.mediaId` remains the shared underlying media identity.
- folder/group organization is notebook-local and can be transferred.
- preview annotations are not transferred in v1 because they are not persisted in workspace state today.

The same transfer engine powers two entry points:

1. A bulk `Move/Copy` action in the Sources pane.
2. A `Split Current Workspace` shortcut in the workspace header.

## Problem

Users often begin with one broad research workspace, then discover later that the material naturally separates into narrower subtopics. Once a workspace becomes large, the current workarounds are clumsy:

1. Duplicate the entire workspace, then manually remove the sources that do not belong.
2. Leave the workspace as-is and repeatedly hand-select relevant sources every time they want a narrower focus.

The product already supports:

- nested source folders inside a workspace
- bulk source selection
- workspace duplication

Those capabilities help, but they do not solve the missing workflow: taking a selected subset of sources and turning that subset into its own focused workspace, or transferring it into another existing workspace, without re-ingesting content.

## Goals

1. Let users bulk move or copy selected sources into another workspace.
2. Let users create a new workspace directly from the selected sources.
3. Preserve shared underlying media identity through `mediaId`.
4. Preserve notebook-local folder organization for transferred sources.
5. Detect destination conflicts by `mediaId` and give the user explicit choices.
6. Keep the implementation local-first and consistent with the current Zustand workspace store.

## Non-Goals

1. Server-backed source membership sync in v1.
2. A global source object shared by multiple workspaces through one common local `source.id`.
3. Transferring generated artifacts, workspace chat sessions, or workspace notes as part of source transfer.
4. Persisting and transferring source preview annotations in v1.
5. Replacing workspace duplication as a whole-workspace cloning tool.

## Current State

### Existing workspace source identity model

The current code already models a workspace source as a local wrapper around a shared server-side media item:

- `WorkspaceSource.id`: local workspace entry ID
- `WorkspaceSource.mediaId`: shared server-side media identity

Within one workspace, duplicate sources are prevented by `mediaId`, not by local source ID.

### Existing organization model

Workspace source folders are already persisted in workspace snapshot state:

- `sourceFolders`
- `sourceFolderMemberships`
- `selectedSourceFolderIds`
- `activeFolderId`

This makes folder transfer feasible in v1.

### Existing duplication model

`duplicateWorkspaceSnapshot(...)` currently clones every source into a new workspace-local source entry with a new `id`, while preserving the same `mediaId`.

This is compatible with a transfer model based on creating new destination wrappers around the same underlying media items.

### Important constraint: annotations are not persisted

Source preview annotations currently live only in `SourcesPane` component state and are not part of:

- `WorkspaceSnapshot`
- workspace export/import bundles
- persisted workspace store state

Because of that, annotation transfer is explicitly out of scope for v1 unless a separate feature first promotes annotations into persisted workspace state.

## Requirements Confirmed With User

1. The missing first-class workflow is direct source transfer across workspaces.
2. The transfer flow must support both `Move` and `Copy`.
3. A copied source should reference the same underlying item, not a fully independent media clone.
4. Notebook-local organization should remain local to each workspace.
5. Bulk transfer is required in v1.
6. The flow must support creating a new destination workspace from the current selection.
7. Folder/group organization should transfer to the destination.
8. For `Move`, empty folders should trigger a user-facing cleanup choice rather than automatic silent deletion.
9. If the destination already contains one of the selected sources, the user should be prompted rather than forced into one default conflict behavior.
10. The feature should be accessible from both the selected-sources UI and a workspace-level split shortcut.

## Code Review Findings Incorporated Into This Design

The initial design discussion was adjusted after reviewing the current implementation:

1. Reusing `createNewWorkspace(...)` directly inside the transfer flow is unsafe because it switches the active workspace immediately and would destroy the origin selection context mid-flow.
2. Source annotation transfer is not viable in v1 because annotations are not persisted.
3. The transfer engine must update saved-workspace metadata such as `sourceCount`, not just raw workspace snapshots.
4. Transferring `effectiveSelectedSourceEntries` can include hidden selected items, so the UI must warn about hidden selections.
5. `Replace local context` must be narrowly defined so it does not wipe unrelated destination organization.

## Approaches Considered

### Approach 1: Generic bulk transfer only

Add a `Move/Copy` action only to the selected-sources toolbar.

Pros:

- minimal UI surface
- directly reuses existing bulk-selection behavior

Cons:

- weak discoverability for users who think in terms of splitting a workspace
- less explicit support for the “this workspace became too broad” job

### Approach 2: Split-workspace wizard only

Add only a workspace-level split flow.

Pros:

- strong alignment with the user story

Cons:

- too narrow for existing cross-workspace reorganization needs
- duplicates logic users will still expect in the source list

### Approach 3: Shared transfer engine with two entry points

Build one store-level transfer engine and expose it through:

1. selected-sources bulk action
2. workspace header split shortcut

Pros:

- matches both mental models
- keeps transfer semantics centralized
- builds directly on existing store and selection logic

Cons:

- slightly broader UI surface
- requires careful wording so `duplicate workspace` and `split workspace` are not confused

## Recommendation

Use Approach 3.

The product gap is not a missing data model. It is a missing workflow on top of a data model that mostly already exists. A shared transfer engine with two entry points gives the user a notebook-splitting tool without introducing a second incompatible organization system.

## Proposed UX

### Entry point 1: Sources pane bulk action

When one or more sources are effectively selected, the selected-sources action bar in `SourcesPane` should show a new action:

- `Move / Copy`

This action operates on `effectiveSelectedSourceEntries`, matching existing bulk-remove semantics.

### Entry point 2: Workspace header shortcut

The workspace header settings menu should add:

- `Split Current Workspace`

This opens the same transfer modal in “create new workspace” mode.

If no sources are selected, the shortcut should not open a broken transfer flow. Instead it should:

1. focus or reveal the Sources pane if possible
2. instruct the user to select the sources to split first

### Shared transfer modal

The modal should follow a short, explicit sequence:

1. Choose action:
   - `Copy selected sources`
   - `Move selected sources`
2. Choose destination:
   - existing workspace
   - create new workspace
3. Review hidden selection warning if some selected sources are not currently visible.
4. Resolve destination conflicts if needed.
5. For `Move`, choose how to handle newly empty origin folders.
6. Confirm and execute.

### Hidden selection warning

If some selected sources are hidden by search, folder focus, or advanced filters, the modal should show a warning before final confirmation:

- how many sources are selected in total
- how many are currently hidden
- that hidden selected sources will also be moved or copied

This mirrors the current behavior expectations already established by batch remove.

### Destination picker rules

The destination picker should:

1. exclude the current workspace
2. exclude archived workspaces in v1
3. allow creating a new workspace inline from the same modal

## State Model

### Shared identity

`mediaId` is the canonical shared identity for conflict detection and destination deduplication.

### Workspace-local identity

`source.id` remains a workspace-local wrapper ID and must be regenerated when a new source wrapper is created in the destination workspace.

### Transferred local context in v1

Transferred local context is limited to persisted folder organization:

- source folder memberships
- destination folder creation or reuse by normalized path

### Not transferred in v1

The following do not transfer in v1:

- preview annotations
- workspace notes
- generated artifacts
- chat session state

## Transfer Algorithm

### Core rule

The transfer action works on selected origin source wrappers but deduplicates and conflicts by `mediaId`.

### Execution steps

1. Build the origin transfer set from `effectiveSelectedSourceEntries`.
2. Deduplicate the transfer set by `mediaId`.
3. Resolve the destination workspace snapshot:
   - existing saved workspace snapshot, or
   - newly created destination snapshot created without switching the active workspace yet
4. For each selected source:
   - if destination has no wrapper with that `mediaId`, create one
   - if destination already has that `mediaId`, queue a conflict
5. Recreate or reuse destination folders needed by the transferred sources.
6. Apply destination folder memberships based on conflict decisions.
7. If action is `Move`, remove origin source wrappers only after destination updates are complete.
8. If `Move` creates newly empty origin folders, apply the chosen cleanup policy.
9. Update saved-workspace metadata for both origin and destination, including `sourceCount`.
10. If the user created a new destination workspace, optionally switch to it after the transfer succeeds.

## Destination Creation Rule

The transfer flow must not reuse the existing `createNewWorkspace(...)` action directly.

Instead, it needs a destination-creation path that:

1. constructs a new workspace snapshot
2. registers it in workspace snapshot metadata
3. does not immediately switch the active UI away from the origin workspace

This is necessary to preserve source selection context until the transfer is confirmed.

### Collection behavior for a newly split workspace

If the user creates a new workspace through the split flow, the new workspace should inherit the source workspace's collection assignment in v1.

This matches the current duplication behavior and keeps related workspaces grouped without requiring extra decisions during the split flow.

## Folder Path Mapping

Only folders actually used by the transferred sources should be considered.

### Folder reuse rule

Destination folders should be matched by normalized path using the same trim/case-insensitive sibling semantics already used by folder naming helpers.

### Folder creation rule

If a required destination path does not exist, create it.

### Membership rule

Transferred sources should be assigned into the resolved destination folder IDs for their mapped paths.

## Conflict Handling

Conflicts occur when the destination workspace already contains a source wrapper with the same `mediaId`.

For each conflicting source, offer:

1. `Skip`
2. `Merge folder memberships`
3. `Replace transferred folder memberships`

### Meaning of merge

Keep the existing destination source wrapper and add any mapped incoming folder memberships.

### Meaning of replace

Keep the existing destination source wrapper, but replace only the destination folder memberships relevant to the transferred paths for that source.

This option must not wipe unrelated destination organization for that source.

## Move Cleanup

If a `Move` leaves origin folders empty, the UI should present a cleanup choice:

1. keep empty folders
2. delete newly empty folders
3. review individually

Cleanup applies only to folders made empty by the current move.

Parent folders may be cleaned up recursively only while they remain empty as a direct consequence of this move.

## Undo And Safety

This feature should use one whole-transfer undo snapshot rather than per-source undo entries.

### Safety requirements

1. Do not remove origin source wrappers until destination writes are successful.
2. Do not allow the current workspace to be selected as destination.
3. Treat “all conflicts skipped” as a no-op success summary, not a hard failure.
4. Surface partial result counts clearly when some items are skipped or merged.

## Error Handling

1. No sources selected:
   - block launch
   - direct the user back to source selection
2. Destination missing:
   - abort with recoverable error
3. Destination conflict review unresolved:
   - block confirmation until each conflict has an explicit resolution
4. Move cleanup choice unresolved when newly empty folders exist:
   - block confirmation until the cleanup step is completed

## Testing Strategy

### Store tests

1. Copy selected sources to an existing workspace.
2. Move selected sources to an existing workspace.
3. Create a new workspace from the current selection without switching before confirmation.
4. Conflict modes:
   - skip
   - merge folder memberships
   - replace transferred folder memberships
5. Folder path reuse and creation behavior.
6. Hidden selected source warning state.
7. Move cleanup behavior for newly empty folders.
8. Saved-workspace `sourceCount` metadata updates correctly for origin and destination.

### UI tests

1. Sources pane selected-action flow opens with the correct selected count.
2. Workspace header split shortcut opens the same transfer flow.
3. Header shortcut with no selection redirects the user to make a selection first.
4. Conflict review appears only when needed.
5. Success summary offers destination navigation after completion.

### Regression tests

1. Existing duplicate-workspace behavior remains unchanged.
2. Within one workspace, duplicate prevention still keys on `mediaId`.
3. Folder selection and grounded-chat source selection continue to work after transfer.
4. Export/import bundle behavior remains unchanged for unchanged snapshot structure.

## Future Follow-Up

### V1.1 candidate

If source preview annotations become persisted workspace state, a follow-up can extend transfer behavior to optionally clone or merge annotation context per workspace.

### Future server-backed evolution

The v1 local-first transfer engine should be written with a clean enough contract that a future server-backed membership API can adopt the same semantics:

- shared source identity by media item
- workspace-local organization
- explicit conflict handling

## Open Questions Resolved For This Design

1. Shared underlying item:
   - use `mediaId`
2. Workspace-local organization:
   - keep local per workspace
3. Bulk support:
   - required in v1
4. Destination creation:
   - required in v1
5. Empty-folder cleanup:
   - prompt the user when the move creates empties
6. Destination conflicts:
   - prompt explicitly rather than silently choosing one behavior
