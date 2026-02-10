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
  policy?: PersonaToolPolicy
}

type PendingPlan = {
  planId: string
  steps: PersonaPlanStep[]
  memory?: PersonaMemoryUsage
}

type PersonaLogEntry = {
  id: string
  kind: "user" | "assistant" | "tool" | "notice"
  text: string
}

type PersonaToolPolicy = {
  allow?: boolean
  requires_confirmation?: boolean
  required_scope?: string | null
  reason_code?: string | null
  reason?: string | null
  action?: string | null
}

type PersonaMemoryUsage = {
  enabled?: boolean
  requested_top_k?: number
  applied_count?: number
}

type PersonaSessionSummary = {
  session_id: string
  persona_id?: string
  created_at?: string
  updated_at?: string
  turn_count?: number
  pending_plan_count?: number
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
  const [sessionHistory, setSessionHistory] = React.useState<PersonaSessionSummary[]>([])
  const [resumeSessionId, setResumeSessionId] = React.useState<string>("")
  const [memoryEnabled, setMemoryEnabled] = React.useState(true)
  const [memoryTopK, setMemoryTopK] = React.useState<number>(3)
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
            why: step?.why ? String(step.why) : undefined,
            policy:
              step?.policy && typeof step.policy === "object"
                ? (step.policy as PersonaToolPolicy)
                : undefined
          }))
          .filter((step) => Number.isFinite(step.idx))

        const nextMap: Record<number, boolean> = {}
        for (const step of steps) {
          nextMap[step.idx] = step.policy?.allow !== false
        }
        setApprovedStepMap(nextMap)
        const memoryPayload =
          payload?.memory && typeof payload.memory === "object"
            ? (payload.memory as PersonaMemoryUsage)
            : undefined
        setPendingPlan({ planId, steps, memory: memoryPayload })
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

      const sessionsResp = await tldwClient.fetchWithAuth(
        `/api/v1/persona/sessions?persona_id=${encodeURIComponent(resolvedPersonaId)}&limit=50` as any,
        {
          method: "GET"
        }
      )
      let sessionsPayload: PersonaSessionSummary[] = []
      if (sessionsResp.ok) {
        const sessionsJson = await sessionsResp.json()
        sessionsPayload = Array.isArray(sessionsJson)
          ? (sessionsJson as PersonaSessionSummary[])
          : []
      }
      setSessionHistory(sessionsPayload)

      const sessionResp = await tldwClient.fetchWithAuth("/api/v1/persona/session" as any, {
        method: "POST",
        body: {
          persona_id: resolvedPersonaId,
          resume_session_id: resumeSessionId || undefined
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
      setResumeSessionId(nextSessionId)
      if (!sessionsPayload.some((item) => item.session_id === nextSessionId)) {
        setSessionHistory((prev) => [{ session_id: nextSessionId }, ...prev])
      }

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
  }, [
    appendLog,
    connected,
    connecting,
    disconnect,
    handleIncomingPayload,
    resumeSessionId,
    selectedPersonaId
  ])

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
          text: trimmed,
          use_memory_context: memoryEnabled,
          memory_top_k: memoryTopK
        })
      )
      appendLog("user", trimmed)
      setInput("")
    } catch (err: any) {
      setError(String(err?.message || "Failed to send message"))
    }
  }, [appendLog, canSend, input, memoryEnabled, memoryTopK, sessionId])

  const loadSessionHistory = React.useCallback(async () => {
    if (!sessionId) return
    const resp = await tldwClient.fetchWithAuth(
      `/api/v1/persona/sessions/${encodeURIComponent(sessionId)}?limit_turns=100` as any,
      { method: "GET" }
    )
    if (!resp.ok) {
      setError(resp.error || "Failed to load session history")
      return
    }
    const payload = await resp.json()
    const turns = Array.isArray(payload?.turns) ? payload.turns : []
    const historyLogs: PersonaLogEntry[] = turns.map((turn: any, idx: number) => {
      const role = String(turn?.role || "notice").toLowerCase()
      const kind: PersonaLogEntry["kind"] =
        role === "user" || role === "assistant" || role === "tool" ? role : "notice"
      return {
        id: String(turn?.turn_id || `${Date.now()}-${idx}`),
        kind,
        text: String(turn?.content || "")
      }
    })
    setLogs(historyLogs)
  }, [sessionId])

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
        className="flex bg-bg flex-col min-h-screen mx-auto max-w-7xl"
      >
        <div className="sticky bg-surface top-0 z-10">
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
        className="flex bg-bg flex-col min-h-screen mx-auto max-w-7xl"
      >
        <div className="sticky bg-surface top-0 z-10">
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
      className="flex bg-bg flex-col min-h-screen mx-auto max-w-7xl"
    >
      <div className="sticky bg-surface top-0 z-10">
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
          <Select
            data-testid="persona-resume-session-select"
            size="small"
            className="min-w-[180px]"
            value={resumeSessionId || "__new__"}
            disabled={connected}
            onChange={(value) =>
              setResumeSessionId(value === "__new__" ? "" : String(value))
            }
            options={[
              { label: t("sidepanel:persona.newSession", "New session"), value: "__new__" },
              ...sessionHistory.map((session) => ({
                label: session.session_id,
                value: session.session_id
              }))
            ]}
            placeholder={t("sidepanel:persona.resume", "Resume session")}
          />
          <Checkbox
            data-testid="persona-memory-toggle"
            checked={memoryEnabled}
            onChange={(event) => setMemoryEnabled(event.target.checked)}
          >
            {t("sidepanel:persona.memoryToggle", "Memory")}
          </Checkbox>
          <Select
            data-testid="persona-memory-topk-select"
            size="small"
            className="w-[90px]"
            value={memoryTopK}
            disabled={!memoryEnabled}
            onChange={(value) => setMemoryTopK(Number(value))}
            options={[1, 2, 3, 4, 5].map((k) => ({ label: `k=${k}`, value: k }))}
            placeholder="k"
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
          {sessionId ? (
            <Button size="small" onClick={() => void loadSessionHistory()}>
              {t("sidepanel:persona.loadHistory", "Load history")}
            </Button>
          ) : null}
        </div>

        {error ? (
          <div className="rounded-md border border-danger/30 bg-danger/10 p-2 text-xs text-danger">
            {error}
          </div>
        ) : null}

        {pendingPlan ? (
          <div className="rounded-lg border border-border bg-surface p-3">
            <Typography.Text strong>
              {t("sidepanel:persona.pendingPlan", "Pending tool plan")}
            </Typography.Text>
            {pendingPlan.memory ? (
              <div className="mt-1 flex flex-wrap items-center gap-1">
                <Tag color={pendingPlan.memory.enabled ? "green" : "default"}>
                  {pendingPlan.memory.enabled ? "memory on" : "memory off"}
                </Tag>
                {typeof pendingPlan.memory.requested_top_k === "number" ? (
                  <Tag color="blue">{`k=${pendingPlan.memory.requested_top_k}`}</Tag>
                ) : null}
                {typeof pendingPlan.memory.applied_count === "number" ? (
                  <Tag color="purple">{`applied=${pendingPlan.memory.applied_count}`}</Tag>
                ) : null}
              </div>
            ) : null}
            <div className="mt-2 space-y-1">
              {pendingPlan.steps.map((step) => (
                <label key={step.idx} className="flex items-start gap-2 text-xs text-text">
                  <Checkbox
                    checked={approvedStepMap[step.idx] !== false}
                    disabled={step.policy?.allow === false}
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
                    <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">
                      {step.policy?.required_scope ? (
                        <Tag color="blue">{`scope: ${step.policy.required_scope}`}</Tag>
                      ) : null}
                      {step.policy?.requires_confirmation ? (
                        <Tag color="gold">confirm</Tag>
                      ) : null}
                      {step.policy?.allow === false ? (
                        <Tag color="red">{`blocked${step.policy.reason_code ? `: ${step.policy.reason_code}` : ""}`}</Tag>
                      ) : null}
                    </span>
                    {step.policy?.allow === false && step.policy.reason ? (
                      <div className="mt-1 text-[11px] text-danger">
                        {step.policy.reason}
                      </div>
                    ) : null}
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
