# Workspace Source Folders + Collections Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add nested source folders inside Workspace Playground plus flat workspace collections in the workspace browser, with correct recursive grounded-selection behavior, persistence, and import/export semantics.

**Architecture:** Extend the existing local-first workspace store with explicit organization entities and pure selector helpers rather than burying recursive folder logic directly in UI components. Keep source folders scoped to workspace snapshots and workspace collections scoped to saved-workspace metadata, so collections can ship first while source-folder selection lands in a second, more isolated phase.

**Tech Stack:** TypeScript, React, Zustand, Ant Design, Vitest, Testing Library, existing `apps/packages/ui` workspace store/component test harnesses.

---

### Task 1: Extend workspace types, persisted defaults, and saved-workspace retention

**Files:**
- Modify: `apps/packages/ui/src/types/workspace.ts`
- Modify: `apps/packages/ui/src/store/workspace.ts`
- Test: `apps/packages/ui/src/store/__tests__/workspace.test.ts`
- Test: `apps/packages/ui/src/store/__tests__/workspace.split-storage.test.ts`

**Step 1: Write the failing test**

```ts
it("initializes organization metadata with empty defaults", () => {
  useWorkspaceStore.getState().initializeWorkspace("Organized")
  const state = useWorkspaceStore.getState()

  expect(state.sourceFolders).toEqual([])
  expect(state.sourceFolderMemberships).toEqual([])
  expect(state.selectedSourceFolderIds).toEqual([])
  expect(state.activeFolderId).toBeNull()
  expect(state.workspaceCollections).toEqual([])
  expect(state.savedWorkspaces[0]?.collectionId ?? null).toBeNull()
})

it("retains more than ten saved workspaces for collection browsing", () => {
  useWorkspaceStore.getState().initializeWorkspace("Workspace 1")
  for (let i = 2; i <= 12; i += 1) {
    useWorkspaceStore.getState().createNewWorkspace(`Workspace ${i}`)
    useWorkspaceStore.getState().saveCurrentWorkspace()
  }

  expect(useWorkspaceStore.getState().savedWorkspaces.length).toBeGreaterThan(10)
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/store/__tests__/workspace.test.ts ../packages/ui/src/store/__tests__/workspace.split-storage.test.ts`

Expected: FAIL because the new organization fields do not exist and saved workspaces are still truncated.

**Step 3: Write minimal implementation**

```ts
export interface WorkspaceSourceFolder {
  id: string
  workspaceId: string
  name: string
  parentFolderId: string | null
  createdAt: Date
  updatedAt: Date
}

export interface WorkspaceSourceFolderMembership {
  folderId: string
  sourceId: string
}

export interface WorkspaceCollection {
  id: string
  name: string
  description?: string | null
  createdAt: Date
  updatedAt: Date
}

export interface SavedWorkspace {
  id: string
  name: string
  tag: string
  createdAt: Date
  lastAccessedAt: Date
  sourceCount: number
  collectionId: string | null
}
```

```ts
const initialSourcesState = {
  sources: [],
  selectedSourceIds: [],
  selectedSourceFolderIds: [],
  activeFolderId: null,
  sourceFolders: [],
  sourceFolderMemberships: [],
  sourceSearchQuery: "",
  sourceFocusTarget: null,
  sourcesLoading: false,
  sourcesError: null
}

const upsertSavedWorkspace = (
  workspaces: SavedWorkspace[],
  workspace: SavedWorkspace
): SavedWorkspace[] => [workspace, ...workspaces.filter((w) => w.id !== workspace.id)]
```

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/store/__tests__/workspace.test.ts ../packages/ui/src/store/__tests__/workspace.split-storage.test.ts`

Expected: PASS for empty defaults and saved-workspace retention.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/types/workspace.ts apps/packages/ui/src/store/workspace.ts apps/packages/ui/src/store/__tests__/workspace.test.ts apps/packages/ui/src/store/__tests__/workspace.split-storage.test.ts
git commit -m "feat(workspace): add organization state defaults and remove saved workspace truncation"
```

### Task 2: Create pure organization selector helpers for nested folders

