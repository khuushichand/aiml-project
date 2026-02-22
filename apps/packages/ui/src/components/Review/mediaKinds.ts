export interface MediaKindsState {
  media: boolean
  notes: boolean
}

export type MediaKindsTab = 'media' | 'notes'

export const isMediaOnly = (kinds: MediaKindsState): boolean =>
  kinds.media && !kinds.notes

export const isNotesOnly = (kinds: MediaKindsState): boolean =>
  !kinds.media && kinds.notes

export const resolveKindsForTab = (
  current: MediaKindsState,
  nextTab: MediaKindsTab
): MediaKindsState => {
  if (nextTab === 'media') {
    if (isMediaOnly(current)) return current
    return { media: true, notes: false }
  }

  if (isNotesOnly(current)) return current
  return { media: false, notes: true }
}
