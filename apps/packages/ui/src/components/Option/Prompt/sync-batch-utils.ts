import type { PromptSyncStatus, PromptSourceSystem } from "@/db/dexie/types"

export type SyncPromptLike = {
  id: string
  name?: string
  title?: string
  syncStatus?: PromptSyncStatus
  sourceSystem?: PromptSourceSystem
  serverId?: number | null
  studioProjectId?: number | null
}

export type SyncStatusItem = {
  prompt: SyncPromptLike
  syncStatus?: PromptSyncStatus
}

export type SyncBatchDirection = "push" | "pull"

export type SyncBatchTask = {
  promptId: string
  promptName: string
  direction: SyncBatchDirection
  serverId?: number
  preferredProjectId?: number
}

export type SyncBatchPlan = {
  tasks: SyncBatchTask[]
  skippedConflicts: number
  skippedCopilotPending: number
}

const resolveStatus = (item: SyncStatusItem): PromptSyncStatus =>
  item.syncStatus || item.prompt.syncStatus || "local"

const resolvePromptName = (prompt: SyncPromptLike): string =>
  prompt.name || prompt.title || "Untitled prompt"

export const buildSyncBatchPlan = (items: SyncStatusItem[]): SyncBatchPlan => {
  const tasks: SyncBatchTask[] = []
  let skippedConflicts = 0
  let skippedCopilotPending = 0

  for (const item of items) {
    const prompt = item.prompt
    const status = resolveStatus(item)
    const sourceSystem = prompt.sourceSystem || "workspace"
    const promptName = resolvePromptName(prompt)

    if (status === "conflict") {
      skippedConflicts += 1
      continue
    }

    if (status === "pending") {
      if (sourceSystem === "copilot") {
        skippedCopilotPending += 1
        continue
      }
      tasks.push({
        promptId: prompt.id,
        promptName,
        direction: "push",
        serverId: typeof prompt.serverId === "number" ? prompt.serverId : undefined,
        preferredProjectId:
          typeof prompt.studioProjectId === "number"
            ? prompt.studioProjectId
            : undefined
      })
      continue
    }

    if (
      status === "local" &&
      sourceSystem === "studio" &&
      typeof prompt.serverId === "number"
    ) {
      tasks.push({
        promptId: prompt.id,
        promptName,
        direction: "pull",
        serverId: prompt.serverId,
        preferredProjectId:
          typeof prompt.studioProjectId === "number"
            ? prompt.studioProjectId
            : undefined
      })
    }
  }

  return {
    tasks,
    skippedConflicts,
    skippedCopilotPending
  }
}
