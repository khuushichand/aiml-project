import React from "react"
import { Button, Checkbox, Input, Select, Tag, Typography } from "antd"
import { CheckCircle2, Send, XCircle } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"

import FeatureEmptyState from "@/components/Common/FeatureEmptyState"
import { useServerOnline } from "@/hooks/useServerOnline"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { tldwClient } from "@/services/tldw/TldwApiClient"
import { buildPersonaWebSocketUrl } from "@/services/persona-stream"
import { SidepanelHeaderSimple } from "~/components/Sidepanel/Chat/SidepanelHeaderSimple"

type PersonaInfo = {
  id: string
  name: string
  description?: string | null
  voice?: string | null
}

type PersonaPlanStep = {
  idx: number
  tool: string
  args?: Record<string, unknown>
  description?: string
  why?: string
}

type PendingPlan = {
  planId: string
  steps: PersonaPlanStep[]
}

type PersonaLogEntry = {
  id: string
  kind: "user" | "assistant" | "tool" | "notice"
  text: string
}

const SidepanelPersona = () => {
  const { t } = useTranslation(["sidepanel", "common"])
  const navigate = useNavigate()
  const isOnline = useServerOnline()
  const { capabilities, loading: capsLoading } = useServerCapabilities()

  const wsRef = React.useRef<WebSocket | null>(null)
  const manuallyClosingRef = React.useRef(false)

  const [catalog, setCatalog] = React.useState<PersonaInfo[]>([])
  const [selectedPersonaId, setSelectedPersonaId] =
    React.useState<string>("research_assistant")
  const [sessionId, setSessionId] = React.useState<string | null>(null)
  const [connected, setConnected] = React.useState(false)
  const [connecting, setConnecting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [input, setInput] = React.useState("")
  const [logs, setLogs] = React.useState<PersonaLogEntry[]>([])
  const [pendingPlan, setPendingPlan] = React.useState<PendingPlan | null>(null)
  const [approvedStepMap, setApprovedStepMap] = React.useState<
    Record<number, boolean>
  >({})

  const appendLog = React.useCallback(
    (kind: PersonaLogEntry["kind"], text: string) => {
      const trimmed = String(text || "").trim()
      if (!trimmed) return
      setLogs((prev) => [
        ...prev,
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          kind,
          text: trimmed
        }
      ])
    },
    []
  )

  const disconnect = React.useCallback(() => {
    const ws = wsRef.current
    if (!ws) return
    manuallyClosingRef.current = true
    try {
      ws.close()
    } catch {
      // ignore close errors
    }
    wsRef.current = null
    setConnected(false)
  }, [])

  const handleIncomingPayload = React.useCallback(
    (payload: any) => {
      const eventType = String(payload?.event || payload?.type || "").toLowerCase()
      if (!eventType) return

      if (eventType === "tool_plan") {
        const planId = String(payload?.plan_id || "")
        const stepsRaw = Array.isArray(payload?.steps) ? payload.steps : []
        const steps: PersonaPlanStep[] = stepsRaw
          .map((step: any, idx: number) => ({
            idx:
              typeof step?.idx === "number"
                ? step.idx
                : Number.parseInt(String(step?.idx ?? idx), 10),
            tool: String(step?.tool || "unknown_tool"),
            args:
              step?.args && typeof step.args === "object"
                ? (step.args as Record<string, unknown>)
                : {},
            description: step?.description ? String(step.description) : undefined,
            why: step?.why ? String(step.why) : undefined
          }))
          .filter((step) => Number.isFinite(step.idx))

        const nextMap: Record<number, boolean> = {}
        for (const step of steps) {
          nextMap[step.idx] = true
        }
        setApprovedStepMap(nextMap)
        setPendingPlan({ planId, steps })
        appendLog("tool", `Plan proposed (${steps.length} step${steps.length === 1 ? "" : "s"})`)
        return
      }

      if (eventType === "assistant_delta") {
        appendLog("assistant", String(payload?.text_delta || ""))
        return
      }

      if (eventType === "partial_transcript") {
        appendLog("user", String(payload?.text_delta || ""))
        return
      }

      if (eventType === "tool_call") {
        appendLog(
          "tool",
          `Calling ${String(payload?.tool || "tool")} (step ${String(payload?.step_idx ?? "?")})`
        )
        return
      }

      if (eventType === "tool_result") {
        const output = payload?.output ?? payload?.result
        const message =
          output == null
            ? JSON.stringify(payload)
            : typeof output === "string"
              ? output
              : JSON.stringify(output)
        appendLog("tool", `Result step ${String(payload?.step_idx ?? "?")}: ${message}`)
        return
      }

      if (eventType === "notice") {
        appendLog("notice", String(payload?.message || "notice"))
        return
      }

      if (eventType === "tts_audio") {
        appendLog("notice", "Received persona TTS audio chunk")
      }
    },
    [appendLog]
  )

  const connect = React.useCallback(async () => {
    if (connecting || connected) return
    setConnecting(true)
    setError(null)

    try {
      disconnect()
      setPendingPlan(null)
      setApprovedStepMap({})

      const config = await tldwClient.getConfig()
      if (!config) {
        throw new Error("tldw server not configured")
      }

      const catalogResp = await tldwClient.fetchWithAuth("/api/v1/persona/catalog" as any, {
        method: "GET"
      })
      if (!catalogResp.ok) {
        throw new Error(catalogResp.error || "Failed to load persona catalog")
      }
      const catalogPayload = await catalogResp.json()
      const personas = Array.isArray(catalogPayload)
        ? (catalogPayload as PersonaInfo[])
        : []
      setCatalog(personas)

      const resolvedPersonaId =
        selectedPersonaId || personas[0]?.id || "research_assistant"
      if (!selectedPersonaId && resolvedPersonaId) {
        setSelectedPersonaId(resolvedPersonaId)
      }

      const sessionResp = await tldwClient.fetchWithAuth("/api/v1/persona/session" as any, {
        method: "POST",
        body: {
          persona_id: resolvedPersonaId
        }
      })
      if (!sessionResp.ok) {
        throw new Error(sessionResp.error || "Failed to create persona session")
      }
      const sessionPayload = await sessionResp.json()
      const nextSessionId = String(sessionPayload?.session_id || "").trim()
      if (!nextSessionId) {
        throw new Error("Persona session response missing session_id")
      }
      setSessionId(nextSessionId)

      const ws = new WebSocket(buildPersonaWebSocketUrl(config))
      ws.binaryType = "arraybuffer"
      wsRef.current = ws
      manuallyClosingRef.current = false

      ws.onopen = () => {
        setConnected(true)
        appendLog("notice", "Persona stream connected")
      }

      ws.onmessage = (event) => {
        if (typeof event.data !== "string") {
          appendLog("notice", "Received binary persona stream payload")
          return
        }
        try {
          const payload = JSON.parse(event.data)
          handleIncomingPayload(payload)
        } catch {
          appendLog("notice", event.data)
        }
      }

      ws.onerror = () => {
        setError("Persona stream error")
      }

      ws.onclose = () => {
        wsRef.current = null
        setConnected(false)
        const manual = manuallyClosingRef.current
        manuallyClosingRef.current = false
        if (!manual) {
          appendLog("notice", "Persona stream disconnected")
        }
      }
    } catch (err: any) {
      const message = String(err?.message || "Failed to connect persona stream")
      setError(message)
      appendLog("notice", message)
    } finally {
      setConnecting(false)
    }
  }, [appendLog, connected, connecting, disconnect, handleIncomingPayload, selectedPersonaId])

  React.useEffect(() => {
    return () => {
      disconnect()
    }
  }, [disconnect])

  const canSend = connected && Boolean(sessionId) && Boolean(input.trim())

  const sendUserMessage = React.useCallback(() => {
    if (!canSend || !sessionId || !wsRef.current) return
    const trimmed = input.trim()
    try {
      wsRef.current.send(
        JSON.stringify({
          type: "user_message",
          session_id: sessionId,
          text: trimmed
        })
      )
      appendLog("user", trimmed)
      setInput("")
    } catch (err: any) {
      setError(String(err?.message || "Failed to send message"))
    }
  }, [appendLog, canSend, input, sessionId])

  const confirmPlan = React.useCallback(() => {
    if (!pendingPlan || !sessionId || !wsRef.current || !connected) return
    const approvedSteps = pendingPlan.steps
      .filter((step) => approvedStepMap[step.idx] !== false)
      .map((step) => step.idx)
    try {
      wsRef.current.send(
        JSON.stringify({
          type: "confirm_plan",
          session_id: sessionId,
          plan_id: pendingPlan.planId,
          approved_steps: approvedSteps
        })
      )
      appendLog(
        "notice",
        `Confirmed ${approvedSteps.length} step${approvedSteps.length === 1 ? "" : "s"}`
      )
      setPendingPlan(null)
    } catch (err: any) {
      setError(String(err?.message || "Failed to confirm plan"))
    }
  }, [appendLog, approvedStepMap, connected, pendingPlan, sessionId])

  const cancelPlan = React.useCallback(() => {
    if (!sessionId || !wsRef.current || !connected) return
    try {
      wsRef.current.send(
        JSON.stringify({
          type: "cancel",
          session_id: sessionId,
          reason: "user_cancelled"
        })
      )
      setPendingPlan(null)
      appendLog("notice", "Cancelled pending plan")
    } catch (err: any) {
      setError(String(err?.message || "Failed to cancel plan"))
    }
  }, [appendLog, connected, sessionId])

  const personaUnsupported = !capsLoading && capabilities && !capabilities.hasPersona

  if (!isOnline) {
    return (
      <div
        data-testid="persona-route-root"
        className="flex bg-neutral-50 dark:bg-surface flex-col min-h-screen mx-auto max-w-7xl"
      >
        <div className="sticky bg-white dark:bg-surface top-0 z-10">
          <SidepanelHeaderSimple activeTitle="Persona" />
        </div>
        <div className="p-4">
          <FeatureEmptyState
            title={t("sidepanel:persona.connectTitle", "Connect to use Persona")}
            description={t(
              "sidepanel:persona.connectDescription",
              "Persona streaming runs on your tldw server. Connect to a server to start a session."
            )}
            primaryActionLabel={t("sidepanel:header.settingsShortLabel", "Settings")}
            onPrimaryAction={() => navigate("/settings")}
          />
        </div>
      </div>
    )
  }

  if (personaUnsupported) {
    return (
      <div
        data-testid="persona-route-root"
        className="flex bg-neutral-50 dark:bg-surface flex-col min-h-screen mx-auto max-w-7xl"
      >
        <div className="sticky bg-white dark:bg-surface top-0 z-10">
          <SidepanelHeaderSimple activeTitle="Persona" />
        </div>
        <div className="p-4">
          <FeatureEmptyState
            title={t("sidepanel:persona.unavailableTitle", "Persona unavailable")}
            description={t(
              "sidepanel:persona.unavailableDescription",
              "This server does not currently advertise persona support."
            )}
            primaryActionLabel={t("sidepanel:header.settingsShortLabel", "Settings")}
            onPrimaryAction={() => navigate("/settings")}
          />
        </div>
      </div>
    )
  }

  return (
    <div
      data-testid="persona-route-root"
      className="flex bg-neutral-50 dark:bg-surface flex-col min-h-screen mx-auto max-w-7xl"
    >
      <div className="sticky bg-white dark:bg-surface top-0 z-10">
        <SidepanelHeaderSimple activeTitle={t("sidepanel:persona.title", "Persona")} />
      </div>

      <div className="flex flex-1 flex-col gap-3 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Select
            size="small"
            className="min-w-[180px]"
            value={selectedPersonaId}
            onChange={(value) => setSelectedPersonaId(String(value))}
            options={catalog.map((persona) => ({
              label: persona.name || persona.id,
              value: persona.id
            }))}
            placeholder={t("sidepanel:persona.select", "Select persona")}
          />
          {!connected ? (
            <Button
              size="small"
              type="primary"
              loading={connecting}
              onClick={() => {
                void connect()
              }}
            >
              {t("sidepanel:persona.connect", "Connect")}
            </Button>
          ) : (
            <Button size="small" onClick={disconnect}>
              {t("sidepanel:persona.disconnect", "Disconnect")}
            </Button>
          )}
          {sessionId ? <Tag color="blue">{`session: ${sessionId.slice(0, 8)}`}</Tag> : null}
        </div>

        {error ? (
          <div className="rounded-md border border-red-300 bg-red-50 p-2 text-xs text-red-700 dark:border-red-600/50 dark:bg-red-950/30 dark:text-red-200">
            {error}
          </div>
        ) : null}

        {pendingPlan ? (
          <div className="rounded-lg border border-border bg-surface p-3">
            <Typography.Text strong>
              {t("sidepanel:persona.pendingPlan", "Pending tool plan")}
            </Typography.Text>
            <div className="mt-2 space-y-1">
              {pendingPlan.steps.map((step) => (
                <label key={step.idx} className="flex items-start gap-2 text-xs text-text">
                  <Checkbox
                    checked={approvedStepMap[step.idx] !== false}
                    onChange={(event) => {
                      const nextChecked = event.target.checked
                      setApprovedStepMap((prev) => ({
                        ...prev,
                        [step.idx]: nextChecked
                      }))
                    }}
                  />
                  <span>
                    <span className="font-semibold">{`${step.idx}. ${step.tool}`}</span>
                    {step.description ? ` - ${step.description}` : ""}
                  </span>
                </label>
              ))}
            </div>
            <div className="mt-3 flex items-center gap-2">
              <Button
                size="small"
                type="primary"
                icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                onClick={confirmPlan}
              >
                {t("sidepanel:persona.confirmPlan", "Confirm plan")}
              </Button>
              <Button
                size="small"
                icon={<XCircle className="h-3.5 w-3.5" />}
                onClick={cancelPlan}
              >
                {t("sidepanel:persona.cancelPlan", "Cancel")}
              </Button>
            </div>
          </div>
        ) : null}

        <div className="min-h-0 flex-1 overflow-auto rounded-lg border border-border bg-surface p-3">
          <div className="space-y-2">
            {logs.length === 0 ? (
              <Typography.Text type="secondary" className="text-xs">
                {t(
                  "sidepanel:persona.empty",
                  "Connect to persona and send a message to start."
                )}
              </Typography.Text>
            ) : (
              logs.map((entry) => (
                <div
                  key={entry.id}
                  className="rounded border border-border bg-surface2 px-2 py-1.5 text-xs"
                >
                  <div className="mb-1 uppercase tracking-wide text-[10px] text-text-muted">
                    {entry.kind}
                  </div>
                  <div className="whitespace-pre-wrap text-text">{entry.text}</div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="flex items-end gap-2">
          <Input.TextArea
            value={input}
            autoSize={{ minRows: 2, maxRows: 4 }}
            onChange={(event) => setInput(event.target.value)}
            placeholder={t("sidepanel:persona.inputPlaceholder", "Ask Persona...")}
            onPressEnter={(event) => {
              if (event.shiftKey) return
              event.preventDefault()
              sendUserMessage()
            }}
          />
          <Button
            type="primary"
            icon={<Send className="h-4 w-4" />}
            disabled={!canSend}
            onClick={sendUserMessage}
          >
            {t("common:send", "Send")}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default SidepanelPersona
