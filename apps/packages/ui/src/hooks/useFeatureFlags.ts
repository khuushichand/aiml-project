import { useCallback } from "react"
import { useStorage } from "@plasmohq/storage/hook"

/**
 * Feature flags for gradual UX redesign rollout.
 * Most flags default to true (new UX); specific flags may default off.
 */

// Flag keys
export const FEATURE_FLAGS = {
  NEW_ONBOARDING: "ff_newOnboarding",
  NEW_CHAT: "ff_newChat",
  NEW_SETTINGS: "ff_newSettings",
  COMMAND_PALETTE: "ff_commandPalette",
  COMPACT_MESSAGES: "ff_compactMessages",
  CHAT_SIDEBAR: "ff_chatSidebar",
  COMPARE_MODE: "ff_compareMode",
  KNOWLEDGE_QA_STREAMING: "ff_knowledgeQaStreaming",
  KNOWLEDGE_QA_COMPARISON: "ff_knowledgeQaComparison",
  KNOWLEDGE_QA_BRANCHING: "ff_knowledgeQaBranching",
  MEDIA_NAVIGATION_PANEL: "ff_mediaNavigationPanel",
  MEDIA_RICH_RENDERING: "ff_mediaRichRendering",
  MEDIA_ANALYSIS_DISPLAY_MODE_SELECTOR: "ff_mediaAnalysisDisplayModeSelector",
  MEDIA_NAVIGATION_GENERATED_FALLBACK_DEFAULT:
    "ff_mediaNavigationGeneratedFallbackDefault"
} as const

export type FeatureFlagKey = (typeof FEATURE_FLAGS)[keyof typeof FEATURE_FLAGS]

const FEATURE_FLAG_DEFAULTS: Partial<Record<FeatureFlagKey, boolean>> = {
  [FEATURE_FLAGS.COMPARE_MODE]: false,
  [FEATURE_FLAGS.KNOWLEDGE_QA_STREAMING]: true,
  [FEATURE_FLAGS.KNOWLEDGE_QA_COMPARISON]: false,
  [FEATURE_FLAGS.KNOWLEDGE_QA_BRANCHING]: true,
  [FEATURE_FLAGS.MEDIA_NAVIGATION_PANEL]: true,
  [FEATURE_FLAGS.MEDIA_RICH_RENDERING]: true,
  [FEATURE_FLAGS.MEDIA_ANALYSIS_DISPLAY_MODE_SELECTOR]: true,
  [FEATURE_FLAGS.MEDIA_NAVIGATION_GENERATED_FALLBACK_DEFAULT]: true
}

/**
 * Hook to check if a feature flag is enabled.
 * @param flag - The feature flag key
 * @returns [isEnabled, setEnabled] tuple
 */
export function useFeatureFlag(flag: FeatureFlagKey) {
  // Default to true to enable new UX features by default
  return useStorage(flag, FEATURE_FLAG_DEFAULTS[flag] ?? true)
}

/**
 * Hook to get all feature flags at once.
 * Useful for settings page or debugging.
 */
