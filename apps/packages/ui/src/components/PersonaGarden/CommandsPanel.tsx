import React from "react"
import { useTranslation } from "react-i18next"

import { tldwClient } from "@/services/tldw/TldwApiClient"

type VoiceCommandActionType = "mcp_tool" | "workflow" | "custom" | "llm_chat"

type PersonaVoiceCommand = {
  id: string
  persona_id?: string | null
  connection_id?: string | null
  connection_status?: "ok" | "missing" | null
  connection_name?: string | null
  name: string
  phrases: string[]
  action_type: VoiceCommandActionType
  action_config: Record<string, unknown>
  priority: number
  enabled: boolean
  requires_confirmation: boolean
  description?: string | null
  created_at?: string | null
}

type PersonaConnectionSummary = {
  id: string
  name: string
  auth_type?: string | null
  key_hint?: string | null
  secret_configured?: boolean
}

type CommandFormState = {
  commandId: string | null
  name: string
  description: string
  phrasesText: string
  actionType: VoiceCommandActionType
  toolName: string
  workflowId: string
  customAction: string
  connectionId: string
  requestMethod: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  requestPath: string
  extractMode: "none" | "query" | "content"
  slotMapText: string
  defaultPayloadText: string
  priority: string
  enabled: boolean
  requiresConfirmation: boolean
}

type CommandTemplate = {
  key: string
  label: string
  description: string
  apply: () => CommandFormState
}

type CommandsPanelProps = {
  selectedPersonaId: string
  selectedPersonaName: string
  isActive?: boolean
  openCommandId?: string | null
  onOpenCommandHandled?: (commandId: string) => void
}

const REQUEST_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"] as const

const DEFAULT_FORM_STATE: CommandFormState = {
  commandId: null,
  name: "",
  description: "",
  phrasesText: "",
  actionType: "mcp_tool",
  toolName: "",
  workflowId: "",
  customAction: "",
  connectionId: "",
  requestMethod: "POST",
  requestPath: "",
  extractMode: "none",
  slotMapText: "{}",
  defaultPayloadText: "{}",
  priority: "50",
  enabled: true,
  requiresConfirmation: false
}

const COMMAND_TEMPLATES: CommandTemplate[] = [
  {
    key: "notes-search",
    label: "Search Notes",
    description: "Find notes by spoken topic",
    apply: () => ({
      ...DEFAULT_FORM_STATE,
      name: "Search Notes",
      description: "Find notes related to a spoken topic",
      phrasesText: "search notes for {topic}\nfind notes about {topic}",
      toolName: "notes.search",
      slotMapText: JSON.stringify({ query: "topic" }, null, 2)
    })
  },
  {
    key: "note-create",
    label: "Create Note",
    description: "Save dictated notes quickly",
    apply: () => ({
      ...DEFAULT_FORM_STATE,
      name: "Create Note",
      description: "Create a new note from spoken content",
      phrasesText: "create note {content}\nnote this {content}",
      toolName: "notes.create",
      slotMapText: JSON.stringify({ content: "content" }, null, 2),
      requiresConfirmation: true
    })
  },
  {
    key: "media-search",
    label: "Search Library",
    description: "Search ingested media by phrase",
    apply: () => ({
      ...DEFAULT_FORM_STATE,
      name: "Search Library",
      description: "Search media and research content",
      phrasesText: "search library for {query}\nfind media about {query}",
      toolName: "media.search",
      slotMapText: JSON.stringify({ query: "query" }, null, 2)
    })
  },
  {
    key: "external-api",
    label: "External API",
    description: "Call a saved connection with a direct request",
    apply: () => ({
      ...DEFAULT_FORM_STATE,
      name: "Call External API",
      description: "Send a direct request through a saved persona connection",
      phrasesText: "call external api for {query}\nsend api request for {query}",
      actionType: "custom",
      customAction: "external_request",
      requestMethod: "POST",
      requestPath: "",
      slotMapText: JSON.stringify({ query: "query" }, null, 2),
      requiresConfirmation: true
    })
  }
]

const splitPhrases = (value: string): string[] =>
  value
    .split("\n")
    .map((item) => item.trim())
    .filter((item) => item.length > 0)

const stringifyJson = (value: unknown): string =>
  JSON.stringify(
    value && typeof value === "object" && !Array.isArray(value) ? value : {},
    null,
    2
  )

