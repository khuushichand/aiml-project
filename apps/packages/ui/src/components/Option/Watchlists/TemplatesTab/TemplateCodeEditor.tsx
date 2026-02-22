import React, { Component, useCallback, useEffect, useImperativeHandle, useRef, useState, forwardRef } from "react"
import type { ReactNode } from "react"
import dynamic from "next/dynamic"
import type { editor as MonacoEditor } from "monaco-editor"
import type { Monaco } from "@monaco-editor/react"

const Monaco = dynamic(
  () => import("@monaco-editor/react"),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center rounded border border-border bg-bg p-4 text-xs text-text-muted" style={{ height: 400 }}>
        Loading editor…
      </div>
    ),
  },
)

/** Error boundary that catches Monaco load/render failures and triggers fallback. */
class MonacoErrorBoundary extends Component<
  { onError: () => void; children: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false }
  static getDerivedStateFromError() {
    return { hasError: true }
  }
  componentDidCatch() {
    this.props.onError()
  }
  render() {
    if (this.state.hasError) return null
    return this.props.children
  }
}

export interface TemplateCodeEditorHandle {
  insertSnippet: (snippet: string) => void
  getValue: () => string
}

interface TemplateCodeEditorProps {
  value: string
  onChange: (value: string) => void
  format: "md" | "html"
  height?: number | string
  readOnly?: boolean
  validationErrors?: Array<{ line?: number | null; column?: number | null; message: string }>
}

export const TemplateCodeEditor = forwardRef<TemplateCodeEditorHandle, TemplateCodeEditorProps>(
  ({ value, onChange, format, height = 400, readOnly, validationErrors }, ref) => {
    const editorRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null)
    const monacoRef = useRef<Monaco | null>(null)
    const [useFallback, setUseFallback] = useState(false)

    useImperativeHandle(ref, () => ({
      insertSnippet: (snippet: string) => {
        const editor = editorRef.current
        if (!editor) {
          // Fallback: append
          onChange(value + (value.endsWith("\n") ? "" : "\n") + snippet)
          return
        }
        const selection = editor.getSelection()
        const position = selection ? selection.getStartPosition() : editor.getPosition()
        if (position) {
          editor.executeEdits("snippet", [
            {
              range: {
                startLineNumber: position.lineNumber,
                startColumn: position.column,
                endLineNumber: position.lineNumber,
                endColumn: position.column,
              },
              text: snippet,
              forceMoveMarkers: true,
            },
          ])
          editor.focus()
        }
      },
      getValue: () => {
        return editorRef.current?.getValue() ?? value
      },
    }))

    // Update validation markers
    useEffect(() => {
      const monaco = monacoRef.current
      const editor = editorRef.current
      if (!monaco || !editor) return
      const model = editor.getModel()
      if (!model) return

      const markers = (validationErrors || []).map((err) => ({
        severity: monaco.MarkerSeverity.Error,
        startLineNumber: err.line ?? 1,
        startColumn: err.column ?? 1,
        endLineNumber: err.line ?? 1,
        endColumn: err.column ? err.column + 20 : 1000,
        message: err.message,
      }))
      monaco.editor.setModelMarkers(model, "template-validation", markers)
    }, [validationErrors])

    const handleEditorChange = useCallback(
      (v?: string) => {
        onChange(v ?? "")
      },
      [onChange],
    )

    const handleEditorMount = useCallback(
      (editor: MonacoEditor.IStandaloneCodeEditor, monaco: Monaco) => {
        editorRef.current = editor
        monacoRef.current = monaco
      },
      [],
    )

    const handleError = useCallback(() => {
      setUseFallback(true)
    }, [])

    if (useFallback) {
      return (
        <textarea
          className="w-full rounded-md border border-border bg-bg font-mono text-sm shadow-sm focus:border-primary focus:ring-primary"
          style={{ height, resize: "none" }}
          value={value}
          readOnly={readOnly}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Enter Jinja2 template…"
        />
      )
    }

    const language = format === "html" ? "html" : "markdown"
    const theme =
      typeof document !== "undefined" &&
      (document.documentElement.classList.contains("dark") ||
        document.documentElement.classList.contains("theme-dark"))
        ? "vs-dark"
        : "light"

    return (
      <MonacoErrorBoundary onError={handleError}>
        <Monaco
          defaultLanguage={language}
          language={language}
          value={value}
          onChange={handleEditorChange}
          height={height}
          theme={theme as string}
          options={{
            readOnly: !!readOnly,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            wordWrap: "on",
            fontSize: 13,
            lineNumbers: "on",
            renderLineHighlight: "line",
            tabSize: 2,
            bracketPairColorization: { enabled: true },
            autoClosingBrackets: "always",
            suggest: { showWords: false },
          }}
          onMount={handleEditorMount}
        />
      </MonacoErrorBoundary>
    )
  },
)

TemplateCodeEditor.displayName = "TemplateCodeEditor"

export default TemplateCodeEditor
