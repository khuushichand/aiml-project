import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { SearchBar } from '../SearchBar'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallbackOrOptions?: string | { defaultValue?: string }) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      return fallbackOrOptions?.defaultValue || key
    }
  })
}))

describe('SearchBar', () => {
  it('renders search syntax help affordance', () => {
    render(<SearchBar value="" onChange={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Search syntax help' })).toBeInTheDocument()
  })

  it('supports clearing search text', () => {
    const onChange = vi.fn()
    render(<SearchBar value="hello" onChange={onChange} />)

    fireEvent.click(screen.getByRole('button', { name: 'Clear search' }))

    expect(onChange).toHaveBeenCalledWith('')
  })
})
