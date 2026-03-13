import React from "react"
import { useTranslation } from "react-i18next"

import { tldwClient } from "@/services/tldw/TldwApiClient"

type PersonaCommandDryRunResult = {
  heard_text: string
  matched: boolean
  match_reason?: string | null
  command_id?: string | null
  command_name?: string | null
  connection_id?: string | null
  connection_status?: "ok" | "missing" | null
  connection_name?: string | null
  extracted_params?: Record<string, unknown>
  planned_action?: {
    target_type: string
    target_name?: string | null
    payload_preview?: Record<string, unknown>
  } | null
  safety_gate?: {
    classification: string
    requires_confirmation: boolean
    reason: string
  } | null
  fallback_to_persona_planner?: boolean
  failure_phase?: string | null
}

type TestLabPanelProps = {
  selectedPersonaId: string
  selectedPersonaName: string
  isActive?: boolean
  onOpenCommand?: (commandId: string, heardText: string) => void
  initialHeardText?: string
  rerunRequestToken?: number
}

const prettyJson = (value: unknown): string =>
  JSON.stringify(value && typeof value === "object" ? value : {}, null, 2)

export const TestLabPanel: React.FC<TestLabPanelProps> = ({
  selectedPersonaId,
  selectedPersonaName,
  isActive = false,
  onOpenCommand,
  initialHeardText = "",
  rerunRequestToken = 0
}) => {
  const { t } = useTranslation(["sidepanel", "common"])
  const [heardText, setHeardText] = React.useState(initialHeardText)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [result, setResult] = React.useState<PersonaCommandDryRunResult | null>(null)
  const [rerunNoticeVisible, setRerunNoticeVisible] = React.useState(false)
  const [repairConfirmedVisible, setRepairConfirmedVisible] = React.useState(false)
  const hasMissingConnection = Boolean(
    result &&
      (result.connection_status === "missing" ||
        result.failure_phase === "missing_connection")
  )

  React.useEffect(() => {
    if (!isActive) return
    setError(null)
  }, [isActive])

  React.useEffect(() => {
    setHeardText((current) =>
      current === initialHeardText ? current : initialHeardText
    )
  }, [initialHeardText])

  const runDryRun = React.useCallback(async (
    nextHeardText: string,
    options?: { source?: "manual" | "rerun" }
  ) => {
    const trimmed = nextHeardText.trim()
    if (!selectedPersonaId || !trimmed) return
    const source = options?.source || "manual"
    if (source !== "rerun") {
      setRepairConfirmedVisible(false)
    }
    setLoading(true)
    setError(null)
    try {
      const response = await tldwClient.fetchWithAuth(
        `/api/v1/persona/profiles/${encodeURIComponent(selectedPersonaId)}/voice-commands/test` as any,
        {
          method: "POST",
          body: { heard_text: trimmed }
        }
      )
      if (!response.ok) {
        throw new Error(response.error || "Failed to run voice command dry-run.")
      }
      const payload = (await response.json()) as PersonaCommandDryRunResult
      setResult(payload)
      if (
        source === "rerun" &&
        payload.matched &&
        payload.connection_status !== "missing" &&
        payload.failure_phase !== "missing_connection"
      ) {
        setRepairConfirmedVisible(true)
      } else {
        setRepairConfirmedVisible(false)
      }
    } catch (runError) {
      setResult(null)
      setRepairConfirmedVisible(false)
      setError(
        runError instanceof Error
          ? runError.message
          : "Failed to run voice command dry-run."
      )
    } finally {
      setRerunNoticeVisible(false)
      setLoading(false)
    }
  }, [selectedPersonaId])

  React.useEffect(() => {
    if (!isActive || !selectedPersonaId || rerunRequestToken <= 0) return
    const nextHeardText = String(initialHeardText || heardText).trim()
    if (!nextHeardText) return
    setHeardText(nextHeardText)
    setRerunNoticeVisible(true)
    setRepairConfirmedVisible(false)
    void runDryRun(nextHeardText, { source: "rerun" })
  }, [
    heardText,
    initialHeardText,
    isActive,
    rerunRequestToken,
    runDryRun,
    selectedPersonaId
  ])

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
        {t("sidepanel:personaGarden.testLab.heading", {
          defaultValue: "Test Lab"
        })}
      </div>
      <div className="mt-2 space-y-3 text-sm text-text">
        <p className="text-xs text-text-muted">
          {selectedPersonaId
            ? t("sidepanel:personaGarden.testLab.description", {
                defaultValue:
                  "Type a spoken phrase for {{personaName}} to inspect matching, slot extraction, planned action, and safety gates before running it live.",
                personaName:
                  selectedPersonaName ||
                  selectedPersonaId ||
                  t("sidepanel:personaGarden.testLab.currentPersona", {
                    defaultValue: "this persona"
                  })
              })
            : t("sidepanel:personaGarden.testLab.noPersona", {
                defaultValue:
                  "Select a persona to test how spoken commands will resolve."
              })}
        </p>

        {error ? (
          <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        ) : null}
        {rerunNoticeVisible ? (
          <div className="rounded-md border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs text-sky-700">
            {t("sidepanel:personaGarden.testLab.rerunningNotice", {
              defaultValue: "Rerunning last phrase..."
            })}
          </div>
        ) : null}
        {repairConfirmedVisible ? (
          <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-700">
            <div>
              {t("sidepanel:personaGarden.testLab.repairConfirmedNotice", {
                defaultValue: "Repair confirmed. The last phrase now resolves cleanly."
              })}
            </div>
            {result?.command_id && onOpenCommand ? (
              <button
                type="button"
                data-testid="persona-test-lab-repair-open-command"
                className="mt-2 rounded-md border border-emerald-500/40 bg-white/60 px-2 py-1 text-xs font-medium text-emerald-700 transition hover:bg-white/80"
                onClick={() =>
                  onOpenCommand(
                    result.command_id as string,
                    String(result.heard_text || heardText).trim()
                  )
                }
              >
                {t("sidepanel:personaGarden.testLab.repairOpenCommand", {
                  defaultValue: "Back to Commands"
                })}
              </button>
            ) : null}
          </div>
        ) : null}

        {selectedPersonaId ? (
          <>
            <label className="block text-xs text-text-muted">
              {t("sidepanel:personaGarden.testLab.heardText", {
                defaultValue: "Heard text"
              })}
              <textarea
                data-testid="persona-test-lab-heard-input"
                className="mt-1 min-h-[88px] w-full rounded-md border border-border bg-bg px-2 py-1 text-sm text-text"
                value={heardText}
                onChange={(event) => {
                  setHeardText(event.target.value)
                  setRepairConfirmedVisible(false)
                }}
                placeholder="search notes for model context protocol"
              />
            </label>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                data-testid="persona-test-lab-run"
                className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={loading || heardText.trim().length === 0}
                onClick={() => {
                  void runDryRun(heardText, { source: "manual" })
                }}
              >
                {loading
                  ? t("sidepanel:personaGarden.testLab.running", {
                      defaultValue: "Running..."
                    })
                  : t("sidepanel:personaGarden.testLab.run", {
                      defaultValue: "Run dry-run"
                    })}
              </button>
              <button
                type="button"
                className="rounded-md border border-border px-3 py-2 text-sm text-text transition hover:bg-surface2"
                onClick={() => {
                  setHeardText("")
                  setResult(null)
                  setError(null)
                  setRerunNoticeVisible(false)
                  setRepairConfirmedVisible(false)
                }}
              >
                {t("common:clear", "Clear")}
              </button>
            </div>

            {result ? (
              <div className="space-y-3 rounded-md border border-border bg-bg p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-text">
                    {result.matched
                      ? t("sidepanel:personaGarden.testLab.matched", {
                          defaultValue: "Matched"
                        })
                      : t("sidepanel:personaGarden.testLab.noMatch", {
                          defaultValue: "No direct match"
                        })}
                  </span>
                  <span
                    data-testid="persona-test-lab-match-status"
                    className={`rounded-full border px-2 py-0.5 text-[11px] ${
                      result.matched
                        ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700"
                        : "border-amber-500/40 bg-amber-500/10 text-amber-700"
                    }`}
                  >
                    {result.matched ? "direct command" : "persona fallback"}
                  </span>
                  {result.fallback_to_persona_planner ? (
                    <span className="rounded-full border border-border px-2 py-0.5 text-[11px] text-text-muted">
                      {t("sidepanel:personaGarden.testLab.fallback", {
                        defaultValue: "planner fallback"
                      })}
                    </span>
                  ) : null}
                  {hasMissingConnection ? (
                    <span className="rounded-full border border-red-500/40 bg-red-500/10 px-2 py-0.5 text-[11px] text-red-700">
                      {t("sidepanel:personaGarden.testLab.missingConnectionBadge", {
                        defaultValue: "broken connection"
                      })}
                    </span>
                  ) : null}
                </div>

                {hasMissingConnection ? (
                  <div className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-700">
                    <div>
                      {t("sidepanel:personaGarden.testLab.missingConnectionWarning", {
                        defaultValue:
                          "This command matched, but its saved connection was deleted. Edit the command in Commands to choose a replacement connection."
                      })}
                    </div>
                    {result?.command_id && onOpenCommand ? (
                      <button
                        type="button"
                        data-testid="persona-test-lab-open-command"
                        className="mt-2 rounded-md border border-red-500/40 bg-white/60 px-2 py-1 text-xs font-medium text-red-700 transition hover:bg-white/80"
                        onClick={() =>
                          onOpenCommand(
                            result.command_id as string,
                            String(result.heard_text || heardText).trim()
                          )
                        }
                      >
                        {t("sidepanel:personaGarden.testLab.openInCommands", {
                          defaultValue: "Open in Commands"
                        })}
                      </button>
                    ) : null}
                  </div>
                ) : null}

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-md border border-border bg-surface p-3">
                    <div className="text-xs font-medium uppercase tracking-wide text-text-subtle">
                      {t("sidepanel:personaGarden.testLab.matching", {
                        defaultValue: "Matching"
                      })}
                    </div>
                    <div className="mt-2 space-y-1 text-sm text-text">
                      <div>{result.heard_text}</div>
                      {result.command_name ? (
                        <div className="text-xs text-text-muted">
                          {t("sidepanel:personaGarden.testLab.commandName", {
                            defaultValue: "Command: {{name}}",
                            name: result.command_name
                          })}
                        </div>
                      ) : null}
                      {result.match_reason ? (
                        <div className="text-xs text-text-muted">
                          {t("sidepanel:personaGarden.testLab.matchReason", {
                            defaultValue: "Reason: {{reason}}",
                            reason: result.match_reason
                          })}
                        </div>
                      ) : null}
                      {result.connection_status === "missing" ? (
                        <div className="text-xs text-red-700">
                          {t("sidepanel:personaGarden.testLab.connectionMissing", {
                            defaultValue: `Connection missing: ${
                              result.connection_id || "unknown connection"
                            }`
                          })}
                        </div>
                      ) : null}
                      {result.connection_status === "ok" && result.connection_name ? (
                        <div className="text-xs text-text-muted">
                          {t("sidepanel:personaGarden.testLab.connectionName", {
                            defaultValue: `Connection: ${result.connection_name}`
                          })}
                        </div>
                      ) : null}
                      {result.failure_phase ? (
                        <div className="text-xs text-text-muted">
                          {t("sidepanel:personaGarden.testLab.failurePhase", {
                            defaultValue: "Failure phase: {{phase}}",
                            phase: result.failure_phase
                          })}
                        </div>
                      ) : null}
                    </div>
                  </div>

                  <div className="rounded-md border border-border bg-surface p-3">
                    <div className="text-xs font-medium uppercase tracking-wide text-text-subtle">
                      {t("sidepanel:personaGarden.testLab.safety", {
                        defaultValue: "Safety gate"
                      })}
                    </div>
                    {result.safety_gate ? (
                      <div className="mt-2 space-y-1 text-sm text-text">
                        <div>{result.safety_gate.classification}</div>
                        <div className="text-xs text-text-muted">
                          {result.safety_gate.requires_confirmation
                            ? t("sidepanel:personaGarden.testLab.confirmationRequired", {
                                defaultValue: "Confirmation required"
                              })
                            : t("sidepanel:personaGarden.testLab.noConfirmation", {
                                defaultValue: "No confirmation required"
                              })}
                        </div>
                        <div className="text-xs text-text-muted">
                          {t("sidepanel:personaGarden.testLab.safetyReason", {
                            defaultValue: "Reason: {{reason}}",
                            reason: result.safety_gate.reason
                          })}
                        </div>
                      </div>
                    ) : (
                      <div className="mt-2 text-xs text-text-muted">
                        {t("sidepanel:personaGarden.testLab.noSafetyGate", {
                          defaultValue: "No safety gate was returned."
                        })}
                      </div>
                    )}
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-md border border-border bg-surface p-3">
                    <div className="text-xs font-medium uppercase tracking-wide text-text-subtle">
                      {t("sidepanel:personaGarden.testLab.extractedParams", {
                        defaultValue: "Extracted params"
                      })}
                    </div>
                    <pre
                      data-testid="persona-test-lab-extracted-params"
                      className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs text-text-muted"
                    >
                      {prettyJson(result.extracted_params || {})}
                    </pre>
                  </div>

                  <div className="rounded-md border border-border bg-surface p-3">
                    <div className="text-xs font-medium uppercase tracking-wide text-text-subtle">
                      {t("sidepanel:personaGarden.testLab.plannedAction", {
                        defaultValue: "Planned action"
                      })}
                    </div>
                    {result.planned_action ? (
                      <div className="mt-2 space-y-2">
                        <div className="text-sm text-text">
                          {result.planned_action.target_type}
                          {result.planned_action.target_name
                            ? ` -> ${result.planned_action.target_name}`
                            : ""}
                        </div>
                        <pre
                          data-testid="persona-test-lab-payload-preview"
                          className="overflow-x-auto whitespace-pre-wrap text-xs text-text-muted"
                        >
                          {prettyJson(
                            result.planned_action.payload_preview || {}
                          )}
                        </pre>
                      </div>
                    ) : (
                      <div className="mt-2 text-xs text-text-muted">
                        {t("sidepanel:personaGarden.testLab.noPlannedAction", {
                          defaultValue: "No deterministic action was planned."
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  )
}
