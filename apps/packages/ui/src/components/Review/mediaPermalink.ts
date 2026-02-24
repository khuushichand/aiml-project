export const normalizeMediaPermalinkId = (
  value: string | null | undefined
): string | null => {
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

export const getMediaPermalinkIdFromSearch = (search: string): string | null => {
  const params = new URLSearchParams(search)
  return normalizeMediaPermalinkId(params.get('id'))
}

export const buildMediaPermalinkSearch = (
  currentSearch: string,
  mediaId: string | null
): string => {
  const params = new URLSearchParams(currentSearch)
  const normalizedId = normalizeMediaPermalinkId(mediaId)

  if (normalizedId) {
    params.set('id', normalizedId)
  } else {
    params.delete('id')
  }

  const serialized = params.toString()
  return serialized ? `?${serialized}` : ''
}

export const buildMediaTrashHandoffSearch = (
  selectedIds: Array<string | number>
): string => {
  const normalizedIds = Array.from(
    new Set(
      selectedIds
        .map((id) => String(id).trim())
        .filter((id) => id.length > 0)
    )
  )

  const params = new URLSearchParams()
  params.set("from", "media-multi")
  if (normalizedIds.length > 0) {
    params.set("ids", normalizedIds.join(","))
  }

  const serialized = params.toString()
  return serialized ? `?${serialized}` : ""
}
