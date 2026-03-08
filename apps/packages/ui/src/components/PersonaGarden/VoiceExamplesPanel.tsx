import React from "react"
import { useTranslation } from "react-i18next"

import {
  type PersonaExemplar,
  tldwClient
} from "@/services/tldw/TldwApiClient"

type VoiceExamplesPanelProps = {
  selectedPersonaId: string
  selectedPersonaName: string
  isActive?: boolean
}

type VoiceExampleFormState = {
  exemplarId: string | null
  kind: string
  content: string
  tone: string
  scenarioTags: string
  capabilityTags: string
  priority: string
  enabled: boolean
}

const DEFAULT_FORM_STATE: VoiceExampleFormState = {
  exemplarId: null,
  kind: "style",
  content: "",
  tone: "",
  scenarioTags: "",
  capabilityTags: "",
  priority: "0",
  enabled: true
}

const parseTags = (value: string): string[] =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0)

const toFormState = (exemplar?: PersonaExemplar | null): VoiceExampleFormState => {
  if (!exemplar) {
    return { ...DEFAULT_FORM_STATE }
  }
  return {
    exemplarId: exemplar.id,
    kind: exemplar.kind || "style",
    content: exemplar.content || "",
    tone: exemplar.tone || "",
    scenarioTags: (exemplar.scenario_tags || []).join(", "),
    capabilityTags: (exemplar.capability_tags || []).join(", "),
    priority: String(exemplar.priority ?? 0),
    enabled: exemplar.enabled !== false
  }
}

