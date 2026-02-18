# Workspace Playground Collaboration & Sync Plan (Stage 3)

## Purpose

Define a phased collaboration roadmap for Workspace Playground and lock a versioned sync payload contract before server APIs are finalized.

## Scope

- Real-time collaboration roadmap for multi-user workspace editing
- Sync payload contract versioning and compatibility gates
- Rollout sequencing from local-only to shared editing

## Phased Roadmap

### Phase 0: Contract Baseline (current)
- Introduce `WORKSPACE_SYNC_PAYLOAD_VERSION = 1`.
- Serialize workspace snapshot payloads with explicit `updatedAt` and normalized ISO timestamps.
- Add runtime validation for contract compatibility (`isWorkspaceSyncPayload`).
- Gate future server sync endpoints on contract validation.

### Phase 1: Server Save/Load (single-writer)
- Add authenticated workspace sync endpoints for push/pull snapshot operations.
- Persist full snapshot history on server with revision IDs.
- Enforce last-write metadata (`updatedAt`, `workspaceId`, `workspaceTag`) and basic conflict detection.

### Phase 2: Multi-user Presence + Soft Locking
- Add workspace presence channels (active collaborators, heartbeat).
- Add soft-lock metadata for high-conflict surfaces (note editor, source ordering).
- Surface conflict notices with non-destructive merge options in UI.

### Phase 3: Realtime Patch Streams
- Move from snapshot-only sync to patch/event streams.
- Use event sequencing and replay for deterministic state recovery.
- Add optimistic local patches with server reconciliation and rollback for rejected patches.

## Contract Summary (v1)

`WorkspaceSyncPayload` fields:
- `version`
- `workspaceId`
- `workspaceTag`
- `updatedAt`
- `snapshot.workspaceName`
- `snapshot.selectedSourceIds`
- `snapshot.sources[]`
- `snapshot.generatedArtifacts[]`
- `snapshot.currentNote`

Compatibility rules:
- Any payload with `version !== 1` is rejected by v1 clients.
- Additive fields are allowed in future minor revisions.
- Breaking field changes require version bump and migration path.

## Validation Artifacts

- Runtime contract helpers:
  - `apps/packages/ui/src/store/workspace-sync-contract.ts`
- Contract tests:
  - `apps/packages/ui/src/store/__tests__/workspace-sync-contract.test.ts`
