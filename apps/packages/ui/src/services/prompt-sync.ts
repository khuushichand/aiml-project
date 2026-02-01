/**
 * Prompt Sync Service
 *
 * Provides manual sync operations between local IndexedDB prompts
 * and server-side Prompt Studio. Sync is user-initiated (no auto-sync).
 */

import { db } from '@/db/dexie/schema'
import { PageAssistDatabase } from '@/db/dexie/chat'
import { generateID } from '@/db/dexie/helpers'
import {
  Prompt as LocalPrompt,
  PromptSyncStatus,
  FewShotExample,
  PromptModule
} from '@/db/dexie/types'
import {
  createPrompt as createServerPrompt,
  updatePrompt as updateServerPrompt,
  getPrompt as getServerPrompt,
  listProjects,
  Prompt as ServerPrompt,
  PromptCreatePayload,
  PromptUpdatePayload,
  Project
} from '@/services/prompt-studio'

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type SyncResult = {
  success: boolean
  localId: string
  serverId?: number
  error?: string
  syncStatus: PromptSyncStatus
}

export type ConflictInfo = {
  localPrompt: LocalPrompt
  serverPrompt: ServerPrompt
  localUpdatedAt: number
  serverUpdatedAt: string
}

export type ConflictResolution = 'keep_local' | 'keep_server' | 'keep_both'

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Convert a local prompt to server create payload.
 */
function localToServerPayload(
  local: LocalPrompt,
  projectId: number
): PromptCreatePayload {
  return {
    project_id: projectId,
    name: local.name || local.title,
    system_prompt: local.system_prompt,
    user_prompt: local.user_prompt,
    few_shot_examples: local.fewShotExamples,
    modules_config: local.modulesConfig,
    change_description: local.changeDescription || 'Initial sync from workspace'
  }
}

/**
 * Convert a local prompt to server update payload.
 */
function localToServerUpdatePayload(local: LocalPrompt): PromptUpdatePayload {
  return {
    name: local.name || local.title,
    system_prompt: local.system_prompt,
    user_prompt: local.user_prompt,
    few_shot_examples: local.fewShotExamples,
    modules_config: local.modulesConfig,
    change_description: local.changeDescription || 'Synced from workspace'
  }
}

/**
 * Convert server prompt to local prompt fields.
 */
function serverToLocalFields(server: ServerPrompt): Partial<LocalPrompt> {
  return {
    serverId: server.id,
    studioProjectId: server.project_id,
    studioPromptId: server.id,
    name: server.name,
    system_prompt: server.system_prompt,
    user_prompt: server.user_prompt,
    fewShotExamples: server.few_shot_examples as FewShotExample[] | undefined,
    modulesConfig: server.modules_config as PromptModule[] | undefined,
    versionNumber: server.version_number,
    changeDescription: server.change_description,
    serverParentVersionId: server.parent_version_id,
    serverUpdatedAt: server.updated_at,
    syncStatus: 'synced' as PromptSyncStatus,
    lastSyncedAt: Date.now()
  }
}

/**
 * Create a new local prompt from server prompt.
 */
