import type { RGBTriple } from "./types"
import { rgbTripleToHex } from "./antd-theme"

/**
 * Convert a hex color string (e.g. "#2f6fed") to an RGB space-separated triple ("47 111 237").
 */
export function hexToRgbTriple(hex: string): RGBTriple {
  const cleaned = hex.replace(/^#/, "")
  if (cleaned.length !== 6) {
    return "0 0 0"
  }
  const r = parseInt(cleaned.slice(0, 2), 16)
  const g = parseInt(cleaned.slice(2, 4), 16)
  const b = parseInt(cleaned.slice(4, 6), 16)
  if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) {
    return "0 0 0"
  }
  return `${r} ${g} ${b}`
}

/**
 * Validate that a string is a valid RGB space-separated triple (e.g. "47 111 237").
 */
export function validateRgbTriple(triple: string): boolean {
  const parts = triple.trim().split(/\s+/)
  if (parts.length !== 3) return false
  return parts.every((p) => {
    const n = parseInt(p, 10)
    return !Number.isNaN(n) && n >= 0 && n <= 255 && String(n) === p
  })
}

// Re-export for convenience
export { rgbTripleToHex }