export const VoiceExamplesPanel: React.FC<VoiceExamplesPanelProps> = ({
  selectedPersonaId,
  selectedPersonaName,
  isActive = false
}) => {
  const { t } = useTranslation(["sidepanel", "common"])
  const [exemplars, setExemplars] = React.useState<PersonaExemplar[]>([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [filterKind, setFilterKind] = React.useState("all")
  const [filterTone, setFilterTone] = React.useState("")
  const [formState, setFormState] =
    React.useState<VoiceExampleFormState>(DEFAULT_FORM_STATE)
  const [validationError, setValidationError] = React.useState<string | null>(
    null
  )
  const [saving, setSaving] = React.useState(false)

  React.useEffect(() => {
    let cancelled = false

    const load = async () => {
      if (!isActive || !selectedPersonaId) {
        setExemplars([])
        setError(null)
        return
      }

      setLoading(true)
      setError(null)
      try {
        const rows = await tldwClient.listPersonaExemplars(selectedPersonaId)
        if (!cancelled) {
          setExemplars(rows)
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : t("sidepanel:personaGarden.voiceExamples.loadError", {
                  defaultValue: "Failed to load persona examples."
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

  const filteredExemplars = exemplars.filter((exemplar) => {
    if (filterKind !== "all" && exemplar.kind !== filterKind) {
      return false
    }
    if (
      filterTone.trim() &&
      !(exemplar.tone || "")
        .toLowerCase()
        .includes(filterTone.trim().toLowerCase())
    ) {
      return false
    }
    return true
  })

  const handleFieldChange = (
    field: keyof VoiceExampleFormState,
    value: string | boolean
  ) => {
    setFormState((current) => ({
      ...current,
      [field]: value
    }))
  }

  const handleEdit = (exemplar: PersonaExemplar) => {
    setFormState(toFormState(exemplar))
    setValidationError(null)
  }

  const handleReset = () => {
    setFormState({ ...DEFAULT_FORM_STATE })
    setValidationError(null)
  }

  const handleSave = async () => {
    if (!selectedPersonaId) {
      return
    }
    if (!formState.content.trim()) {
      setValidationError(
        t("sidepanel:personaGarden.voiceExamples.validationContent", {
          defaultValue: "Content is required"
        })
      )
      return
    }

    setSaving(true)
    setValidationError(null)
    setError(null)

    const payload = {
      kind: formState.kind,
      content: formState.content.trim(),
      tone: formState.tone.trim() || null,
      scenario_tags: parseTags(formState.scenarioTags),
      capability_tags: parseTags(formState.capabilityTags),
      priority: Number.parseInt(formState.priority, 10) || 0,
      enabled: formState.enabled
    }

    try {
      if (formState.exemplarId) {
        const updated = await tldwClient.updatePersonaExemplar(
          selectedPersonaId,
          formState.exemplarId,
          payload
        )
        setExemplars((current) =>
          current.map((item) => (item.id === updated.id ? updated : item))
        )
      } else {
        const created = await tldwClient.createPersonaExemplar(
          selectedPersonaId,
          payload
        )
        setExemplars((current) => [...current, created])
      }
      handleReset()
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : t("sidepanel:personaGarden.voiceExamples.saveError", {
              defaultValue: "Failed to save persona example."
            })
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
        {t("sidepanel:personaGarden.voiceExamples.heading", {
          defaultValue: "Voice & Examples"
        })}
      </div>
      <div className="mt-2 space-y-3 text-sm text-text">
        <p className="text-xs text-text-muted">
          {selectedPersonaId
            ? t("sidepanel:personaGarden.voiceExamples.description", {
                defaultValue:
                  "Curate style, boundary, and scenario exemplars for {{personaName}}.",
                personaName:
                  selectedPersonaName ||
                  selectedPersonaId ||
                  t("sidepanel:personaGarden.voiceExamples.currentPersona", {
                    defaultValue: "this persona"
                  })
              })
            : t("sidepanel:personaGarden.voiceExamples.noPersona", {
                defaultValue:
                  "Select a persona to manage its voice and example bank."
              })}
        </p>

        {selectedPersonaId ? (
          <>
            <div className="grid gap-2 md:grid-cols-2">
              <label className="text-xs text-text-muted">
                {t("sidepanel:personaGarden.voiceExamples.filterKind", {
                  defaultValue: "Filter by kind"
                })}
                <select
                  data-testid="voice-examples-kind-filter"
                  className="mt-1 w-full rounded-md border border-border bg-bg px-2 py-1 text-sm text-text"
                  value={filterKind}
                  onChange={(event) => setFilterKind(event.target.value)}
                >
                  <option value="all">
                    {t("sidepanel:personaGarden.voiceExamples.filterAllKinds", {
                      defaultValue: "All kinds"
                    })}
                  </option>
                  <option value="style">style</option>
                  <option value="boundary">boundary</option>
                  <option value="catchphrase">catchphrase</option>
                  <option value="scenario_demo">scenario_demo</option>
                  <option value="tool_behavior">tool_behavior</option>
                </select>
              </label>
              <label className="text-xs text-text-muted">
                {t("sidepanel:personaGarden.voiceExamples.filterTone", {
                  defaultValue: "Filter by tone"
                })}
                <input
                  data-testid="voice-examples-tone-filter"
                  className="mt-1 w-full rounded-md border border-border bg-bg px-2 py-1 text-sm text-text"
                  value={filterTone}
                  onChange={(event) => setFilterTone(event.target.value)}
                  placeholder={t(
                    "sidepanel:personaGarden.voiceExamples.filterTonePlaceholder",
                    {
                      defaultValue: "e.g. neutral"
                    }
                  )}
                />
              </label>
            </div>

            <div className="space-y-2">
              {loading ? (
                <div className="text-xs text-text-muted">
                  {t("sidepanel:personaGarden.voiceExamples.loading", {
                    defaultValue: "Loading examples..."
                  })}
                </div>
              ) : filteredExemplars.length > 0 ? (
                filteredExemplars.map((exemplar) => (
                  <div
                    key={exemplar.id}
                    className="rounded-md border border-border bg-bg p-2"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
                        <span>{exemplar.kind}</span>
                        {exemplar.tone ? <span>{exemplar.tone}</span> : null}
                        {!exemplar.enabled ? (
                          <span
                            data-testid={`voice-examples-disabled-${exemplar.id}`}
                            className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-700"
                          >
                            {t(
                              "sidepanel:personaGarden.voiceExamples.disabledBadge",
                              {
                                defaultValue: "Disabled"
                              }
                            )}
                          </span>
                        ) : null}
                      </div>
                      <button
                        type="button"
                        data-testid={`voice-examples-edit-${exemplar.id}`}
                        className="rounded-md border border-border px-2 py-1 text-xs text-text hover:bg-surface2"
                        onClick={() => handleEdit(exemplar)}
                      >
                        {t("common:edit", { defaultValue: "Edit" })}
                      </button>
                    </div>
                    <div className="mt-2 text-sm text-text">{exemplar.content}</div>
                    <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-text-muted">
                      {(exemplar.scenario_tags || []).map((tag) => (
                        <span key={`${exemplar.id}-scenario-${tag}`}>
                          {tag}
                        </span>
                      ))}
                      {(exemplar.capability_tags || []).map((tag) => (
                        <span key={`${exemplar.id}-capability-${tag}`}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-md border border-dashed border-border p-3 text-xs text-text-muted">
                  {t("sidepanel:personaGarden.voiceExamples.empty", {
                    defaultValue: "No exemplars match the current filters."
                  })}
                </div>
              )}
            </div>

            <div className="rounded-md border border-border bg-bg p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-text-subtle">
                  {formState.exemplarId
                    ? t("sidepanel:personaGarden.voiceExamples.editHeading", {
                        defaultValue: "Edit exemplar"
                      })
                    : t("sidepanel:personaGarden.voiceExamples.createHeading", {
                        defaultValue: "Create exemplar"
                      })}
                </div>
                <button
                  type="button"
                  className="rounded-md border border-border px-2 py-1 text-xs text-text hover:bg-surface2"
                  onClick={handleReset}
                >
                  {t("sidepanel:personaGarden.voiceExamples.reset", {
                    defaultValue: "Reset"
                  })}
                </button>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                <label className="text-xs text-text-muted">
                  {t("sidepanel:personaGarden.voiceExamples.kindLabel", {
                    defaultValue: "Kind"
                  })}
                  <select
                    data-testid="voice-examples-kind-input"
                    className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                    value={formState.kind}
                    onChange={(event) =>
                      handleFieldChange("kind", event.target.value)
                    }
                  >
                    <option value="style">style</option>
                    <option value="boundary">boundary</option>
                    <option value="catchphrase">catchphrase</option>
                    <option value="scenario_demo">scenario_demo</option>
                    <option value="tool_behavior">tool_behavior</option>
                  </select>
                </label>
                <label className="text-xs text-text-muted">
                  {t("sidepanel:personaGarden.voiceExamples.toneLabel", {
                    defaultValue: "Tone"
                  })}
                  <input
                    data-testid="voice-examples-tone-input"
                    className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                    value={formState.tone}
                    onChange={(event) =>
                      handleFieldChange("tone", event.target.value)
                    }
                  />
                </label>
                <label className="text-xs text-text-muted md:col-span-2">
                  {t("sidepanel:personaGarden.voiceExamples.contentLabel", {
                    defaultValue: "Content"
                  })}
                  <textarea
                    data-testid="voice-examples-content-input"
                    className="mt-1 min-h-24 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                    value={formState.content}
                    onChange={(event) =>
                      handleFieldChange("content", event.target.value)
                    }
                  />
                </label>
                <label className="text-xs text-text-muted">
                  {t("sidepanel:personaGarden.voiceExamples.scenarioLabel", {
                    defaultValue: "Scenario tags"
                  })}
                  <input
                    className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                    value={formState.scenarioTags}
                    onChange={(event) =>
                      handleFieldChange("scenarioTags", event.target.value)
                    }
                  />
                </label>
                <label className="text-xs text-text-muted">
                  {t("sidepanel:personaGarden.voiceExamples.capabilityLabel", {
                    defaultValue: "Capability tags"
                  })}
                  <input
                    className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                    value={formState.capabilityTags}
                    onChange={(event) =>
                      handleFieldChange("capabilityTags", event.target.value)
                    }
                  />
                </label>
                <label className="text-xs text-text-muted">
                  {t("sidepanel:personaGarden.voiceExamples.priorityLabel", {
                    defaultValue: "Priority"
                  })}
                  <input
                    type="number"
                    className="mt-1 w-full rounded-md border border-border bg-surface px-2 py-1 text-sm text-text"
                    value={formState.priority}
                    onChange={(event) =>
                      handleFieldChange("priority", event.target.value)
                    }
                  />
                </label>
                <label className="flex items-center gap-2 pt-5 text-xs text-text-muted">
                  <input
                    type="checkbox"
                    checked={formState.enabled}
                    onChange={(event) =>
                      handleFieldChange("enabled", event.target.checked)
                    }
                  />
                  {t("sidepanel:personaGarden.voiceExamples.enabledLabel", {
                    defaultValue: "Enabled"
                  })}
                </label>
              </div>

              {validationError ? (
                <div className="mt-2 text-xs text-red-600">{validationError}</div>
              ) : null}
              {error ? (
                <div className="mt-2 text-xs text-red-600">{error}</div>
              ) : null}

              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  data-testid="voice-examples-save"
                  className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={saving}
                  onClick={() => {
                    void handleSave()
                  }}
                >
                  {saving
                    ? t("common:saving", { defaultValue: "Saving..." })
                    : t("common:save", { defaultValue: "Save" })}
                </button>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
