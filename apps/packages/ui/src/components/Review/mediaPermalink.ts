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