**Files:**
- Create: `apps/packages/ui/src/store/workspace-organization.ts`
- Test: `apps/packages/ui/src/store/__tests__/workspace-organization.test.ts`

**Step 1: Write the failing test**

```ts
import {
  collectDescendantFolderIds,
  createWorkspaceOrganizationIndex,
  deriveEffectiveSelectedSourceIds,
  getFolderSelectionState,
  getSourceSelectionOrigin
} from "../workspace-organization"

it("includes descendant folders recursively and deduplicates sources", () => {
  const index = createWorkspaceOrganizationIndex({
    sourceFolders: [
      { id: "root", workspaceId: "w1", name: "Root", parentFolderId: null, createdAt: new Date(), updatedAt: new Date() },
      { id: "child", workspaceId: "w1", name: "Child", parentFolderId: "root", createdAt: new Date(), updatedAt: new Date() }
    ],
    sourceFolderMemberships: [
      { folderId: "root", sourceId: "s1" },
      { folderId: "child", sourceId: "s2" },
      { folderId: "child", sourceId: "s1" }
    ],
    sources: [
      { id: "s1", mediaId: 1, title: "One", type: "pdf", status: "ready", addedAt: new Date() },
      { id: "s2", mediaId: 2, title: "Two", type: "pdf", status: "ready", addedAt: new Date() }
    ]
  })

  expect(collectDescendantFolderIds(index, "root")).toEqual(["root", "child"])
  expect(deriveEffectiveSelectedSourceIds(index, ["s2"], ["root"])).toEqual(["s1", "s2"])
  expect(getFolderSelectionState(index, "root", ["s2"], [])).toBe("indeterminate")
  expect(getSourceSelectionOrigin("s1", ["s1"], ["root"], index)).toBe("both")
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/store/__tests__/workspace-organization.test.ts`

Expected: FAIL because the selector module does not exist.

**Step 3: Write minimal implementation**

```ts
export type FolderSelectionState = "unchecked" | "checked" | "indeterminate"
export type SourceSelectionOrigin = "none" | "direct" | "folder" | "both"

export const createWorkspaceOrganizationIndex = (...) => ({ ...maps })
export const collectDescendantFolderIds = (...) => { ... }
export const collectDescendantReadySourceIds = (...) => { ... }
export const deriveEffectiveSelectedSourceIds = (...) => { ... }
export const getFolderSelectionState = (...) => { ... }
export const getSourceSelectionOrigin = (...) => { ... }
```

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/store/__tests__/workspace-organization.test.ts`

Expected: PASS for recursive resolution, deduplication, tri-state, and selection origin.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/store/workspace-organization.ts apps/packages/ui/src/store/__tests__/workspace-organization.test.ts
git commit -m "feat(workspace): add source folder organization selectors"
```

### Task 3: Add source-folder store actions, validation, and derived getters

**Files:**
- Modify: `apps/packages/ui/src/store/workspace.ts`
- Test: `apps/packages/ui/src/store/__tests__/workspace.test.ts`

**Step 1: Write the failing test**

```ts
it("creates, renames, reparents, and deletes source folders safely", () => {
  useWorkspaceStore.getState().initializeWorkspace("Folders")
  const root = useWorkspaceStore.getState().createSourceFolder("Root")
  const child = useWorkspaceStore.getState().createSourceFolder("Child", root.id)

  useWorkspaceStore.getState().renameSourceFolder(child.id, "Evidence")
  useWorkspaceStore.getState().moveSourceFolder(child.id, null)
  useWorkspaceStore.getState().deleteSourceFolder(root.id)

  const state = useWorkspaceStore.getState()
  expect(state.sourceFolders.find((folder) => folder.id === child.id)?.name).toBe("Evidence")
  expect(state.sourceFolders.find((folder) => folder.id === child.id)?.parentFolderId).toBeNull()
})

it("deduplicates memberships and rejects cyclic folder moves", () => {
  useWorkspaceStore.getState().initializeWorkspace("Folders")
  const root = useWorkspaceStore.getState().createSourceFolder("Root")
  const child = useWorkspaceStore.getState().createSourceFolder("Child", root.id)

  useWorkspaceStore.getState().addSource({ mediaId: 1, title: "Alpha", type: "pdf" })
  const sourceId = useWorkspaceStore.getState().sources[0]!.id

  useWorkspaceStore.getState().assignSourceToFolders(sourceId, [root.id, root.id])

  expect(() => useWorkspaceStore.getState().moveSourceFolder(root.id, child.id)).toThrow()
  expect(useWorkspaceStore.getState().sourceFolderMemberships).toHaveLength(1)
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/store/__tests__/workspace.test.ts`