const parseJsonRecord = (
  rawValue: string,
  label: string
): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } => {
  const trimmed = rawValue.trim()
  if (!trimmed) {
    return { ok: true, value: {} }
  }
  try {
    const parsed = JSON.parse(trimmed)
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { ok: false, error: `${label} must be a JSON object.` }
    }
    return { ok: true, value: parsed as Record<string, unknown> }
  } catch {
    return { ok: false, error: `${label} must be valid JSON.` }
  }
}

const normalizeRequestMethod = (
  value: unknown
): CommandFormState["requestMethod"] => {
  const normalized = String(value || "POST").trim().toUpperCase()
  return REQUEST_METHODS.includes(normalized as CommandFormState["requestMethod"])
    ? (normalized as CommandFormState["requestMethod"])
    : "POST"
}

const resolveCommandConnectionStatus = (
  command: PersonaVoiceCommand,
  availableConnections: PersonaConnectionSummary[]
): "ok" | "missing" | null => {
  if (!command.connection_id) return null
  if (command.connection_status === "ok" || command.connection_status === "missing") {
    return command.connection_status
  }
  return availableConnections.some((connection) => connection.id === command.connection_id)
    ? "ok"
    : "missing"
}

const toCommandTargetLabel = (command: PersonaVoiceCommand): string => {
  if (command.action_type === "mcp_tool") {
    return String(command.action_config?.tool_name || "").trim() || "MCP tool"
  }
  if (command.action_type === "workflow") {
    return (
      String(command.action_config?.workflow_name || "").trim() ||
      String(command.action_config?.workflow_id || "").trim() ||
      "Workflow"
    )
  }
  if (command.action_type === "custom") {
    if (command.connection_id) {
      const method = String(command.action_config?.method || "POST").trim().toUpperCase()
      const path = String(command.action_config?.path || "").trim()
      return path ? `${method} ${path}` : `${method} connection base URL`
    }
    return String(command.action_config?.action || "").trim() || "Custom action"
  }
  return "Persona planner fallback"
}

const toFormState = (command: PersonaVoiceCommand): CommandFormState => {
  const rawSlotMap =
    (command.action_config?.slot_to_param_map as Record<string, unknown> | undefined) ||
    (command.action_config?.param_map as Record<string, unknown> | undefined) ||
    {}
  const rawDefaultPayload =
    (command.action_config?.default_payload as Record<string, unknown> | undefined) || {}
  const extractMode =
    command.action_config?.extract_query === true
      ? "query"
      : command.action_config?.extract_content === true
        ? "content"
        : "none"

  return {
    commandId: command.id,
    name: command.name || "",
    description: String(command.description || ""),
    phrasesText: Array.isArray(command.phrases) ? command.phrases.join("\n") : "",
    actionType: command.action_type,
    toolName: String(command.action_config?.tool_name || ""),
    workflowId:
      String(command.action_config?.workflow_id || "") ||
      String(command.action_config?.workflow_name || ""),
    customAction: String(command.action_config?.action || ""),
    connectionId: String(command.connection_id || ""),
    requestMethod: normalizeRequestMethod(command.action_config?.method),
    requestPath: String(command.action_config?.path || ""),
    extractMode,
    slotMapText: stringifyJson(rawSlotMap),
    defaultPayloadText: stringifyJson(rawDefaultPayload),
    priority: String(command.priority ?? 50),
    enabled: command.enabled !== false,
    requiresConfirmation: Boolean(command.requires_confirmation)
  }
}

