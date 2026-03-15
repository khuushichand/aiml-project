import { applyTextAtRange } from "@/components/Option/WritingPlayground/writing-editor-actions-utils"

export type TextSelection = {
  start: number
  end: number
}

export const getSelectionFromElement = (
  element: HTMLInputElement | HTMLTextAreaElement | null | undefined,
  currentValue: string
): TextSelection => {
  const fallback = currentValue.length
  return {
    start: element?.selectionStart ?? fallback,
    end: element?.selectionEnd ?? element?.selectionStart ?? fallback
  }
}

export const insertTextAtSelection = (
  currentValue: string,
  selection: TextSelection,
  textToInsert: string
): { nextValue: string; cursor: number } =>
  applyTextAtRange(currentValue, selection.start, selection.end, textToInsert)

export const restoreSelection = (
  element: HTMLInputElement | HTMLTextAreaElement | null | undefined,
  cursor: number
): void => {
  if (!element) return
  if (typeof window === "undefined") return
  window.requestAnimationFrame(() => {
    element.focus()
    element.setSelectionRange(cursor, cursor)
  })
}
