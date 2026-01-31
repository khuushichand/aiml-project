import { afterEach, describe, expect, it, vi } from 'vitest'
import { shouldSkillTrigger } from '../disco-skill-check'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('shouldSkillTrigger clamping', () => {
  it('clamps low stats to 1 for trigger/pass rolls', () => {
    const rand = vi.spyOn(Math, 'random')
    rand.mockReturnValueOnce(0.05)
    rand.mockReturnValueOnce(0.9)

    const result = shouldSkillTrigger(0, 1)

    expect(result.shouldTrigger).toBe(true)
    expect(result.passed).toBe(true)
  })

  it('clamps high stats to 10 for trigger probability', () => {
    const rand = vi.spyOn(Math, 'random')
    rand.mockReturnValueOnce(0.6)

    const result = shouldSkillTrigger(20, 0.5)

    expect(result.shouldTrigger).toBe(false)
    expect(result.passed).toBe(false)
  })
})