function serverToNewLocalPrompt(server: ServerPrompt): LocalPrompt {
  const now = Date.now()
  return {
    id: generateID(),
    title: server.name,
    name: server.name,
    content: server.system_prompt || server.user_prompt || '',
    is_system: !!server.system_prompt,
    system_prompt: server.system_prompt,
    user_prompt: server.user_prompt,
    createdAt: now,
    updatedAt: now,
    // Server sync fields
    serverId: server.id,
    studioProjectId: server.project_id,
    studioPromptId: server.id,
    fewShotExamples: server.few_shot_examples as FewShotExample[] | undefined,
    modulesConfig: server.modules_config as PromptModule[] | undefined,
    versionNumber: server.version_number,
    changeDescription: server.change_description,
    serverParentVersionId: server.parent_version_id,
    serverUpdatedAt: server.updated_at,
    syncStatus: 'synced',
    sourceSystem: 'studio',
    lastSyncedAt: now
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Sync Operations
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Push a local prompt to Prompt Studio (create or update).
 *
 * @param localId - Local prompt ID
 * @param projectId - Target Prompt Studio project ID
 * @returns Sync result
 */
export async function pushToStudio(
  localId: string,
  projectId: number
): Promise<SyncResult> {
  try {
    const local = await db.prompts.get(localId)
    if (!local) {
      return {
        success: false,
        localId,
        error: 'Local prompt not found',
        syncStatus: 'local'
      }
    }

    // If already linked, update existing server prompt
    if (local.serverId) {
      const updatePayload = localToServerUpdatePayload(local)
      const response = await updateServerPrompt(local.serverId, updatePayload)

      if (!(response as any)?.data?.data && !(response as any)?.data?.id) {
        return {
          success: false,
          localId,
          serverId: local.serverId,
          error: 'Failed to update server prompt',
          syncStatus: 'pending'
        }
      }

      const serverPrompt = (response as any)?.data?.data || (response as any)?.data
      const updateFields = serverToLocalFields(serverPrompt)
      await db.prompts.update(localId, updateFields)

      return {
        success: true,
        localId,
        serverId: serverPrompt.id,
        syncStatus: 'synced'
      }
    }

    // Create new server prompt
    const createPayload = localToServerPayload(local, projectId)
    const response = await createServerPrompt(createPayload)

    if (!(response as any)?.data?.data && !(response as any)?.data?.id) {
      return {
        success: false,
        localId,
        error: 'Failed to create server prompt',
        syncStatus: 'pending'
      }
    }

    const serverPrompt = (response as any)?.data?.data || (response as any)?.data
    const updateFields = serverToLocalFields(serverPrompt)
    updateFields.studioProjectId = projectId
    await db.prompts.update(localId, updateFields)

    return {
      success: true,
      localId,
      serverId: serverPrompt.id,
      syncStatus: 'synced'
    }
  } catch (error: any) {
    return {
      success: false,
      localId,
      error: error?.message || 'Push failed',
      syncStatus: 'pending'
    }
  }
}

/**
 * Pull a server prompt to local storage.
 *
 * @param serverId - Server prompt ID
 * @param existingLocalId - Optional existing local ID to update
 * @returns Sync result
 */
export async function pullFromStudio(
  serverId: number,
  existingLocalId?: string
): Promise<SyncResult> {
  try {
    const response = await getServerPrompt(serverId)
    const serverPrompt = (response as any)?.data?.data || (response as any)?.data

    if (!serverPrompt) {
      return {
        success: false,
        localId: existingLocalId || '',
        serverId,
        error: 'Server prompt not found',
        syncStatus: 'local'
      }
    }

    // Update existing local prompt
    if (existingLocalId) {
      const local = await db.prompts.get(existingLocalId)
      if (local) {
        const updateFields = serverToLocalFields(serverPrompt)
        await db.prompts.update(existingLocalId, updateFields)

        return {
          success: true,
          localId: existingLocalId,
          serverId,
          syncStatus: 'synced'
        }
      }
    }

    // Check if we already have this prompt locally by serverId
    const existing = await db.prompts.where('serverId').equals(serverId).first()
    if (existing) {
      const updateFields = serverToLocalFields(serverPrompt)
      await db.prompts.update(existing.id, updateFields)

      return {
        success: true,
        localId: existing.id,
        serverId,
        syncStatus: 'synced'
      }
    }

    // Create new local prompt
    const newLocal = serverToNewLocalPrompt(serverPrompt)
    await db.prompts.add(newLocal)

    return {
      success: true,
      localId: newLocal.id,
      serverId,
      syncStatus: 'synced'
    }
  } catch (error: any) {
    return {
      success: false,
      localId: existingLocalId || '',
      serverId,
      error: error?.message || 'Pull failed',
      syncStatus: 'local'
    }
  }
}

/**
 * Link an existing local prompt to an existing server prompt.
 *
 * @param localId - Local prompt ID
 * @param serverId - Server prompt ID
 * @returns Sync result
 */
export async function linkPrompts(
  localId: string,
  serverId: number
): Promise<SyncResult> {
  try {
    const local = await db.prompts.get(localId)
    if (!local) {
      return {
        success: false,
        localId,
        serverId,
        error: 'Local prompt not found',
        syncStatus: 'local'
      }
    }

    const response = await getServerPrompt(serverId)
    const serverPrompt = (response as any)?.data?.data || (response as any)?.data

    if (!serverPrompt) {
      return {
        success: false,
        localId,
        serverId,
        error: 'Server prompt not found',
        syncStatus: 'local'
      }
    }

    // Link by updating local with server reference
    await db.prompts.update(localId, {
      serverId,
      studioProjectId: serverPrompt.project_id,
      studioPromptId: serverId,
      serverUpdatedAt: serverPrompt.updated_at,
      syncStatus: 'pending', // Pending because content may differ
      lastSyncedAt: Date.now()
    })

    return {
      success: true,
      localId,
      serverId,
      syncStatus: 'pending'
    }
  } catch (error: any) {
    return {
      success: false,
      localId,
      serverId,
      error: error?.message || 'Link failed',
      syncStatus: 'local'
    }
  }
}

/**
 * Unlink a local prompt from server (keep local copy).
 */
export async function unlinkPrompt(localId: string): Promise<SyncResult> {
  let local: LocalPrompt | undefined
  try {
    local = await db.prompts.get(localId)
    if (!local) {
      return {
        success: false,
        localId,
        error: 'Local prompt not found',
        syncStatus: 'local'
      }
    }

    await db.prompts.update(localId, {
      serverId: null,
      studioProjectId: null,
      studioPromptId: null,
      serverUpdatedAt: null,
      syncStatus: 'local',
      sourceSystem: 'workspace',
      lastSyncedAt: null
    })

    return {
      success: true,
      localId,
      syncStatus: 'local'
    }
  } catch (error: any) {
    return {
      success: false,
      localId,
      error: error?.message || 'Unlink failed',
      syncStatus: local?.syncStatus || 'local'
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Status & Conflict Detection
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Get sync status for a local prompt.
 */
export async function getSyncStatus(localId: string): Promise<{
  status: PromptSyncStatus
  serverId?: number
  lastSyncedAt?: number
  hasConflict: boolean
}> {
  const local = await db.prompts.get(localId)
  if (!local) {
    return { status: 'local', hasConflict: false }
  }

  if (!local.serverId) {
    return { status: 'local', hasConflict: false }
  }

  // Check for conflict by comparing timestamps
  try {
    const response = await getServerPrompt(local.serverId)
    const serverPrompt = (response as any)?.data?.data || (response as any)?.data

    if (!serverPrompt) {
      // Server prompt deleted
      return {
        status: 'conflict',
        serverId: local.serverId,
        lastSyncedAt: local.lastSyncedAt || undefined,
        hasConflict: true
      }
    }

    const serverUpdatedAt = serverPrompt.updated_at
    const hasConflict = local.serverUpdatedAt !== serverUpdatedAt &&
      (local.updatedAt || 0) > (local.lastSyncedAt || 0)

    return {
      status: hasConflict ? 'conflict' : local.syncStatus || 'synced',
      serverId: local.serverId,
      lastSyncedAt: local.lastSyncedAt || undefined,
      hasConflict
    }
  } catch {
    return {
      status: local.syncStatus || 'local',
      serverId: local.serverId,
      lastSyncedAt: local.lastSyncedAt || undefined,
      hasConflict: false
    }
  }
}

/**
 * Get detailed conflict information.
 */
export async function getConflictInfo(localId: string): Promise<ConflictInfo | null> {
  const local = await db.prompts.get(localId)
  if (!local || !local.serverId) return null

  try {
    const response = await getServerPrompt(local.serverId)
    const serverPrompt = (response as any)?.data?.data || (response as any)?.data
    if (!serverPrompt) return null

    return {
      localPrompt: local,
      serverPrompt,
      localUpdatedAt: local.updatedAt || local.createdAt,
      serverUpdatedAt: serverPrompt.updated_at
    }
  } catch {
    return null
  }
}

/**
 * Resolve a sync conflict.
 */
export async function resolveConflict(
  localId: string,
  resolution: ConflictResolution
): Promise<SyncResult> {
  const local = await db.prompts.get(localId)
  if (!local || !local.serverId) {
    return {
      success: false,
      localId,
      error: 'No conflict to resolve',
      syncStatus: 'local'
    }
  }

  switch (resolution) {
    case 'keep_local':
      // Push local to server (overwrite server)
      return await pushToStudio(localId, local.studioProjectId!)

    case 'keep_server':
      // Pull server to local (overwrite local)
      return await pullFromStudio(local.serverId, localId)

    case 'keep_both':
      // Unlink and create a new server version
      await unlinkPrompt(localId)
      if (local.studioProjectId) {
        return await pushToStudio(localId, local.studioProjectId)
      }
      return {
        success: true,
        localId,
        syncStatus: 'local'
      }

    default:
      return {
        success: false,
        localId,
        error: 'Invalid resolution',
        syncStatus: 'conflict'
      }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Batch Operations
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Get all prompts with their sync status.
 */
export async function getAllPromptsWithSyncStatus(): Promise<Array<{
  prompt: LocalPrompt
  syncStatus: PromptSyncStatus
  isSynced: boolean
}>> {
  const dbInstance = new PageAssistDatabase()
  const prompts = await dbInstance.getAllPrompts()

  return prompts.map(prompt => ({
    prompt,
    syncStatus: prompt.syncStatus || 'local',
    isSynced: prompt.syncStatus === 'synced'
  }))
}

/**
 * Get all prompts linked to a specific project.
 */
export async function getPromptsByProject(projectId: number): Promise<LocalPrompt[]> {
  return await db.prompts
    .where('studioProjectId')
    .equals(projectId)
    .filter(p => !p.deletedAt)
    .toArray()
}

/**
 * Get available projects for syncing.
 */
export async function getAvailableProjects(): Promise<Project[]> {
  try {
    const response = await listProjects({ per_page: 100 })
    return (response as any)?.data?.data || []
  } catch {
    return []
  }
}
