import React from "react"
import { useTranslation } from "react-i18next"
import {
  Modal,
  Tabs,
  Upload,
  Input,
  Button,
  Alert,
  Spin,
  List,
  Checkbox,
  Empty
} from "antd"
import type { UploadFile, UploadProps } from "antd"
import {
  Upload as UploadIcon,
  Link,
  FileText,
  Search,
  Database,
  X
} from "lucide-react"
import { useWorkspaceStore } from "@/store/workspace"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import type { AddSourceTab, WorkspaceSourceType } from "@/types/workspace"

const { TextArea } = Input
const { Dragger } = Upload

const toMediaId = (value: unknown): number | null => {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return null
  if (parsed <= 0) return null
  return Math.trunc(parsed)
}

const extractMediaFromAddResponse = (
  response: unknown
): { mediaId: number | null; title?: string } => {
  if (!response || typeof response !== "object") {
    return { mediaId: null }
  }
  const root = response as Record<string, unknown>
  const rootTitle =
    typeof root.title === "string" && root.title.trim()
      ? root.title
      : undefined
  const candidates: Array<Record<string, unknown>> = []
  if (Array.isArray(root.results)) {
    for (const item of root.results) {
      if (item && typeof item === "object") {
        candidates.push(item as Record<string, unknown>)
      }
    }
  }
  if (root.result && typeof root.result === "object") {
    candidates.push(root.result as Record<string, unknown>)
  }
  candidates.push(root)

  for (const candidate of candidates) {
    const mediaId = toMediaId(
      candidate.media_id ?? candidate.db_id ?? candidate.id
    )
    if (mediaId == null) {
      continue
    }
    const title =
      typeof candidate.title === "string" && candidate.title.trim()
        ? candidate.title
        : rootTitle
    return { mediaId, title }
  }
  return { mediaId: null, title: rootTitle }
}

/**
 * UploadTab - Upload files via drag-and-drop
 */