export function useAllFeatureFlags() {
  const [newOnboarding, setNewOnboarding] = useStorage(
    FEATURE_FLAGS.NEW_ONBOARDING,
    true
  )
  const [newChat, setNewChat] = useStorage(FEATURE_FLAGS.NEW_CHAT, true)
  const [newSettings, setNewSettings] = useStorage(
    FEATURE_FLAGS.NEW_SETTINGS,
    true
  )
  const [commandPalette, setCommandPalette] = useStorage(
    FEATURE_FLAGS.COMMAND_PALETTE,
    true
  )
  const [compactMessages, setCompactMessages] = useStorage(
    FEATURE_FLAGS.COMPACT_MESSAGES,
    true
  )
  const [chatSidebar, setChatSidebar] = useStorage(
    FEATURE_FLAGS.CHAT_SIDEBAR,
    true
  )
  const [compareMode, setCompareMode] = useStorage(
    FEATURE_FLAGS.COMPARE_MODE,
    FEATURE_FLAG_DEFAULTS[FEATURE_FLAGS.COMPARE_MODE] ?? true
  )
  const [knowledgeQaStreaming, setKnowledgeQaStreaming] = useStorage(
    FEATURE_FLAGS.KNOWLEDGE_QA_STREAMING,
    FEATURE_FLAG_DEFAULTS[FEATURE_FLAGS.KNOWLEDGE_QA_STREAMING] ?? true
  )
  const [knowledgeQaComparison, setKnowledgeQaComparison] = useStorage(
    FEATURE_FLAGS.KNOWLEDGE_QA_COMPARISON,
    FEATURE_FLAG_DEFAULTS[FEATURE_FLAGS.KNOWLEDGE_QA_COMPARISON] ?? true
  )
  const [knowledgeQaBranching, setKnowledgeQaBranching] = useStorage(
    FEATURE_FLAGS.KNOWLEDGE_QA_BRANCHING,
    FEATURE_FLAG_DEFAULTS[FEATURE_FLAGS.KNOWLEDGE_QA_BRANCHING] ?? true
  )
  const [mediaNavigationPanel, setMediaNavigationPanel] = useStorage(
    FEATURE_FLAGS.MEDIA_NAVIGATION_PANEL,
    FEATURE_FLAG_DEFAULTS[FEATURE_FLAGS.MEDIA_NAVIGATION_PANEL] ?? true
  )
  const [mediaRichRendering, setMediaRichRendering] = useStorage(
    FEATURE_FLAGS.MEDIA_RICH_RENDERING,
    FEATURE_FLAG_DEFAULTS[FEATURE_FLAGS.MEDIA_RICH_RENDERING] ?? true
  )
  const [mediaAnalysisDisplayModeSelector, setMediaAnalysisDisplayModeSelector] =
    useStorage(
      FEATURE_FLAGS.MEDIA_ANALYSIS_DISPLAY_MODE_SELECTOR,
      FEATURE_FLAG_DEFAULTS[
        FEATURE_FLAGS.MEDIA_ANALYSIS_DISPLAY_MODE_SELECTOR
      ] ?? true
    )
  const [
    mediaNavigationGeneratedFallbackDefault,
    setMediaNavigationGeneratedFallbackDefault
  ] = useStorage(
    FEATURE_FLAGS.MEDIA_NAVIGATION_GENERATED_FALLBACK_DEFAULT,
    FEATURE_FLAG_DEFAULTS[
      FEATURE_FLAGS.MEDIA_NAVIGATION_GENERATED_FALLBACK_DEFAULT
    ] ?? true
  )

  return {
    flags: {
      newOnboarding,
      newChat,
      newSettings,
      commandPalette,
      compactMessages,
      chatSidebar,
      compareMode,
      knowledgeQaStreaming,
      knowledgeQaComparison,
      knowledgeQaBranching,
      mediaNavigationPanel,
      mediaRichRendering,
      mediaAnalysisDisplayModeSelector,
      mediaNavigationGeneratedFallbackDefault
    },
    setters: {
      setNewOnboarding,
      setNewChat,
      setNewSettings,
      setCommandPalette,
      setCompactMessages,
      setChatSidebar,
      setCompareMode,
      setKnowledgeQaStreaming,
      setKnowledgeQaComparison,
      setKnowledgeQaBranching,
      setMediaNavigationPanel,
      setMediaRichRendering,
      setMediaAnalysisDisplayModeSelector,
      setMediaNavigationGeneratedFallbackDefault
    },
    // Enable all new UX features
    enableAll: useCallback(() => {
      setNewOnboarding(true)
      setNewChat(true)
      setNewSettings(true)
      setCommandPalette(true)
      setCompactMessages(true)
      setChatSidebar(true)
      setCompareMode(true)
      setKnowledgeQaStreaming(true)
      setKnowledgeQaComparison(true)
      setKnowledgeQaBranching(true)
      setMediaNavigationPanel(true)
      setMediaRichRendering(true)
      setMediaAnalysisDisplayModeSelector(true)
      setMediaNavigationGeneratedFallbackDefault(true)
    }, [
      setNewOnboarding,
      setNewChat,
      setNewSettings,
      setCommandPalette,
      setCompactMessages,
      setChatSidebar,
      setCompareMode,
      setKnowledgeQaStreaming,
      setKnowledgeQaComparison,
      setKnowledgeQaBranching,
      setMediaNavigationPanel,
      setMediaRichRendering,
      setMediaAnalysisDisplayModeSelector,
      setMediaNavigationGeneratedFallbackDefault
    ]),
    // Disable all new UX features (revert to old)
    disableAll: useCallback(() => {
      setNewOnboarding(false)
      setNewChat(false)
      setNewSettings(false)
      setCommandPalette(false)
      setCompactMessages(false)
      setChatSidebar(false)
      setCompareMode(false)
      setKnowledgeQaStreaming(false)
      setKnowledgeQaComparison(false)
      setKnowledgeQaBranching(false)
      setMediaNavigationPanel(false)
      setMediaRichRendering(false)
      setMediaAnalysisDisplayModeSelector(false)
      setMediaNavigationGeneratedFallbackDefault(false)
    }, [
      setNewOnboarding,
      setNewChat,
      setNewSettings,
      setCommandPalette,
      setCompactMessages,
      setChatSidebar,
      setCompareMode,
      setKnowledgeQaStreaming,
      setKnowledgeQaComparison,
      setKnowledgeQaBranching,
      setMediaNavigationPanel,
      setMediaRichRendering,
      setMediaAnalysisDisplayModeSelector,
      setMediaNavigationGeneratedFallbackDefault
    ])
  }
}

