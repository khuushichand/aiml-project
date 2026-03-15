import React from "react"

import type { PersonaConfirmationMode } from "@/hooks/useResolvedPersonaVoiceDefaults"

export type SetupSafetyConnectionDraft = {
  name: string
  baseUrl: string
  authType: string
  secret: string
}

type SetupUrlValidation = {
  error: string | null
  note: string | null
}

type SetupSafetyConnectionsStepSubmit =
  | {
      confirmationMode: PersonaConfirmationMode
      connectionMode: "none"
    }
  | {
      confirmationMode: PersonaConfirmationMode
      connectionMode: "create"
      connection: SetupSafetyConnectionDraft
    }

type SetupSafetyConnectionsStepProps = {
  saving: boolean
  error?: string | null
  currentConfirmationMode?: PersonaConfirmationMode | null
  onContinue: (payload: SetupSafetyConnectionsStepSubmit) => void
}

const CONFIRMATION_OPTIONS: Array<{
  value: PersonaConfirmationMode
  label: string
  description: string
}> = [
  {
    value: "always",
    label: "Always ask before actions",
    description: "Require approval before every tool-backed action."
  },
  {
    value: "destructive_only",
    label: "Ask for destructive actions",
    description: "Only stop for actions that may change or delete data."
  },
  {
    value: "never",
    label: "Never ask",
    description: "Run matched commands immediately without an approval pause."
  }
]

const formatConfirmationMode = (
  mode?: PersonaConfirmationMode | null
): string => {
  if (mode === "always") return "Always ask before actions"
  if (mode === "never") return "Never ask"
  return "Ask for destructive actions"
}

const validateSetupConnectionUrl = (rawValue: string): SetupUrlValidation => {
  const trimmed = String(rawValue || "").trim()
  if (!trimmed) {
    return {
      error: null,
      note: null
    }
  }

  let parsed: URL
  try {
    parsed = new URL(trimmed)
  } catch {
    return {
      error: "Enter a valid http or https URL.",
      note: null
    }
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return {
      error: "Enter a valid http or https URL.",
      note: null
    }
  }

  const hasEndpointDetails =
    parsed.pathname !== "/" || Boolean(parsed.search) || Boolean(parsed.hash)

  return {
    error: null,
    note: hasEndpointDetails
      ? "This endpoint includes a path, query, or fragment, which is common for webhook-style integrations."
      : "URL looks valid."
  }
}

export const SetupSafetyConnectionsStep: React.FC<
  SetupSafetyConnectionsStepProps
