import React from "react"
import { useTranslation } from "react-i18next"
import {
  Modal,
  Tabs,
  Input,
  Button,
  List,
  Spin,
  Empty,
  Tag,
  Switch,
  Alert
} from "antd"
import { Search, UploadCloud, FileText, BookOpen, PlayCircle } from "lucide-react"
import { tldwClient } from "@/services/tldw"
import { useDebounce } from "@/hooks/useDebounce"
import { useServerOnline } from "@/hooks/useServerOnline"
import { inferUploadMediaTypeFromFile } from "@/services/tldw/media-routing"
import { inferDocumentTypeFromMedia } from "./document-utils"
import type { DocumentType } from "./types"
import { useNavigate } from "react-router-dom"
import { setSetting } from "@/services/settings/registry"
import { LAST_MEDIA_ID_SETTING } from "@/services/settings/ui-settings"

export type DocumentPickerTab = "library" | "upload"

interface DocumentPickerModalProps {
  open: boolean
  initialTab?: DocumentPickerTab
  onClose: () => void
  onOpenDocument: (mediaId: number, docTypeHint?: DocumentType | null) => Promise<void>
}

interface MediaListItem {
  id: number
  title?: string
  type?: string
  created_at?: string
  keywords?: string[]
  url?: string
  filename?: string
}

const normalizeMediaItems = (response: any): MediaListItem[] => {
  const items =
    response?.items ||
    response?.media ||
    response?.results ||
    response?.data ||
    []
  if (!Array.isArray(items)) return []
  return items
    .map((item: any) => ({
      id: Number(item.media_id ?? item.id),
      title: item.title || item.name,
      type: item.type || item.media_type,
      created_at: item.created_at,
      keywords: item.keywords,
      url: item.url,
      filename: item.filename || item.original_filename
    }))
    .filter((item: MediaListItem) => Number.isFinite(item.id))
}

const isSupportedDocType = (docType: DocumentType | null): docType is DocumentType =>
  docType === "pdf" || docType === "epub"

const getDocType = (item: MediaListItem): DocumentType | null =>
  inferDocumentTypeFromMedia(item.type, item.filename)

const isDocumentCandidate = (item: MediaListItem): boolean =>
  isSupportedDocType(getDocType(item))

