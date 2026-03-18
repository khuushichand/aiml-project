import React from "react"

import {
  tldwClient,
  type VisualStyleCreateInput,
  type VisualStyleRecord
} from "@/services/tldw/TldwApiClient"

const VISUAL_STYLE_THEME_OPTIONS = [
  "black",
  "white",
  "league",
  "beige",
  "sky",
  "night",
  "serif",
  "simple",
  "solarized",
  "blood",
  "moon",
  "dracula"
] as const
const VISUAL_STYLE_DENSITY_OPTIONS = ["low", "medium", "high"] as const
const VISUAL_STYLE_ARTIFACT_OPTIONS = [
  { value: "timeline", label: "Timeline" },
  { value: "comparison_matrix", label: "Comparison Matrix" },
  { value: "process_flow", label: "Process Flow" },
  { value: "stat_group", label: "Stat Group" },
  { value: "chart_spec", label: "Chart Spec" },
  { value: "map_spec", label: "Map Spec" }
] as const
const VISUAL_STYLE_SIGNAL_OPTIONS = [
  { key: "exam_focus", label: "Exam focus" },
  { key: "chronology_bias", label: "Chronology" },
  { key: "narrative_bias", label: "Narrative" },
  { key: "comparison_bias", label: "Comparison" },
  { key: "quant_focus", label: "Quant focus" },
  { key: "spatial_reasoning", label: "Spatial reasoning" },
  { key: "scanability", label: "Scanability" },
  { key: "citation_bias", label: "Citation bias" },
  { key: "visual_callouts", label: "Visual callouts" },
  { key: "argument_bias", label: "Argument bias" }
] as const
const VISUAL_STYLE_FALLBACK_MODE_OPTIONS = [
  "textual-summary",
  "outline",
  "key-points",
  "labeled-outline",
  "ordered-bullets",
  "metric-summary",
  "narrative-outline",
  "flashcard-points",
  "two-column-summary",
  "brief-outline"
] as const

type CustomStyleEditorMode = "closed" | "create" | "edit"

type CustomVisualStyleDraft = {
  name: string
  description: string
  theme: string
  density: string
  bulletBias: string
  artifactPreferences: string[]
  emphasisSignals: string[]
  extraGenerationRulesJson: string
  extraAppearanceDefaultsJson: string
  fallbackMode: string
  preserveKeyStats: boolean
  extraFallbackPolicyJson: string
}

type VisualStyleManagerProps = {
  selectedCustomStyle: VisualStyleRecord | null
  refreshVisualStyles: () => Promise<VisualStyleRecord[]>
  onStyleSelected: (style: VisualStyleRecord | null) => void
}

const toErrorMessage = (error: unknown): string =>
  error instanceof Error ? error.message || "Failed to save visual style." : "Failed to save visual style."

const isDensityValue = (value: unknown): value is (typeof VISUAL_STYLE_DENSITY_OPTIONS)[number] =>
  typeof value === "string" &&
  VISUAL_STYLE_DENSITY_OPTIONS.includes(
    value as (typeof VISUAL_STYLE_DENSITY_OPTIONS)[number]
  )

const isFallbackModeValue = (
  value: unknown
): value is (typeof VISUAL_STYLE_FALLBACK_MODE_OPTIONS)[number] =>
  typeof value === "string" &&
  VISUAL_STYLE_FALLBACK_MODE_OPTIONS.includes(
    value as (typeof VISUAL_STYLE_FALLBACK_MODE_OPTIONS)[number]
  )

const toggleListValue = (values: string[], nextValue: string, checked: boolean): string[] => {
  if (checked) {
    return values.includes(nextValue) ? values : [...values, nextValue]
  }
  return values.filter((value) => value !== nextValue)
}

const createEmptyCustomStyleDraft = (): CustomVisualStyleDraft => ({
  name: "",
  description: "",
  theme: "white",
  density: "medium",
  bulletBias: "medium",
  artifactPreferences: [],
  emphasisSignals: [],
  extraGenerationRulesJson: "{}",
  extraAppearanceDefaultsJson: "{}",
  fallbackMode: "outline",
  preserveKeyStats: true,
  extraFallbackPolicyJson: "{}"
})

