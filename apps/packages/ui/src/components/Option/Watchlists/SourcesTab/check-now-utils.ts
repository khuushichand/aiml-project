export const normalizeSourceIds = (sourceIds: Array<number | string | null | undefined>): number[] =>
  Array.from(
    new Set(
      sourceIds
        .map((id) => Number(id))
        .filter((id) => Number.isInteger(id) && id > 0)
    )
  )

export const shouldConfirmMultiSourceCheck = (
  sourceIds: Array<number | string | null | undefined>
): boolean => normalizeSourceIds(sourceIds).length > 1

export const resolveCheckNowTargets = (
  clickedSourceId: number,
  selectedSourceIds: Array<number | string | null | undefined>
): number[] => {
  const normalizedSelectedIds = normalizeSourceIds(selectedSourceIds)
  if (normalizedSelectedIds.length > 1 && normalizedSelectedIds.includes(clickedSourceId)) {
    return normalizedSelectedIds
  }
  return normalizeSourceIds([clickedSourceId])
}
