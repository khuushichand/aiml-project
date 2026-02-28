import type { WritingWorldInfoEntry } from "./writing-context-utils"

export type WorldInfoMoveDirection = "up" | "down"

export const moveWorldInfoEntry = (
  entries: WritingWorldInfoEntry[],
  entryId: string,
  direction: WorldInfoMoveDirection
): WritingWorldInfoEntry[] => {
  if (!Array.isArray(entries) || entries.length === 0) return entries
  const index = entries.findIndex((entry) => entry.id === entryId)
  if (index < 0) return entries

  const targetIndex = direction === "up" ? index - 1 : index + 1
  if (targetIndex < 0 || targetIndex >= entries.length) return entries

  const next = [...entries]
  const [entry] = next.splice(index, 1)
  next.splice(targetIndex, 0, entry)
  return next
}
