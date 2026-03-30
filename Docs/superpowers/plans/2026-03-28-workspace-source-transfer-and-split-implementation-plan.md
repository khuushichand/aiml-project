# Workspace Source Transfer And Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class move/copy source transfer between workspaces, including split-to-new-workspace, with shared `mediaId` identity, workspace-local folder context transfer, conflict handling, and safe move cleanup.

**Architecture:** Keep the transfer algorithm pure and snapshot-based so move/copy semantics, folder-path mapping, and cleanup rules are testable without React. Wrap that helper in one store-level transaction that updates origin and destination snapshots, saved-workspace metadata, and undo state atomically. Then expose the same flow through a shared modal opened from both the Sources pane bulk actions and the Workspace header split shortcut.

**Tech Stack:** React, TypeScript, Zustand, Ant Design, Vitest, React Testing Library

---

## File Structure

- `apps/packages/ui/src/types/workspace.ts`
  Purpose: add the transfer request/result/conflict policy types shared by the store and modal.
- `apps/packages/ui/src/store/workspace-source-transfer.ts`
  Purpose: pure snapshot-to-snapshot transfer planner/applier for dedupe-by-`mediaId`, folder recreation, conflict handling, and empty-folder cleanup.
- `apps/packages/ui/src/store/workspace.ts`
  Purpose: extend top-level store action typing so the new transfer action is available to UI callers.
- `apps/packages/ui/src/store/workspace-slices/workspace-list-slice.ts`
  Purpose: execute the transfer transaction, create a destination snapshot without switching, update saved-workspace metadata, and optionally switch after success.
- `apps/packages/ui/src/store/__tests__/workspace-source-transfer.test.ts`
  Purpose: lock pure algorithm invariants for copy, move, conflict resolution, folder-path reuse, and empty-folder cleanup.
- `apps/packages/ui/src/store/__tests__/workspace.test.ts`
  Purpose: lock store-level behavior for metadata updates, collection inheritance, undo safety, and destination-creation rules.
- `apps/packages/ui/src/components/Option/WorkspacePlayground/TransferSourcesModal.tsx`
  Purpose: shared modal flow for action selection, destination selection, hidden/ineligible summaries, conflict review, move cleanup, and completion messaging.
- `apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx`
  Purpose: own the shared modal open state, pass the same entrypoint to both SourcesPane and WorkspaceHeader, and reveal the Sources pane when the header shortcut needs it.
- `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx`
  Purpose: add the selected-sources `Move / Copy` action and launch the shared modal with the current selection context.
- `apps/packages/ui/src/components/Option/WorkspacePlayground/WorkspaceHeader.tsx`
  Purpose: add `Split Current Workspace` to the settings menu and route it into the shared modal or source-pane reveal flow.
- `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage5.transfer.test.tsx`
  Purpose: verify the selected-sources action opens the modal and carries hidden/ineligible selection context correctly.
- `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx`
  Purpose: verify the settings-menu shortcut opens split mode or reveals the Sources pane when no selection exists.
- `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage13.source-transfer.test.tsx`
  Purpose: verify the end-to-end modal flow against the shared store hooks, including successful move/copy summaries and split-to-new-workspace behavior.

## Task 1: Add A Pure Workspace Source Transfer Helper

**Files:**
- Modify: `apps/packages/ui/src/types/workspace.ts`
- Create: `apps/packages/ui/src/store/workspace-source-transfer.ts`
- Test: `apps/packages/ui/src/store/__tests__/workspace-source-transfer.test.ts`

- [ ] **Step 1: Write the failing pure transfer tests**

Add focused tests for the algorithm, not the UI:

```ts
it("copies selected sources into a destination by shared mediaId", () => {
  const result = applyWorkspaceSourceTransfer({
    mode: "copy",
    originSnapshot,
    destinationSnapshot,
    selectedSourceIds: ["origin-s1"],
    conflictResolutions: {},
    emptyFolderPolicy: "keep"
  })

  expect(result.destinationSnapshot.sources.map((source) => source.mediaId)).toEqual([101])
  expect(result.destinationSnapshot.sources[0]?.id).not.toBe("origin-s1")
  expect(result.originSnapshot.sources).toHaveLength(1)
})
```

```ts
it("reuses matching destination folder paths and replaces only transferred memberships", () => {
  const result = applyWorkspaceSourceTransfer({
    mode: "copy",
    originSnapshot,
    destinationSnapshot,
    selectedSourceIds: ["origin-s1"],
    conflictResolutions: { 101: "replace-transferred-folders" },
    emptyFolderPolicy: "keep"
  })

  expect(result.conflictsResolved).toEqual([101])
  expect(result.destinationSnapshot.sourceFolderMemberships).toEqual(
    expect.arrayContaining([{ folderId: "dest-evidence", sourceId: "dest-existing-s1" }])
  )
})
```

