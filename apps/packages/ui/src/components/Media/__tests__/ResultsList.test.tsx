import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ResultsList } from '../ResultsList'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallbackOrOptions?: string | { defaultValue?: string }) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      return fallbackOrOptions?.defaultValue || key
    }
  })
}))

describe('ResultsList', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows relative created date badge when metadata includes created_at', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-02-18T12:00:00.000Z'))

    render(
      <ResultsList
        results={[
          {
            id: '1',
            kind: 'media',
            title: 'Document A',
            snippet: 'Sample snippet',
            meta: {
              type: 'pdf',
              created_at: '2026-02-16T12:00:00.000Z'
            }
          }
        ]}
        selectedId={null}
        onSelect={vi.fn()}
        totalCount={1}
        loadedCount={1}
      />
    )

    expect(screen.getByText('2d ago')).toBeInTheDocument()
  })

  it('highlights snippet matches for the active search query', () => {
    render(
      <ResultsList
        results={[
          {
            id: '1',
            kind: 'media',
            title: 'Document A',
            snippet: 'Alpha beta gamma',
          }
        ]}
        selectedId={null}
        onSelect={vi.fn()}
        totalCount={1}
        loadedCount={1}
        searchQuery="beta"
      />
    )

    expect(screen.getByText('beta').tagName).toBe('MARK')
  })

  it('shows actionable guidance when filters hide all results', () => {
    const onClearSearch = vi.fn()
    const onClearFilters = vi.fn()
    const onOpenQuickIngest = vi.fn()

    render(
      <ResultsList
        results={[]}
        selectedId={null}
        onSelect={vi.fn()}
        totalCount={0}
        loadedCount={0}
        hasActiveFilters
        searchQuery="deep query"
        onClearSearch={onClearSearch}
        onClearFilters={onClearFilters}
        onOpenQuickIngest={onOpenQuickIngest}
      />
    )

    expect(screen.getByText('No results match your filters')).toBeInTheDocument()
    expect(screen.getByText('Try broadening your query or removing filters.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Clear search' }))
    fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
    fireEvent.click(screen.getByRole('button', { name: 'Open Quick Ingest' }))

    expect(onClearSearch).toHaveBeenCalledTimes(1)
    expect(onClearFilters).toHaveBeenCalledTimes(1)
    expect(onOpenQuickIngest).toHaveBeenCalledTimes(1)
  })

  it('shows contextual guidance for empty query results and offers recovery actions', () => {
    const onClearSearch = vi.fn()
    const onOpenQuickIngest = vi.fn()

    render(
      <ResultsList
        results={[]}
        selectedId={null}
        onSelect={vi.fn()}
        totalCount={0}
        loadedCount={0}
        searchQuery="rare phrase"
        onClearSearch={onClearSearch}
        onOpenQuickIngest={onOpenQuickIngest}
      />
    )

    expect(screen.getByText('No results found')).toBeInTheDocument()
    expect(screen.getByText('Try broader terms, or ingest new content to search.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Clear search' }))
    fireEvent.click(screen.getByRole('button', { name: 'Open Quick Ingest' }))

    expect(onClearSearch).toHaveBeenCalledTimes(1)
    expect(onOpenQuickIngest).toHaveBeenCalledTimes(1)
  })

  it('uses enlarged favorite hit target padding for touch ergonomics', () => {
    const onToggleFavorite = vi.fn()

    render(
      <ResultsList
        results={[
          {
            id: '1',
            kind: 'media',
            title: 'Document A'
          }
        ]}
        selectedId={null}
        onSelect={vi.fn()}
        totalCount={1}
        loadedCount={1}
        favorites={new Set()}
        onToggleFavorite={onToggleFavorite}
      />
    )

    const favoriteButton = screen.getByRole('button', { name: 'Add to favorites' })
    expect(favoriteButton).toHaveClass('p-1.5')

    fireEvent.click(favoriteButton)
    expect(onToggleFavorite).toHaveBeenCalledWith('1')
  })

  it('shows loading skeletons before results resolve and removes them after data arrives', () => {
    const { rerender, container } = render(
      <ResultsList
        results={[]}
        selectedId={null}
        onSelect={vi.fn()}
        totalCount={0}
        loadedCount={0}
        isLoading
      />
    )

    expect(container.querySelectorAll('.animate-pulse')).toHaveLength(5)

    rerender(
      <ResultsList
        results={[
          {
            id: '1',
            kind: 'media',
            title: 'Loaded row',
            snippet: 'Resolved content'
          }
        ]}
        selectedId={null}
        onSelect={vi.fn()}
        totalCount={1}
        loadedCount={1}
        isLoading={false}
      />
    )

    expect(container.querySelectorAll('.animate-pulse')).toHaveLength(0)
    expect(screen.getByText('Loaded row')).toBeInTheDocument()
  })
})
