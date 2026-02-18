import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { JumpToNavigator } from '../JumpToNavigator'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallbackOrOptions?: string | { defaultValue?: string }) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      return fallbackOrOptions?.defaultValue || key
    }
  })
}))

describe('JumpToNavigator', () => {
  it('does not render when result count is 5 or fewer', () => {
    const { container } = render(
      <JumpToNavigator
        results={[1, 2, 3, 4, 5].map((id) => ({ id, title: `Item ${id}` }))}
        selectedId={null}
        onSelect={vi.fn()}
      />
    )

    expect(container.firstChild).toBeNull()
  })

  it('renders buttons and preserves selected aria-pressed state', () => {
    const onSelect = vi.fn()
    render(
      <JumpToNavigator
        results={[1, 2, 3, 4, 5, 6].map((id) => ({ id, title: `Item ${id}` }))}
        selectedId={3}
        onSelect={onSelect}
        maxButtons={12}
      />
    )

    const selectedButton = screen.getByTitle('Item 3')
    expect(selectedButton).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(screen.getByTitle('Item 2'))
    expect(onSelect).toHaveBeenCalledWith(2)
  })

  it('shows overflow indicator when results exceed maxButtons', () => {
    render(
      <JumpToNavigator
        results={Array.from({ length: 14 }, (_, idx) => ({
          id: idx + 1,
          title: `Item ${idx + 1}`
        }))}
        selectedId={null}
        onSelect={vi.fn()}
        maxButtons={12}
      />
    )

    expect(screen.getByText('+2')).toBeInTheDocument()
  })
})
