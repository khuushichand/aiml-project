import React, { useCallback, useMemo, useState } from "react"
import { Button, Input, Tag, Typography } from "antd"
import { useTranslation } from "react-i18next"
import {
  FileText,
  Film,
  Globe,
  Music,
  Image as ImageIcon,
  BookOpen,
  File as FileIcon,
  X,
  Plus,
} from "lucide-react"
import type { DetectedMediaType, WizardQueueItem, QueueItemValidation } from "./types"
import { useIngestWizard } from "./IngestWizardContext"
import { FileDropZone } from "./QueueTab/FileDropZone"
import {
  QUICK_INGEST_ACCEPT_STRING,
  QUICK_INGEST_MAX_FILE_SIZE,
} from "./constants"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MEDIA_TYPE_ICONS: Record<DetectedMediaType, React.ReactNode> = {
  audio: <Music className="h-4 w-4 text-purple-500" aria-hidden="true" />,
  video: <Film className="h-4 w-4 text-blue-500" aria-hidden="true" />,
  document: <FileText className="h-4 w-4 text-green-500" aria-hidden="true" />,
  pdf: <FileText className="h-4 w-4 text-red-500" aria-hidden="true" />,
  ebook: <BookOpen className="h-4 w-4 text-amber-500" aria-hidden="true" />,
  image: <ImageIcon className="h-4 w-4 text-pink-500" aria-hidden="true" />,
  web: <Globe className="h-4 w-4 text-cyan-500" aria-hidden="true" />,
  unknown: <FileIcon className="h-4 w-4 text-text-muted" aria-hidden="true" />,
}

const ICON_NAME_MAP: Record<DetectedMediaType, string> = {
  audio: "Music",
  video: "Film",
  document: "FileText",
  pdf: "FileText",
  ebook: "BookOpen",
  image: "Image",
  web: "Globe",
  unknown: "File",
}

