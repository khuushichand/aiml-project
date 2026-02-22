import { describe, expect, it } from 'vitest'
import {
  isMediaOnly,
  isNotesOnly,
  resolveKindsForTab,
  type MediaKindsState
} from '../mediaKinds'

describe('mediaKinds helpers', () => {
  it('identifies media-only and notes-only states', () => {
    expect(isMediaOnly({ media: true, notes: false })).toBe(true)
    expect(isMediaOnly({ media: false, notes: true })).toBe(false)

    expect(isNotesOnly({ media: false, notes: true })).toBe(true)
    expect(isNotesOnly({ media: true, notes: false })).toBe(false)
  })

  it('switches to media tab state', () => {
    const current: MediaKindsState = { media: false, notes: true }
    expect(resolveKindsForTab(current, 'media')).toEqual({ media: true, notes: false })
  })

  it('switches to notes tab state', () => {
    const current: MediaKindsState = { media: true, notes: false }
    expect(resolveKindsForTab(current, 'notes')).toEqual({ media: false, notes: true })
  })

  it('returns same object when selected tab already active', () => {
    const mediaCurrent: MediaKindsState = { media: true, notes: false }
    const notesCurrent: MediaKindsState = { media: false, notes: true }

    expect(resolveKindsForTab(mediaCurrent, 'media')).toBe(mediaCurrent)
    expect(resolveKindsForTab(notesCurrent, 'notes')).toBe(notesCurrent)
  })
})