export const DocumentPickerModal: React.FC<DocumentPickerModalProps> = ({
  open,
  initialTab = "library",
  onClose,
  onOpenDocument
}) => {
  const { t } = useTranslation(["option", "common"])
  const navigate = useNavigate()
  const isOnline = useServerOnline()

  const [activeTab, setActiveTab] = React.useState<DocumentPickerTab>(initialTab)
  const [searchQuery, setSearchQuery] = React.useState("")
  const debouncedQuery = useDebounce(searchQuery, 300)
  const [mediaItems, setMediaItems] = React.useState<MediaListItem[]>([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [openingId, setOpeningId] = React.useState<number | null>(null)
  const [showAllMedia, setShowAllMedia] = React.useState(false)
  const [uploading, setUploading] = React.useState(false)
  const [uploadWarning, setUploadWarning] = React.useState<{
    message: string
    mediaId?: number
  } | null>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  React.useEffect(() => {
    if (open) {
      setActiveTab(initialTab)
      setError(null)
      setUploadWarning(null)
    }
  }, [open, initialTab])

  const loadMedia = React.useCallback(
    async (query?: string) => {
      if (!isOnline) return
      setLoading(true)
      setError(null)
      try {
        let response
        const trimmed = query?.trim()
        if (trimmed) {
            response = await tldwClient.searchMedia(
              {
                query: trimmed,
                ...(showAllMedia ? {} : { media_types: ["pdf", "ebook"] })
              },
              { page: 1, results_per_page: 50 }
            )
        } else {
          response = await tldwClient.listMedia({
            page: 1,
            results_per_page: 50,
            include_keywords: true
          })
        }
        const items = normalizeMediaItems(response)
        const filtered = showAllMedia ? items : items.filter(isDocumentCandidate)
        setMediaItems(filtered)
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : t("option:documentWorkspace.loadMediaError", "Failed to load media library")
        )
      } finally {
        setLoading(false)
      }
    },
    [isOnline, showAllMedia, t]
  )

  React.useEffect(() => {
    if (!open || activeTab !== "library") return
    void loadMedia(debouncedQuery)
  }, [open, activeTab, debouncedQuery, loadMedia])

  const handleOpen = async (item: MediaListItem) => {
    if (!item?.id) return
    const docType = getDocType(item)
    if (!isSupportedDocType(docType)) {
      // Route to Media review for unsupported types
      await setSetting(LAST_MEDIA_ID_SETTING, String(item.id))
      navigate("/media-multi")
      onClose()
      return
    }

    setOpeningId(item.id)
    try {
      await onOpenDocument(item.id, docType)
      onClose()
    } finally {
      setOpeningId(null)
    }
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleFileSelected = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0]
    if (!file) return

    setUploading(true)
    setError(null)
    setUploadWarning(null)

    try {
      const mediaType = inferUploadMediaTypeFromFile(file.name, file.type)
      const response = await tldwClient.uploadMedia(file, {
        media_type: mediaType,
        keep_original_file: true
      })

      const mediaId = extractMediaId(response)
      if (!mediaId) {
        throw new Error(
          t("option:documentWorkspace.uploadMissingMediaId", "Upload succeeded but no media ID was returned")
        )
      }

      const result = extractUploadResult(response)
      const warnings = extractWarnings(result)
      const hasStorageWarning =
        warnings.some((warning) => warning.includes("original file")) ||
        result?.original_file_stored === false
      if (hasStorageWarning) {
        setUploadWarning({
          message: t(
            "option:documentWorkspace.uploadStorageWarning",
            "Upload finished, but the original file could not be stored. Open in Media to view extracted text, or re-upload after fixing storage."
          ),
          mediaId: Number(mediaId)
        })
        return
      }

      const docType = inferDocumentTypeFromMedia(mediaType, file.name)
      await onOpenDocument(Number(mediaId), docType)
      onClose()
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : t("option:documentWorkspace.uploadFailed", "Upload failed")
      )
    } finally {
      setUploading(false)
      if (event.target) {
        event.target.value = ""
      }
    }
  }

  const libraryPane = () => (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Input
          prefix={<Search className="h-4 w-4 text-text-muted" />}
          placeholder={t(
            "option:documentWorkspace.searchLibrary",
            "Search your media library..."
          )}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          allowClear
        />
        <Button onClick={() => loadMedia(searchQuery)} loading={loading}>
          {t("common:search", "Search")}
        </Button>
      </div>

      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>
          {t(
            "option:documentWorkspace.showAllMedia",
            "Show non-document media"
          )}
        </span>
        <Switch
          checked={showAllMedia}
          onChange={(checked) => setShowAllMedia(checked)}
          size="small"
        />
      </div>

      {loading ? (
        <div className="flex justify-center py-8">
          <Spin />
        </div>
      ) : mediaItems.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={t(
            "option:documentWorkspace.noMediaFound",
            "No matching media found"
          )}
        />
      ) : (
        <div className="max-h-96 overflow-y-auto rounded border border-border">
          <List
            size="small"
            dataSource={mediaItems}
            renderItem={(item) => {
              const docType = getDocType(item)
              const supported = isSupportedDocType(docType)
              const icon = supported
                ? docType === "epub"
                  ? <BookOpen className="h-4 w-4 text-primary" />
                  : <FileText className="h-4 w-4 text-primary" />
                : <PlayCircle className="h-4 w-4 text-text-muted" />

              return (
                <List.Item
                  className="flex items-center justify-between gap-3"
                  actions={[
                    <Button
                      key="open"
                      type={supported ? "primary" : "default"}
                      size="small"
                      onClick={() => handleOpen(item)}
                      loading={openingId === item.id}
                    >
                      {supported
                        ? t("option:documentWorkspace.open", "Open")
                        : t("option:documentWorkspace.openInMedia", "Open in Media")}
                    </Button>
                  ]}
                >
                  <div className="flex min-w-0 flex-1 items-start gap-2">
                    <div className="mt-0.5 shrink-0">{icon}</div>
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-text">
                        {item.title || `Media #${item.id}`}
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
                        <span className="capitalize">{item.type || "document"}</span>
                        {item.keywords && item.keywords.length > 0 && (
                          <Tag>{item.keywords.slice(0, 3).join(", ")}</Tag>
                        )}
                      </div>
                    </div>
                  </div>
                </List.Item>
              )
            }}
          />
        </div>
      )}
    </div>
  )

  const uploadPane = () => (
    <div className="space-y-4">
      <div className="rounded-lg border border-dashed border-border bg-surface2 p-6 text-center">
        <UploadCloud className="mx-auto mb-3 h-8 w-8 text-primary" />
        <p className="text-sm text-text">
          {t(
            "option:documentWorkspace.uploadHint",
            "Upload a PDF or EPUB file to start reading"
          )}
        </p>
        <p className="text-xs text-text-muted">
          {t(
            "option:documentWorkspace.uploadNote",
            "Files are ingested into your media library and kept for document review."
          )}
        </p>
        <div className="mt-4">
          <Button type="primary" onClick={handleUploadClick} loading={uploading}>
            {t("option:documentWorkspace.chooseFile", "Choose file")}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.epub"
            className="hidden"
            onChange={handleFileSelected}
          />
        </div>
      </div>
    </div>
  )

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      title={t("option:documentWorkspace.openDocument", "Open document")}
      width={720}
      destroyOnClose
    >
      {!isOnline && (
        <Alert
          type="warning"
          showIcon
          message={t(
            "option:documentWorkspace.serverRequired",
            "Connect to server to use document workspace"
          )}
          className="mb-3"
        />
      )}
      {uploadWarning && (
        <Alert
          type="warning"
          showIcon
          message={uploadWarning.message}
          className="mb-3"
          action={
            uploadWarning.mediaId ? (
              <Button
                size="small"
                onClick={async () => {
                  await setSetting(LAST_MEDIA_ID_SETTING, String(uploadWarning.mediaId))
                  navigate("/media-multi")
                  onClose()
                }}
              >
                {t("option:documentWorkspace.openInMedia", "Open in Media")}
              </Button>
            ) : undefined
          }
        />
      )}
      {error && (
        <Alert
          type="error"
          showIcon
          message={error}
          className="mb-3"
        />
      )}
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as DocumentPickerTab)}
        items={[
          {
            key: "library",
            label: t("option:documentWorkspace.fromLibrary", "From library"),
            children: libraryPane()
          },
          {
            key: "upload",
            label: t("option:documentWorkspace.upload", "Upload"),
            children: uploadPane()
          }
        ]}
      />
    </Modal>
  )
}