Expected: FAIL because the folder actions and validations do not exist.

**Step 3: Write minimal implementation**

```ts
createSourceFolder: (name, parentFolderId = null) => { ... }
renameSourceFolder: (folderId, name) => { ... }
moveSourceFolder: (folderId, parentFolderId) => { ... }
deleteSourceFolder: (folderId) => { ...reparent children...clear selections... }
assignSourceToFolders: (sourceId, folderIds) => { ...dedupe memberships... }
removeSourceFromFolder: (sourceId, folderId) => { ... }
toggleSourceFolderSelection: (folderId) => { ... }
setActiveFolder: (folderId) => { ... }
getEffectiveSelectedSources: () => { ...use deriveEffectiveSelectedSourceIds(...)... }
getEffectiveSelectedMediaIds: () => { ... }
```

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/store/__tests__/workspace.test.ts`

Expected: PASS for folder CRUD, cycle rejection, membership dedupe, and derived getters.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/store/workspace.ts apps/packages/ui/src/store/__tests__/workspace.test.ts
git commit -m "feat(workspace): add source folder store actions and validation"
```

### Task 4: Add workspace collection store actions and grouping helpers

**Files:**
- Modify: `apps/packages/ui/src/store/workspace.ts`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/workspace-header.utils.ts`
- Test: `apps/packages/ui/src/store/__tests__/workspace.test.ts`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/workspace-header.utils.test.ts`

**Step 1: Write the failing test**

```ts
it("creates collections, assigns workspaces, and unassigns on delete", () => {
  useWorkspaceStore.getState().initializeWorkspace("Alpha")
  useWorkspaceStore.getState().saveCurrentWorkspace()
  useWorkspaceStore.getState().createNewWorkspace("Beta")
  useWorkspaceStore.getState().saveCurrentWorkspace()

  const collection = useWorkspaceStore.getState().createWorkspaceCollection("Topic A")
  const betaId = useWorkspaceStore.getState().workspaceId
  useWorkspaceStore.getState().assignWorkspaceToCollection(betaId, collection.id)
  useWorkspaceStore.getState().deleteWorkspaceCollection(collection.id)

  const beta = useWorkspaceStore.getState().savedWorkspaces.find((workspace) => workspace.id === betaId)
  expect(beta?.collectionId ?? null).toBeNull()
})

it("groups workspaces into collection buckets and unassigned", () => {
  expect(groupWorkspacesByCollection(
    [{ id: "c1", name: "Topic A", description: null, createdAt: new Date(), updatedAt: new Date() }],
    [
      { id: "w1", name: "Alpha", tag: "workspace:alpha", createdAt: new Date(), lastAccessedAt: new Date(), sourceCount: 1, collectionId: "c1" },
      { id: "w2", name: "Beta", tag: "workspace:beta", createdAt: new Date(), lastAccessedAt: new Date(), sourceCount: 1, collectionId: null }
    ]
  )).toHaveLength(2)
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/store/__tests__/workspace.test.ts ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/workspace-header.utils.test.ts`

Expected: FAIL because the collection actions and grouping helpers do not exist.

**Step 3: Write minimal implementation**

```ts
createWorkspaceCollection: (name, description = null) => { ... }
renameWorkspaceCollection: (collectionId, name, description = null) => { ... }
deleteWorkspaceCollection: (collectionId) => {
  set((state) => ({
    workspaceCollections: state.workspaceCollections.filter((collection) => collection.id !== collectionId),
    savedWorkspaces: state.savedWorkspaces.map((workspace) =>
      workspace.collectionId === collectionId ? { ...workspace, collectionId: null } : workspace
    ),
    archivedWorkspaces: state.archivedWorkspaces.map((workspace) =>
      workspace.collectionId === collectionId ? { ...workspace, collectionId: null } : workspace
    )
  }))
}
assignWorkspaceToCollection: (workspaceId, collectionId) => { ... }
```

