import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useReducer,
} from "react"
import type {
  WizardStep,
  WizardQueueItem,
  IngestPreset,
  PresetConfig,
  WizardProcessingState,
  WizardResultItem,
  ItemProgress,
} from "./types"
import { DEFAULT_PRESETS } from "./presets"
import { DEFAULT_PRESET } from "./presets"

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

type IngestWizardState = {
  currentStep: WizardStep
  /** Highest step the user has reached (for backward navigation guard). */
  highestStep: WizardStep
  queueItems: WizardQueueItem[]
  selectedPreset: IngestPreset
  presetConfig: PresetConfig
  customOptions: Partial<PresetConfig>
  processingState: WizardProcessingState
  results: WizardResultItem[]
  isMinimized: boolean
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

type Action =
  | { type: "GO_TO_STEP"; step: WizardStep }
  | { type: "GO_NEXT" }
  | { type: "GO_BACK" }
  | { type: "SET_QUEUE_ITEMS"; items: WizardQueueItem[] }
  | { type: "SET_PRESET"; preset: IngestPreset }
  | { type: "SET_CUSTOM_OPTIONS"; options: Partial<PresetConfig> }
  | { type: "START_PROCESSING" }
  | { type: "CANCEL_PROCESSING" }
  | { type: "CANCEL_ITEM"; id: string }
  | { type: "UPDATE_ITEM_PROGRESS"; progress: ItemProgress }
  | { type: "UPDATE_PROCESSING_STATE"; state: Partial<WizardProcessingState> }
  | { type: "SET_RESULTS"; results: WizardResultItem[] }
  | { type: "SKIP_TO_PROCESSING" }
  | { type: "MINIMIZE" }
  | { type: "RESTORE" }
  | { type: "RESET" }

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const resolvePresetConfig = (
  preset: IngestPreset,
  customOptions: Partial<PresetConfig>
): PresetConfig => {
  if (preset === "custom") {
    // Merge custom options on top of the standard preset as a base
    const base = DEFAULT_PRESETS.standard
    return {
      common: { ...base.common, ...(customOptions.common ?? {}) },
      storeRemote: customOptions.storeRemote ?? base.storeRemote,
      reviewBeforeStorage:
        customOptions.reviewBeforeStorage ?? base.reviewBeforeStorage,
      typeDefaults: {
        audio: {
          ...base.typeDefaults?.audio,
          ...(customOptions.typeDefaults?.audio ?? {}),
        },
        document: {
          ...base.typeDefaults?.document,
          ...(customOptions.typeDefaults?.document ?? {}),
        },
        video: {
          ...base.typeDefaults?.video,
          ...(customOptions.typeDefaults?.video ?? {}),
        },
      },
      advancedValues: {
        ...(base.advancedValues ?? {}),
        ...(customOptions.advancedValues ?? {}),
      },
    }
  }
  return DEFAULT_PRESETS[preset]
}

const INITIAL_PROCESSING_STATE: WizardProcessingState = {
  status: "idle",
  perItemProgress: [],
  elapsed: 0,
  estimatedRemaining: 0,
}

const createInitialState = (): IngestWizardState => ({
  currentStep: 1,
  highestStep: 1,
  queueItems: [],
  selectedPreset: DEFAULT_PRESET,
  presetConfig: DEFAULT_PRESETS[DEFAULT_PRESET],
  customOptions: {},
  processingState: { ...INITIAL_PROCESSING_STATE },
  results: [],
  isMinimized: false,
})

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

const clampStep = (step: number): WizardStep =>
  Math.max(1, Math.min(5, step)) as WizardStep

const reducer = (state: IngestWizardState, action: Action): IngestWizardState => {
  switch (action.type) {
    case "GO_TO_STEP": {
      // Can only go backward (to a step <= highestStep)
      const target = clampStep(action.step)
      if (target > state.highestStep) return state
      return { ...state, currentStep: target }
    }

    case "GO_NEXT": {
      const next = clampStep(state.currentStep + 1)
      if (next === state.currentStep) return state // already at max
      const newHighest = Math.max(state.highestStep, next) as WizardStep
      return { ...state, currentStep: next, highestStep: newHighest }
    }

    case "GO_BACK": {
      const prev = clampStep(state.currentStep - 1)
      if (prev === state.currentStep) return state // already at min
      return { ...state, currentStep: prev }
    }

    case "SET_QUEUE_ITEMS":
      return { ...state, queueItems: action.items }

    case "SET_PRESET": {
      const presetConfig = resolvePresetConfig(action.preset, state.customOptions)
      return {
        ...state,
        selectedPreset: action.preset,
        presetConfig,
      }
    }

    case "SET_CUSTOM_OPTIONS": {
      const customOptions = { ...state.customOptions, ...action.options }
      const presetConfig = resolvePresetConfig(state.selectedPreset, customOptions)
      return { ...state, customOptions, presetConfig }
    }

    case "START_PROCESSING": {
      const perItemProgress: ItemProgress[] = state.queueItems.map((item) => ({
        id: item.id,
        status: "queued",
        progressPercent: 0,
        currentStage: "",
        estimatedRemaining: 0,
      }))
      return {
        ...state,
        processingState: {
          status: "running",
          perItemProgress,
          elapsed: 0,
          estimatedRemaining: 0,
        },
        results: [],
      }
    }

    case "CANCEL_PROCESSING":
      return {
        ...state,
        processingState: {
          ...state.processingState,
          status: "cancelled",
          perItemProgress: state.processingState.perItemProgress.map((p) =>
            p.status === "queued" || p.status === "uploading" || p.status === "processing" || p.status === "analyzing" || p.status === "storing"
              ? { ...p, status: "cancelled" as const }
              : p
          ),
        },
      }

    case "CANCEL_ITEM":
      return {
        ...state,
        processingState: {
          ...state.processingState,
          perItemProgress: state.processingState.perItemProgress.map((p) =>
            p.id === action.id &&
            p.status !== "complete" &&
            p.status !== "failed" &&
            p.status !== "cancelled"
              ? { ...p, status: "cancelled" as const }
              : p
          ),
        },
      }

    case "UPDATE_ITEM_PROGRESS":
      return {
        ...state,
        processingState: {
          ...state.processingState,
          perItemProgress: state.processingState.perItemProgress.map((p) =>
            p.id === action.progress.id ? action.progress : p
          ),
        },
      }

    case "UPDATE_PROCESSING_STATE":
      return {
        ...state,
        processingState: { ...state.processingState, ...action.state },
      }

    case "SET_RESULTS":
      return { ...state, results: action.results }

    case "SKIP_TO_PROCESSING": {
      // Quick Mode: skip Steps 2-3, jump directly to Step 4 with default preset
      const perItemProgress: ItemProgress[] = state.queueItems.map((item) => ({
        id: item.id,
        status: "queued" as const,
        progressPercent: 0,
        currentStage: "",
        estimatedRemaining: 0,
      }))
      return {
        ...state,
        currentStep: 4 as WizardStep,
        highestStep: 4 as WizardStep,
        processingState: {
          status: "running",
          perItemProgress,
          elapsed: 0,
          estimatedRemaining: 0,
        },
        results: [],
      }
    }

    case "MINIMIZE":
      return { ...state, isMinimized: true }

    case "RESTORE":
      return { ...state, isMinimized: false }

    case "RESET":
      return createInitialState()

    default:
      return state
  }
}

// ---------------------------------------------------------------------------
// Context value type
// ---------------------------------------------------------------------------

type IngestWizardContextValue = {
  state: IngestWizardState
  // Navigation
  goToStep: (step: WizardStep) => void
  goNext: () => void
  goBack: () => void
  // Queue
  setQueueItems: (items: WizardQueueItem[]) => void
  // Presets & options
  setPreset: (preset: IngestPreset) => void
  setCustomOptions: (options: Partial<PresetConfig>) => void
  // Processing
  startProcessing: () => void
  skipToProcessing: () => void
  cancelProcessing: () => void
  cancelItem: (id: string) => void
  updateItemProgress: (progress: ItemProgress) => void
  updateProcessingState: (state: Partial<WizardProcessingState>) => void
  setResults: (results: WizardResultItem[]) => void
  // Minimize / restore
  minimize: () => void
  restore: () => void
  // Reset
  reset: () => void
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const IngestWizardContext = createContext<IngestWizardContextValue | null>(null)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

type IngestWizardProviderProps = {
  children: React.ReactNode
}

export const IngestWizardProvider: React.FC<IngestWizardProviderProps> = ({
  children,
}) => {
  const [state, dispatch] = useReducer(reducer, undefined, createInitialState)

  const goToStep = useCallback(
    (step: WizardStep) => dispatch({ type: "GO_TO_STEP", step }),
    []
  )
  const goNext = useCallback(() => dispatch({ type: "GO_NEXT" }), [])
  const goBack = useCallback(() => dispatch({ type: "GO_BACK" }), [])
  const setQueueItems = useCallback(
    (items: WizardQueueItem[]) => dispatch({ type: "SET_QUEUE_ITEMS", items }),
    []
  )
  const setPreset = useCallback(
    (preset: IngestPreset) => dispatch({ type: "SET_PRESET", preset }),
    []
  )
  const setCustomOptions = useCallback(
    (options: Partial<PresetConfig>) =>
      dispatch({ type: "SET_CUSTOM_OPTIONS", options }),
    []
  )
  const startProcessing = useCallback(
    () => dispatch({ type: "START_PROCESSING" }),
    []
  )
  const skipToProcessing = useCallback(
    () => dispatch({ type: "SKIP_TO_PROCESSING" }),
    []
  )
  const cancelProcessing = useCallback(
    () => dispatch({ type: "CANCEL_PROCESSING" }),
    []
  )
  const cancelItem = useCallback(
    (id: string) => dispatch({ type: "CANCEL_ITEM", id }),
    []
  )
  const updateItemProgress = useCallback(
    (progress: ItemProgress) =>
      dispatch({ type: "UPDATE_ITEM_PROGRESS", progress }),
    []
  )
  const updateProcessingState = useCallback(
    (ps: Partial<WizardProcessingState>) =>
      dispatch({ type: "UPDATE_PROCESSING_STATE", state: ps }),
    []
  )
  const setResults = useCallback(
    (results: WizardResultItem[]) => dispatch({ type: "SET_RESULTS", results }),
    []
  )
  const minimize = useCallback(() => dispatch({ type: "MINIMIZE" }), [])
  const restore = useCallback(() => dispatch({ type: "RESTORE" }), [])
  const reset = useCallback(() => dispatch({ type: "RESET" }), [])

  const value = useMemo<IngestWizardContextValue>(
    () => ({
      state,
      goToStep,
      goNext,
      goBack,
      setQueueItems,
      setPreset,
      setCustomOptions,
      startProcessing,
      skipToProcessing,
      cancelProcessing,
      cancelItem,
      updateItemProgress,
      updateProcessingState,
      setResults,
      minimize,
      restore,
      reset,
    }),
    [
      state,
      goToStep,
      goNext,
      goBack,
      setQueueItems,
      setPreset,
      setCustomOptions,
      startProcessing,
      skipToProcessing,
      cancelProcessing,
      cancelItem,
      updateItemProgress,
      updateProcessingState,
      setResults,
      minimize,
      restore,
      reset,
    ]
  )

  return (
    <IngestWizardContext.Provider value={value}>
      {children}
    </IngestWizardContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Access the ingest wizard context. Must be used within an IngestWizardProvider.
 */
export const useIngestWizard = (): IngestWizardContextValue => {
  const ctx = useContext(IngestWizardContext)
  if (!ctx) {
    throw new Error("useIngestWizard must be used within an IngestWizardProvider")
  }
  return ctx
}

export default IngestWizardContext
