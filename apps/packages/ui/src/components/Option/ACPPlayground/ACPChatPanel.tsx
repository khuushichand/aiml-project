import React, { useState, useRef, useEffect } from "react"
import { useTranslation } from "react-i18next"
import { Button, Input, Empty, Spin } from "antd"
import { Send, Square, Bot, User, Wrench, AlertCircle } from "lucide-react"
import { useACPSessionsStore } from "@/store/acp-sessions"
import type { ACPUpdate, ACPSessionState } from "@/services/acp/types"

const { TextArea } = Input

interface ACPChatPanelProps {
  state: ACPSessionState
  isConnected: boolean
  updates: ACPUpdate[]
  sendPrompt: (messages: Array<{ role: "system" | "user" | "assistant"; content: string }>) => void
  cancel: () => void
  connect: () => Promise<void>
  error?: string | null
}

export const ACPChatPanel: React.FC<ACPChatPanelProps> = ({
  state,
  isConnected,
  updates,
  sendPrompt,
  cancel,
  connect,
  error,
}) => {
  const { t } = useTranslation(["playground", "option", "common"])
  const [inputValue, setInputValue] = useState("")
  const [isReconnecting, setIsReconnecting] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Store
  const activeSessionId = useACPSessionsStore((s) => s.activeSessionId)

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [updates])

  const handleSend = () => {
    if (!inputValue.trim() || !isConnected) return

    sendPrompt([{ role: "user", content: inputValue.trim() }])
    setInputValue("")
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleCancel = () => {
    cancel()
  }

  const handleReconnect = async () => {
    setIsReconnecting(true)
    try {
      await connect()
    } finally {
      setIsReconnecting(false)
    }
  }

  const isRunning = state === "running" || state === "waiting_permission"

  // No active session
  if (!activeSessionId) {
    return (
      <div className="flex h-full items-center justify-center">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <div className="space-y-2 text-sm text-text-muted">
              <p>{t("playground:acp.selectOrCreate", "Select or create a session to start")}</p>
              <p>
                {t(
                  "playground:acp.selectOrCreateHelp",
                  "ACP connects you to AI coding agents like Claude Code. Create a session, point it at a project directory, and start prompting."
                )}
              </p>
            </div>
          }
        />
      </div>
    )
  }

  // Connecting
  if (state === "connecting") {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <Spin size="large" />
          <div className="mt-4 text-text-muted">
            {t("playground:acp.connecting", "Connecting to session...")}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Messages area */}
      <div className="custom-scrollbar flex-1 overflow-y-auto p-4">
        {updates.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center text-text-muted">
              <Bot className="mx-auto h-12 w-12 opacity-50" />
              <p className="mt-4">
                {t("playground:acp.startPrompt", "Send a message to start the conversation")}
              </p>
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-4">
            {updates.map((update, index) => (
              <UpdateMessage key={index} update={update} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t border-border bg-surface p-4">
        <div className="mx-auto max-w-3xl">
          <div className="flex gap-2">
            <TextArea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t("playground:acp.inputPlaceholder", "Type your message...")}
              autoSize={{ minRows: 1, maxRows: 6 }}
              disabled={!isConnected || isRunning}
              className="flex-1"
            />
            {isRunning ? (
              <Button
                type="primary"
                danger
                icon={<Square className="h-4 w-4" />}
                onClick={handleCancel}
              >
                {t("playground:acp.stop", "Stop")}
              </Button>
            ) : (
              <Button
                type="primary"
                icon={<Send className="h-4 w-4" />}
                onClick={handleSend}
                disabled={!inputValue.trim() || !isConnected}
              >
                {t("playground:acp.send", "Send")}
              </Button>
            )}
          </div>

          {!isConnected && (
            <div className="mt-2 flex items-center justify-between gap-2 text-xs text-warning">
              <span className="flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {t("playground:acp.notConnected", "Not connected to session")}
              </span>
              <Button size="small" onClick={handleReconnect} loading={isReconnecting}>
                {t("playground:acp.reconnect", "Reconnect")}
              </Button>
            </div>
          )}

          {error && (
            <div className="mt-2 text-xs text-error">{error}</div>
          )}
        </div>
      </div>
    </div>
  )
}

interface UpdateMessageProps {
  update: ACPUpdate
}

const UpdateMessage: React.FC<UpdateMessageProps> = ({ update }) => {
  const { t } = useTranslation(["playground"])

  // Determine the message type and content
  const getMessageContent = () => {
    const data = update.data as Record<string, unknown>

    switch (update.type) {
      case "text":
      case "assistant_text":
        return {
          role: "assistant" as const,
          content: String(data.text || data.content || ""),
        }

      case "user_text":
        return {
          role: "user" as const,
          content: String(data.text || data.content || ""),
        }

      case "tool_call":
        return {
          role: "tool" as const,
          toolName: String(data.name || data.tool || "unknown"),
          toolArgs: data.arguments || data.input || {},
        }

      case "tool_result":
        return {
          role: "tool_result" as const,
          toolName: String(data.name || data.tool || ""),
          result: data.result || data.output || "",
        }

      case "error":
        return {
          role: "error" as const,
          content: String(data.message || data.error || "Unknown error"),
        }

      case "cancelled":
        return {
          role: "system" as const,
          content: t("playground:acp.operationCancelled", "Operation cancelled"),
        }

      default:
        // Generic update
        return {
          role: "system" as const,
          content: JSON.stringify(data, null, 2),
        }
    }
  }

  const message = getMessageContent()

  // User message
  if (message.role === "user") {
    return (
      <div className="flex gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10">
          <User className="h-4 w-4 text-primary" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium text-text-muted">You</div>
          <div className="mt-1 whitespace-pre-wrap text-text">
            {message.content}
          </div>
        </div>
      </div>
    )
  }

  // Assistant message
  if (message.role === "assistant") {
    return (
      <div className="flex gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-success/10">
          <Bot className="h-4 w-4 text-success" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium text-text-muted">Agent</div>
          <div className="mt-1 whitespace-pre-wrap text-text">
            {message.content}
          </div>
        </div>
      </div>
    )
  }

  // Tool call
  if (message.role === "tool") {
    return (
      <div className="flex gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-info/10">
          <Wrench className="h-4 w-4 text-info" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium text-text-muted">
            Tool: {message.toolName}
          </div>
          <div className="mt-1 rounded-lg bg-surface2 p-2">
            <pre className="overflow-x-auto text-xs text-text-muted">
              {JSON.stringify(message.toolArgs, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    )
  }

  // Tool result
  if (message.role === "tool_result") {
    return (
      <div className="flex gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-info/10">
          <Wrench className="h-4 w-4 text-info" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium text-text-muted">
            Result: {message.toolName}
          </div>
          <div className="mt-1 rounded-lg bg-surface2 p-2">
            <pre className="overflow-x-auto text-xs text-text-muted">
              {typeof message.result === "string"
                ? message.result
                : JSON.stringify(message.result, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    )
  }

  // Error message
  if (message.role === "error") {
    return (
      <div className="flex gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-error/10">
          <AlertCircle className="h-4 w-4 text-error" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium text-error">Error</div>
          <div className="mt-1 whitespace-pre-wrap text-error">
            {message.content}
          </div>
        </div>
      </div>
    )
  }

  // System message
  return (
    <div className="flex justify-center">
      <div className="rounded-lg bg-surface2 px-3 py-1 text-xs text-text-muted">
        {message.content}
      </div>
    </div>
  )
}