> = ({ saving, error = null, currentConfirmationMode, onContinue }) => {
  const [confirmationMode, setConfirmationMode] =
    React.useState<PersonaConfirmationMode | null>(null)
  const [connectionMode, setConnectionMode] = React.useState<"none" | "create" | null>(
    null
  )
  const [connectionName, setConnectionName] = React.useState("")
  const [connectionBaseUrl, setConnectionBaseUrl] = React.useState("")
  const [connectionAuthType, setConnectionAuthType] = React.useState("none")
  const [connectionSecret, setConnectionSecret] = React.useState("")

  const urlValidation = React.useMemo(
    () => validateSetupConnectionUrl(connectionBaseUrl),
    [connectionBaseUrl]
  )
  const authHint = React.useMemo(() => {
    if (connectionMode !== "create") return null
    if (connectionAuthType === "bearer" && !String(connectionSecret || "").trim()) {
      return "This connection will be created without a bearer token. You can add one later in Connections."
    }
    if (connectionAuthType === "none") {
      return "No authentication selected. Use this only for public endpoints."
    }
    return null
  }, [connectionAuthType, connectionMode, connectionSecret])
  const connectionRetryHint =
    error &&
    connectionMode === "create" &&
    /connection/i.test(error)
      ? "Fix the connection details below and try again, or skip external connections for now."
      : null

  const canContinue =
    confirmationMode !== null &&
    connectionMode !== null &&
    (connectionMode === "none" ||
      (String(connectionName || "").trim().length > 0 &&
        String(connectionBaseUrl || "").trim().length > 0 &&
        urlValidation.error === null))

  const handleContinue = React.useCallback(() => {
    if (!confirmationMode || !connectionMode) return
    if (connectionMode === "create") {
      const name = String(connectionName || "").trim()
      const baseUrl = String(connectionBaseUrl || "").trim()
      if (!name || !baseUrl) return
      onContinue({
        confirmationMode,
        connectionMode,
        connection: {
          name,
          baseUrl,
          authType: String(connectionAuthType || "none").trim() || "none",
          secret: String(connectionSecret || "").trim()
        }
      })
      return
    }
    onContinue({
      confirmationMode,
      connectionMode: "none"
    })
  }, [
    confirmationMode,
    connectionAuthType,
    connectionBaseUrl,
    connectionMode,
    connectionName,
    connectionSecret,
    onContinue
  ])

  return (
    <div className="space-y-3">
      <div>
        <div className="text-sm font-semibold text-text">Safety and connections</div>
        <div className="text-xs text-text-muted">
          Choose how often the assistant should stop for approval, then decide
          whether to add an external connection now.
        </div>
        {currentConfirmationMode ? (
          <div className="mt-2 text-xs text-text-muted">
            Current default: {formatConfirmationMode(currentConfirmationMode)}
          </div>
        ) : null}
      </div>
      {error ? (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
          <div>{error}</div>
          {connectionRetryHint ? (
            <div className="mt-1 text-xs text-red-100">{connectionRetryHint}</div>
          ) : null}
        </div>
      ) : null}

      <div className="space-y-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-text-subtle">
          Approval behavior
        </div>
        {CONFIRMATION_OPTIONS.map((option) => {
          const selected = confirmationMode === option.value
          return (
            <button
              key={option.value}
              type="button"
              aria-label={option.label}
              aria-pressed={selected}
              data-selected={selected ? "true" : "false"}
              disabled={saving}
              className="flex w-full items-start justify-between rounded-lg border border-border bg-surface2 px-3 py-3 text-left disabled:cursor-not-allowed disabled:opacity-60"
              onClick={() => setConfirmationMode(option.value)}
            >
              <div>
                <div className="text-sm font-medium text-text">{option.label}</div>
                <div className="mt-1 text-xs text-text-muted">{option.description}</div>
              </div>
            </button>
          )
        })}
      </div>

      <div className="space-y-2">
        <div className="text-xs font-semibold uppercase tracking-wide text-text-subtle">
          External connections
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          <button
            type="button"
            aria-label="No external connections for now"
            aria-pressed={connectionMode === "none"}
            data-selected={connectionMode === "none" ? "true" : "false"}
            disabled={saving}
            className="rounded-lg border border-border bg-surface2 px-3 py-3 text-left disabled:cursor-not-allowed disabled:opacity-60"
            onClick={() => setConnectionMode("none")}
          >
            <div className="text-sm font-medium text-text">
              No external connections for now
            </div>
            <div className="mt-1 text-xs text-text-muted">
              Skip API hooks for now and keep setup focused on built-in tools.
            </div>
          </button>
          <button
            type="button"
            aria-label="Add one connection now"
            aria-pressed={connectionMode === "create"}
            data-selected={connectionMode === "create" ? "true" : "false"}
            disabled={saving}
            className="rounded-lg border border-border bg-surface2 px-3 py-3 text-left disabled:cursor-not-allowed disabled:opacity-60"
            onClick={() => setConnectionMode("create")}
          >
            <div className="text-sm font-medium text-text">Add one connection now</div>
            <div className="mt-1 text-xs text-text-muted">
              Create a lightweight API connection now and manage the rest later.
            </div>
          </button>
        </div>
      </div>

      {connectionMode === "create" ? (
        <div className="space-y-2 rounded-lg border border-border bg-surface2 p-3">
          <input
            type="text"
            value={connectionName}
            aria-label="Connection name"
            placeholder="Connection name"
            className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text"
            onChange={(event) => setConnectionName(event.target.value)}
          />
          <input
            type="text"
            value={connectionBaseUrl}
            aria-label="Base URL"
            placeholder="Base URL"
            className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text"
            onChange={(event) => setConnectionBaseUrl(event.target.value)}
          />
          {urlValidation.error ? (
            <div className="text-xs text-red-200">{urlValidation.error}</div>
          ) : urlValidation.note ? (
            <div className="text-xs text-text-muted">{urlValidation.note}</div>
          ) : null}
          <label className="block text-xs text-text-muted">
            Authentication
            <select
              aria-label="Authentication"
              value={connectionAuthType}
              className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text"
              onChange={(event) => setConnectionAuthType(event.target.value)}
            >
              <option value="none">None</option>
              <option value="bearer">Bearer token</option>
            </select>
          </label>
          <input
            type="password"
            value={connectionSecret}
            aria-label="Connection secret"
            placeholder="Secret (optional)"
            className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-text"
            onChange={(event) => setConnectionSecret(event.target.value)}
          />
          {authHint ? (
            <div className="text-xs text-text-muted">{authHint}</div>
          ) : null}
        </div>
      ) : null}

      <button
        type="button"
        className="rounded-md border border-border px-3 py-2 text-sm font-medium text-text disabled:cursor-not-allowed disabled:opacity-60"
        disabled={saving || !canContinue}
        onClick={handleContinue}
      >
        {connectionMode === "create"
          ? "Save safety and connection"
          : "Save safety choices"}
      </button>
    </div>
  )
}