function extractMediaId(data: any, visited: WeakSet<object> = new WeakSet()): string | number | null {
  if (!data || typeof data !== "object") return null
  if (Array.isArray(data)) {
    return data.length > 0 ? extractMediaId(data[0], visited) : null
  }
  if (visited.has(data as object)) return null
  visited.add(data as object)

  if ("results" in data && Array.isArray((data as any).results) && (data as any).results.length > 0) {
    return extractMediaId((data as any).results[0], visited)
  }
  if ("result" in data && (data as any).result) {
    return extractMediaId((data as any).result, visited)
  }
  if ("media" in data && (data as any).media) {
    return extractMediaId((data as any).media, visited)
  }

  const direct =
    (data as any).id ??
    (data as any).media_id ??
    (data as any).db_id ??
    (data as any).pk ??
    (data as any).uuid
  if (direct !== undefined && direct !== null) return direct

  return null
}

function extractUploadResult(data: any): any {
  if (!data || typeof data !== "object") return null
  if (Array.isArray(data?.results) && data.results.length > 0) {
    return data.results[0]
  }
  if (data?.result) return data.result
  if (data?.media) return data.media
  return data
}

function extractWarnings(result: any): string[] {
  if (!result) return []
  const warnings = result?.warnings
  if (!Array.isArray(warnings)) return []
  return warnings.map((warning) => String(warning || "").toLowerCase())
}

export default DocumentPickerModal
