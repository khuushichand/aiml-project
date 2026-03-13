/**
 * One-time migration of local workspaces to server.
 * After migration, localStorage is no longer the source of truth
 * for workspace data — only UI preferences remain local.
 */

interface MigrationDeps {
  upsertWorkspace: (id: string, body: any) => Promise<any>
  addSource: (workspaceId: string, data: any) => Promise<any>
  addArtifact: (workspaceId: string, data: any) => Promise<any>
  addNote: (workspaceId: string, data: any) => Promise<any>
}

interface LocalWorkspace {
  id: string
  name: string
  sources: any[]
  artifacts: any[]
  notes: any[]
}

const MIGRATION_FLAG = "workspace_migrated"

export async function migrateLocalWorkspacesToServer(
  localWorkspaces: LocalWorkspace[],
  deps: MigrationDeps
): Promise<void> {
  if (localStorage.getItem(MIGRATION_FLAG) === "true") return

  for (const ws of localWorkspaces) {
    await deps.upsertWorkspace(ws.id, { name: ws.name })
    for (const src of ws.sources) {
      await deps.addSource(ws.id, src)
    }
    for (const art of ws.artifacts) {
      await deps.addArtifact(ws.id, art)
    }
    for (const note of ws.notes) {
      await deps.addNote(ws.id, note)
    }
  }

  localStorage.setItem(MIGRATION_FLAG, "true")
}
