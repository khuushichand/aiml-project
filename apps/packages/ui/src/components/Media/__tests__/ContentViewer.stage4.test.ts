import { describe, expect, it } from 'vitest'
import { shouldShowMediaDeveloperTools } from '../ContentViewer'

describe('ContentViewer stage 4 developer tools gating', () => {
  it('returns false when runtime env is missing', () => {
    expect(shouldShowMediaDeveloperTools(undefined)).toBe(false)
    expect(shouldShowMediaDeveloperTools(null)).toBe(false)
  })

  it('returns true when DEV mode is enabled', () => {
    expect(shouldShowMediaDeveloperTools({ DEV: true, MODE: 'test' })).toBe(true)
  })

  it('returns true when MODE is development', () => {
    expect(shouldShowMediaDeveloperTools({ MODE: 'development' })).toBe(true)
  })

  it('returns false in non-development runtime modes', () => {
    expect(shouldShowMediaDeveloperTools({ DEV: false, MODE: 'production' })).toBe(false)
    expect(shouldShowMediaDeveloperTools({ DEV: false, MODE: 'test' })).toBe(false)
  })
})
