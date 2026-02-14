import React from "react"
import { useStorage } from "@plasmohq/storage/hook"
import { Empty } from "antd"
import { Terminal as TerminalIcon } from "lucide-react"
import { Terminal } from "xterm"
import { FitAddon } from "@xterm/addon-fit"
import "xterm/css/xterm.css"
import { useTranslation } from "react-i18next"

import { useACPSessionsStore } from "@/store/acp-sessions"

type WebSocketWithHeaders = new (
  url: string,
  protocols?: string | string[],
  options?: { headers?: Record<string, string> }
) => WebSocket

const buildWsUrl = (baseUrl: string, path: string): string => {
  const wsBase = baseUrl.replace(/^http/, "ws").replace(/\/$/, "")
  const url = new URL(path.startsWith("/") ? path : `/${path}`, wsBase)
  return url.toString()
}

const buildAuthHeaders = (
  authMode: string,
  apiKey: string,
  accessToken: string
): Record<string, string> => {
  if (authMode === "single-user" && apiKey) {
    return { "X-API-KEY": apiKey }
  }
  if (authMode === "multi-user" && accessToken) {
    return { Authorization: `Bearer ${accessToken}` }
  }
  return {}
}

const buildAuthProtocols = (headers: Record<string, string>): string[] | undefined => {
  const authHeader = headers.Authorization || headers.authorization
  if (authHeader?.toLowerCase().startsWith("bearer ")) {
    return ["bearer", authHeader.slice(7).trim()]
  }
  const apiKey = headers["X-API-KEY"] || headers["x-api-key"]
  if (apiKey) {
    return ["x-api-key", apiKey]
  }
  return undefined
}

const createWebSocket = (
  url: string,
  headers: Record<string, string>,
  protocols?: string[]
): WebSocket => {
  const WsCtor = WebSocket as unknown as WebSocketWithHeaders
  try {
    return new WsCtor(url, protocols, { headers })
  } catch {
    return new WebSocket(url, protocols)
  }
}

const resolveTokenColor = (tokenName: string, fallbackRgb: string): string => {
  if (typeof window === "undefined") return fallbackRgb
  const tokenValue = getComputedStyle(document.documentElement).getPropertyValue(tokenName).trim()
  return tokenValue ? `rgb(${tokenValue})` : fallbackRgb
}

export const ACPWorkspacePanel: React.FC = () => {
  const { t } = useTranslation("playground")
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
        background: resolveTokenColor("--color-bg", "rgb(11 15 26)"),
        foreground: resolveTokenColor("--color-text", "rgb(220 226 240)"),
        cursor: resolveTokenColor("--color-focus", "rgb(110 231 255)")
      },
      cursorBlink: true,
    })
    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    term.open(containerRef.current)
    fitAddon.fit()

    terminalRef.current = term
    fitAddonRef.current = fitAddon

    const headers = buildAuthHeaders(authMode, apiKey, accessToken)
    const protocols = buildAuthProtocols(headers)
    const wsUrl = buildWsUrl(serverUrl, sshPath)
    const ws = createWebSocket(wsUrl, headers, protocols)
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
        <Empty
          description={t(
            "playground:acp.workspace.selectSession",
            "Select a session to open the workspace terminal."
          )}
        />
      </div>
    )
  }

  if (!activeSession?.sshWsUrl) {
    return (
      <div className="flex h-full items-center justify-center">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={t(
            "playground:acp.workspace.unavailable",
            "Workspace terminal is unavailable for this session."
          )}
        />
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-border bg-surface px-3 py-2 text-sm text-text-muted">
        <TerminalIcon className="h-4 w-4" />
        {t("playground:acp.workspace.title", "Workspace Terminal")}
      </div>
      <div ref={containerRef} className="flex-1 bg-black" />
    </div>
  )
}

export default ACPWorkspacePanel
