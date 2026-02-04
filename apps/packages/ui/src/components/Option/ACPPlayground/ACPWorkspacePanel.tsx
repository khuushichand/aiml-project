import React from "react"
import { useStorage } from "@plasmohq/storage/hook"
import { Empty } from "antd"
import { Terminal as TerminalIcon } from "lucide-react"
import { Terminal } from "xterm"
import { FitAddon } from "@xterm/addon-fit"
import "xterm/css/xterm.css"

import { useACPSessionsStore } from "@/store/acp-sessions"

const buildWsUrl = (baseUrl: string, path: string, params: Record<string, string>): string => {
  const wsBase = baseUrl.replace(/^http/, "ws").replace(/\/$/, "")
  const url = new URL(path.startsWith("/") ? path : `/${path}`, wsBase)
  Object.entries(params).forEach(([k, v]) => {
    if (v) url.searchParams.set(k, v)
  })
  return url.toString()
}

export const ACPWorkspacePanel: React.FC = () => {
  const containerRef = React.useRef<HTMLDivElement | null>(null)
  const terminalRef = React.useRef<Terminal | null>(null)
  const fitAddonRef = React.useRef<FitAddon | null>(null)
  const wsRef = React.useRef<WebSocket | null>(null)
  const resizeTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const fitTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  const activeSessionId = useACPSessionsStore((s) => s.activeSessionId)
  const activeSession = useACPSessionsStore((s) =>
    s.activeSessionId ? s.getSession(s.activeSessionId) : undefined
  )

  const [serverUrl] = useStorage("serverUrl", "http://localhost:8000")
  const [authMode] = useStorage("authMode", "single-user")
  const [apiKey] = useStorage("apiKey", "")
  const [accessToken] = useStorage("accessToken", "")

  const sshPath = activeSession?.sshWsUrl || ""

  React.useEffect(() => {
    if (!activeSessionId || !sshPath || !containerRef.current) return

    const term = new Terminal({
      fontFamily: "JetBrains Mono, Menlo, Monaco, monospace",
      fontSize: 13,
      theme: {
        background: "#0b0f1a",
        foreground: "#dce2f0",
        cursor: "#6ee7ff",
      },
      cursorBlink: true,
    })
    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    term.open(containerRef.current)
    fitAddon.fit()

    terminalRef.current = term
    fitAddonRef.current = fitAddon

    const params: Record<string, string> = {}
    if (authMode === "single-user" && apiKey) {
      params.api_key = apiKey
    } else if (authMode === "multi-user" && accessToken) {
      params.token = accessToken
    }
    const wsUrl = buildWsUrl(serverUrl, sshPath, params)
    const ws = new WebSocket(wsUrl)
    ws.binaryType = "arraybuffer"
    wsRef.current = ws

    ws.onopen = () => {
      term.focus()
    }
    ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        term.write(event.data)
        return
      }
      const data = new Uint8Array(event.data)
      term.write(data)
    }
    ws.onerror = () => {
      term.write("\\r\\n[SSH connection error]\\r\\n")
    }
    ws.onclose = () => {
      term.write("\\r\\n[SSH connection closed]\\r\\n")
    }

    const disposeInput = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data)
      }
    })

    const scheduleResize = (cols: number, rows: number) => {
      if (resizeTimeoutRef.current) {
        clearTimeout(resizeTimeoutRef.current)
      }
      resizeTimeoutRef.current = setTimeout(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "resize", cols, rows }))
        }
      }, 100)
    }

    const disposeResize = term.onResize(({ cols, rows }) => {
      scheduleResize(cols, rows)
    })

    const scheduleFit = () => {
      if (fitTimeoutRef.current) {
        clearTimeout(fitTimeoutRef.current)
      }
      fitTimeoutRef.current = setTimeout(() => {
        fitAddon.fit()
      }, 100)
    }

    const handleResize = () => scheduleFit()
    window.addEventListener("resize", handleResize)

    return () => {
      disposeInput.dispose()
      disposeResize.dispose()
      window.removeEventListener("resize", handleResize)
      if (resizeTimeoutRef.current) {
        clearTimeout(resizeTimeoutRef.current)
        resizeTimeoutRef.current = null
      }
      if (fitTimeoutRef.current) {
        clearTimeout(fitTimeoutRef.current)
        fitTimeoutRef.current = null
      }
      ws.close()
      term.dispose()
      terminalRef.current = null
      fitAddonRef.current = null
    }
  }, [activeSessionId, sshPath, serverUrl, authMode, apiKey, accessToken])

  if (!activeSessionId) {
    return (
      <div className="flex h-full items-center justify-center">
        <Empty description="Select a session to open the workspace terminal." />
      </div>
    )
  }

  if (!activeSession?.sshWsUrl) {
    return (
      <div className="flex h-full items-center justify-center">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="Workspace terminal is unavailable for this session."
        />
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border bg-surface px-3 py-2 text-sm text-text-muted">
        <TerminalIcon className="h-4 w-4" />
        Workspace Terminal
      </div>
      <div ref={containerRef} className="flex-1 bg-black" />
    </div>
  )
}

export default ACPWorkspacePanel
