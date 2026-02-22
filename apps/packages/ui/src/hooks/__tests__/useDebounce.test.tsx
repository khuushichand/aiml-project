import React from 'react'
import { describe, expect, it, vi, afterEach } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { useDebounce } from '../useDebounce'

function DebounceProbe({ value, delay }: { value: string; delay: number }) {
  const debounced = useDebounce(value, delay)
  return <div data-testid="debounced-value">{debounced}</div>
}

describe('useDebounce', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('delays value updates until the debounce duration elapses', () => {
    vi.useFakeTimers()

    const { rerender } = render(<DebounceProbe value="" delay={300} />)
    expect(screen.getByTestId('debounced-value')).toHaveTextContent('')

    act(() => {
      rerender(<DebounceProbe value="abc" delay={300} />)
    })
    expect(screen.getByTestId('debounced-value')).toHaveTextContent('')

    act(() => {
      vi.advanceTimersByTime(299)
    })
    expect(screen.getByTestId('debounced-value')).toHaveTextContent('')

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(screen.getByTestId('debounced-value')).toHaveTextContent('abc')
  })

  it('coalesces rapid input changes to the latest value', () => {
    vi.useFakeTimers()

    const { rerender } = render(<DebounceProbe value="a" delay={300} />)
    act(() => {
      rerender(<DebounceProbe value="ab" delay={300} />)
      rerender(<DebounceProbe value="abc" delay={300} />)
    })

    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(screen.getByTestId('debounced-value')).toHaveTextContent('abc')
  })
})