Cover these cases:
1. `copy` keeps origin unchanged.
2. `move` removes origin wrappers only after destination work succeeds.
3. conflicts are keyed by `mediaId`.
4. folder paths are recreated/reused case-insensitively.
5. empty-folder cleanup reports only folders made empty by the move.

- [ ] **Step 2: Run the new pure test file and verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/store/__tests__/workspace-source-transfer.test.ts
```

Expected: FAIL because `workspace-source-transfer.ts` and the transfer types do not exist yet.

- [ ] **Step 3: Implement the minimal pure helper and shared types**

Add transfer-specific types to `workspace.ts`, then implement a pure helper module with explicit inputs and outputs:

```ts
export type WorkspaceSourceTransferMode = "copy" | "move"
export type WorkspaceSourceTransferConflictResolution =
  | "skip"
  | "merge-folders"
  | "replace-transferred-folders"
```

```ts
export const applyWorkspaceSourceTransfer = (
  input: WorkspaceSourceTransferInput
): WorkspaceSourceTransferResult => {
  // clone snapshots
  // dedupe selected sources by mediaId
  // map folder paths into destination
  // apply conflict policy
  // remove origin wrappers only for move
  // compute newly empty origin folders
}
```

Keep the helper boring:
1. no store reads
2. no React imports
3. no UI strings
4. return enough structured data for the modal summary and the store transaction

- [ ] **Step 4: Re-run the pure transfer tests**

Run:

```bash
bunx vitest run apps/packages/ui/src/store/__tests__/workspace-source-transfer.test.ts
```

Expected: PASS for copy, move, conflict, folder mapping, and cleanup invariants.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/types/workspace.ts \
  apps/packages/ui/src/store/workspace-source-transfer.ts \
  apps/packages/ui/src/store/__tests__/workspace-source-transfer.test.ts
git commit -m "feat(workspace): add source transfer planner"
```

## Task 2: Add The Store-Level Transfer Transaction

**Files:**
- Modify: `apps/packages/ui/src/store/workspace.ts`
- Modify: `apps/packages/ui/src/store/workspace-slices/workspace-list-slice.ts`
- Test: `apps/packages/ui/src/store/__tests__/workspace.test.ts`

- [ ] **Step 1: Write the failing store tests for transfer orchestration**

Extend `workspace.test.ts` to prove the store transaction does the system-level work that the pure helper cannot:

```ts
it("creates a destination workspace for split without switching before transfer commit", () => {
  const result = useWorkspaceStore.getState().transferSourcesBetweenWorkspaces({
    mode: "copy",
    destination: { kind: "new", name: "Strategy Workspace" },
    selectedSourceIds: ["source-1"],
    switchToDestinationOnComplete: false
  })

  expect(result?.destinationWorkspaceId).toBeTruthy()
  expect(useWorkspaceStore.getState().workspaceName).toBe("Original Workspace")
})
```

```ts
it("updates sourceCount, lastAccessedAt, and collection assignment for origin and destination", () => {
  const before = useWorkspaceStore.getState().savedWorkspaces
  const result = useWorkspaceStore.getState().transferSourcesBetweenWorkspaces(request)
  const after = useWorkspaceStore.getState().savedWorkspaces

  expect(after[0]?.id).toBe(result?.destinationWorkspaceId)
  expect(after.find((workspace) => workspace.id === originId)?.sourceCount).toBe(1)
})
```

Also cover:
1. destination cannot be the current workspace.
2. archived workspaces cannot be transfer targets in v1.
3. undo snapshot restore returns origin and destination to the pre-transfer state.
4. new split workspaces inherit the source workspace collection.
5. switching into a newly created split workspace selects the transferred destination wrappers by default.

- [ ] **Step 2: Run the store tests and verify they fail**

Run:

```bash
bunx vitest run apps/packages/ui/src/store/__tests__/workspace.test.ts
```

Expected: FAIL because the store has no transfer action and no non-switching destination-creation path.

- [ ] **Step 3: Implement the minimal transaction in the workspace store**

Add one store action in `workspace.ts` and implement it in `workspace-list-slice.ts`:

```ts
transferSourcesBetweenWorkspaces: (
  request: WorkspaceSourceTransferRequest
) => WorkspaceSourceTransferExecutionResult | null
```

