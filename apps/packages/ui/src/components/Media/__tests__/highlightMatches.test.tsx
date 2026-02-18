import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { highlightMatches, tokenizeSearchQuery } from '../highlightMatches'

describe('highlightMatches', () => {
  it('tokenizes quoted phrases and skips boolean operators', () => {
    expect(tokenizeSearchQuery('alpha AND "exact phrase" -beta +gamma OR NOT delta')).toEqual([
      'alpha',
      'exact phrase',
      'beta',
      'gamma',
      'delta'
    ])
  })

  it('highlights literal regex characters safely', () => {
    render(
      <div>{highlightMatches('Use C++ and (test) patterns.', 'C++ (test)')}</div>
    )

    expect(screen.getByText('C++').tagName).toBe('MARK')
    expect(screen.getByText('(test)').tagName).toBe('MARK')
  })

  it('keeps html-like snippet content escaped', () => {
    const { container } = render(
      <div>{highlightMatches('<script>alert(1)</script>', 'script')}</div>
    )

    expect(container.querySelector('script')).toBeNull()
    expect(container.querySelectorAll('mark').length).toBeGreaterThan(0)
  })
})
