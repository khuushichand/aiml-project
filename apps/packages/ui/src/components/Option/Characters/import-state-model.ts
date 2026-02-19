export const CHARACTER_IMPORT_FILE_STATES = [
  "queued",
  "processing",
  "success",
  "failure"
] as const

export type CharacterImportFileState =
  (typeof CHARACTER_IMPORT_FILE_STATES)[number]

export type CharacterImportDragState = "idle" | "drag-over"

export type CharacterImportQueueItem = {
  id: string
  fileName: string
  state: CharacterImportFileState
  message: string | null
}

export type CharacterImportQueueState = {
  dragState: CharacterImportDragState
  items: CharacterImportQueueItem[]
}

export type CharacterImportBatchSummary = {
  total: number
  queued: number
  processing: number
  success: number
  failure: number
  complete: boolean
}

export type CharacterImportQueueAction =
  | {
      type: "queue/replace"
      files: Array<{ id: string; fileName: string }>
    }
  | {
      type: "queue/append"
      files: Array<{ id: string; fileName: string }>
    }
  | {
      type: "item/processing"
      id: string
    }
  | {
      type: "item/success"
      id: string
      message?: string | null
    }
  | {
      type: "item/failure"
      id: string
      message: string
    }
  | {
      type: "drag/enter"
    }
  | {
      type: "drag/leave"
    }
  | {
      type: "queue/reset"
    }

export const initialCharacterImportQueueState: CharacterImportQueueState = {
  dragState: "idle",
  items: []
}

const createQueuedItem = (file: {
  id: string
  fileName: string
}): CharacterImportQueueItem => ({
  id: file.id,
  fileName: file.fileName,
  state: "queued",
  message: null
})

const mergeQueuedItems = (
  current: CharacterImportQueueItem[],
  files: Array<{ id: string; fileName: string }>
): CharacterImportQueueItem[] => {
  const seen = new Set(current.map((item) => item.id))
  const next = [...current]
  for (const file of files) {
    if (seen.has(file.id)) continue
    next.push(createQueuedItem(file))
    seen.add(file.id)
  }
  return next
}

const updateQueueItem = (
  items: CharacterImportQueueItem[],
  id: string,
  state: CharacterImportFileState,
  message: string | null
): CharacterImportQueueItem[] =>
  items.map((item) =>
    item.id === id
      ? {
          ...item,
          state,
          message
        }
      : item
  )

export const characterImportQueueReducer = (
  state: CharacterImportQueueState,
  action: CharacterImportQueueAction
): CharacterImportQueueState => {
  switch (action.type) {
    case "queue/replace":
      return {
        ...state,
        items: action.files.map(createQueuedItem)
      }
    case "queue/append":
      return {
        ...state,
        items: mergeQueuedItems(state.items, action.files)
      }
    case "item/processing":
      return {
        ...state,
        items: updateQueueItem(state.items, action.id, "processing", null)
      }
    case "item/success":
      return {
        ...state,
        items: updateQueueItem(
          state.items,
          action.id,
          "success",
          action.message ?? null
        )
      }
    case "item/failure":
      return {
        ...state,
        items: updateQueueItem(state.items, action.id, "failure", action.message)
      }
    case "drag/enter":
      return {
        ...state,
        dragState: "drag-over"
      }
    case "drag/leave":
      return {
        ...state,
        dragState: "idle"
      }
    case "queue/reset":
      return {
        ...initialCharacterImportQueueState
      }
    default:
      return state
  }
}

export const summarizeCharacterImportQueue = (
  items: CharacterImportQueueItem[]
): CharacterImportBatchSummary => {
  const summary: CharacterImportBatchSummary = {
    total: items.length,
    queued: 0,
    processing: 0,
    success: 0,
    failure: 0,
    complete: false
  }

  for (const item of items) {
    if (item.state === "queued") summary.queued += 1
    else if (item.state === "processing") summary.processing += 1
    else if (item.state === "success") summary.success += 1
    else if (item.state === "failure") summary.failure += 1
  }

  summary.complete = summary.total > 0 && summary.queued + summary.processing === 0
  return summary
}

export type CharacterImportUploadFileLike = {
  uid?: string | null
  name: string
  size: number
  lastModified: number
}

export const shouldHandleImportUploadEvent = ({
  file,
  fileList
}: {
  file: CharacterImportUploadFileLike
  fileList: CharacterImportUploadFileLike[]
}): boolean => {
  const batch = (fileList && fileList.length > 0 ? fileList : [file]).filter(
    Boolean
  )
  if (batch.length <= 1) return true

  const first = batch[0]
  const firstUid = typeof first?.uid === "string" ? first.uid : null
  const fileUid = typeof file?.uid === "string" ? file.uid : null
  if (firstUid && fileUid) {
    return firstUid === fileUid
  }

  return (
    first?.name === file.name &&
    first?.size === file.size &&
    first?.lastModified === file.lastModified
  )
}

export const toCharacterImportPreviewMode = (
  fileCount: number
): "single" | "batch" => (fileCount > 1 ? "batch" : "single")
