import React, { useCallback, useEffect, useRef, useState } from "react"
import { Alert, Radio, Select, Spin } from "antd"
import DOMPurify from "dompurify"
import { marked } from "marked"
import { previewWatchlistTemplate } from "@/services/watchlists"

interface TemplatePreviewPaneProps {
  content: string
  format: "md" | "html"
  /** Available runs to preview against (id + label) */
  runs?: Array<{ id: number; label: string }>
}

export const TemplatePreviewPane: React.FC<TemplatePreviewPaneProps> = ({
  content,
  format,
  runs,
}) => {
  const [mode, setMode] = useState<"static" | "live">("static")
  const [selectedRunId, setSelectedRunId] = useState<number | undefined>(undefined)
  const [liveRendered, setLiveRendered] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const abortRef = useRef<AbortController | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Static preview: render markup locally (no Jinja2 evaluation)
  const staticHtml = React.useMemo(() => {
    if (!content) return ""
    if (format === "md") {
      const rendered = marked.parse(content)
      return DOMPurify.sanitize(String(rendered), { USE_PROFILES: { html: true } })
    }
    return DOMPurify.sanitize(content, { USE_PROFILES: { html: true } })
  }, [content, format])

  // Live preview: debounced server-side render
  const fetchLivePreview = useCallback(async () => {
    if (!selectedRunId || !content.trim()) {
      setLiveRendered("")
      return
    }
    // Cancel previous request
    if (abortRef.current) {
      abortRef.current.abort()
    }
    abortRef.current = new AbortController()

    setLoading(true)
    setError(null)
    try {
      const result = await previewWatchlistTemplate(content, selectedRunId, format)
      setLiveRendered(result.rendered)
      setWarnings(result.warnings || [])
    } catch (err: any) {
      if (err?.name === "AbortError") return
      setError(err?.message || "Preview failed")
      setLiveRendered("")
    } finally {
      setLoading(false)
    }
  }, [content, selectedRunId, format])

  // Debounce live preview
  useEffect(() => {
    if (mode !== "live" || !selectedRunId) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      fetchLivePreview()
    }, 500)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [content, selectedRunId, mode, fetchLivePreview])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortRef.current) abortRef.current.abort()
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  const livePreviewHtml = React.useMemo(() => {
    if (!liveRendered) return ""
    if (format === "md") {
      const rendered = marked.parse(liveRendered)
      return DOMPurify.sanitize(String(rendered), { USE_PROFILES: { html: true } })
    }
    return DOMPurify.sanitize(liveRendered, { USE_PROFILES: { html: true } })
  }, [liveRendered, format])

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4">
        <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)} size="small">
          <Radio.Button value="static">Static markup</Radio.Button>
          <Radio.Button value="live">Live (render with run data)</Radio.Button>
        </Radio.Group>

        {mode === "live" && (
          <Select
            value={selectedRunId}
            onChange={setSelectedRunId}
            placeholder="Select a run…"
            size="small"
            className="min-w-[200px]"
            allowClear
            options={(runs || []).map((r) => ({
              value: r.id,
              label: r.label,
            }))}
          />
        )}

        {loading && <Spin size="small" />}
      </div>

      {mode === "live" && !selectedRunId && (
        <Alert
          type="info"
          showIcon
          title="Select a run to preview the template with real data."
        />
      )}

      {error && (
        <Alert type="error" showIcon title={error} />
      )}

      {warnings.length > 0 && (
        <Alert
          type="warning"
          showIcon
          title="Render warnings"
          description={warnings.join("; ")}
        />
      )}

      {mode === "static" ? (
        staticHtml ? (
          <div
            className="prose dark:prose-invert max-w-none p-4 bg-surface rounded-lg border border-border overflow-auto max-h-96"
            dangerouslySetInnerHTML={{ __html: staticHtml }}
          />
        ) : (
          <div className="text-sm text-text-muted p-4">
            Nothing to preview yet.
          </div>
        )
      ) : (
        livePreviewHtml ? (
          <div
            className="prose dark:prose-invert max-w-none p-4 bg-surface rounded-lg border border-border overflow-auto max-h-96"
            dangerouslySetInnerHTML={{ __html: livePreviewHtml }}
          />
        ) : !loading && selectedRunId ? (
          <div className="text-sm text-text-muted p-4">
            No preview content yet. The template will render after a short delay.
          </div>
        ) : null
      )}
    </div>
  )
}

export default TemplatePreviewPane
