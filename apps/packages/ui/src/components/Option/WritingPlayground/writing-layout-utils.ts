export type WritingLayoutMode = "compact" | "expanded"

const EXPANDED_LAYOUT_MIN_WIDTH = 1100

export function resolveWritingLayoutMode(width: number): WritingLayoutMode {
  return width < EXPANDED_LAYOUT_MIN_WIDTH ? "compact" : "expanded"
}
