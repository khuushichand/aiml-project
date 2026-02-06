import { useCallback, useEffect } from "react"
import { useDocumentWorkspaceStore } from "@/store/document-workspace"
import type { EpubTheme, EpubScrollMode, EpubSpreadMode, EpubFontFamily } from "@/components/DocumentWorkspace/types"

/**
 * EPUB theme definitions for epub.js
 * Each theme defines CSS styles to be applied to the EPUB content
 */
export const EPUB_THEMES: Record<EpubTheme, Record<string, Record<string, string>>> = {
  light: {
    body: {
      background: "#ffffff",
      color: "#1a1a1a"
    }
  },
  dark: {
    body: {
      background: "#1a1a1a",
      color: "#e5e5e5"
    },
    a: {
      color: "#93c5fd"
    }
  },
  sepia: {
    body: {
      background: "#f4ecd8",
      color: "#5b4636"
    },
    a: {
      color: "#8b6914"
    }
  }
}

/**
 * Theme display information for the UI
 */
export const THEME_INFO: Record<EpubTheme, { label: string; icon: string; preview: { bg: string; text: string } }> = {
  light: {
    label: "Light",
    icon: "sun",
    preview: { bg: "#ffffff", text: "#1a1a1a" }
  },
  dark: {
    label: "Dark",
    icon: "moon",
    preview: { bg: "#1a1a1a", text: "#e5e5e5" }
  },
  sepia: {
    label: "Sepia",
    icon: "book",
    preview: { bg: "#f4ecd8", text: "#5b4636" }
  }
}

/**
 * Scroll mode display information for the UI
 */
export const SCROLL_MODE_INFO: Record<EpubScrollMode, { label: string; description: string }> = {
  paginated: {
    label: "Paginated",
    description: "Navigate page by page"
  },
  continuous: {
    label: "Continuous",
    description: "Scroll through content"
  }
}

/**
 * Spread mode display information for the UI
 */
export const SPREAD_MODE_INFO: Record<EpubSpreadMode, { label: string; description: string }> = {
  none: {
    label: "Single",
    description: "Single page view"
  },
  auto: {
    label: "Auto",
    description: "Two pages when window is wide enough"
  },
  always: {
    label: "Two-Page",
    description: "Always show two pages side by side"
  }
}

/**
 * Font family CSS values
 */
export const FONT_FAMILY_CSS: Record<EpubFontFamily, string> = {
  inter: "'Inter', system-ui, sans-serif",
  georgia: "Georgia, 'Times New Roman', serif",
  merriweather: "'Merriweather', Georgia, serif",
  system: "system-ui, -apple-system, sans-serif"
}

/**
 * Font family display information
 */
export const FONT_FAMILY_INFO: Record<EpubFontFamily, { label: string }> = {
  inter: { label: "Inter" },
  georgia: { label: "Georgia" },
  merriweather: { label: "Merriweather" },
  system: { label: "System" }
}

/**
 * Hook to manage EPUB reader settings.
 *
 * Provides access to:
 * - Current theme and scroll mode
 * - Setters for theme and scroll mode
 * - Persistence via localStorage
 *
 * @returns EPUB settings state and actions
 */
export function useEpubSettings() {
  const epubTheme = useDocumentWorkspaceStore((s) => s.epubTheme)
  const epubScrollMode = useDocumentWorkspaceStore((s) => s.epubScrollMode)
  const epubSpreadMode = useDocumentWorkspaceStore((s) => s.epubSpreadMode)
  const epubFontSize = useDocumentWorkspaceStore((s) => s.epubFontSize)
  const epubFontFamily = useDocumentWorkspaceStore((s) => s.epubFontFamily)
  const epubLineHeight = useDocumentWorkspaceStore((s) => s.epubLineHeight)
  const setEpubTheme = useDocumentWorkspaceStore((s) => s.setEpubTheme)
  const setEpubScrollMode = useDocumentWorkspaceStore((s) => s.setEpubScrollMode)
  const setEpubSpreadMode = useDocumentWorkspaceStore((s) => s.setEpubSpreadMode)
  const setEpubFontSize = useDocumentWorkspaceStore((s) => s.setEpubFontSize)
  const setEpubFontFamily = useDocumentWorkspaceStore((s) => s.setEpubFontFamily)
  const setEpubLineHeight = useDocumentWorkspaceStore((s) => s.setEpubLineHeight)

  // Get theme styles for epub.js
  const getThemeStyles = useCallback((theme: EpubTheme) => {
    return EPUB_THEMES[theme]
  }, [])

  // Get current theme styles
  const currentThemeStyles = EPUB_THEMES[epubTheme]

  return {
    // State
    theme: epubTheme,
    scrollMode: epubScrollMode,
    spreadMode: epubSpreadMode,
    fontSize: epubFontSize,
    fontFamily: epubFontFamily,
    lineHeight: epubLineHeight,
    currentThemeStyles,

    // Actions
    setTheme: setEpubTheme,
    setScrollMode: setEpubScrollMode,
    setSpreadMode: setEpubSpreadMode,
    setFontSize: setEpubFontSize,
    setFontFamily: setEpubFontFamily,
    setLineHeight: setEpubLineHeight,
    getThemeStyles,

    // Theme info
    themeInfo: THEME_INFO[epubTheme],
    scrollModeInfo: SCROLL_MODE_INFO[epubScrollMode]
  }
}

export default useEpubSettings
