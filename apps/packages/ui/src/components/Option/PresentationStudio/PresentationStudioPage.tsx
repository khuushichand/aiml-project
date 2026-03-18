import React from "react"
import { useNavigate } from "react-router-dom"

import { ProjectWorkspace } from "./ProjectWorkspace"
import {
  buildPresentationVisualStyleSnapshot,
  tldwClient,
  type PresentationStudioRecord,
  type VisualStyleCreateInput,
  type VisualStyleRecord
} from "@/services/tldw/TldwApiClient"
import { useServerCapabilities } from "@/hooks/useServerCapabilities"
import { useServerOnline } from "@/hooks/useServerOnline"
import { usePresentationStudioStore } from "@/store/presentation-studio"

type PresentationStudioPageProps = {
  mode?: "index" | "new" | "detail"
  projectId?: string | null
}

const formatEtag = (version: number | null | undefined): string | null =>
  typeof version === "number" && Number.isFinite(version) ? `W/"v${version}"` : null

const toErrorMessage = (error: unknown): string =>
  error instanceof Error ? error.message || "Failed to load presentation." : "Failed to load presentation."

const createBlankSlideId = (): string =>
  globalThis.crypto?.randomUUID?.() ||
  `slide-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`

const DEFAULT_VISUAL_STYLE_ID = "minimal-academic"
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
const VISUAL_STYLE_SIGNAL_KEYS = new Set(
  VISUAL_STYLE_SIGNAL_OPTIONS.map((option) => option.key)
)

type InFlightProjectRequest = {
  projectId: string | null
  promise: Promise<PresentationStudioRecord>
}

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

const encodeVisualStyleValue = (styleId: string | null, styleScope: string | null): string =>
  styleId && styleScope ? `${styleScope}::${styleId}` : ""

const parseVisualStyleValue = (
  value: string
): { visualStyleId: string | null; visualStyleScope: string | null } => {
  if (!value) {
    return { visualStyleId: null, visualStyleScope: null }
  }
  const separatorIndex = value.indexOf("::")
  if (separatorIndex === -1) {
    return { visualStyleId: null, visualStyleScope: null }
  }
  const visualStyleScope = value.slice(0, separatorIndex).trim()
  const visualStyleId = value.slice(separatorIndex + 2).trim()
  if (!visualStyleScope || !visualStyleId) {
    return { visualStyleId: null, visualStyleScope: null }
  }
  return { visualStyleId, visualStyleScope }
}

const getDefaultVisualStyleValue = (styles: VisualStyleRecord[]): string => {
  const preferred =
    styles.find((style) => style.id === DEFAULT_VISUAL_STYLE_ID && style.scope === "builtin") ||
    styles[0]
  return preferred ? encodeVisualStyleValue(preferred.id, preferred.scope) : ""
}

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