const UploadTab: React.FC<{
  onAddSources: (sources: Array<{ mediaId: number; title: string; type: WorkspaceSourceType }>) => void
  setProcessing: (p: boolean) => void
  setError: (e: string | null) => void
}> = ({ onAddSources, setProcessing, setError }) => {
  const { t } = useTranslation(["playground", "common"])

  const handleUpload = async (file: File) => {
    setProcessing(true)
    setError(null)

    try {
      const response = await tldwClient.uploadMedia(file, {
        overwrite: "false",
        perform_chunking: "true"
      })
      const added = extractMediaFromAddResponse(response)

      if (added.mediaId != null) {
        const type = getSourceTypeFromFile(file)
        onAddSources([
          {
            mediaId: added.mediaId,
            title: added.title || file.name,
            type
          }
        ])
      } else {
        setError(t("playground:sources.uploadError", "Failed to upload file"))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setProcessing(false)
    }
  }

  const uploadProps: UploadProps = {
    name: "file",
    multiple: true,
    showUploadList: true,
    beforeUpload: (file) => {
      handleUpload(file)
      return false // Prevent default upload behavior
    },
    accept:
      ".pdf,.doc,.docx,.txt,.md,.epub,.html,.htm,.mp3,.wav,.mp4,.webm,.mkv,.avi"
  }

  return (
    <div className="space-y-4">
      <Dragger {...uploadProps} className="bg-surface">
        <p className="ant-upload-drag-icon">
          <UploadIcon className="mx-auto h-12 w-12 text-primary" />
        </p>
        <p className="ant-upload-text">
          {t(
            "playground:sources.uploadDragText",
            "Click or drag files to upload"
          )}
        </p>
        <p className="ant-upload-hint text-text-muted">
          {t(
            "playground:sources.uploadHint",
            "Supports PDF, documents, audio, and video files"
          )}
        </p>
      </Dragger>
    </div>
  )
}

/**
 * UrlTab - Add content from URL
 */
const UrlTab: React.FC<{
  onAddSources: (sources: Array<{ mediaId: number; title: string; type: WorkspaceSourceType }>) => void
  setProcessing: (p: boolean) => void
  setError: (e: string | null) => void
}> = ({ onAddSources, setProcessing, setError }) => {
  const { t } = useTranslation(["playground", "common"])
  const [url, setUrl] = React.useState("")

  const handleAddUrl = async () => {
    if (!url.trim()) return

    setProcessing(true)
    setError(null)

    try {
      // Use the media/add endpoint with URL
      const response = await tldwClient.addMedia(url.trim())
      const added = extractMediaFromAddResponse(response)

      if (added.mediaId != null) {
        const type = getSourceTypeFromUrl(url)
        onAddSources([
          {
            mediaId: added.mediaId,
            title: added.title || url,
            type
          }
        ])
        setUrl("")
      } else {
        setError(t("playground:sources.urlError", "Failed to add URL"))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add URL")
    } finally {
      setProcessing(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-text">
          {t("playground:sources.urlLabel", "Enter URL")}
        </label>
        <Input
          prefix={<Link className="h-4 w-4 text-text-muted" />}
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onPressEnter={handleAddUrl}
          placeholder={t(
            "playground:sources.urlPlaceholder",
            "https://example.com/article or YouTube URL"
          )}
          size="large"
        />
      </div>
      <p className="text-xs text-text-muted">
        {t(
          "playground:sources.urlSupportHint",
          "Supports websites, YouTube videos, and direct file links"
        )}
      </p>
      <Button
        type="primary"
        onClick={handleAddUrl}
        disabled={!url.trim()}
        className="w-full"
      >
        {t("playground:sources.addUrl", "Add URL")}
      </Button>
    </div>
  )
}

/**
 * PasteTab - Paste text content
 */
const PasteTab: React.FC<{
  onAddSources: (sources: Array<{ mediaId: number; title: string; type: WorkspaceSourceType }>) => void
  setProcessing: (p: boolean) => void
  setError: (e: string | null) => void
}> = ({ onAddSources, setProcessing, setError }) => {
  const { t } = useTranslation(["playground", "common"])
  const [title, setTitle] = React.useState("")
  const [content, setContent] = React.useState("")

  const handleAddText = async () => {
    if (!content.trim()) return

    setProcessing(true)
    setError(null)

    try {
      // Create a text file and upload it
      const blob = new Blob([content], { type: "text/plain" })
      const file = new File([blob], `${title || "Pasted Text"}.txt`, {
        type: "text/plain"
      })

      const response = await tldwClient.uploadMedia(file, {
        title: title || "Pasted Text",
        overwrite: "false",
        perform_chunking: "true"
      })
      const added = extractMediaFromAddResponse(response)

      if (added.mediaId != null) {
        onAddSources([
          {
            mediaId: added.mediaId,
            title: added.title || title || "Pasted Text",
            type: "text"
          }
        ])
        setTitle("")
        setContent("")
      } else {
        setError(t("playground:sources.pasteError", "Failed to add text"))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add text")
    } finally {
      setProcessing(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-text">
          {t("playground:sources.titleLabel", "Title (optional)")}
        </label>
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t("playground:sources.titlePlaceholder", "Give your content a title")}
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-text">
          {t("playground:sources.contentLabel", "Content")}
        </label>
        <TextArea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={t(
            "playground:sources.pastePlaceholder",
            "Paste your text content here..."
          )}
          rows={8}
        />
      </div>
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>
          {t("playground:sources.charCount", "{{count}} characters", {
            count: content.length
          })}
        </span>
      </div>
      <Button
        type="primary"
        onClick={handleAddText}
        disabled={!content.trim()}
        className="w-full"
      >
        {t("playground:sources.addText", "Add Text")}
      </Button>
    </div>
  )
}

/**
 * SearchTab - Web search and add results
 */
const SearchTab: React.FC<{
  onAddSources: (sources: Array<{ mediaId: number; title: string; type: WorkspaceSourceType }>) => void
  setProcessing: (p: boolean) => void
  setError: (e: string | null) => void
}> = ({ onAddSources, setProcessing, setError }) => {
  const { t } = useTranslation(["playground", "common"])
  const [query, setQuery] = React.useState("")
  const [results, setResults] = React.useState<any[]>([])
  const [selectedResults, setSelectedResults] = React.useState<Set<number>>(
    new Set()
  )
  const [isSearching, setIsSearching] = React.useState(false)

  const handleSearch = async () => {
    if (!query.trim()) return

    setIsSearching(true)
    setError(null)
    setResults([])
    setSelectedResults(new Set())

    try {
      const response = await tldwClient.webSearch({
        query: query.trim(),
        engine: "searxng",
        max_results: 10
      })

      if (response?.results) {
        setResults(response.results)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed")
    } finally {
      setIsSearching(false)
    }
  }

  const handleAddSelected = async () => {
    if (selectedResults.size === 0) return

    setProcessing(true)
    const selectedUrls = results.filter((_, idx) => selectedResults.has(idx))
    const addedSources: Array<{ mediaId: number; title: string; type: WorkspaceSourceType }> = []

    for (const result of selectedUrls) {
      try {
        const response = await tldwClient.addMedia(result.url || result.link)
        const added = extractMediaFromAddResponse(response)
        if (added.mediaId != null) {
          addedSources.push({
            mediaId: added.mediaId,
            title: added.title || result.title || result.url,
            type: "website"
          })
        }
      } catch {
        // Continue with other URLs
      }
    }

    if (addedSources.length > 0) {
      onAddSources(addedSources)
    }
    setProcessing(false)
  }

  const toggleResult = (idx: number) => {
    const newSelected = new Set(selectedResults)
    if (newSelected.has(idx)) {
      newSelected.delete(idx)
    } else {
      newSelected.add(idx)
    }
    setSelectedResults(newSelected)
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          prefix={<Search className="h-4 w-4 text-text-muted" />}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onPressEnter={handleSearch}
          placeholder={t("playground:sources.searchPlaceholder", "Search the web...")}
          size="large"
          className="flex-1"
        />
        <Button
          type="primary"
          onClick={handleSearch}
          loading={isSearching}
          disabled={!query.trim()}
        >
          {t("common:search", "Search")}
        </Button>
      </div>

      {results.length > 0 && (
        <>
          <div className="max-h-64 overflow-y-auto rounded border border-border">
            <List
              size="small"
              dataSource={results}
              renderItem={(item, idx) => (
                <List.Item
                  className={`cursor-pointer transition hover:bg-surface2 ${
                    selectedResults.has(idx) ? "bg-primary/10" : ""
                  }`}
                  onClick={() => toggleResult(idx)}
                >
                  <div className="flex items-start gap-2">
                    <Checkbox
                      checked={selectedResults.has(idx)}
                      onChange={() => toggleResult(idx)}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-text">
                        {item.title}
                      </p>
                      <p className="truncate text-xs text-text-muted">
                        {item.url || item.link}
                      </p>
                    </div>
                  </div>
                </List.Item>
              )}
            />
          </div>
          <Button
            type="primary"
            onClick={handleAddSelected}
            disabled={selectedResults.size === 0}
            className="w-full"
          >
            {t("playground:sources.addSelected", "Add {{count}} selected", {
              count: selectedResults.size
            })}
          </Button>
        </>
      )}

      {isSearching && (
        <div className="flex justify-center py-8">
          <Spin />
        </div>
      )}
    </div>
  )
}

/**
 * ExistingTab - Pick from already-ingested media
 */
const ExistingTab: React.FC<{
  onAddSources: (sources: Array<{ mediaId: number; title: string; type: WorkspaceSourceType }>) => void
  setProcessing: (p: boolean) => void
  setError: (e: string | null) => void
}> = ({ onAddSources, setProcessing, setError }) => {
  const { t } = useTranslation(["playground", "common"])
  const [searchQuery, setSearchQuery] = React.useState("")
  const [media, setMedia] = React.useState<any[]>([])
  const [isLoading, setIsLoading] = React.useState(false)
  const [selectedMedia, setSelectedMedia] = React.useState<Set<number>>(
    new Set()
  )

  // Already added source media IDs
  const sources = useWorkspaceStore((s) => s.sources)
  const existingMediaIds = React.useMemo(
    () => new Set(sources.map((s) => s.mediaId)),
    [sources]
  )

  const loadMedia = React.useCallback(async (query?: string) => {
    setIsLoading(true)
    setError(null)

    try {
      let response
      if (query?.trim()) {
        response = await tldwClient.searchMedia(
          { query: query.trim() },
          { page: 1, results_per_page: 50 }
        )
      } else {
        response = await tldwClient.listMedia({
          page: 1,
          results_per_page: 50,
          include_keywords: true
        })
      }

      if (response?.media || response?.results) {
        setMedia(response.media || response.results || [])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load media")
    } finally {
      setIsLoading(false)
    }
  }, [setError])

  React.useEffect(() => {
    loadMedia()
  }, [loadMedia])

  const handleSearch = () => {
    loadMedia(searchQuery)
  }

  const handleAddSelected = () => {
    const selectedItems = media.filter(
      (m) => selectedMedia.has(m.media_id || m.id) && !existingMediaIds.has(m.media_id || m.id)
    )

    const newSources = selectedItems.map((m) => ({
      mediaId: m.media_id || m.id,
      title: m.title || m.name || "Untitled",
      type: getSourceTypeFromMediaType(m.type || m.media_type) as WorkspaceSourceType
    }))

    if (newSources.length > 0) {
      onAddSources(newSources)
    }
  }

  const toggleMedia = (id: number) => {
    const newSelected = new Set(selectedMedia)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedMedia(newSelected)
  }

  const availableMedia = media.filter(
    (m) => !existingMediaIds.has(m.media_id || m.id)
  )

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          prefix={<Search className="h-4 w-4 text-text-muted" />}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onPressEnter={handleSearch}
          placeholder={t("playground:sources.searchExisting", "Search your media library...")}
          className="flex-1"
        />
        <Button onClick={handleSearch} loading={isLoading}>
          {t("common:search", "Search")}
        </Button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-8">
          <Spin />
        </div>
      ) : availableMedia.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={t(
            "playground:sources.noMediaFound",
            "No available media found"
          )}
        />
      ) : (
        <>
          <div className="max-h-64 overflow-y-auto rounded border border-border">
            <List
              size="small"
              dataSource={availableMedia}
              renderItem={(item) => {
                const id = item.media_id || item.id
                return (
                  <List.Item
                    className={`cursor-pointer transition hover:bg-surface2 ${
                      selectedMedia.has(id) ? "bg-primary/10" : ""
                    }`}
                    onClick={() => toggleMedia(id)}
                  >
                    <div className="flex items-start gap-2">
                      <Checkbox
                        checked={selectedMedia.has(id)}
                        onChange={() => toggleMedia(id)}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-text">
                          {item.title || item.name || "Untitled"}
                        </p>
                        <p className="text-xs text-text-muted capitalize">
                          {item.type || item.media_type || "document"}
                        </p>
                      </div>
                    </div>
                  </List.Item>
                )
              }}
            />
          </div>
          <Button
            type="primary"
            onClick={handleAddSelected}
            disabled={selectedMedia.size === 0}
            className="w-full"
          >
            {t("playground:sources.addSelected", "Add {{count}} selected", {
              count: selectedMedia.size
            })}
          </Button>
        </>
      )}
    </div>
  )
}

// Helper functions
function getSourceTypeFromFile(file: File): WorkspaceSourceType {
  const ext = file.name.split(".").pop()?.toLowerCase() || ""
  const mimeType = file.type.toLowerCase()

  if (ext === "pdf" || mimeType === "application/pdf") return "pdf"
  if (["mp4", "webm", "mkv", "avi", "mov"].includes(ext) || mimeType.startsWith("video/"))
    return "video"
  if (["mp3", "wav", "m4a", "ogg", "flac"].includes(ext) || mimeType.startsWith("audio/"))
    return "audio"
  if (["doc", "docx", "odt", "rtf"].includes(ext)) return "document"
  if (["txt", "md", "markdown"].includes(ext)) return "text"
  if (["html", "htm"].includes(ext)) return "website"

  return "document"
}

function getSourceTypeFromUrl(url: string): WorkspaceSourceType {
  const urlLower = url.toLowerCase()
  if (
    urlLower.includes("youtube.com") ||
    urlLower.includes("youtu.be") ||
    urlLower.includes("vimeo.com")
  ) {
    return "video"
  }
  if (urlLower.endsWith(".pdf")) return "pdf"
  if (urlLower.match(/\.(mp3|wav|m4a|ogg|flac)$/)) return "audio"
  if (urlLower.match(/\.(mp4|webm|mkv|avi|mov)$/)) return "video"

  return "website"
}

function getSourceTypeFromMediaType(mediaType: string): WorkspaceSourceType {
  const type = mediaType?.toLowerCase() || ""
  if (type.includes("pdf")) return "pdf"
  if (type.includes("video")) return "video"
  if (type.includes("audio")) return "audio"
  if (type.includes("website") || type.includes("web") || type.includes("url"))
    return "website"
  if (type.includes("text")) return "text"
  return "document"
}

/**
 * AddSourceModal - Modal for adding sources to workspace
 */
export const AddSourceModal: React.FC = () => {
  const { t } = useTranslation(["playground", "common"])

  // Store state
  const isOpen = useWorkspaceStore((s) => s.addSourceModalOpen)
  const activeTab = useWorkspaceStore((s) => s.addSourceModalTab)
  const isProcessing = useWorkspaceStore((s) => s.addSourceProcessing)
  const error = useWorkspaceStore((s) => s.addSourceError)

  // Store actions
  const closeModal = useWorkspaceStore((s) => s.closeAddSourceModal)
  const setTab = useWorkspaceStore((s) => s.setAddSourceModalTab)
  const setProcessing = useWorkspaceStore((s) => s.setAddSourceProcessing)
  const setError = useWorkspaceStore((s) => s.setAddSourceError)
  const addSource = useWorkspaceStore((s) => s.addSource)
  const workspaceTag = useWorkspaceStore((s) => s.workspaceTag)

  const handleAddSources = async (
    sources: Array<{ mediaId: number; title: string; type: WorkspaceSourceType }>
  ) => {
    // Add sources to workspace
    for (const source of sources) {
      addSource(source)

      // Tag media with workspace tag
      if (workspaceTag) {
        try {
          await tldwClient.updateMediaKeywords(source.mediaId, {
            keywords: [workspaceTag],
            mode: "add"
          })
        } catch {
          // Continue even if tagging fails
        }
      }
    }

    // Close modal after successful add
    closeModal()
  }

  const tabItems = [
    {
      key: "upload",
      label: (
        <span className="flex items-center gap-1.5">
          <UploadIcon className="h-4 w-4" />
          {t("playground:sources.tabUpload", "Upload")}
        </span>
      ),
      children: (
        <UploadTab
          onAddSources={handleAddSources}
          setProcessing={setProcessing}
          setError={setError}
        />
      )
    },
    {
      key: "url",
      label: (
        <span className="flex items-center gap-1.5">
          <Link className="h-4 w-4" />
          {t("playground:sources.tabUrl", "URL")}
        </span>
      ),
      children: (
        <UrlTab
          onAddSources={handleAddSources}
          setProcessing={setProcessing}
          setError={setError}
        />
      )
    },
    {
      key: "paste",
      label: (
        <span className="flex items-center gap-1.5">
          <FileText className="h-4 w-4" />
          {t("playground:sources.tabPaste", "Paste")}
        </span>
      ),
      children: (
        <PasteTab
          onAddSources={handleAddSources}
          setProcessing={setProcessing}
          setError={setError}
        />
      )
    },
    {
      key: "search",
      label: (
        <span className="flex items-center gap-1.5">
          <Search className="h-4 w-4" />
          {t("playground:sources.tabSearch", "Search")}
        </span>
      ),
      children: (
        <SearchTab
          onAddSources={handleAddSources}
          setProcessing={setProcessing}
          setError={setError}
        />
      )
    },
    {
      key: "existing",
      label: (
        <span className="flex items-center gap-1.5">
          <Database className="h-4 w-4" />
          {t("playground:sources.tabExisting", "Library")}
        </span>
      ),
      children: (
        <ExistingTab
          onAddSources={handleAddSources}
          setProcessing={setProcessing}
          setError={setError}
        />
      )
    }
  ]

  return (
    <Modal
      open={isOpen}
      onCancel={closeModal}
      title={t("playground:sources.addSourceTitle", "Add Sources")}
      footer={null}
      width={600}
      destroyOnHidden
    >
      <Spin spinning={isProcessing}>
        {error && (
          <Alert
            type="error"
            message={error}
            closable
            onClose={() => setError(null)}
            className="mb-4"
          />
        )}
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setTab(key as AddSourceTab)}
          items={tabItems}
        />
      </Spin>
    </Modal>
  )
}

export default AddSourceModal