export const CommandsPanel: React.FC<CommandsPanelProps> = ({
  selectedPersonaId,
  selectedPersonaName,
  isActive = false,
  openCommandId = null,
  onOpenCommandHandled
}) => {
  const { t } = useTranslation(["sidepanel", "common"])
  const [commands, setCommands] = React.useState<PersonaVoiceCommand[]>([])
  const [connections, setConnections] = React.useState<PersonaConnectionSummary[]>([])
  const [loading, setLoading] = React.useState(false)
  const [commandsLoaded, setCommandsLoaded] = React.useState(false)
  const [saving, setSaving] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [validationError, setValidationError] = React.useState<string | null>(null)
  const [formState, setFormState] =
    React.useState<CommandFormState>(DEFAULT_FORM_STATE)
  const editingCommand = React.useMemo(
    () =>
      formState.commandId
        ? commands.find((command) => command.id === formState.commandId) ?? null
        : null,
    [commands, formState.commandId]
  )
  const selectedConnectionMissing = React.useMemo(() => {
    if (!formState.connectionId.trim()) return false
    return !connections.some((connection) => connection.id === formState.connectionId.trim())
  }, [connections, formState.connectionId])

  React.useEffect(() => {
    let cancelled = false

    const load = async () => {
      if (!isActive || !selectedPersonaId) {
        setCommands([])
        setConnections([])
        setCommandsLoaded(false)
        setError(null)
        return
      }

      setLoading(true)
      setCommandsLoaded(false)
      setError(null)
      try {
        const [commandsResp, connectionsResp] = await Promise.all([
          tldwClient.fetchWithAuth(
            `/api/v1/persona/profiles/${encodeURIComponent(selectedPersonaId)}/voice-commands` as any,
            { method: "GET" }
          ),
          tldwClient.fetchWithAuth(
            `/api/v1/persona/profiles/${encodeURIComponent(selectedPersonaId)}/connections` as any,
            { method: "GET" }
          )
        ])

        if (!commandsResp.ok) {
          throw new Error(
            commandsResp.error ||
              t("sidepanel:personaGarden.commands.loadError", {
                defaultValue: "Failed to load persona commands."
              })
          )
        }
        if (!connectionsResp.ok) {
          throw new Error(
            connectionsResp.error ||
              t("sidepanel:personaGarden.connections.loadError", {
                defaultValue: "Failed to load persona connections."
              })
          )
        }

        const commandPayload = await commandsResp.json()
        const connectionPayload = await connectionsResp.json()
        const nextCommands = Array.isArray(commandPayload?.commands)
          ? commandPayload.commands
          : []
        const nextConnections = Array.isArray(connectionPayload)
          ? connectionPayload
          : []
        if (!cancelled) {
          setCommands(nextCommands as PersonaVoiceCommand[])
          setConnections(nextConnections as PersonaConnectionSummary[])
          setCommandsLoaded(true)
        }
      } catch (loadError) {
        if (!cancelled) {
          setCommands([])
          setConnections([])
          setCommandsLoaded(false)
          setError(
            loadError instanceof Error
              ? loadError.message
              : t("sidepanel:personaGarden.commands.loadError", {
                  defaultValue: "Failed to load persona commands."
                })
          )
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [isActive, selectedPersonaId])

  const resetForm = React.useCallback(() => {
    setFormState(DEFAULT_FORM_STATE)
    setValidationError(null)
  }, [])

  const updateFormField = React.useCallback(
    (field: keyof CommandFormState, value: string | boolean | null) => {
      setFormState((current) => ({
        ...current,
        [field]: value
      }))
    },
    []
  )

  const handleTemplateApply = React.useCallback((template: CommandTemplate) => {
    setFormState(template.apply())
    setValidationError(null)
  }, [])

  const handleEdit = React.useCallback((command: PersonaVoiceCommand) => {
    setFormState(toFormState(command))
    setValidationError(null)
    setError(null)
  }, [])

  React.useEffect(() => {
    const normalizedRequestedCommandId = String(openCommandId || "").trim()
    if (
      !isActive ||
      !selectedPersonaId ||
      !normalizedRequestedCommandId ||
      !commandsLoaded
    ) {
      return
    }
    const requestedCommand = commands.find(
      (command) => command.id === normalizedRequestedCommandId
    )
    if (requestedCommand) {
      handleEdit(requestedCommand)
    } else {
      setError("Requested voice command could not be found.")
    }
    onOpenCommandHandled?.(normalizedRequestedCommandId)
  }, [
    commands,
    commandsLoaded,
    handleEdit,
    isActive,
    onOpenCommandHandled,
    openCommandId,
    selectedPersonaId
  ])

  const handleToggle = React.useCallback(
    async (command: PersonaVoiceCommand) => {
      if (!selectedPersonaId) return
      setError(null)
      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(selectedPersonaId)}/voice-commands/${encodeURIComponent(command.id)}/toggle` as any,
          {
            method: "POST",
            body: { enabled: !command.enabled }
          }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to update command status.")
        }
        const payload = await response.json()
        setCommands((current) =>
          current.map((item) =>
            item.id === command.id ? (payload as PersonaVoiceCommand) : item
          )
        )
      } catch (toggleError) {
        setError(
          toggleError instanceof Error
            ? toggleError.message
            : "Failed to update command status."
        )
      }
    },
    [selectedPersonaId]
  )

  const handleDelete = React.useCallback(
    async (commandId: string) => {
      if (!selectedPersonaId) return
      if (
        typeof window !== "undefined" &&
        !window.confirm("Delete this voice command?")
      ) {
        return
      }
      setError(null)
      try {
        const response = await tldwClient.fetchWithAuth(
          `/api/v1/persona/profiles/${encodeURIComponent(selectedPersonaId)}/voice-commands/${encodeURIComponent(commandId)}` as any,
          {
            method: "DELETE"
          }
        )
        if (!response.ok) {
          throw new Error(response.error || "Failed to delete command.")
        }
        setCommands((current) => current.filter((item) => item.id !== commandId))
        setFormState((current) =>
          current.commandId === commandId ? DEFAULT_FORM_STATE : current
        )
      } catch (deleteError) {
        setError(
          deleteError instanceof Error
            ? deleteError.message
            : "Failed to delete command."
        )
      }
    },
    [selectedPersonaId]
  )

  const handleSave = React.useCallback(async () => {
    if (!selectedPersonaId) return

    const name = formState.name.trim()
    const phrases = splitPhrases(formState.phrasesText)
    const trimmedConnectionId = formState.connectionId.trim()
    if (!name) {
      setValidationError("Command name is required.")
      return
    }
    if (phrases.length === 0) {
      setValidationError("Add at least one trigger phrase.")
      return
    }
    if (
      trimmedConnectionId &&
      !connections.some((connection) => connection.id === trimmedConnectionId)
    ) {
      setValidationError(
        "Selected connection no longer exists. Choose another connection or clear it."
      )
      return
    }

    const slotMapResult = parseJsonRecord(formState.slotMapText, "Slot mapping")
    if (!slotMapResult.ok) {
      setValidationError(slotMapResult.error)
      return
    }
    const defaultPayloadResult = parseJsonRecord(
      formState.defaultPayloadText,
      "Default payload"
    )
    if (!defaultPayloadResult.ok) {
      setValidationError(defaultPayloadResult.error)
      return
    }

    const actionConfig: Record<string, unknown> = {}
    if (formState.actionType === "mcp_tool") {
      const toolName = formState.toolName.trim()
      if (!toolName) {
        setValidationError("Tool name is required for MCP tool commands.")
        return
      }
      actionConfig.tool_name = toolName
      if (formState.extractMode === "query") actionConfig.extract_query = true
      if (formState.extractMode === "content") actionConfig.extract_content = true
    } else if (formState.actionType === "workflow") {
      const workflowId = formState.workflowId.trim()
      if (!workflowId) {
        setValidationError("Workflow id is required for workflow commands.")
        return
      }
      actionConfig.workflow_id = workflowId
    } else if (formState.actionType === "custom") {
      const customAction = formState.customAction.trim()
      if (!customAction && !formState.connectionId.trim()) {
        setValidationError("Action name is required for custom commands.")
        return
      }
      if (customAction) {
        actionConfig.action = customAction
      }
      if (formState.connectionId.trim()) {
        actionConfig.method = formState.requestMethod
        if (formState.requestPath.trim()) {
          actionConfig.path = formState.requestPath.trim()
        }
      }
    }

    if (Object.keys(slotMapResult.value).length > 0) {
      actionConfig.slot_to_param_map = slotMapResult.value
    }
    if (Object.keys(defaultPayloadResult.value).length > 0) {
      actionConfig.default_payload = defaultPayloadResult.value
    }

    const payload = {
      connection_id: trimmedConnectionId || null,
      name,
      description: formState.description.trim() || null,
      phrases,
      action_type: formState.actionType,
      action_config: actionConfig,
      priority: Number.parseInt(formState.priority, 10) || 0,
      enabled: formState.enabled,
      requires_confirmation: formState.requiresConfirmation
    }

    setSaving(true)
    setValidationError(null)
    setError(null)
    try {
      const isEditing = Boolean(formState.commandId)
      const response = await tldwClient.fetchWithAuth(
        isEditing
          ? (`/api/v1/persona/profiles/${encodeURIComponent(selectedPersonaId)}/voice-commands/${encodeURIComponent(formState.commandId || "")}` as any)
          : (`/api/v1/persona/profiles/${encodeURIComponent(selectedPersonaId)}/voice-commands` as any),
        {
          method: isEditing ? "PUT" : "POST",
          body: payload
        }
      )
      if (!response.ok) {
        throw new Error(
          response.error ||
            (isEditing
              ? "Failed to update voice command."
              : "Failed to create voice command.")
        )
      }
      const saved = (await response.json()) as PersonaVoiceCommand
      setCommands((current) => {
        const existingIndex = current.findIndex((item) => item.id === saved.id)
        if (existingIndex === -1) {
          return [saved, ...current]
        }
        const next = [...current]
        next[existingIndex] = saved
        return next
      })
      resetForm()
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Failed to save voice command."
      )
    } finally {
      setSaving(false)
    }
  }, [connections, formState, resetForm, selectedPersonaId])

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
        {t("sidepanel:personaGarden.commands.heading", {
          defaultValue: "Commands"
        })}
      </div>
      <div className="mt-2 space-y-3 text-sm text-text">
        <p className="text-xs text-text-muted">
          {selectedPersonaId
            ? t("sidepanel:personaGarden.commands.description", {
                defaultValue:
                  "Register direct voice commands for {{personaName}} with phrases, tool targets, and optional slot mappings.",
                personaName:
                  selectedPersonaName ||
                  selectedPersonaId ||
                  t("sidepanel:personaGarden.commands.currentPersona", {
                    defaultValue: "this persona"
                  })
              })
            : t("sidepanel:personaGarden.commands.noPersona", {
                defaultValue:
                  "Select a persona to manage its voice command registry."
              })}
        </p>

        {error ? (
          <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        ) : null}
        {validationError ? (
          <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700">
            {validationError}
          </div>
        ) : null}

        {selectedPersonaId ? (
          <>
            <div className="space-y-2">
              <div className="text-xs font-medium text-text">
                {t("sidepanel:personaGarden.commands.templates", {
                  defaultValue: "Quick templates"
                })}
              </div>
              <div className="grid gap-2 md:grid-cols-3">
                {COMMAND_TEMPLATES.map((template) => (
                  <button
                    key={template.key}
                    type="button"
                    data-testid={`persona-commands-template-${template.key}`}
                    className="rounded-md border border-border bg-bg px-3 py-2 text-left transition hover:border-primary/40 hover:bg-surface2"
                    onClick={() => handleTemplateApply(template)}
                  >
                    <div className="text-sm font-medium text-text">
                      {template.label}
                    </div>
                    <div className="text-xs text-text-muted">
                      {template.description}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-3 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-medium text-text">
                    {t("sidepanel:personaGarden.commands.existing", {
                      defaultValue: "Registered commands"
                    })}
                  </div>
                  {loading ? (
                    <span className="text-xs text-text-muted">
                      {t("common:loading", "Loading...")}
                    </span>
                  ) : null}
                </div>
                {commands.length > 0 ? (
                  commands.map((command) => (
                    <div
                      key={command.id}
                      data-testid={`persona-commands-row-${command.id}`}
                      data-selected={formState.commandId === command.id ? "true" : "false"}
                      className={`rounded-md border bg-bg p-3 transition ${
                        formState.commandId === command.id
                          ? "border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20"
                          : "border-border"
                      }`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <div className="font-medium text-text">
                            {command.name}
                          </div>
                          <div className="text-xs text-text-muted">
                            {toCommandTargetLabel(command)}
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2 text-[11px]">
                          <span className="rounded-full border border-border px-2 py-0.5 text-text-muted">
                            {command.action_type}
                          </span>
                          {command.enabled ? (
                            <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-emerald-700">
                              enabled
                            </span>
                          ) : (
                            <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-amber-700">
                              disabled
                            </span>
                          )}
                          {command.requires_confirmation ? (
                            <span className="rounded-full border border-border px-2 py-0.5 text-text-muted">
                              confirm
                            </span>
                          ) : null}
                          {command.connection_id ? (
                            resolveCommandConnectionStatus(command, connections) === "missing" ? (
                              <span className="rounded-full border border-red-500/40 bg-red-500/10 px-2 py-0.5 text-red-700">
                                missing connection
                              </span>
                            ) : (
                              <span className="rounded-full border border-sky-500/40 bg-sky-500/10 px-2 py-0.5 text-sky-700">
                                connection
                              </span>
                            )
                          ) : null}
                        </div>
                      </div>
                      {command.description ? (
                        <p className="mt-2 text-xs text-text-muted">
                          {command.description}
                        </p>
                      ) : null}
                      {resolveCommandConnectionStatus(command, connections) === "missing" ? (
                        <div className="mt-2 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-700">
                          {t("sidepanel:personaGarden.commands.missingConnectionHint", {
                            defaultValue:
                              "The saved connection for this command was deleted. Edit the command to choose a replacement connection."
                          })}
                        </div>
                      ) : null}
                      <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-text-muted">
                        {command.phrases.map((phrase) => (
                          <span
                            key={`${command.id}-${phrase}`}
                            className="rounded-full border border-border px-2 py-0.5"
                          >
                            {phrase}
                          </span>
                        ))}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          type="button"
                          data-testid={`persona-commands-edit-${command.id}`}
                          className="rounded-md border border-border px-2 py-1 text-xs text-text transition hover:bg-surface2"
                          onClick={() => handleEdit(command)}
                        >
                          {t("common:edit", "Edit")}
                        </button>
                        <button
                          type="button"
                          data-testid={`persona-commands-toggle-${command.id}`}
                          className="rounded-md border border-border px-2 py-1 text-xs text-text transition hover:bg-surface2"
                          onClick={() => {
                            void handleToggle(command)
                          }}
                        >
                          {command.enabled
                            ? t("sidepanel:personaGarden.commands.disable", {
                                defaultValue: "Disable"
                              })
                            : t("sidepanel:personaGarden.commands.enable", {
                                defaultValue: "Enable"
                              })}
                        </button>
                        <button
                          type="button"
                          data-testid={`persona-commands-delete-${command.id}`}
                          className="rounded-md border border-red-500/40 px-2 py-1 text-xs text-red-700 transition hover:bg-red-500/10"
                          onClick={() => {
                            void handleDelete(command.id)
                          }}
                        >
                          {t("common:delete", "Delete")}
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div
                    data-testid="persona-commands-empty"
                    className="rounded-md border border-dashed border-border px-3 py-4 text-xs text-text-muted"
                  >
                    {loading
                      ? t("sidepanel:personaGarden.commands.loading", {
                          defaultValue: "Loading commands..."
                        })
                      : t("sidepanel:personaGarden.commands.empty", {
                          defaultValue:
                            "No direct voice commands yet. Start from a template or create one manually."
                        })}
                  </div>
                )}
              </div>

              <div className="rounded-md border border-border bg-bg p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium text-text">
                    {formState.commandId
                      ? t("sidepanel:personaGarden.commands.editHeading", {
                          defaultValue: "Edit command"
                        })
                      : t("sidepanel:personaGarden.commands.createHeading", {
                          defaultValue: "Create command"
                        })}
                  </div>
                  {formState.commandId ? (
                    <button
                      type="button"
                      data-testid="persona-commands-reset"
                      className="rounded-md border border-border px-2 py-1 text-xs text-text transition hover:bg-surface2"
                      onClick={resetForm}
                    >
                      {t("common:reset", "Reset")}
                    </button>
                  ) : null}
                </div>

                <div className="mt-3 space-y-3">
                  <label className="block text-xs text-text-muted">
                    {t("sidepanel:personaGarden.commands.name", {
                      defaultValue: "Command name"
                    })}
                    <input
                      data-testid="persona-commands-name-input"
                      className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                      value={formState.name}
                      onChange={(event) =>
                        updateFormField("name", event.target.value)
                      }
                      placeholder="Search notes"
                    />
                  </label>

                  <label className="block text-xs text-text-muted">
                    {t("sidepanel:personaGarden.commands.descriptionLabel", {
                      defaultValue: "Description"
                    })}
                    <input
                      data-testid="persona-commands-description-input"
                      className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                      value={formState.description}
                      onChange={(event) =>
                        updateFormField("description", event.target.value)
                      }
                      placeholder="What this command should do"
                    />
                  </label>

                  <label className="block text-xs text-text-muted">
                    {t("sidepanel:personaGarden.commands.phrases", {
                      defaultValue: "Trigger phrases"
                    })}
                    <textarea
                      data-testid="persona-commands-phrases-input"
                      className="mt-1 min-h-[88px] w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                      value={formState.phrasesText}
                      onChange={(event) =>
                        updateFormField("phrasesText", event.target.value)
                      }
                      placeholder={"search notes for {topic}\nfind notes about {topic}"}
                    />
                  </label>

                  <div className="grid gap-3 md:grid-cols-2">
                    <label className="block text-xs text-text-muted">
                      {t("sidepanel:personaGarden.commands.actionType", {
                        defaultValue: "Action type"
                      })}
                      <select
                        data-testid="persona-commands-action-type-select"
                        className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                        value={formState.actionType}
                        onChange={(event) =>
                          updateFormField(
                            "actionType",
                            event.target.value as VoiceCommandActionType
                          )
                        }
                      >
                        <option value="mcp_tool">mcp_tool</option>
                        <option value="workflow">workflow</option>
                        <option value="custom">custom</option>
                        <option value="llm_chat">llm_chat</option>
                      </select>
                    </label>

                    <label className="block text-xs text-text-muted">
                      {t("sidepanel:personaGarden.commands.connection", {
                        defaultValue: "Connection"
                      })}
                      <select
                        data-testid="persona-commands-connection-select"
                        className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                        value={formState.connectionId}
                        onChange={(event) =>
                          updateFormField("connectionId", event.target.value)
                        }
                      >
                        <option value="">
                          {t("sidepanel:personaGarden.commands.noConnection", {
                            defaultValue: "No connection"
                          })}
                        </option>
                        {selectedConnectionMissing ? (
                          <option value={formState.connectionId}>
                            {t("sidepanel:personaGarden.commands.missingConnectionOption", {
                              defaultValue: "Missing connection ({{connectionId}})",
                              connectionId: formState.connectionId
                            })}
                          </option>
                        ) : null}
                        {connections.map((connection) => (
                          <option key={connection.id} value={connection.id}>
                            {connection.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>

                  {formState.actionType === "mcp_tool" ? (
                    <>
                      <label className="block text-xs text-text-muted">
                        {t("sidepanel:personaGarden.commands.toolName", {
                          defaultValue: "Tool name"
                        })}
                        <input
                          data-testid="persona-commands-target-input"
                          className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                          value={formState.toolName}
                          onChange={(event) =>
                            updateFormField("toolName", event.target.value)
                          }
                          placeholder="notes.search"
                        />
                      </label>
                      <label className="block text-xs text-text-muted">
                        {t("sidepanel:personaGarden.commands.extractMode", {
                          defaultValue: "Phrase extraction"
                        })}
                        <select
                          data-testid="persona-commands-extract-mode-select"
                          className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                          value={formState.extractMode}
                          onChange={(event) =>
                            updateFormField(
                              "extractMode",
                              event.target.value as CommandFormState["extractMode"]
                            )
                          }
                        >
                          <option value="none">none</option>
                          <option value="query">extract_query</option>
                          <option value="content">extract_content</option>
                        </select>
                      </label>
                    </>
                  ) : null}

                  {formState.actionType === "workflow" ? (
                    <label className="block text-xs text-text-muted">
                      {t("sidepanel:personaGarden.commands.workflowId", {
                        defaultValue: "Workflow id"
                      })}
                      <input
                        data-testid="persona-commands-target-input"
                        className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                        value={formState.workflowId}
                        onChange={(event) =>
                          updateFormField("workflowId", event.target.value)
                        }
                        placeholder="daily-research-digest"
                      />
                    </label>
                  ) : null}

                  {formState.actionType === "custom" ? (
                    <div className="space-y-3">
                      {selectedConnectionMissing ? (
                        <div className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-700">
                          {t("sidepanel:personaGarden.commands.missingConnectionWarning", {
                            defaultValue:
                              "Selected connection no longer exists. Choose another connection or clear it."
                          })}
                        </div>
                      ) : null}
                      <label className="block text-xs text-text-muted">
                        {t("sidepanel:personaGarden.commands.customAction", {
                          defaultValue: "Custom action"
                        })}
                        <input
                          data-testid="persona-commands-custom-action-input"
                          className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                          value={formState.customAction}
                          onChange={(event) =>
                            updateFormField("customAction", event.target.value)
                          }
                          placeholder={
                            formState.connectionId
                              ? "external_request"
                              : "help"
                          }
                        />
                      </label>

                      {formState.connectionId ? (
                        <div className="space-y-3 rounded-md border border-sky-500/30 bg-sky-500/10 px-3 py-3">
                          <div className="text-xs text-sky-900">
                            {t("sidepanel:personaGarden.commands.externalRequestHint", {
                              defaultValue:
                                "This command will call the selected connection directly. Leave request path blank to call the connection base URL."
                            })}
                          </div>
                          <div className="grid gap-3 md:grid-cols-[minmax(0,140px)_minmax(0,1fr)]">
                            <label className="block text-xs text-text-muted">
                              {t("sidepanel:personaGarden.commands.httpMethod", {
                                defaultValue: "HTTP method"
                              })}
                              <select
                                data-testid="persona-commands-http-method-select"
                                className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                                value={formState.requestMethod}
                                onChange={(event) =>
                                  updateFormField(
                                    "requestMethod",
                                    event.target.value as CommandFormState["requestMethod"]
                                  )
                                }
                              >
                                {REQUEST_METHODS.map((method) => (
                                  <option key={method} value={method}>
                                    {method}
                                  </option>
                                ))}
                              </select>
                            </label>

                            <label className="block text-xs text-text-muted">
                              {t("sidepanel:personaGarden.commands.requestPath", {
                                defaultValue: "Request path"
                              })}
                              <input
                                data-testid="persona-commands-request-path-input"
                                className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                                value={formState.requestPath}
                                onChange={(event) =>
                                  updateFormField("requestPath", event.target.value)
                                }
                                placeholder="alerts/search"
                              />
                            </label>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {formState.actionType === "llm_chat" ? (
                    <div className="rounded-md border border-border bg-surface px-3 py-2 text-xs text-text-muted">
                      {t("sidepanel:personaGarden.commands.llmChatNote", {
                        defaultValue:
                          "LLM chat commands hand the utterance to the persona planner rather than a direct tool target."
                      })}
                    </div>
                  ) : null}

                  <details className="rounded-md border border-border bg-surface px-3 py-2">
                    <summary className="cursor-pointer text-xs font-medium text-text">
                      {t("sidepanel:personaGarden.commands.advanced", {
                        defaultValue: "Advanced mappings"
                      })}
                    </summary>
                    <div className="mt-3 space-y-3">
                      <label className="block text-xs text-text-muted">
                        {t("sidepanel:personaGarden.commands.slotMap", {
                          defaultValue: "Slot to param map (JSON)"
                        })}
                        <textarea
                          data-testid="persona-commands-slot-map-input"
                          className="mt-1 min-h-[96px] w-full rounded-md border border-border bg-bg px-2 py-1 text-sm text-text"
                          value={formState.slotMapText}
                          onChange={(event) =>
                            updateFormField("slotMapText", event.target.value)
                          }
                        />
                      </label>
                      <label className="block text-xs text-text-muted">
                        {t("sidepanel:personaGarden.commands.defaultPayload", {
                          defaultValue: "Default payload (JSON)"
                        })}
                        <textarea
                          data-testid="persona-commands-default-payload-input"
                          className="mt-1 min-h-[96px] w-full rounded-md border border-border bg-bg px-2 py-1 text-sm text-text"
                          value={formState.defaultPayloadText}
                          onChange={(event) =>
                            updateFormField(
                              "defaultPayloadText",
                              event.target.value
                            )
                          }
                        />
                      </label>
                    </div>
                  </details>

                  <div className="grid gap-3 md:grid-cols-2">
                    <label className="block text-xs text-text-muted">
                      {t("sidepanel:personaGarden.commands.priority", {
                        defaultValue: "Priority"
                      })}
                      <input
                        data-testid="persona-commands-priority-input"
                        className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                        value={formState.priority}
                        onChange={(event) =>
                          updateFormField("priority", event.target.value)
                        }
                        inputMode="numeric"
                        placeholder="50"
                      />
                    </label>
                    <div className="grid gap-2 text-xs text-text-muted">
                      <label className="flex items-center gap-2">
                        <input
                          data-testid="persona-commands-enabled-toggle"
                          type="checkbox"
                          checked={formState.enabled}
                          onChange={(event) =>
                            updateFormField("enabled", event.target.checked)
                          }
                        />
                        {t("sidepanel:personaGarden.commands.enabled", {
                          defaultValue: "Enabled"
                        })}
                      </label>
                      <label className="flex items-center gap-2">
                        <input
                          data-testid="persona-commands-confirmation-toggle"
                          type="checkbox"
                          checked={formState.requiresConfirmation}
                          onChange={(event) =>
                            updateFormField(
                              "requiresConfirmation",
                              event.target.checked
                            )
                          }
                        />
                        {t("sidepanel:personaGarden.commands.requireConfirmation", {
                          defaultValue: "Require confirmation"
                        })}
                      </label>
                    </div>
                  </div>

                  {formState.connectionId ? (
                    formState.actionType === "custom" ? null : (
                      <div className="rounded-md border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-800">
                        {t("sidepanel:personaGarden.commands.connectionHint", {
                          defaultValue:
                            "Connection-backed live execution is configured through custom commands. Switch to custom to define the HTTP request for this connection."
                        })}
                      </div>
                    )
                  ) : null}

                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      data-testid="persona-commands-save"
                      className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={saving}
                      onClick={() => {
                        void handleSave()
                      }}
                    >
                      {saving
                        ? t("common:saving", "Saving...")
                        : formState.commandId
                          ? t("common:update", "Update")
                          : t("common:create", "Create")}
                    </button>
                    <button
                      type="button"
                      className="rounded-md border border-border px-3 py-2 text-sm text-text transition hover:bg-surface2"
                      onClick={resetForm}
                    >
                      {t("common:clear", "Clear")}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