/**
 * Convenience hooks for specific features
 */
export function useNewOnboarding() {
  return useFeatureFlag(FEATURE_FLAGS.NEW_ONBOARDING)
}

export function useNewChat() {
  return useFeatureFlag(FEATURE_FLAGS.NEW_CHAT)
}

export function useNewSettings() {
  return useFeatureFlag(FEATURE_FLAGS.NEW_SETTINGS)
}

export function useCommandPalette() {
  return useFeatureFlag(FEATURE_FLAGS.COMMAND_PALETTE)
}

export function useCompactMessages() {
  return useFeatureFlag(FEATURE_FLAGS.COMPACT_MESSAGES)
}

export function useChatSidebar() {
  return useFeatureFlag(FEATURE_FLAGS.CHAT_SIDEBAR)
}

export function useMediaNavigationPanel() {
  return useFeatureFlag(FEATURE_FLAGS.MEDIA_NAVIGATION_PANEL)
}

export function useKnowledgeQaStreaming() {
  return useFeatureFlag(FEATURE_FLAGS.KNOWLEDGE_QA_STREAMING)
}

export function useKnowledgeQaComparison() {
  return useFeatureFlag(FEATURE_FLAGS.KNOWLEDGE_QA_COMPARISON)
}

export function useKnowledgeQaBranching() {
  return useFeatureFlag(FEATURE_FLAGS.KNOWLEDGE_QA_BRANCHING)
}

export function useMediaRichRendering() {
  return useFeatureFlag(FEATURE_FLAGS.MEDIA_RICH_RENDERING)
}

export function useMediaAnalysisDisplayModeSelector() {
  return useFeatureFlag(FEATURE_FLAGS.MEDIA_ANALYSIS_DISPLAY_MODE_SELECTOR)
}

export function useMediaNavigationGeneratedFallbackDefault() {
  return useFeatureFlag(FEATURE_FLAGS.MEDIA_NAVIGATION_GENERATED_FALLBACK_DEFAULT)
}
