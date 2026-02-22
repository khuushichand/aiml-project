import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { Pagination } from '../Pagination'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallbackOrOptions?: string | { defaultValue?: string }) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      return fallbackOrOptions?.defaultValue || key
    }
  })
}))

describe('Pagination', () => {
  it('supports changing page size via selector', () => {
    const onItemsPerPageChange = vi.fn()

    render(
      <Pagination
        currentPage={1}
        totalPages={5}
        onPageChange={vi.fn()}
        totalItems={100}
        itemsPerPage={20}
        currentItemsCount={20}
        pageSizeOptions={[20, 50, 100]}
        onItemsPerPageChange={onItemsPerPageChange}
      />
    )

    const select = screen.getByLabelText('Per page:') as HTMLSelectElement
    fireEvent.change(select, { target: { value: '50' } })

    expect(onItemsPerPageChange).toHaveBeenCalledWith(50)
  })
})