Implementation requirements:
1. build the active snapshot with `buildWorkspaceSnapshot(state)` when the origin is current.
2. create a new destination snapshot record without calling `createNewWorkspace(...)`.
3. call `applyWorkspaceSourceTransfer(...)`.
4. update `workspaceSnapshots`, `savedWorkspaces`, `archivedWorkspaces`, and active state together.
5. keep the operation atomic so one undo snapshot can restore the whole transfer.
6. if `switchToDestinationOnComplete` is true, apply the destination snapshot only after the transaction succeeds.
7. when switching into a newly split workspace, set `selectedSourceIds` to the transferred destination source IDs returned by the helper.

Use existing helpers instead of inventing parallel metadata code:

```ts
createSavedWorkspaceEntry(...)
upsertSavedWorkspace(...)
getSavedWorkspaceCollectionId(...)
applyWorkspaceSnapshot(...)
```

- [ ] **Step 4: Re-run the store tests**

Run:

```bash
bunx vitest run apps/packages/ui/src/store/__tests__/workspace.test.ts
```

Expected: PASS for transfer orchestration, metadata updates, collection inheritance, and undo safety.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/store/workspace.ts \
  apps/packages/ui/src/store/workspace-slices/workspace-list-slice.ts \
  apps/packages/ui/src/store/__tests__/workspace.test.ts
git commit -m "feat(workspace): add source transfer store action"
```

## Task 3: Add The Shared Transfer Modal And Sources Pane Entry Point

**Files:**
- Create: `apps/packages/ui/src/components/Option/WorkspacePlayground/TransferSourcesModal.tsx`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage5.transfer.test.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage13.source-transfer.test.tsx`

- [ ] **Step 1: Write the failing UI tests for the bulk Move / Copy flow**

Add one focused SourcesPane test and one shared-workspace integration test.

SourcesPane example:

```tsx
it("shows Move / Copy when effective selection exists", () => {
  render(<SourcesPane onOpenTransferSources={mockOpenTransferSources} />)

  fireEvent.click(screen.getByRole("button", { name: "Move / Copy" }))

  expect(mockOpenTransferSources).toHaveBeenCalledWith(
    expect.objectContaining({ entryPoint: "sources" })
  )
})
```

WorkspacePlayground example:

```tsx
it("shows hidden and ineligible selection summaries before confirming transfer", async () => {
  render(<WorkspacePlayground />)

  fireEvent.click(screen.getByRole("button", { name: "Move / Copy" }))

  expect(await screen.findByText(/selected sources are hidden/i)).toBeInTheDocument()
  expect(screen.getByText(/processing or errored sources are excluded/i)).toBeInTheDocument()
})
```

Also cover:
1. destination picker excludes the current workspace.
2. destination picker excludes archived workspaces.
3. conflict UI offers `Skip`, `Merge folder memberships`, and `Replace transferred folder memberships`.
4. move mode shows the empty-folder cleanup step.
5. successful transfer to an existing workspace offers an `Open destination` follow-up action.

- [ ] **Step 2: Run the UI tests and verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage5.transfer.test.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage13.source-transfer.test.tsx
```

Expected: FAIL because the shared modal and the new SourcesPane action do not exist yet.

- [ ] **Step 3: Implement the modal and SourcesPane wiring**

Add a parent-owned modal state in `index.tsx`, then wire the SourcesPane selected-actions bar into it.

The modal should own this sequence:

```tsx
<TransferSourcesModal
  open={transferModalOpen}
  entryPoint="sources"
  sourceListViewState={sourceListViewState}
  onCancel={closeTransferModal}
  onConfirm={handleConfirmTransfer}
/>
```

Inside `TransferSourcesModal.tsx`, keep the flow explicit and serial:
1. choose `Copy selected sources` or `Move selected sources`
2. choose destination or create new workspace inline
3. show hidden/ineligible summaries
4. resolve conflicts, with an `apply to all remaining` path
5. if moving, choose the empty-folder cleanup policy
6. execute the store action and show a concise success summary with an `Open destination` action for existing-workspace transfers

Do not duplicate store logic in React. The modal should collect decisions, then call `transferSourcesBetweenWorkspaces(...)`.

- [ ] **Step 4: Re-run the new UI tests**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage5.transfer.test.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage13.source-transfer.test.tsx
```