const styleToCustomStyleDraft = (style: VisualStyleRecord): CustomVisualStyleDraft => {
  const generationRules = { ...(style.generation_rules || {}) }
  const appearanceDefaults = { ...(style.appearance_defaults || {}) }
  const fallbackPolicy = { ...(style.fallback_policy || {}) }

  const density = isDensityValue(generationRules.density) ? generationRules.density : "medium"
  if (isDensityValue(generationRules.density)) {
    delete generationRules.density
  }

  const bulletBias = isDensityValue(generationRules.bullet_bias)
    ? generationRules.bullet_bias
    : "medium"
  if (isDensityValue(generationRules.bullet_bias)) {
    delete generationRules.bullet_bias
  }

  const emphasisSignals = VISUAL_STYLE_SIGNAL_OPTIONS.flatMap((option) => {
    const value = generationRules[option.key]
    if (option.key === "exam_focus" ? value === true : value === "high") {
      delete generationRules[option.key]
      return [option.key]
    }
    return []
  })

  const theme =
    typeof appearanceDefaults.theme === "string" && appearanceDefaults.theme
      ? appearanceDefaults.theme
      : "white"
  if (typeof appearanceDefaults.theme === "string") {
    delete appearanceDefaults.theme
  }

  const fallbackMode = isFallbackModeValue(fallbackPolicy.mode)
    ? fallbackPolicy.mode
    : "outline"
  if (isFallbackModeValue(fallbackPolicy.mode)) {
    delete fallbackPolicy.mode
  }
  const preserveKeyStats =
    typeof fallbackPolicy.preserve_key_stats === "boolean"
      ? fallbackPolicy.preserve_key_stats
      : true
  if (typeof fallbackPolicy.preserve_key_stats === "boolean") {
    delete fallbackPolicy.preserve_key_stats
  }

  return {
    name: style.name,
    description: style.description || "",
    theme,
    density,
    bulletBias,
    artifactPreferences: [...(style.artifact_preferences || [])],
    emphasisSignals,
    extraGenerationRulesJson: JSON.stringify(generationRules, null, 2),
    extraAppearanceDefaultsJson: JSON.stringify(appearanceDefaults, null, 2),
    fallbackMode,
    preserveKeyStats,
    extraFallbackPolicyJson: JSON.stringify(fallbackPolicy, null, 2)
  }
}