export const PresentationStudioPage: React.FC<PresentationStudioPageProps> = ({
  mode = "index",
  projectId = null
}) => {
  const navigate = useNavigate()
  const isOnline = useServerOnline()
  const { capabilities, loading } = useServerCapabilities()
  const loadProject = usePresentationStudioStore((state) => state.loadProject)
  const title = usePresentationStudioStore((state) => state.title)
  const slides = usePresentationStudioStore((state) => state.slides)
  const currentProjectId = usePresentationStudioStore((state) => state.projectId)
  const visualStyleId = usePresentationStudioStore((state) => state.visualStyleId)
  const visualStyleScope = usePresentationStudioStore((state) => state.visualStyleScope)
  const visualStyleName = usePresentationStudioStore((state) => state.visualStyleName)
  const updateProjectMeta = usePresentationStudioStore((state) => state.updateProjectMeta)
  const [isProjectLoading, setIsProjectLoading] = React.useState(mode === "detail")
  const [loadError, setLoadError] = React.useState<string | null>(null)
  const [availableStyles, setAvailableStyles] = React.useState<VisualStyleRecord[]>([])
  const [stylesLoading, setStylesLoading] = React.useState(mode !== "index")
  const [stylesError, setStylesError] = React.useState<string | null>(null)
  const [draftTitle, setDraftTitle] = React.useState("Untitled Presentation")
  const [draftVisualStyleValue, setDraftVisualStyleValue] = React.useState("")
  const [isCreatingProject, setIsCreatingProject] = React.useState(false)
  const [customStyleEditorMode, setCustomStyleEditorMode] = React.useState<
    "closed" | "create" | "edit"
  >("closed")
  const [customStyleDraft, setCustomStyleDraft] = React.useState<CustomVisualStyleDraft>(
    createEmptyCustomStyleDraft()
  )
  const [customStyleError, setCustomStyleError] = React.useState<string | null>(null)
  const [isSavingCustomStyle, setIsSavingCustomStyle] = React.useState(false)
  const [isDeletingCustomStyle, setIsDeletingCustomStyle] = React.useState(false)
  const detailRequestRef = React.useRef<InFlightProjectRequest | null>(null)

  const refreshVisualStyles = React.useCallback(async (): Promise<VisualStyleRecord[]> => {
    const styles = await tldwClient.listVisualStyles()
    setAvailableStyles(Array.isArray(styles) ? styles : [])
    return Array.isArray(styles) ? styles : []
  }, [])

  React.useEffect(() => {
    if (mode === "index" || !isOnline) {
      return
    }

    let cancelled = false
    setStylesLoading(true)
    setStylesError(null)
    void refreshVisualStyles()
      .then((styles) => {
        if (cancelled) {
          return
        }
        setDraftVisualStyleValue((currentValue) => currentValue || getDefaultVisualStyleValue(styles))
      })
      .catch((error) => {
        if (cancelled) {
          return
        }
        setAvailableStyles([])
        setStylesError(toErrorMessage(error))
        setDraftVisualStyleValue("")
      })
      .finally(() => {
        if (cancelled) {
          return
        }
        setStylesLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [isOnline, mode, refreshVisualStyles])

  React.useEffect(() => {
    if (mode !== "detail" || !projectId) {
      return
    }
    if (currentProjectId === projectId) {
      setIsProjectLoading(false)
      return
    }
    let cancelled = false
    setIsProjectLoading(true)
    setLoadError(null)
    if (!detailRequestRef.current || detailRequestRef.current.projectId !== projectId) {
      detailRequestRef.current = {
        projectId,
        promise: tldwClient.getPresentation(projectId)
      }
    }

    void detailRequestRef.current.promise
      .then((project) => {
        if (cancelled) {
          return
        }
        setIsProjectLoading(false)
        loadProject(project, {
          etag: formatEtag(project.version)
        })
        detailRequestRef.current = null
      })
      .catch((error) => {
        if (cancelled) {
          return
        }
        detailRequestRef.current = null
        setLoadError(toErrorMessage(error))
        setIsProjectLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [currentProjectId, loadProject, mode, projectId])

  const styleOptions = React.useMemo(() => {
    const options = [...availableStyles]
    if (
      visualStyleId &&
      visualStyleScope &&
      !options.some((style) => style.id === visualStyleId && style.scope === visualStyleScope)
    ) {
      options.unshift({
        id: visualStyleId,
        scope: visualStyleScope,
        name: visualStyleName || `${visualStyleScope}:${visualStyleId}`,
        description: "This style is no longer available, but this deck still retains its snapshot.",
        generation_rules: {},
        artifact_preferences: [],
        appearance_defaults: {},
        fallback_policy: {},
        version: null
      })
    }
    return options
  }, [availableStyles, visualStyleId, visualStyleName, visualStyleScope])

  const groupedStyleOptions = React.useMemo(
    () => ({
      builtin: styleOptions.filter((style) => style.scope === "builtin"),
      user: styleOptions.filter((style) => style.scope !== "builtin")
    }),
    [styleOptions]
  )

  const selectedDraftStyle = React.useMemo(() => {
    const { visualStyleId: nextStyleId, visualStyleScope: nextStyleScope } =
      parseVisualStyleValue(draftVisualStyleValue)
    return (
      availableStyles.find(
        (style) => style.id === nextStyleId && style.scope === nextStyleScope
      ) || null
    )
  }, [availableStyles, draftVisualStyleValue])

  const selectedPresentationStyle = React.useMemo(
    () =>
      styleOptions.find(
        (style) => style.id === visualStyleId && style.scope === visualStyleScope
      ) || null,
    [styleOptions, visualStyleId, visualStyleScope]
  )
  const selectedCustomStyle = React.useMemo(() => {
    const candidate = mode === "new" ? selectedDraftStyle : selectedPresentationStyle
    return candidate?.scope === "user" ? candidate : null
  }, [mode, selectedDraftStyle, selectedPresentationStyle])

  const applySelectedStyle = React.useCallback(
    (style: VisualStyleRecord | null) => {
      if (mode === "new") {
        setDraftVisualStyleValue(
          style ? encodeVisualStyleValue(style.id, style.scope) : ""
        )
        return
      }
      updateProjectMeta({
        visualStyleId: style?.id ?? null,
        visualStyleScope: style?.scope ?? null,
        visualStyleName: style?.name ?? null,
        visualStyleVersion: style?.version ?? null,
        visualStyleSnapshot: style ? buildPresentationVisualStyleSnapshot(style) : null
      })
    },
    [mode, updateProjectMeta]
  )

  const handleCreateProject = React.useCallback(async () => {
    if (isCreatingProject) {
      return
    }
    const { visualStyleId: selectedVisualStyleId, visualStyleScope: selectedVisualStyleScope } =
      parseVisualStyleValue(draftVisualStyleValue)
    const blankSlideId = createBlankSlideId()
    setIsCreatingProject(true)
    setLoadError(null)
    try {
      const project = await tldwClient.createPresentation({
        title: draftTitle.trim() || "Untitled Presentation",
        description: null,
        visual_style_id: selectedVisualStyleId,
        visual_style_scope: selectedVisualStyleScope,
        studio_data: {
          origin: "blank",
          entry_surface: "webui_new"
        },
        slides: [
          {
            order: 0,
            layout: "title",
            title: "Title slide",
            content: "",
            speaker_notes: "",
            metadata: {
              studio: {
                slideId: blankSlideId,
                transition: "fade",
                timing_mode: "auto",
                manual_duration_ms: null,
                audio: { status: "missing" },
                image: { status: "missing" }
              }
            }
          }
        ]
      })
      loadProject(project, {
        etag: formatEtag(project.version)
      })
      navigate(`/presentation-studio/${project.id}`, {
        replace: true
      })
    } catch (error) {
      setLoadError(toErrorMessage(error))
    } finally {
      setIsCreatingProject(false)
    }
  }, [draftTitle, draftVisualStyleValue, isCreatingProject, loadProject, navigate])

  const handleDetailStyleChange = React.useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>) => {
      const nextValue = event.target.value
      const { visualStyleId: nextStyleId, visualStyleScope: nextStyleScope } =
        parseVisualStyleValue(nextValue)
      const selectedStyle =
        styleOptions.find(
          (style) => style.id === nextStyleId && style.scope === nextStyleScope
        ) || null
      updateProjectMeta({
        visualStyleId: nextStyleId,
        visualStyleScope: nextStyleScope,
        visualStyleName: selectedStyle?.name ?? null,
        visualStyleVersion: selectedStyle?.version ?? null,
        visualStyleSnapshot: selectedStyle
          ? buildPresentationVisualStyleSnapshot(selectedStyle)
          : null
      })
    },
    [styleOptions, updateProjectMeta]
  )

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
      applySelectedStyle(savedStyle)
      setCustomStyleEditorMode("closed")
      setCustomStyleDraft(createEmptyCustomStyleDraft())
    } catch (error) {
      setCustomStyleError(toErrorMessage(error))
    } finally {
      setIsSavingCustomStyle(false)
    }
  }, [
    applySelectedStyle,
    customStyleDraft,
    customStyleEditorMode,
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
      applySelectedStyle(null)
      setCustomStyleEditorMode("closed")
      setCustomStyleDraft(createEmptyCustomStyleDraft())
    } catch (error) {
      setCustomStyleError(toErrorMessage(error))
    } finally {
      setIsDeletingCustomStyle(false)
    }
  }, [applySelectedStyle, refreshVisualStyles, selectedCustomStyle])

  const customStyleManager = (
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
              onClick={() => {
                setCustomStyleEditorMode("closed")
                setCustomStyleError(null)
                setCustomStyleDraft(createEmptyCustomStyleDraft())
              }}
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

  if (!isOnline) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h1 className="text-2xl font-semibold text-slate-900">Presentation Studio</h1>
        <p className="mt-2 text-sm text-slate-600">
          Server is offline. Connect to use Presentation Studio.
        </p>
      </section>
    )
  }

  if (!loading && capabilities && !capabilities.hasPresentationStudio) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h1 className="text-2xl font-semibold text-slate-900">Presentation Studio</h1>
        <p className="mt-2 text-sm text-slate-600">
          Presentation Studio is not available on this server.
        </p>
      </section>
    )
  }

  if (mode === "index") {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h1 className="text-2xl font-semibold text-slate-900">Presentation Studio</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          Create structured narrated slide decks, stage media per slide, and publish a
          rendered presentation video when the server advertises render support.
        </p>
      </section>
    )
  }

  if (mode === "new") {
    return (
      <section className="space-y-4">
        <header className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold text-slate-900">Presentation Studio</h1>
            <p className="max-w-2xl text-sm text-slate-600">
              Start a new deck with a reusable visual style preset. The selected style
              sets the default strategy for future generated slides.
            </p>
          </div>
        </header>

        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_280px]">
            <div className="space-y-4">
              <div>
                <label
                  className="mb-1 block text-sm font-medium text-slate-700"
                  htmlFor="presentation-studio-title"
                >
                  Presentation title
                </label>
                <input
                  id="presentation-studio-title"
                  value={draftTitle}
                  onChange={(event) => setDraftTitle(event.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
                  placeholder="Untitled Presentation"
                />
              </div>

              <div>
                <label
                  className="mb-1 block text-sm font-medium text-slate-700"
                  htmlFor="presentation-studio-visual-style"
                >
                  Choose visual style
                </label>
                <select
                  id="presentation-studio-visual-style"
                  aria-label="Choose visual style"
                  value={draftVisualStyleValue}
                  onChange={(event) => setDraftVisualStyleValue(event.target.value)}
                  disabled={stylesLoading || isCreatingProject}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100 disabled:bg-slate-100"
                >
                  <option value="">No visual style preset</option>
                  {groupedStyleOptions.builtin.length > 0 && (
                    <optgroup label="Built-in styles">
                      {groupedStyleOptions.builtin.map((style) => (
                        <option
                          key={`${style.scope}:${style.id}`}
                          value={encodeVisualStyleValue(style.id, style.scope)}
                        >
                          {style.name}
                        </option>
                      ))}
                    </optgroup>
                  )}
                  {groupedStyleOptions.user.length > 0 && (
                    <optgroup label="Custom styles">
                      {groupedStyleOptions.user.map((style) => (
                        <option
                          key={`${style.scope}:${style.id}`}
                          value={encodeVisualStyleValue(style.id, style.scope)}
                        >
                          {style.name}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-medium text-slate-900">
                  {selectedDraftStyle?.name || "Manual deck defaults"}
                </p>
                <p className="mt-1 text-sm text-slate-600">
                  {selectedDraftStyle?.description ||
                    "No preset selected. The deck starts with standard manual settings."}
                </p>
                <p className="mt-3 text-xs uppercase tracking-wide text-slate-500">
                  Applies to future generated slides. Existing slides stay unchanged.
                </p>
              </div>

              {stylesError && <p className="text-sm text-rose-600">{stylesError}</p>}
              {loadError && <p className="text-sm text-rose-600">{loadError}</p>}
            </div>

            <aside className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <h2 className="text-sm font-semibold text-slate-900">Style coverage</h2>
              <p className="mt-2 text-sm text-slate-600">
                Built-ins include academic, exam-focused, infographic, timeline,
                data-heavy, storytelling, diagram-first, and high-contrast revision
                presets.
              </p>
              <p className="mt-4 text-xs uppercase tracking-wide text-slate-500">
                Built-in and per-user custom styles are listed together here.
              </p>
            </aside>
          </div>

          <div className="mt-6 flex items-center justify-end">
            <button
              type="button"
              data-testid="presentation-studio-create-button"
              onClick={() => void handleCreateProject()}
              disabled={isCreatingProject}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {isCreatingProject ? "Creating presentation…" : "Create presentation"}
            </button>
          </div>
        </section>

        {customStyleManager}
      </section>
    )
  }

  if (isProjectLoading) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <p className="text-sm text-slate-600">Loading presentation…</p>
      </section>
    )
  }

  if (loadError) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h1 className="text-2xl font-semibold text-slate-900">Presentation Studio</h1>
        <p className="mt-2 text-sm text-rose-600">{loadError}</p>
      </section>
    )
  }

  return (
    <section className="space-y-4">
      <header className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Presentation Studio</h1>
            <p className="mt-1 text-sm text-slate-600">
              {title || "Untitled Presentation"} · {slides.length} slide
              {slides.length === 1 ? "" : "s"}
            </p>
          </div>
          <div className="min-w-[240px] flex-1 sm:max-w-sm">
            <label
              className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500"
              htmlFor="presentation-studio-detail-visual-style"
            >
              Choose visual style
            </label>
            <select
              id="presentation-studio-detail-visual-style"
              aria-label="Choose visual style"
              value={encodeVisualStyleValue(visualStyleId, visualStyleScope)}
              onChange={handleDetailStyleChange}
              disabled={stylesLoading}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100 disabled:bg-slate-100"
            >
              <option value="">No visual style preset</option>
              {groupedStyleOptions.builtin.length > 0 && (
                <optgroup label="Built-in styles">
                  {groupedStyleOptions.builtin.map((style) => (
                    <option
                      key={`${style.scope}:${style.id}`}
                      value={encodeVisualStyleValue(style.id, style.scope)}
                    >
                      {style.name}
                    </option>
                  ))}
                </optgroup>
              )}
              {groupedStyleOptions.user.length > 0 && (
                <optgroup label="Custom styles">
                  {groupedStyleOptions.user.map((style) => (
                    <option
                      key={`${style.scope}:${style.id}`}
                      value={encodeVisualStyleValue(style.id, style.scope)}
                    >
                      {style.name}
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
            <p className="mt-1 text-xs text-slate-500">
              {selectedPresentationStyle?.description ||
                "Applies to future generated slides. Existing slides are unchanged."}
            </p>
          </div>
        </div>
      </header>

      {customStyleManager}

      <ProjectWorkspace canRender={Boolean(capabilities?.hasPresentationRender)} />
    </section>
  )
}