Expected: PASS for the shared modal flow, hidden/ineligible summaries, conflict controls, and sources-pane launch path.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/WorkspacePlayground/TransferSourcesModal.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/SourcesPane/index.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage5.transfer.test.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage13.source-transfer.test.tsx
git commit -m "feat(workspace): add source transfer modal"
```

## Task 4: Add The Workspace Header Split Shortcut

**Files:**
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/WorkspaceHeader.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx`
- Test: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage13.source-transfer.test.tsx`

- [ ] **Step 1: Write the failing header tests**

Add focused tests for the two header behaviors:

```tsx
it("opens split mode from the workspace settings menu when sources are selected", async () => {
  render(<WorkspaceHeader {...defaultProps} onOpenSplitWorkspace={mockOpenSplit} />)

  fireEvent.click(screen.getByRole("button", { name: "Workspace settings" }))
  fireEvent.click(await screen.findByText("Split Current Workspace"))

  expect(mockOpenSplit).toHaveBeenCalled()
})
```

```tsx
it("reveals the Sources pane instead of opening split mode when nothing is selected", async () => {
  render(<WorkspacePlayground />)

  fireEvent.click(screen.getByRole("button", { name: "Workspace settings" }))
  fireEvent.click(await screen.findByText("Split Current Workspace"))

  expect(screen.getByText(/select the sources to split first/i)).toBeInTheDocument()
})
```

Also cover:
1. the header path opens the same modal in `create new workspace` mode.
2. desktop layout reveals the left pane if it is collapsed.
3. mobile layout moves the user to the sources tab instead of doing nothing.

- [ ] **Step 2: Run the header-focused tests and verify they fail**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage13.source-transfer.test.tsx
```

Expected: FAIL because the settings menu has no split action and the parent component does not coordinate pane reveal/open behavior.

- [ ] **Step 3: Implement the header shortcut and pane-reveal behavior**

Add one new header callback and keep the decision logic in the parent:

```tsx
<WorkspaceHeader
  ...
  onOpenSplitWorkspace={handleOpenSplitWorkspace}
/>
```

`handleOpenSplitWorkspace` in `index.tsx` should:
1. inspect `getEffectiveSelectedSources()`
2. if none are selected, reveal the Sources pane and show an info message
3. if some are selected, open `TransferSourcesModal` in `mode = copy` and `destination = new`

Keep the header itself dumb. It should raise intent, not reimplement selection logic.

- [ ] **Step 4: Re-run the header-focused tests**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage13.source-transfer.test.tsx
```

Expected: PASS for the settings-menu shortcut, no-selection reveal behavior, and split-to-new-workspace modal defaults.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/WorkspacePlayground/index.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/WorkspaceHeader.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage13.source-transfer.test.tsx
git commit -m "feat(workspace): add split workspace shortcut"
```

## Task 5: Lock Regressions And Run Final Verification

**Files:**
- Modify: `apps/packages/ui/src/store/__tests__/workspace.test.ts`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage3.folders.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage13.source-transfer.test.tsx`

- [ ] **Step 1: Add regression coverage for the sharp edges**

Before calling the feature done, add explicit coverage for the places most likely to regress:

1. deleting newly empty origin folders clears `selectedSourceFolderIds` and repairs `activeFolderId`
2. `replace-transferred-folders` does not wipe unrelated destination folder memberships
3. `move` updates `sourceCount` in both workspaces correctly
4. split-created workspaces inherit the origin collection
5. hidden selected sources still count toward the transfer summary
6. split-created workspaces open with the transferred sources selected

Example assertion:

```ts
expect(useWorkspaceStore.getState().activeFolderId).toBeNull()
expect(useWorkspaceStore.getState().selectedSourceFolderIds).toEqual([])
```

- [ ] **Step 2: Run the full targeted frontend verification suite**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/store/__tests__/workspace-source-transfer.test.ts \
  apps/packages/ui/src/store/__tests__/workspace.test.ts \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage3.folders.test.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage5.transfer.test.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspaceHeader.test.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage13.source-transfer.test.tsx
```

Expected: PASS across the transfer helper, store transaction, folder cleanup behavior, and both UI entry points.

- [ ] **Step 3: Do the final cleanup pass**

Review the touched code for:
1. duplicate store logic that belongs in `workspace-source-transfer.ts`
2. UI-only strings that accidentally leaked into store code
3. modal state that can get stuck open after success or cancel
4. dead props or dead test fixtures left behind from incremental development

Security note: this implementation scope is TypeScript/React only, so Bandit is not applicable unless the scope expands into Python files later.

- [ ] **Step 4: Re-run the same targeted verification suite**

Run the same `bunx vitest run ...` command from Step 2.

Expected: PASS after cleanup, with no new failures introduced by the polish pass.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/store/__tests__/workspace.test.ts \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/SourcesPane.stage3.folders.test.tsx \
  apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/WorkspacePlayground.stage13.source-transfer.test.tsx
git commit -m "test(workspace): lock source transfer regressions"
```
