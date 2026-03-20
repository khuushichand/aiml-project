import React from 'react'
import type { MessageInstance } from 'antd/es/message/interface'
import {
  coerceDraftMediaType,
  inferIngestTypeFromUrl,
  inferUploadMediaTypeFromFile
} from "@/services/tldw/media-routing"
import { useStorage } from '@plasmohq/storage/hook'
import { useQuickIngestStore } from "@/store/quick-ingest"
import { QUICK_INGEST_ACCEPT_STRING } from "../QuickIngest/constants"

// ---------------------------------------------------------------------------
// Shared types (mirrored from QuickIngestModal to avoid circular deps)
// ---------------------------------------------------------------------------

export type TypeDefaults = {
  audio?: { language?: string; diarize?: boolean }
  document?: { ocr?: boolean }
  video?: { captions?: boolean }
}

export type Entry = {
  id: string
  url: string
  type: 'auto' | 'html' | 'pdf' | 'document' | 'audio' | 'video'
  defaults?: TypeDefaults
  keywords?: string
  audio?: { language?: string; diarize?: boolean }
  document?: { ocr?: boolean }
  video?: { captions?: boolean }
}

export type QueuedFileStub = {
  id: string
  key: string
  instanceId?: string
  name: string
  size: number
  type?: string
  lastModified?: number
  defaults?: TypeDefaults
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

const buildLocalFileKey = (file: File) => {
  const name = file?.name || ""
  const size = Number.isFinite(file?.size) ? file.size : 0
  const lastModified = Number.isFinite(file?.lastModified) ? file.lastModified : 0
  return `${name}::${size}::${lastModified}`
}

const fileInstanceIds = new WeakMap<File, string>()

export const getFileInstanceId = (file: File) => {
  const existing = fileInstanceIds.get(file)
  if (existing) return existing
  const id = crypto.randomUUID()
  fileInstanceIds.set(file, id)
  return id
}

export const snapshotTypeDefaults = (defaults?: TypeDefaults): TypeDefaults | undefined => {
  if (!defaults) return undefined
  const next: TypeDefaults = {}
  if (defaults.audio && (defaults.audio.language || typeof defaults.audio.diarize === 'boolean')) {
    next.audio = { ...defaults.audio }
  }
  if (defaults.document && typeof defaults.document.ocr === 'boolean') {
    next.document = { ...defaults.document }
  }
  if (defaults.video && typeof defaults.video.captions === 'boolean') {
    next.video = { ...defaults.video }
  }
  return Object.keys(next).length > 0 ? next : undefined
}

export const buildQueuedFileStub = (
  file: File,
  defaults?: TypeDefaults
): QueuedFileStub => ({
  id: crypto.randomUUID(),
  key: buildLocalFileKey(file),
  instanceId: getFileInstanceId(file),
  name: file?.name || "",
  size: Number.isFinite(file?.size) ? file.size : 0,
  type: file?.type,
  lastModified: Number.isFinite(file?.lastModified) ? file.lastModified : undefined,
  defaults: snapshotTypeDefaults(defaults)
})

const MAX_LOCAL_FILE_BYTES = 500 * 1024 * 1024

const DEFAULT_TYPE_DEFAULTS: TypeDefaults = {
  document: { ocr: true }
}

const isLikelyUrl = (raw: string) => {
  const trimmed = (raw || "").trim()
  if (!trimmed) return false
  try {
    const parsed = new URL(trimmed)
    return parsed.protocol === "http:" || parsed.protocol === "https:"
  } catch {
    return false
  }
}

// ---------------------------------------------------------------------------
// Deps interface
// ---------------------------------------------------------------------------

export interface UseIngestQueueDeps {
  open: boolean
  running: boolean
  ingestBlocked: boolean
  messageApi: MessageInstance
  /** Quick-ingest i18n helper */
  qi: (key: string, defaultValue: string, options?: Record<string, any>) => string
  /** Normalised type defaults from options hook */
  normalizedTypeDefaults: TypeDefaults
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useIngestQueue(deps: UseIngestQueueDeps) {
  const {
    open,
    running,
    ingestBlocked,
    messageApi,
    qi,
    normalizedTypeDefaults,
  } = deps

  // ---- persisted queue state ----
  const [rows, setRows] = useStorage<Entry[]>(
    "quickIngestQueuedRows",
    [createEmptyRow()]
  )
  const [queuedFiles, setQueuedFiles] = useStorage<QueuedFileStub[]>(
    "quickIngestQueuedFiles",
    []
  )

  // ---- local (session) state ----
  const [localFiles, setLocalFiles] = React.useState<File[]>([])
  const [selectedRowId, setSelectedRowId] = React.useState<string | null>(null)
  const [selectedFileId, setSelectedFileId] = React.useState<string | null>(null)
  const [pendingUrlInput, setPendingUrlInput] = React.useState<string>('')
  const [pendingReattachId, setPendingReattachId] = React.useState<string | null>(null)
  const reattachInputRef = React.useRef<HTMLInputElement | null>(null)

  const { setQueuedCount } = useQuickIngestStore((s) => ({
    setQueuedCount: s.setQueuedCount,
  }))

  // ---- derived helpers ----
  const createDefaultsSnapshot = React.useCallback(
    () => snapshotTypeDefaults(normalizedTypeDefaults),
    [normalizedTypeDefaults]
  )

  const buildRowEntry = React.useCallback(
    (url = '', type: Entry['type'] = 'auto'): Entry => ({
      id: crypto.randomUUID(),
      url,
      type,
      defaults: createDefaultsSnapshot()
    }),
    [createDefaultsSnapshot]
  )

  const fileTypeFromName = React.useCallback(
    (f: { name?: string; type?: string }): Entry['type'] => {
      const uploadType = inferUploadMediaTypeFromFile(
        f?.name || '',
        f?.type || ''
      )
      return uploadType === 'ebook' ? 'document' : uploadType
    },
    []
  )

  const formatBytes = React.useCallback((bytes?: number) => {
    if (!bytes || Number.isNaN(bytes)) return ''
    const units = ['B', 'KB', 'MB', 'GB']
    let v = bytes
    let u = 0
    while (v >= 1024 && u < units.length - 1) {
      v /= 1024
      u += 1
    }
    return `${v.toFixed(v >= 10 ? 0 : 1)} ${units[u]}`
  }, [])

  // ---- queued file stubs ----
  const queuedFileStubs = queuedFiles || []

  // ---- file attachment resolution ----
  const attachedFilesByInstanceId = React.useMemo(
    () => new Map(localFiles.map((file) => [getFileInstanceId(file), file])),
    [localFiles]
  )

  const {
    attachedFileStubs,
    missingFileStubs,
    attachedFiles,
    fileForStubId,
    stubsNeedingInstanceId
  } = React.useMemo(() => {
    const fileForStubId = new Map<string, File>()
    const matchedInstanceIds = new Set<string>()
    const filesBySignature = new Map<string, File[]>()
    for (const file of localFiles) {
      const signature = buildLocalFileKey(file)
      const list = filesBySignature.get(signature) || []
      list.push(file)
      filesBySignature.set(signature, list)
    }
    const stubsNeedingInstanceId: Array<{ id: string; instanceId: string }> = []

    for (const stub of queuedFileStubs) {
      let file: File | undefined
      if (stub.instanceId) {
        file = attachedFilesByInstanceId.get(stub.instanceId)
      }
      if (!file) {
        const candidates = filesBySignature.get(stub.key)
        if (candidates) {
          file = candidates.find(
            (candidate) => !matchedInstanceIds.has(getFileInstanceId(candidate))
          )
        }
      }
      if (file) {
        const instanceId = getFileInstanceId(file)
        fileForStubId.set(stub.id, file)
        matchedInstanceIds.add(instanceId)
        if (!stub.instanceId || stub.instanceId !== instanceId) {
          stubsNeedingInstanceId.push({ id: stub.id, instanceId })
        }
      }
    }

    const attachedFileStubs = queuedFileStubs.filter((stub) =>
      fileForStubId.has(stub.id)
    )
    const missingFileStubs = queuedFileStubs.filter(
      (stub) => !fileForStubId.has(stub.id)
    )
    const attachedFiles = attachedFileStubs
      .map((stub) => fileForStubId.get(stub.id))
      .filter(Boolean) as File[]

    return {
      attachedFileStubs,
      missingFileStubs,
      attachedFiles,
      fileForStubId,
      stubsNeedingInstanceId
    }
  }, [attachedFilesByInstanceId, localFiles, queuedFileStubs])

  const hasMissingFiles = missingFileStubs.length > 0

  // Sync instance IDs when stubs need updating
  React.useEffect(() => {
    if (!stubsNeedingInstanceId.length) return
    setQueuedFiles((prev) => {
      if (!prev || prev.length === 0) return prev
      let changed = false
      const updates = new Map(
        stubsNeedingInstanceId.map((item) => [item.id, item.instanceId])
      )
      const next = prev.map((stub) => {
        const nextInstanceId = updates.get(stub.id)
        if (!nextInstanceId || stub.instanceId === nextInstanceId) return stub
        changed = true
        return { ...stub, instanceId: nextInstanceId }
      })
      return changed ? next : prev
    })
  }, [setQueuedFiles, stubsNeedingInstanceId])

  // ---- planned count ----
  const plannedCount = React.useMemo(() => {
    const valid = rows.filter((r) => r.url.trim().length > 0)
    return valid.length + attachedFileStubs.length
  }, [rows, attachedFileStubs.length])

  // Sync queued count to store
  React.useEffect(() => {
    const queuedUrls = rows.filter((r) => r.url.trim().length > 0).length
    const queuedFilesCount = queuedFileStubs.length
    setQueuedCount(queuedUrls + queuedFilesCount)
  }, [queuedFileStubs.length, rows, setQueuedCount])

  // Backfill defaults on open
  React.useEffect(() => {
    if (!open) return
    const snapshot = createDefaultsSnapshot()
    if (!snapshot) return
    setRows((prev) => {
      let changed = false
      const next = prev.map((row) => {
        if (row.defaults) return row
        changed = true
        return { ...row, defaults: snapshotTypeDefaults(snapshot) }
      })
      return changed ? next : prev
    })
    setQueuedFiles((prev) => {
      if (!prev || prev.length === 0) return prev
      let changed = false
      const next = prev.map((stub) => {
        if (stub.defaults) return stub
        changed = true
        return { ...stub, defaults: snapshotTypeDefaults(snapshot) }
      })
      return changed ? next : prev
    })
  }, [createDefaultsSnapshot, open, setQueuedFiles, setRows])

  // ---- media type detection ----
  const hasAudioItems = React.useMemo(
    () =>
      rows.some(
        (r) =>
          r.type === "audio" ||
          (r.type === "auto" && inferIngestTypeFromUrl(r.url) === "audio")
      ) ||
      queuedFileStubs.some((stub) => fileTypeFromName(stub) === "audio"),
    [fileTypeFromName, queuedFileStubs, rows]
  )

  const hasDocumentItems = React.useMemo(
    () =>
      rows.some(
        (r) =>
          r.type === "document" ||
          r.type === "pdf" ||
          (r.type === "auto" &&
            ["document", "pdf"].includes(inferIngestTypeFromUrl(r.url)))
      ) ||
      queuedFileStubs.some((stub) =>
        ["document", "pdf"].includes(fileTypeFromName(stub))
      ),
    [fileTypeFromName, queuedFileStubs, rows]
  )

  const hasVideoItems = React.useMemo(
    () =>
      rows.some(
        (r) =>
          r.type === "video" ||
          (r.type === "auto" && inferIngestTypeFromUrl(r.url) === "video")
      ) ||
      queuedFileStubs.some((stub) => fileTypeFromName(stub) === "video"),
    [fileTypeFromName, queuedFileStubs, rows]
  )

  // ---- selection helpers ----
  const selectedRow = React.useMemo(
    () => rows.find((r) => r.id === selectedRowId) || null,
    [rows, selectedRowId]
  )

  const selectedFileStub = React.useMemo(
    () => queuedFileStubs.find((f) => f.id === selectedFileId) || null,
    [queuedFileStubs, selectedFileId]
  )

  const selectedFile = React.useMemo(() => {
    if (!selectedFileStub) return null
    return fileForStubId.get(selectedFileStub.id) || null
  }, [fileForStubId, selectedFileStub])

  // Auto-select first row/file when selection becomes stale
  React.useEffect(() => {
    setSelectedFileId((prev) => {
      if (queuedFileStubs.length === 0) return null
      if (prev && queuedFileStubs.some((f) => f.id === prev)) return prev
      return queuedFileStubs[0].id
    })
    if (selectedRowId && rows.some((r) => r.id === selectedRowId)) {
      return
    }
    if (rows.length > 0) {
      setSelectedRowId(rows[0].id)
      setSelectedFileId(null)
      return
    }
  }, [queuedFileStubs, rows, selectedRowId])

  // ---- status helpers ----
  const mergeDefaults = React.useCallback(
    <T extends Record<string, any>>(defaults?: T, overrides?: T): T | undefined => {
      const next: Record<string, any> = {
        ...(defaults || {}),
        ...(overrides || {})
      }
      for (const key of Object.keys(next)) {
        if (next[key] === undefined || next[key] === null || next[key] === '') {
          delete next[key]
        }
      }
      return Object.keys(next).length > 0 ? (next as T) : undefined
    },
    []
  )

  const hasOverrides = React.useCallback(
    <T extends Record<string, any>>(overrides?: T, defaults?: T): boolean => {
      if (!overrides) return false
      for (const [key, value] of Object.entries(overrides)) {
        if (value === undefined || value === null || value === '') continue
        const defaultValue = defaults ? (defaults as Record<string, any>)[key] : undefined
        if (value !== defaultValue) return true
      }
      return false
    },
    []
  )

  const statusForUrlRow = React.useCallback((row: Entry) => {
    const raw = (row.url || '').trim()
    if (raw && !isLikelyUrl(raw)) {
      return {
        label: qi('needsReview', 'Needs review'),
        color: 'orange',
        reason: qi('invalidUrlFormat', 'Invalid URL format')
      }
    }
    const baselineDefaults = row.defaults || normalizedTypeDefaults
    const hasKeywords = Boolean(row.keywords && row.keywords.trim())
    const custom =
      row.type !== 'auto' ||
      hasKeywords ||
      hasOverrides(row.audio, baselineDefaults.audio) ||
      hasOverrides(row.document, baselineDefaults.document) ||
      hasOverrides(row.video, baselineDefaults.video)
    return {
      label: custom ? qi('customLabel', 'Custom') : qi('defaultLabel', 'Default'),
      color: custom ? 'blue' : 'default' as const,
      reason: custom
        ? qi('customReason', 'Custom type or options')
        : undefined
    }
  }, [hasOverrides, qi, normalizedTypeDefaults])

  const statusForFile = React.useCallback((fileLike: { size: number }, attached: boolean) => {
    if (!attached) {
      return {
        label: qi('missingFile', 'Missing file'),
        color: 'orange',
        reason: qi('missingFileReason', 'Reattach this file to process it.')
      }
    }
    if (fileLike.size && fileLike.size > MAX_LOCAL_FILE_BYTES) {
      return {
        label: qi('needsReview', 'Needs review'),
        color: 'orange',
        reason: qi('fileTooLarge', 'File is over 500MB')
      }
    }
    return {
      label: qi('defaultLabel', 'Default'),
      color: 'default' as const
    }
  }, [qi])

  // ---- queue mutations ----
  const addRow = React.useCallback(
    () => setRows((r) => [...r, buildRowEntry()]),
    [buildRowEntry, setRows]
  )

  const removeRow = React.useCallback(
    (id: string) => {
      setRows((r) => r.filter((x) => x.id !== id))
      if (selectedRowId === id) {
        setSelectedRowId(null)
      }
    },
    [selectedRowId, setRows]
  )

  const updateRow = React.useCallback(
    (id: string, patch: Partial<Entry>) => {
      setRows((r) => r.map((x) => (x.id === id ? { ...x, ...patch } : x)))
    },
    [setRows]
  )

  const addUrlsFromInput = React.useCallback(
    async (text: string) => {
      if (ingestBlocked) {
        messageApi.warning(
          qi("queueBlocked", "Connect to your server to add items.")
        )
        return
      }
      const parts = text
        .split(/[\n,]+/)
        .map((s) => s.trim())
        .filter(Boolean)
      if (parts.length === 0) return
      const entries = parts.map((u) =>
        buildRowEntry(u, inferIngestTypeFromUrl(u) as Entry['type'])
      )
      setRows((prev) => [...prev, ...entries])
      setPendingUrlInput('')
      setSelectedRowId(entries[0].id)
      setSelectedFileId(null)
      messageApi.success(
        qi("urlsAdded", "Added {{count}} URL(s) to the queue.", {
          count: entries.length
        })
      )
    },
    [buildRowEntry, ingestBlocked, messageApi, qi, setRows]
  )

  const clearAllQueues = React.useCallback(() => {
    setRows([buildRowEntry()])
    setQueuedFiles([])
    setLocalFiles([])
    setSelectedRowId(null)
    setSelectedFileId(null)
    setPendingReattachId(null)
    setPendingUrlInput('')
  }, [buildRowEntry, setQueuedFiles, setRows])

  const pasteFromClipboard = React.useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText()
      if (!text) {
        messageApi.info('Clipboard is empty.')
        return
      }
      setPendingUrlInput(text)
    } catch {
      messageApi.error('Unable to read from clipboard. Check browser permissions.')
    }
  }, [messageApi])

  const addLocalFiles = React.useCallback(
    (incoming: File[]) => {
      if (incoming.length === 0) return
      if (ingestBlocked) {
        messageApi.warning(
          qi("queueBlocked", "Connect to your server to add items.")
        )
        return
      }
      const defaultsSnapshot = createDefaultsSnapshot()
      const attachedInstanceIds = new Set(
        localFiles.map((file) => getFileInstanceId(file))
      )
      const stubsByKey = new Map<string, QueuedFileStub[]>()
      for (const stub of queuedFiles || []) {
        const list = stubsByKey.get(stub.key) || []
        list.push(stub)
        stubsByKey.set(stub.key, list)
      }
      const claimedStubIds = new Set<string>()
      const seenInstanceIds = new Set<string>()
      const accepted: File[] = []
      const newStubs: QueuedFileStub[] = []
      const updatedStubs: Array<{ id: string; instanceId: string }> = []
      const skipped: string[] = []
      let firstSelectedId: string | null = null

      for (const file of incoming) {
        const name = file?.name || ""
        const instanceId = getFileInstanceId(file)
        if (seenInstanceIds.has(instanceId) || attachedInstanceIds.has(instanceId)) {
          skipped.push(name || "Unnamed file")
          continue
        }
        seenInstanceIds.add(instanceId)
        const key = buildLocalFileKey(file)
        const candidates = stubsByKey.get(key) || []
        const existingStub = candidates.find((stub) => {
          if (claimedStubIds.has(stub.id)) return false
          if (stub.instanceId && attachedInstanceIds.has(stub.instanceId)) return false
          return true
        })
        if (existingStub) {
          claimedStubIds.add(existingStub.id)
          accepted.push(file)
          if (existingStub.instanceId !== instanceId) {
            updatedStubs.push({ id: existingStub.id, instanceId })
          }
          if (!firstSelectedId) firstSelectedId = existingStub.id
          continue
        }
        const stub = buildQueuedFileStub(file, defaultsSnapshot)
        newStubs.push(stub)
        accepted.push(file)
        if (!firstSelectedId) firstSelectedId = stub.id
      }

      if (skipped.length > 0) {
        const uniqueNames = Array.from(new Set(skipped))
        const label = uniqueNames.slice(0, 3).join(", ")
        const suffix = uniqueNames.length > 3 ? "..." : ""
        messageApi.warning(
          qi(
            "duplicateFiles",
            "Skipped {{count}} duplicate file(s): {{names}}",
            {
              count: skipped.length,
              names: `${label}${suffix}`
            }
          )
        )
      }

      if (newStubs.length > 0 || updatedStubs.length > 0) {
        setQueuedFiles((prev) => {
          const base = prev || []
          let changed = false
          const updates = new Map(
            updatedStubs.map((item) => [item.id, item.instanceId])
          )
          const next = base.map((stub) => {
            const nextInstanceId = updates.get(stub.id)
            if (!nextInstanceId || stub.instanceId === nextInstanceId) return stub
            changed = true
            return { ...stub, instanceId: nextInstanceId }
          })
          if (newStubs.length > 0) {
            changed = true
            return [...next, ...newStubs]
          }
          return changed ? next : prev
        })
      }
      if (accepted.length === 0) return
      setLocalFiles((prev) => [...prev, ...accepted])
      if (firstSelectedId) {
        setSelectedFileId(firstSelectedId)
      }
      setSelectedRowId(null)
    },
    [
      createDefaultsSnapshot,
      ingestBlocked,
      localFiles,
      messageApi,
      qi,
      queuedFiles,
      setQueuedFiles
    ]
  )

  const handleReattachChange = React.useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      event.currentTarget.value = ''
      const stubId = pendingReattachId
      setPendingReattachId(null)
      if (!file || !stubId) return
      const stub = queuedFileStubs.find((item) => item.id === stubId)
      if (!stub) return
      const instanceId = getFileInstanceId(file)
      if (buildLocalFileKey(file) !== stub.key) {
        messageApi.error(
          qi(
            "reattachMismatch",
            "That file does not match {{name}}. Choose the original file or remove this item.",
            { name: stub.name || "this file" }
          )
        )
        return
      }
      setLocalFiles((prev) => {
        if (
          stub.instanceId &&
          prev.some((existing) => getFileInstanceId(existing) === stub.instanceId)
        ) {
          return prev
        }
        return [...prev, file]
      })
      if (stub.instanceId !== instanceId) {
        setQueuedFiles((prev) => {
          if (!prev) return prev
          return prev.map((item) =>
            item.id === stub.id ? { ...item, instanceId } : item
          )
        })
      }
      setSelectedFileId(stub.id)
      setSelectedRowId(null)
      messageApi.success(
        qi("reattachSuccess", "Reattached {{name}}.", {
          name: stub.name || "file"
        })
      )
    },
    [
      messageApi,
      pendingReattachId,
      qi,
      queuedFileStubs,
      setQueuedFiles,
    ]
  )

  const requestFileReattach = React.useCallback((stubId: string) => {
    setPendingReattachId(stubId)
    if (reattachInputRef.current) {
      reattachInputRef.current.click()
    }
  }, [])

  const handleReattachSelectedFile = React.useCallback(() => {
    if (!selectedFileStub) return
    requestFileReattach(selectedFileStub.id)
  }, [requestFileReattach, selectedFileStub])

  const handleFileDrop = React.useCallback(
    (ev: React.DragEvent<HTMLDivElement>) => {
      ev.preventDefault()
      ev.stopPropagation()
      const files = Array.from(ev.dataTransfer?.files || [])
      addLocalFiles(files)
    },
    [addLocalFiles]
  )

  return {
    // persisted state
    rows, setRows,
    queuedFiles, setQueuedFiles,
    // local state
    localFiles, setLocalFiles,
    selectedRowId, setSelectedRowId,
    selectedFileId, setSelectedFileId,
    pendingUrlInput, setPendingUrlInput,
    pendingReattachId, setPendingReattachId,
    reattachInputRef,
    // derived
    queuedFileStubs,
    attachedFilesByInstanceId,
    attachedFileStubs,
    missingFileStubs,
    attachedFiles,
    fileForStubId,
    hasMissingFiles,
    plannedCount,
    hasAudioItems,
    hasDocumentItems,
    hasVideoItems,
    selectedRow,
    selectedFileStub,
    selectedFile,
    // helpers
    createDefaultsSnapshot,
    buildRowEntry,
    fileTypeFromName,
    formatBytes,
    mergeDefaults,
    hasOverrides,
    statusForUrlRow,
    statusForFile,
    // mutations
    addRow,
    removeRow,
    updateRow,
    addUrlsFromInput,
    clearAllQueues,
    pasteFromClipboard,
    addLocalFiles,
    handleReattachChange,
    requestFileReattach,
    handleReattachSelectedFile,
    handleFileDrop,
  }
}

// Re-export the empty row creator for use by other modules
function createEmptyRow(): Entry {
  return {
    id: crypto.randomUUID(),
    url: '',
    type: 'auto'
  }
}

export { createEmptyRow, MAX_LOCAL_FILE_BYTES, DEFAULT_TYPE_DEFAULTS, isLikelyUrl, buildLocalFileKey }
