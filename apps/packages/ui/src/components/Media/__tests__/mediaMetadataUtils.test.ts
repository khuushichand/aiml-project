import { describe, expect, it } from 'vitest'
import { estimateReadingTimeMinutes } from '../mediaMetadataUtils'

describe('mediaMetadataUtils', () => {
  it('estimates reading time from word count', () => {
    expect(
      estimateReadingTimeMinutes({
        wordCount: 450,
        charCount: 0
      })
    ).toBe(3)
  })

  it('falls back to character count when word count is unavailable', () => {
    expect(
      estimateReadingTimeMinutes({
        wordCount: 0,
        charCount: 2500
      })
    ).toBe(3)
  })

  it('returns null when no usable text length exists', () => {
    expect(
      estimateReadingTimeMinutes({
        wordCount: 0,
        charCount: 0
      })
    ).toBeNull()
  })

  it('returns null for invalid words-per-minute input', () => {
    expect(
      estimateReadingTimeMinutes({
        wordCount: 200,
        wordsPerMinute: 0
      })
    ).toBeNull()
  })
})
