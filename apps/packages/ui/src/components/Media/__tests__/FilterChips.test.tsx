import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { FilterChips } from '../FilterChips'

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) => options?.defaultValue || key,
  }),
}))

describe('FilterChips', () => {
  const defaultProps = {
    mediaTypes: [] as string[],
    keywords: [] as string[],
    showFavoritesOnly: false,
    onRemoveMediaType: vi.fn(),
    onRemoveKeyword: vi.fn(),
    onToggleFavorites: vi.fn(),
    onClearAll: vi.fn(),
  }

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('returns null when no filters active', () => {
    const { container } = render(<FilterChips {...defaultProps} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders favorites chip when showFavoritesOnly is true', () => {
    render(<FilterChips {...defaultProps} showFavoritesOnly={true} />)

    expect(screen.getByText('Favorites only')).toBeInTheDocument()
    expect(screen.getByText('Active filters:')).toBeInTheDocument()
  })

  it('renders media type chips', () => {
    render(<FilterChips {...defaultProps} mediaTypes={['video', 'audio']} />)

    expect(screen.getByText('video')).toBeInTheDocument()
    expect(screen.getByText('audio')).toBeInTheDocument()
  })

  it('renders keyword chips', () => {
    render(<FilterChips {...defaultProps} keywords={['test', 'demo']} />)

    expect(screen.getByText('test')).toBeInTheDocument()
    expect(screen.getByText('demo')).toBeInTheDocument()
  })

  it('renders all filter types together', () => {
    render(
      <FilterChips
        {...defaultProps}
        showFavoritesOnly={true}
        mediaTypes={['video']}
        keywords={['research']}
      />
    )

    expect(screen.getByText('Favorites only')).toBeInTheDocument()
    expect(screen.getByText('video')).toBeInTheDocument()
    expect(screen.getByText('research')).toBeInTheDocument()
  })

  it('calls onRemoveMediaType when type chip clicked', () => {
    const onRemoveMediaType = vi.fn()
    render(
      <FilterChips
        {...defaultProps}
        mediaTypes={['video', 'audio']}
        onRemoveMediaType={onRemoveMediaType}
      />
    )

    const videoChip = screen.getByText('video').closest('button')
    expect(videoChip).not.toBeNull()
    fireEvent.click(videoChip!)

    expect(onRemoveMediaType).toHaveBeenCalledTimes(1)
    expect(onRemoveMediaType).toHaveBeenCalledWith('video')
  })

  it('calls onRemoveKeyword when keyword chip clicked', () => {
    const onRemoveKeyword = vi.fn()
    render(
      <FilterChips
        {...defaultProps}
        keywords={['test', 'demo']}
        onRemoveKeyword={onRemoveKeyword}
      />
    )

    const testChip = screen.getByText('test').closest('button')
    expect(testChip).not.toBeNull()
    fireEvent.click(testChip!)

    expect(onRemoveKeyword).toHaveBeenCalledTimes(1)
    expect(onRemoveKeyword).toHaveBeenCalledWith('test')
  })

  it('calls onToggleFavorites when favorites chip clicked', () => {
    const onToggleFavorites = vi.fn()
    render(
      <FilterChips
        {...defaultProps}
        showFavoritesOnly={true}
        onToggleFavorites={onToggleFavorites}
      />
    )

    const favoritesChip = screen.getByText('Favorites only').closest('button')
    expect(favoritesChip).not.toBeNull()
    fireEvent.click(favoritesChip!)

    expect(onToggleFavorites).toHaveBeenCalledTimes(1)
  })

  it('calls onClearAll when clear all clicked', () => {
    const onClearAll = vi.fn()
    render(
      <FilterChips
        {...defaultProps}
        mediaTypes={['video']}
        keywords={['test']}
        showFavoritesOnly={true}
        onClearAll={onClearAll}
      />
    )

    const clearAllButton = screen.getByText('Clear all')
    fireEvent.click(clearAllButton)

    expect(onClearAll).toHaveBeenCalledTimes(1)
  })

  it('displays clear all button when any filter is active', () => {
    render(<FilterChips {...defaultProps} mediaTypes={['video']} />)

    expect(screen.getByText('Clear all')).toBeInTheDocument()
  })

  it('handles multiple media types correctly', () => {
    const onRemoveMediaType = vi.fn()
    render(
      <FilterChips
        {...defaultProps}
        mediaTypes={['video', 'audio', 'document']}
        onRemoveMediaType={onRemoveMediaType}
      />
    )

    const audioChip = screen.getByText('audio').closest('button')
    fireEvent.click(audioChip!)

    expect(onRemoveMediaType).toHaveBeenCalledWith('audio')
  })

  it('handles multiple keywords correctly', () => {
    const onRemoveKeyword = vi.fn()
    render(
      <FilterChips
        {...defaultProps}
        keywords={['keyword1', 'keyword2', 'keyword3']}
        onRemoveKeyword={onRemoveKeyword}
      />
    )

    const keyword2Chip = screen.getByText('keyword2').closest('button')
    fireEvent.click(keyword2Chip!)

    expect(onRemoveKeyword).toHaveBeenCalledWith('keyword2')
  })

  it('has proper title attributes for accessibility', () => {
    render(
      <FilterChips
        {...defaultProps}
        showFavoritesOnly={true}
        mediaTypes={['video']}
        keywords={['test']}
      />
    )

    // Favorites chip should have a title
    const favoritesButton = screen.getByText('Favorites only').closest('button')
    expect(favoritesButton).toHaveAttribute('title', 'Remove favorites filter')

    // Clear all should have a title
    const clearAllButton = screen.getByText('Clear all')
    expect(clearAllButton).toHaveAttribute('title', 'Clear all filters')
  })

  it('renders correctly with only favorites filter', () => {
    const { container } = render(
      <FilterChips {...defaultProps} showFavoritesOnly={true} />
    )

    expect(container.firstChild).not.toBeNull()
    expect(screen.getByText('Favorites only')).toBeInTheDocument()
    expect(screen.getByText('Clear all')).toBeInTheDocument()
  })

  it('renders correctly with only media types', () => {
    const { container } = render(
      <FilterChips {...defaultProps} mediaTypes={['video']} />
    )

    expect(container.firstChild).not.toBeNull()
    expect(screen.getByText('video')).toBeInTheDocument()
    expect(screen.queryByText('Favorites only')).not.toBeInTheDocument()
  })

  it('renders correctly with only keywords', () => {
    const { container } = render(
      <FilterChips {...defaultProps} keywords={['research']} />
    )

    expect(container.firstChild).not.toBeNull()
    expect(screen.getByText('research')).toBeInTheDocument()
    expect(screen.queryByText('Favorites only')).not.toBeInTheDocument()
  })
})