const parseJsonObjectInput = (
  value: string,
  fieldLabel: string
): Record<string, unknown> => {
  const normalized = value.trim()
  if (!normalized) {
    return {}
  }
  let parsed: unknown
  try {
    parsed = JSON.parse(normalized)
  } catch {
    throw new Error(`${fieldLabel} must be valid JSON.`)
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${fieldLabel} must be a JSON object.`)
  }
  return { ...(parsed as Record<string, unknown>) }
}

const buildCustomVisualStylePayload = (
  draft: CustomVisualStyleDraft
): VisualStyleCreateInput => {
  const name = draft.name.trim()
  if (!name) {
    throw new Error("Custom style name is required.")
  }
  const appearanceDefaults = parseJsonObjectInput(
    draft.extraAppearanceDefaultsJson,
    "Additional appearance defaults"
  )
  if (
    "custom_css" in appearanceDefaults &&
    appearanceDefaults.custom_css !== null &&
    typeof appearanceDefaults.custom_css !== "string"
  ) {
    throw new Error("Additional appearance defaults custom_css must be a string or null.")
  }
  if (draft.theme.trim()) {
    appearanceDefaults.theme = draft.theme.trim()
  }
  const generationRules = parseJsonObjectInput(
    draft.extraGenerationRulesJson,
    "Additional generation rules"
  )
  generationRules.density = draft.density.trim() || "medium"
  generationRules.bullet_bias = draft.bulletBias.trim() || "medium"
  for (const signal of draft.emphasisSignals) {
    generationRules[signal] = signal === "exam_focus" ? true : "high"
  }
  const fallbackPolicy = parseJsonObjectInput(
    draft.extraFallbackPolicyJson,
    "Additional fallback policy"
  )
  if (draft.fallbackMode.trim()) {
    fallbackPolicy.mode = draft.fallbackMode.trim()
  }
  fallbackPolicy.preserve_key_stats = draft.preserveKeyStats
  return {
    name,
    description: draft.description.trim() || null,
    generation_rules: generationRules,
    artifact_preferences: draft.artifactPreferences.filter(Boolean),
    appearance_defaults: appearanceDefaults,
    fallback_policy: fallbackPolicy
  }
}

export const VisualStyleManager: React.FC<VisualStyleManagerProps> = ({
  selectedCustomStyle,
  refreshVisualStyles,
  onStyleSelected
}) => {
  const [customStyleEditorMode, setCustomStyleEditorMode] =
    React.useState<CustomStyleEditorMode>("closed")
  const [customStyleDraft, setCustomStyleDraft] = React.useState<CustomVisualStyleDraft>(
    createEmptyCustomStyleDraft()
  )
  const [customStyleError, setCustomStyleError] = React.useState<string | null>(null)
  const [isSavingCustomStyle, setIsSavingCustomStyle] = React.useState(false)
  const [isDeletingCustomStyle, setIsDeletingCustomStyle] = React.useState(false)

  const closeEditor = React.useCallback(() => {
    setCustomStyleEditorMode("closed")
    setCustomStyleError(null)
    setCustomStyleDraft(createEmptyCustomStyleDraft())
  }, [])

  const handleStartCreateCustomStyle = React.useCallback(() => {
    setCustomStyleEditorMode("create")
    setCustomStyleDraft(createEmptyCustomStyleDraft())
    setCustomStyleError(null)
  }, [])

  const handleStartEditCustomStyle = React.useCallback(() => {
    if (!selectedCustomStyle) {
      return
    }
    setCustomStyleEditorMode("edit")
    setCustomStyleDraft(styleToCustomStyleDraft(selectedCustomStyle))
    setCustomStyleError(null)
  }, [selectedCustomStyle])

  const handleSaveCustomStyle = React.useCallback(async () => {
    setCustomStyleError(null)
    let payload: VisualStyleCreateInput
    try {
      payload = buildCustomVisualStylePayload(customStyleDraft)
    } catch (error) {
      setCustomStyleError(toErrorMessage(error))
      return
    }

    setIsSavingCustomStyle(true)
    try {
      const savedStyle =
        customStyleEditorMode === "edit" && selectedCustomStyle
          ? await tldwClient.patchVisualStyle(selectedCustomStyle.id, payload)
          : await tldwClient.createVisualStyle(payload)
      await refreshVisualStyles()
      onStyleSelected(savedStyle)
      closeEditor()
    } catch (error) {
      setCustomStyleError(toErrorMessage(error))
    } finally {
      setIsSavingCustomStyle(false)
    }
  }, [
    closeEditor,
    customStyleDraft,
    customStyleEditorMode,
    onStyleSelected,
    refreshVisualStyles,
    selectedCustomStyle
  ])

  const handleDeleteCustomStyle = React.useCallback(async () => {
    if (!selectedCustomStyle) {
      return
    }
    setCustomStyleError(null)
    setIsDeletingCustomStyle(true)
    try {
      await tldwClient.deleteVisualStyle(selectedCustomStyle.id)
      await refreshVisualStyles()
      onStyleSelected(null)
      closeEditor()
    } catch (error) {
      setCustomStyleError(toErrorMessage(error))
    } finally {
      setIsDeletingCustomStyle(false)
    }
  }, [closeEditor, onStyleSelected, refreshVisualStyles, selectedCustomStyle])

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Custom visual styles</h2>
          <p className="mt-1 text-sm text-slate-600">
            Create per-user presets for exam prep, revision decks, or presentation-specific
            structure. Built-ins stay read-only.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            data-testid="presentation-studio-new-custom-style"
            onClick={handleStartCreateCustomStyle}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
          >
            New custom style
          </button>
          {selectedCustomStyle && (
            <>
              <button
                type="button"
                data-testid="presentation-studio-edit-custom-style"
                onClick={handleStartEditCustomStyle}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
              >
                Edit selected custom style
              </button>
              <button
                type="button"
                data-testid="presentation-studio-delete-custom-style"
                onClick={() => void handleDeleteCustomStyle()}
                disabled={isDeletingCustomStyle}
                className="rounded-lg border border-rose-300 px-3 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isDeletingCustomStyle ? "Deleting…" : "Delete selected custom style"}
              </button>
            </>
          )}
        </div>
      </div>

      {customStyleEditorMode !== "closed" && (
        <div className="mt-4 grid gap-4 rounded-lg border border-slate-200 bg-slate-50 p-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="presentation-studio-custom-style-name"
            >
              Custom style name
            </label>
            <input
              id="presentation-studio-custom-style-name"
              aria-label="Custom style name"
              value={customStyleDraft.name}
              onChange={(event) =>
                setCustomStyleDraft((current) => ({
                  ...current,
                  name: event.target.value
                }))
              }
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            />
          </div>

          <div className="md:col-span-2">
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="presentation-studio-custom-style-description"
            >
              Custom style description
            </label>
            <textarea
              id="presentation-studio-custom-style-description"
              aria-label="Custom style description"
              value={customStyleDraft.description}
              onChange={(event) =>
                setCustomStyleDraft((current) => ({
                  ...current,
                  description: event.target.value
                }))
              }
              rows={3}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            />
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="presentation-studio-custom-style-theme"
            >
              Default theme
            </label>
            <select
              id="presentation-studio-custom-style-theme"
              aria-label="Default theme"
              value={customStyleDraft.theme}
              onChange={(event) =>
                setCustomStyleDraft((current) => ({
                  ...current,
                  theme: event.target.value
                }))
              }
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            >
              {VISUAL_STYLE_THEME_OPTIONS.map((theme) => (
                <option key={theme} value={theme}>
                  {theme}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="presentation-studio-custom-style-density"
            >
              Content density
            </label>
            <select
              id="presentation-studio-custom-style-density"
              aria-label="Content density"
              value={customStyleDraft.density}
              onChange={(event) =>
                setCustomStyleDraft((current) => ({
                  ...current,
                  density: event.target.value
                }))
              }
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            >
              {VISUAL_STYLE_DENSITY_OPTIONS.map((density) => (
                <option key={density} value={density}>
                  {density}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="presentation-studio-custom-style-bullet-bias"
            >
              Bullet emphasis
            </label>
            <select
              id="presentation-studio-custom-style-bullet-bias"
              aria-label="Bullet emphasis"
              value={customStyleDraft.bulletBias}
              onChange={(event) =>
                setCustomStyleDraft((current) => ({
                  ...current,
                  bulletBias: event.target.value
                }))
              }
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            >
              {VISUAL_STYLE_DENSITY_OPTIONS.map((density) => (
                <option key={density} value={density}>
                  {density}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2">
            <span className="mb-2 block text-sm font-medium text-slate-700">
              Artifact preferences
            </span>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {VISUAL_STYLE_ARTIFACT_OPTIONS.map((option) => {
                const checked = customStyleDraft.artifactPreferences.includes(option.value)
                return (
                  <label
                    key={option.value}
                    className={`flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-3 text-sm transition ${
                      checked
                        ? "border-sky-400 bg-sky-50 text-slate-900"
                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                    }`}
                  >
                    <input
                      type="checkbox"
                      aria-label={`${option.label} artifact preference`}
                      checked={checked}
                      onChange={(event) =>
                        setCustomStyleDraft((current) => ({
                          ...current,
                          artifactPreferences: toggleListValue(
                            current.artifactPreferences,
                            option.value,
                            event.target.checked
                          )
                        }))
                      }
                      className="mt-0.5 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                    />
                    <span>{option.label}</span>
                  </label>
                )
              })}
            </div>
            <p className="mt-2 text-xs text-slate-500">
              These tell the generator which structured visual blocks to prefer when it can.
            </p>
          </div>

          <div className="md:col-span-2">
            <span className="mb-2 block text-sm font-medium text-slate-700">
              Emphasis signals
            </span>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {VISUAL_STYLE_SIGNAL_OPTIONS.map((option) => {
                const checked = customStyleDraft.emphasisSignals.includes(option.key)
                return (
                  <label
                    key={option.key}
                    className={`flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-3 text-sm transition ${
                      checked
                        ? "border-sky-400 bg-sky-50 text-slate-900"
                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                    }`}
                  >
                    <input
                      type="checkbox"
                      aria-label={`${option.label} emphasis signal`}
                      checked={checked}
                      onChange={(event) =>
                        setCustomStyleDraft((current) => ({
                          ...current,
                          emphasisSignals: toggleListValue(
                            current.emphasisSignals,
                            option.key,
                            event.target.checked
                          )
                        }))
                      }
                      className="mt-0.5 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                    />
                    <span>{option.label}</span>
                  </label>
                )
              })}
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Guided emphasis uses the common preset signals. Use Advanced JSON below for less
              common rule shapes or custom strengths.
            </p>
          </div>

          <div>
            <label
              className="mb-1 block text-sm font-medium text-slate-700"
              htmlFor="presentation-studio-custom-style-fallback-mode"
            >
              Fallback mode
            </label>
            <select
              id="presentation-studio-custom-style-fallback-mode"
              aria-label="Fallback mode"
              value={customStyleDraft.fallbackMode}
              onChange={(event) =>
                setCustomStyleDraft((current) => ({
                  ...current,
                  fallbackMode: event.target.value
                }))
              }
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            >
              {VISUAL_STYLE_FALLBACK_MODE_OPTIONS.map((modeOption) => (
                <option key={modeOption} value={modeOption}>
                  {modeOption}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end">
            <label className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-3 text-sm text-slate-700">
              <input
                type="checkbox"
                aria-label="Preserve key stats"
                checked={customStyleDraft.preserveKeyStats}
                onChange={(event) =>
                  setCustomStyleDraft((current) => ({
                    ...current,
                    preserveKeyStats: event.target.checked
                  }))
                }
                className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
              />
              Preserve key stats in fallback output
            </label>
          </div>

          <details
            className="md:col-span-2 rounded-lg border border-slate-200 bg-white"
            data-testid="presentation-studio-custom-style-advanced"
          >
            <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium text-slate-800">
              Advanced JSON overrides
            </summary>
            <div className="grid gap-4 border-t border-slate-200 px-4 py-4 md:grid-cols-2">
              <div>
                <label
                  className="mb-1 block text-sm font-medium text-slate-700"
                  htmlFor="presentation-studio-custom-style-generation-rules"
                >
                  Additional generation rules JSON
                </label>
                <textarea
                  id="presentation-studio-custom-style-generation-rules"
                  aria-label="Additional generation rules JSON"
                  value={customStyleDraft.extraGenerationRulesJson}
                  onChange={(event) =>
                    setCustomStyleDraft((current) => ({
                      ...current,
                      extraGenerationRulesJson: event.target.value
                    }))
                  }
                  rows={8}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                />
              </div>

              <div>
                <label
                  className="mb-1 block text-sm font-medium text-slate-700"
                  htmlFor="presentation-studio-custom-style-appearance-defaults"
                >
                  Additional appearance defaults JSON
                </label>
                <textarea
                  id="presentation-studio-custom-style-appearance-defaults"
                  aria-label="Additional appearance defaults JSON"
                  value={customStyleDraft.extraAppearanceDefaultsJson}
                  onChange={(event) =>
                    setCustomStyleDraft((current) => ({
                      ...current,
                      extraAppearanceDefaultsJson: event.target.value
                    }))
                  }
                  rows={8}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                />
              </div>

              <div className="md:col-span-2">
                <label
                  className="mb-1 block text-sm font-medium text-slate-700"
                  htmlFor="presentation-studio-custom-style-fallback-policy"
                >
                  Additional fallback policy JSON
                </label>
                <textarea
                  id="presentation-studio-custom-style-fallback-policy"
                  aria-label="Additional fallback policy JSON"
                  value={customStyleDraft.extraFallbackPolicyJson}
                  onChange={(event) =>
                    setCustomStyleDraft((current) => ({
                      ...current,
                      extraFallbackPolicyJson: event.target.value
                    }))
                  }
                  rows={6}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                />
                <p className="mt-2 text-xs text-slate-500">
                  Advanced JSON is merged with the guided controls above. The guided fields win
                  when the same keys appear in both places.
                </p>
              </div>
            </div>
          </details>

          {customStyleError && (
            <p className="md:col-span-2 text-sm text-rose-600">{customStyleError}</p>
          )}

          <div className="md:col-span-2 flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={closeEditor}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-white"
            >
              Cancel
            </button>
            <button
              type="button"
              data-testid="presentation-studio-save-custom-style"
              onClick={() => void handleSaveCustomStyle()}
              disabled={isSavingCustomStyle}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {isSavingCustomStyle ? "Saving custom style…" : "Save custom style"}
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
