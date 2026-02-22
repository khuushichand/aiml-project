export const FLASHCARD_FIELD_MAX_BYTES = 8192
const FLASHCARD_FIELD_WARNING_THRESHOLD_RATIO = 0.9

export type FlashcardFieldLimitState = "normal" | "warning" | "over"

export function getUtf8ByteLength(value: string | null | undefined): number {
  if (!value) return 0
  if (typeof TextEncoder === "undefined") {
    return value.length
  }
  return new TextEncoder().encode(value).length
}

export function getFlashcardFieldLimitState(
  byteLength: number,
  maxBytes: number = FLASHCARD_FIELD_MAX_BYTES
): FlashcardFieldLimitState {
  if (byteLength > maxBytes) return "over"
  if (byteLength >= Math.floor(maxBytes * FLASHCARD_FIELD_WARNING_THRESHOLD_RATIO)) {
    return "warning"
  }
  return "normal"
}