const detectTypeFromExtension = (name: string): DetectedMediaType => {
  const ext = name.split(".").pop()?.toLowerCase() || ""
  if (["mp3", "wav", "ogg", "flac", "m4a", "aac", "wma", "opus"].includes(ext)) return "audio"
  if (["mp4", "mkv", "avi", "mov", "webm", "wmv", "flv", "m4v"].includes(ext)) return "video"
  if (["pdf"].includes(ext)) return "pdf"
  if (["epub", "mobi", "azw3"].includes(ext)) return "ebook"
  if (["jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "tiff"].includes(ext)) return "image"
  if (["doc", "docx", "txt", "rtf", "md", "markdown", "html", "htm", "xml", "json", "csv", "tsv"].includes(ext)) return "document"
  return "unknown"
}

const detectTypeFromUrl = (url: string): DetectedMediaType => {
  try {
    const parsed = new URL(url)
    const pathname = parsed.pathname.toLowerCase()
    // Check common file extensions in URL path
    const ext = pathname.split(".").pop() || ""
    if (["mp3", "wav", "ogg", "flac", "m4a"].includes(ext)) return "audio"
    if (["mp4", "mkv", "avi", "mov", "webm"].includes(ext)) return "video"
    if (ext === "pdf") return "pdf"
    if (["epub", "mobi"].includes(ext)) return "ebook"
    // YouTube and common video platforms
    if (parsed.hostname.includes("youtube.com") || parsed.hostname.includes("youtu.be")) return "video"
    if (parsed.hostname.includes("vimeo.com")) return "video"
    if (parsed.hostname.includes("soundcloud.com")) return "audio"
    if (parsed.hostname.includes("spotify.com")) return "audio"
    // Default for URLs is web
    return "web"
  } catch {
    return "web"
  }
}

const isValidUrl = (raw: string): boolean => {
  const trimmed = raw.trim()
  if (!trimmed) return false
  try {
    const parsed = new URL(trimmed)
    return parsed.protocol === "http:" || parsed.protocol === "https:"
  } catch {
    return false
  }
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return "0 B"
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

const validateQueueItem = (
  item: WizardQueueItem,
  existingItems: WizardQueueItem[]
): QueueItemValidation => {
  const errors: string[] = []
  const warnings: string[] = []

  if (item.url) {
    if (!isValidUrl(item.url)) {
      errors.push("Invalid URL format")
    }
    // Check for duplicates
    const isDuplicate = existingItems.some(
      (other) => other.id !== item.id && other.url && other.url === item.url
    )
    if (isDuplicate) {
      warnings.push("Duplicate URL")
    }
  }

  if (item.file) {
    if (item.fileSize > QUICK_INGEST_MAX_FILE_SIZE) {
      errors.push("File exceeds 500 MB limit")
    }
    // Check for duplicate files
    const isDuplicate = existingItems.some(
      (other) =>
        other.id !== item.id &&
        other.fileName === item.fileName &&
        other.fileSize === item.fileSize
    )
    if (isDuplicate) {
      warnings.push("Duplicate file")
    }
  }

  if (item.detectedType === "unknown") {
    warnings.push("Unrecognized file type")
  }

  return {
    valid: errors.length === 0,
    errors: errors.length > 0 ? errors : undefined,
    warnings: warnings.length > 0 ? warnings : undefined,
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

type AddContentStepProps = {
  isOnlineForIngest?: boolean
  onQuickProcess?: () => void
}

export const AddContentStep: React.FC<AddContentStepProps> = ({
  isOnlineForIngest = true,
  onQuickProcess,
}) => {
  const { t } = useTranslation(["option"])
  const { state, setQueueItems, goNext } = useIngestWizard()
  const { queueItems } = state

  const [urlInput, setUrlInput] = useState("")

  const qi = useCallback(
    (key: string, defaultValue: string, options?: Record<string, unknown>) =>
      options
        ? t(`quickIngest.${key}`, { defaultValue, ...options })
        : t(`quickIngest.${key}`, defaultValue),
    [t]
  )

  // Add files from the drop zone
  const handleFilesAdded = useCallback(
    (files: File[]) => {
      const newItems: WizardQueueItem[] = files.map((file) => {
        const detectedType = detectTypeFromExtension(file.name)
        const item: WizardQueueItem = {
          id: crypto.randomUUID(),
          fileName: file.name,
          file,
          detectedType,
          icon: ICON_NAME_MAP[detectedType],
          fileSize: file.size,
          mimeType: file.type || undefined,
          validation: { valid: true },
        }
        item.validation = validateQueueItem(item, [...queueItems, ...newItems])
        return item
      })
      setQueueItems([...queueItems, ...newItems])
    },
    [queueItems, setQueueItems]
  )

  // Add URLs from the multi-line input
  const handleAddUrls = useCallback(() => {
    const lines = urlInput
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)

    if (lines.length === 0) return

    const newItems: WizardQueueItem[] = lines.map((url) => {
      const detectedType = detectTypeFromUrl(url)
      const item: WizardQueueItem = {
        id: crypto.randomUUID(),
        url,
        detectedType,
        icon: ICON_NAME_MAP[detectedType],
        fileSize: 0,
        validation: { valid: true },
      }
      item.validation = validateQueueItem(item, [...queueItems, ...newItems])
      return item
    })

    setQueueItems([...queueItems, ...newItems])
    setUrlInput("")
  }, [urlInput, queueItems, setQueueItems])

  // Handle Enter key in URL input
  const handleUrlKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault()
        handleAddUrls()
      }
    },
    [handleAddUrls]
  )

  // Remove an item from the queue
  const handleRemoveItem = useCallback(
    (id: string) => {
      setQueueItems(queueItems.filter((item) => item.id !== id))
    },
    [queueItems, setQueueItems]
  )

  // Clear all items
  const handleClearAll = useCallback(() => {
    setQueueItems([])
  }, [setQueueItems])

  const hasItems = queueItems.length > 0
  const validItemCount = useMemo(
    () => queueItems.filter((item) => item.validation.valid).length,
    [queueItems]
  )
  const canProceed = validItemCount > 0

  return (
    <div className="py-3">
      {/* Drop zone + URL input area */}
      <div className="space-y-3">
        <FileDropZone
          onFilesAdded={handleFilesAdded}
          isOnlineForIngest={isOnlineForIngest}
        />

        {/* Multi-line URL paste area */}
        <div>
          <Typography.Text className="text-xs text-text-muted">
            {qi("pasteUrlsTitle", "Paste URLs (one per line):")}
          </Typography.Text>
          <div className="mt-1 flex gap-2">
            <Input.TextArea
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onKeyDown={handleUrlKeyDown}
              placeholder={qi(
                "urlsPlaceholder",
                "https://example.com/article\nhttps://youtube.com/watch?v=..."
              )}
              autoSize={{ minRows: 2, maxRows: 4 }}
              aria-label={qi("urlsInputAria", "URL input area")}
              className="flex-1"
            />
            <Button
              type="primary"
              onClick={handleAddUrls}
              disabled={!urlInput.trim()}
              aria-label={qi("addUrlsAria", "Add URLs to queue")}
              className="self-end"
            >
              <Plus className="mr-1 h-4 w-4" />
              {qi("addUrls", "Add")}
            </Button>
          </div>
        </div>
      </div>

      {/* Queued items list */}
      {hasItems && (
        <div className="mt-4">
          <div className="flex items-center justify-between">
            <Typography.Text className="text-sm font-medium">
              {qi("queueTitle", "QUEUED")}
              <span className="ml-1.5 text-text-muted font-normal">
                ({queueItems.length}{" "}
                {queueItems.length === 1
                  ? qi("wizard.item", "item")
                  : qi("wizard.items", "items")}
                )
              </span>
            </Typography.Text>
            <Button
              size="small"
              type="text"
              danger
              onClick={handleClearAll}
              aria-label={qi("clearAllAria", "Remove all items from queue")}
            >
              {qi("clearAll", "Clear all")}
            </Button>
          </div>

          <div className="mt-2 space-y-1.5">
            {queueItems.map((item) => (
              <div
                key={item.id}
                className={`flex items-center gap-3 rounded-md border px-3 py-2 ${
                  !item.validation.valid
                    ? "border-danger/30 bg-danger/5"
                    : item.validation.warnings?.length
                      ? "border-warn/30 bg-warn/5"
                      : "border-border"
                }`}
              >
                {/* Type icon */}
                <span className="flex-shrink-0">
                  {MEDIA_TYPE_ICONS[item.detectedType]}
                </span>

                {/* Name/URL and metadata */}
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">
                    {item.fileName || item.url || qi("untitledItem", "Untitled")}
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-text-muted">
                    {item.fileSize > 0 && (
                      <span>{formatFileSize(item.fileSize)}</span>
                    )}
                    <Tag
                      color="geekblue"
                      className="!text-[10px] !leading-tight !px-1 !py-0 !m-0"
                    >
                      {item.detectedType === "web"
                        ? "Web page"
                        : item.detectedType.charAt(0).toUpperCase() +
                          item.detectedType.slice(1)}
                    </Tag>
                    {item.detectedType !== "unknown" && (
                      <span className="text-text-subtle">(auto)</span>
                    )}
                  </div>
                  {/* Validation errors/warnings */}
                  {item.validation.errors?.map((err, i) => (
                    <div key={`e-${i}`} className="text-[11px] text-danger mt-0.5">
                      {err}
                    </div>
                  ))}
                  {item.validation.warnings?.map((warn, i) => (
                    <div key={`w-${i}`} className="text-[11px] text-warn mt-0.5">
                      {warn}
                    </div>
                  ))}
                </div>

                {/* Remove button */}
                <button
                  type="button"
                  onClick={() => handleRemoveItem(item.id)}
                  className="flex-shrink-0 rounded p-1 text-text-muted hover:bg-surface2 hover:text-danger transition-colors"
                  aria-label={qi("removeItemAria", "Remove this item from queue")}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="mt-4 flex items-center justify-end gap-2">
        {hasItems && queueItems.length <= 1 && onQuickProcess && (
          <Button
            onClick={onQuickProcess}
            disabled={!canProceed}
          >
            {qi("wizard.useDefaultsProcess", "Use defaults & process")}
          </Button>
        )}
        <Button
          type="primary"
          onClick={goNext}
          disabled={!canProceed}
          aria-label={qi("wizard.configureItems", "Configure {{count}} items", {
            count: validItemCount,
          })}
        >
          {qi("wizard.configureItems", "Configure {{count}} items >", {
            count: validItemCount,
          })}
        </Button>
      </div>
    </div>
  )
}

export default AddContentStep
