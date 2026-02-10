import { theme, type ThemeConfig } from "antd"
import type { RGBTriple, ThemeColorTokens } from "./types"

/**
 * Convert an RGB space-separated triple (e.g. "47 111 237") to a hex string ("#2f6fed").
 */
export function rgbTripleToHex(triple: RGBTriple): string {
  const parts = triple.trim().split(/\s+/)
  const r = Math.max(0, Math.min(255, parseInt(parts[0] ?? "0", 10)))
  const g = Math.max(0, Math.min(255, parseInt(parts[1] ?? "0", 10)))
  const b = Math.max(0, Math.min(255, parseInt(parts[2] ?? "0", 10)))
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`
}

/**
 * Build an Ant Design ThemeConfig from our semantic tokens + dark mode flag.
 * This bridges our CSS custom property system to Ant Design's theme engine
 * so that modals, dropdowns, tables, buttons, etc. all match.
 */
export function buildAntdThemeConfig(
  tokens: ThemeColorTokens,
  isDark: boolean
): ThemeConfig {
  return {
    algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: rgbTripleToHex(tokens.primary),
      colorSuccess: rgbTripleToHex(tokens.success),
      colorWarning: rgbTripleToHex(tokens.warn),
      colorError: rgbTripleToHex(tokens.danger),
      colorTextBase: rgbTripleToHex(tokens.text),
      colorBgBase: rgbTripleToHex(tokens.bg),
      colorBorder: rgbTripleToHex(tokens.border),
      colorBgContainer: rgbTripleToHex(tokens.surface),
      colorBgElevated: rgbTripleToHex(tokens.elevated),
      colorLink: rgbTripleToHex(tokens.primary),
      fontFamily: "Arimo",
    },
  }
}
