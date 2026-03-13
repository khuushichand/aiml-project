/**
 * API-first workspace state helpers.
 * These functions enable server hydration and optimistic mutation
 * with rollback on 409 conflicts.
 */

export interface ServerWorkspaceState {
  id: string
  name: string
  sources?: any[]
  artifacts?: any[]
  notes?: any[]
  version: number
  [key: string]: unknown
}

export interface LocalWorkspaceState {
  id: string
  name: string
  sources: any[]
  artifacts: any[]
  notes: any[]
  version: number
}

/**
 * Hydrate local workspace state from the server.
 * Called on workspace switch to ensure local state reflects server truth.
 */
export async function hydrateWorkspaceFromServer(
  workspaceId: string,
  deps: { fetch: (id: string) => Promise<ServerWorkspaceState> }
): Promise<LocalWorkspaceState> {
  const server = await deps.fetch(workspaceId)
  return {
    id: server.id,
    name: server.name,
    sources: server.sources ?? [],
    artifacts: server.artifacts ?? [],
    notes: server.notes ?? [],
    version: server.version,
  }
}

/**
 * Perform an optimistic workspace update.
 * On success, returns the server's updated state.
 * On 409 conflict, returns the server's current state (rollback).
 */
export async function optimisticWorkspaceUpdate(
  current: { id: string; name: string; version: number },
  updates: Record<string, unknown>,
  deps: { update: (id: string, body: any) => Promise<any> }
): Promise<{ name: string; version: number; [key: string]: unknown }> {
  try {
    const result = await deps.update(current.id, { ...updates, version: current.version })
    return result
  } catch (err: any) {
    if (err.status === 409 && err.body) {
      return err.body
    }
    throw err
  }
}