```ts
export const groupWorkspacesByCollection = (
  collections: WorkspaceCollection[],
  workspaces: SavedWorkspace[]
) => { ...return ordered collection buckets plus Unassigned... }
```

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/store/__tests__/workspace.test.ts ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/workspace-header.utils.test.ts`

Expected: PASS for collection creation, assignment, deletion, and grouping.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/store/workspace.ts apps/packages/ui/src/components/Option/WorkspacePlayground/workspace-header.utils.ts apps/packages/ui/src/store/__tests__/workspace.test.ts apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/workspace-header.utils.test.ts
git commit -m "feat(workspace): add workspace collection store primitives"
```

### Task 5: Render the source-folder tree in SourcesPane with separate focus and context selection

**Files:**
- Create: `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/SourceFolderTree.tsx`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage3.folders.test.tsx`

**Step 1: Write the failing test**

```tsx
it("renders nested folders with separate focus and selection controls", () => {
  render(<SourcesPane />)

  expect(screen.getByText("Evidence")).toBeInTheDocument()
  fireEvent.click(screen.getByRole("button", { name: "Focus folder Evidence" }))
  expect(mockSetActiveFolder).toHaveBeenCalledWith("folder-evidence")

  fireEvent.click(screen.getByRole("checkbox", { name: "Select folder Evidence" }))
  expect(mockToggleSourceFolderSelection).toHaveBeenCalledWith("folder-evidence")
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage3.folders.test.tsx`

Expected: FAIL because the folder tree component and handlers do not exist.

**Step 3: Write minimal implementation**

```tsx
export const SourceFolderTree = ({
  folders,
  activeFolderId,
  selectedFolderIds,
  onFocusFolder,
  onToggleFolderSelection
}: SourceFolderTreeProps) => (
  <div aria-label="Source folders">
    {folderTree.map((folder) => (
      <div key={folder.id}>
        <button aria-label={`Focus folder ${folder.name}`} onClick={() => onFocusFolder(folder.id)}>
          {folder.name}
        </button>
        <Checkbox
          aria-label={`Select folder ${folder.name}`}
          checked={folder.selectionState === "checked"}
          indeterminate={folder.selectionState === "indeterminate"}
          onChange={() => onToggleFolderSelection(folder.id)}
        />
      </div>
    ))}
  </div>
)
```

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage3.folders.test.tsx`

Expected: PASS for folder rendering, focus, and context selection.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/SourceFolderTree.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage3.folders.test.tsx
git commit -m "feat(workspace): add source folder tree to sources pane"
```

### Task 6: Add folder membership editing and source-row selection-origin states

**Files:**
- Create: `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/SourceFolderMembershipMenu.tsx`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage3.folders.test.tsx`

**Step 1: Write the failing test**

```tsx
it("shows direct and inherited selection states separately on source rows", () => {
  render(<SourcesPane />)

  expect(screen.getByText("From folder")).toBeInTheDocument()
  expect(screen.getByText("Direct")).toBeInTheDocument()
})

it("adds a source to multiple folders from the membership menu", async () => {
  render(<SourcesPane />)

  fireEvent.click(screen.getByRole("button", { name: "Add Source One to folders" }))
  fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "Evidence" }))
  fireEvent.click(screen.getByRole("menuitemcheckbox", { name: "Quotes" }))

  await waitFor(() => {
    expect(mockAssignSourceToFolders).toHaveBeenCalledWith("s1", ["folder-evidence", "folder-quotes"])
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage3.folders.test.tsx`

Expected: FAIL because source rows do not expose selection origin or membership editing.

**Step 3: Write minimal implementation**

```tsx
const selectionOrigin = getSourceSelectionOrigin(
  source.id,
  selectedSourceIds,
  selectedSourceFolderIds,
  organizationIndex
)

{selectionOrigin === "folder" && <span>From folder</span>}
{selectionOrigin === "direct" && <span>Direct</span>}
{selectionOrigin === "both" && <span>Direct + folder</span>}
```

```tsx
<SourceFolderMembershipMenu
  sourceId={source.id}
  folders={sourceFolders}
  selectedFolderIds={folderIdsBySourceId.get(source.id) ?? []}
  onChange={(folderIds) => assignSourceToFolders(source.id, folderIds)}
/>
```

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage3.folders.test.tsx`

Expected: PASS for inherited/direct state display and many-to-many membership editing.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/SourceFolderMembershipMenu.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage3.folders.test.tsx
git commit -m "feat(workspace): add source folder membership editing"
```

### Task 7: Wire effective folder-aware source selection into chat and studio flows

**Files:**
- Modify: `apps/packages/ui/src/store/workspace.ts`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage5.folder-context.test.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage5.folder-context.test.tsx`

**Step 1: Write the failing test**

```tsx
it("grounds chat using sources selected through folders", async () => {
  render(<ChatPane />)
  await userEvent.type(screen.getByRole("textbox"), "Summarize")
  await userEvent.click(screen.getByRole("button", { name: "Send" }))

  expect(mockSetRagMediaIds).toHaveBeenCalledWith([101, 102])
})

it("enables studio outputs when effective folder selection contains ready sources", () => {
  render(<StudioPane />)
  expect(screen.getByRole("button", { name: "Summary" })).toBeEnabled()
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage5.folder-context.test.tsx ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage5.folder-context.test.tsx`

Expected: FAIL because chat/studio still rely on direct source selection only.

**Step 3: Write minimal implementation**

```ts
getEffectiveSelectedMediaIds: () =>
  get().getEffectiveSelectedSources().map((source) => source.mediaId)
```

```tsx
const effectiveMediaIds = useWorkspaceStore((state) => state.getEffectiveSelectedMediaIds())

useEffect(() => {
  setRagMediaIds(effectiveMediaIds)
  setChatMode(effectiveMediaIds.length > 0 ? "rag" : "normal")
}, [effectiveMediaIds, setChatMode, setRagMediaIds])
```

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage5.folder-context.test.tsx ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage5.folder-context.test.tsx`

Expected: PASS for folder-derived grounded chat and studio enabling.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/store/workspace.ts apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/StudioPane/index.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.stage5.folder-context.test.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/StudioPane.stage5.folder-context.test.tsx
git commit -m "feat(workspace): ground chat and studio with folder-aware source selection"
```

### Task 8: Add workspace collections to the workspace browser UI

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/workspace-header.utils.ts`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/WorkspaceHeader.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/workspace-header.utils.test.ts`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx`

**Step 1: Write the failing test**

```tsx
it("filters workspaces by collection and shows an unassigned bucket", async () => {
  render(<WorkspaceHeader />)

  await userEvent.click(screen.getByRole("button", { name: "Browse workspaces" }))
  expect(screen.getByText("Unassigned")).toBeInTheDocument()
  expect(screen.getByText("Topic A")).toBeInTheDocument()
})

it("reassigns a workspace to a collection from the browser row action", async () => {
  render(<WorkspaceHeader />)

  await userEvent.click(screen.getByRole("button", { name: "Assign Beta Deep Dive to collection" }))
  await userEvent.click(screen.getByRole("menuitemradio", { name: "Topic A" }))

  expect(mockAssignWorkspaceToCollection).toHaveBeenCalledWith("workspace-beta", "collection-topic-a")
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/workspace-header.utils.test.ts`

Expected: FAIL because collection grouping and assignment UI do not exist in the browser modal.

**Step 3: Write minimal implementation**

```tsx
{groupWorkspacesByCollection(workspaceCollections, filterSavedWorkspaces(savedWorkspaces, workspaceSearchQuery)).map(
  (group) => (
    <section key={group.id ?? "unassigned"} aria-label={group.name}>
      <h3>{group.name}</h3>
      {group.workspaces.map((workspace) => (
        <WorkspaceBrowserRow
          key={workspace.id}
          workspace={workspace}
          collections={workspaceCollections}
          onAssignCollection={assignWorkspaceToCollection}
        />
      ))}
    </section>
  )
)}
```

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/workspace-header.utils.test.ts`

Expected: PASS for collection grouping, `Unassigned`, and row reassignment.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/WorkspacePlayground/workspace-header.utils.ts apps/packages/ui/src/components/Option/WorkspacePlayground/WorkspaceHeader.tsx apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/workspace-header.utils.test.ts apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx
git commit -m "feat(workspace): add collections to workspace browser"
```

### Task 9: Update workspace bundle import/export and persistence regressions

**Files:**
- Modify: `apps/packages/ui/src/store/workspace-bundle.ts`
- Modify: `apps/packages/ui/src/store/workspace.ts`
- Test: `apps/packages/ui/src/store/__tests__/workspace-bundle.test.ts`
- Test: `apps/packages/ui/src/store/__tests__/workspace.test.ts`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx`

**Step 1: Write the failing test**

```ts
it("round-trips source folders and memberships through workspace bundle zip export/import", async () => {
  const bundle = createBundleFixture()
  bundle.workspace.snapshot.sourceFolders = [
    { id: "folder-1", workspaceId: "workspace-1", name: "Evidence", parentFolderId: null, createdAt: new Date("2026-03-11T00:00:00.000Z"), updatedAt: new Date("2026-03-11T00:00:00.000Z") }
  ]
  bundle.workspace.snapshot.sourceFolderMemberships = [{ folderId: "folder-1", sourceId: "source-1" }]
  bundle.workspace.snapshot.selectedSourceFolderIds = ["folder-1"]

  const zipBlob = await createWorkspaceExportZipBlob(bundle)
  const parsed = await parseWorkspaceImportFile(new File([zipBlob], "bundle.workspace.zip"))

  expect(parsed.workspace.snapshot.sourceFolders).toHaveLength(1)
  expect(parsed.workspace.snapshot.selectedSourceFolderIds).toEqual(["folder-1"])
})

it("imports workspaces as unassigned even when bundle metadata includes a collection name", () => {
  const importedId = useWorkspaceStore.getState().importWorkspaceBundle(bundleWithCollectionMetadata)
  const saved = useWorkspaceStore.getState().savedWorkspaces.find((workspace) => workspace.id === importedId)
  expect(saved?.collectionId ?? null).toBeNull()
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/store/__tests__/workspace-bundle.test.ts ../packages/ui/src/store/__tests__/workspace.test.ts ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx`

Expected: FAIL because the bundle schema does not carry source-folder organization and import semantics are not defined.

**Step 3: Write minimal implementation**

```ts
export interface WorkspaceBundleSnapshot {
  workspaceName: string
  workspaceTag: string
  workspaceCreatedAt: ExportDateValue
  sources: WorkspaceSource[]
  sourceFolders: WorkspaceSourceFolder[]
  sourceFolderMemberships: WorkspaceSourceFolderMembership[]
  selectedSourceIds: string[]
  selectedSourceFolderIds: string[]
  generatedArtifacts: GeneratedArtifact[]
  notes: string
  currentNote: WorkspaceNote
  workspaceBanner: WorkspaceBanner
  leftPaneCollapsed: boolean
  rightPaneCollapsed: boolean
  audioSettings: AudioGenerationSettings
}
```

```ts
const importedSnapshot = hydrateWorkspaceBundleSnapshot(bundle.workspace.snapshot, workspaceId, workspaceName, workspaceTag)
nextSavedWorkspaces = upsertSavedWorkspace(nextSavedWorkspaces, {
  ...createSavedWorkspaceEntry(importedSnapshot, now),
  collectionId: null
})
```

**Step 4: Run test to verify it passes**

Run: `cd apps/tldw-frontend && bunx vitest run ../packages/ui/src/store/__tests__/workspace-bundle.test.ts ../packages/ui/src/store/__tests__/workspace.test.ts ../packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx`

Expected: PASS for source-folder bundle round-trip and unassigned imports.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/store/workspace-bundle.ts apps/packages/ui/src/store/workspace.ts apps/packages/ui/src/store/__tests__/workspace-bundle.test.ts apps/packages/ui/src/store/__tests__/workspace.test.ts apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage9.persistence.test.tsx
git commit -m "feat(workspace): persist and bundle source folders and collections safely"
```
