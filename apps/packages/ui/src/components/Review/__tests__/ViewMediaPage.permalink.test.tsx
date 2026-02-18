import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import ViewMediaPage from '../ViewMediaPage'

const mocks = vi.hoisted(() => ({
  queryData: [] as Array<any>,
  detailById: {} as Record<string, any>,
  refetch: vi.fn(),
  bgRequest: vi.fn(),
  getSetting: vi.fn(),
  setSetting: vi.fn(),
  clearSetting: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  messageWarning: vi.fn(),
  showUndoNotification: vi.fn()
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string; [k: string]: unknown }
    ) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      return fallbackOrOptions?.defaultValue || key
    }
  })
}))

vi.mock('@tanstack/react-query', () => ({
  useQuery: () => ({
    data: mocks.queryData,
    refetch: mocks.refetch,
    isLoading: false,
    isFetching: false
  })
}))

vi.mock('@plasmohq/storage', () => ({
  Storage: class {
    async get() {
      return null
    }
    async set() {
      return undefined
    }
    async remove() {
      return undefined
    }
  }
}))

vi.mock('@plasmohq/storage/hook', async () => {
  const React = await import('react')
  return {
    useStorage: (key: string, initialValue: unknown) => {
      const [value, setValue] = React.useState(initialValue)
      return [value, setValue] as const
    }
  }
})

vi.mock('@/services/background-proxy', () => ({
  bgRequest: mocks.bgRequest
}))

vi.mock('@/services/settings/registry', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/settings/registry')>()
  return {
    ...actual,
    getSetting: mocks.getSetting,
    setSetting: mocks.setSetting,
    clearSetting: mocks.clearSetting
  }
})

vi.mock('@/hooks/useDebounce', () => ({
  useDebounce: (value: string) => value
}))

vi.mock('@/hooks/useServerOnline', () => ({
  useServerOnline: () => true
}))

vi.mock('@/hooks/useServerCapabilities', () => ({
  useServerCapabilities: () => ({ capabilities: { hasMedia: true }, loading: false })
}))

vi.mock('@/context/demo-mode', () => ({
  useDemoMode: () => ({ demoEnabled: false })
}))

vi.mock('@/hooks/useConnectionState', () => ({
  useConnectionState: () => ({ serverUrl: 'http://localhost:8000' })
}))

vi.mock('@/hooks/useMessageOption', () => ({
  useMessageOption: () => ({
    setChatMode: vi.fn(),
    setSelectedKnowledge: vi.fn(),
    setRagMediaIds: vi.fn()
  })
}))

vi.mock('@/hooks/useAntdMessage', () => ({
  useAntdMessage: () => ({
    success: mocks.messageSuccess,
    error: mocks.messageError,
    warning: mocks.messageWarning
  })
}))

vi.mock('@/hooks/useUndoNotification', () => ({
  useUndoNotification: () => ({
    showUndoNotification: mocks.showUndoNotification
  })
}))

vi.mock('@/hooks/useFeatureFlags', () => ({
  useMediaNavigationPanel: () => [false],
  useMediaNavigationGeneratedFallbackDefault: () => [false],
  useMediaRichRendering: () => [false],
  useMediaAnalysisDisplayModeSelector: () => [false]
}))

vi.mock('@/hooks/useMediaNavigation', () => ({
  useMediaNavigation: () => ({
    data: { nodes: [] },
    isLoading: false,
    error: null,
    refetch: vi.fn()
  })
}))

vi.mock('@/services/tldw/TldwApiClient', () => ({
  tldwClient: {
    getConfig: vi.fn().mockResolvedValue({})
  }
}))

vi.mock('@/components/Common/FeatureEmptyState', () => ({
  default: () => <div data-testid="feature-empty" />
}))

vi.mock('@/components/Media/SearchBar', () => ({
  SearchBar: () => <div data-testid="search-bar" />
}))

vi.mock('@/components/Media/FilterPanel', () => ({
  FilterPanel: () => <div data-testid="filter-panel" />
}))

vi.mock('@/components/Media/JumpToNavigator', () => ({
  JumpToNavigator: () => <div data-testid="jump-to-navigator" />
}))

vi.mock('@/components/Media/KeyboardShortcutsOverlay', () => ({
  KeyboardShortcutsOverlay: () => null
}))

vi.mock('@/components/Media/FilterChips', () => ({
  FilterChips: () => <div data-testid="filter-chips" />
}))

vi.mock('@/components/Media/Pagination', () => ({
  Pagination: () => <div data-testid="pagination" />
}))

vi.mock('@/components/Media/MediaSectionNavigator', () => ({
  MediaSectionNavigator: () => <div data-testid="media-section-navigator" />
}))

vi.mock('@/components/Media/ResultsList', () => ({
  ResultsList: ({ results, selectedId, onSelect }: any) => (
    <div data-testid="results-list">
      {results.map((result: any) => (
        <button
          key={String(result.id)}
          type="button"
          data-testid={`result-${String(result.id)}`}
          aria-pressed={selectedId === result.id}
          onClick={() => onSelect(result.id)}
        >
          {result.title}
        </button>
      ))}
    </div>
  )
}))

vi.mock('@/components/Media/ContentViewer', () => ({
  ContentViewer: ({ selectedMedia, onNext, onPrevious, hasNext, hasPrevious }: any) => (
    <div data-testid="mock-content-viewer">
      <div data-testid="selected-media-id">
        {selectedMedia?.id != null ? String(selectedMedia.id) : 'none'}
      </div>
      <button
        type="button"
        onClick={onPrevious}
        disabled={!hasPrevious}
        aria-label="Previous item"
      >
        Previous item
      </button>
      <button
        type="button"
        onClick={onNext}
        disabled={!hasNext}
        aria-label="Next item"
      >
        Next item
      </button>
    </div>
  )
}))

const LocationProbe = () => {
  const location = useLocation()
  return <div data-testid="location-search">{location.search}</div>
}

const renderMediaPage = (initialEntry: string) => {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route
          path="/media"
          element={
            <>
              <LocationProbe />
              <ViewMediaPage />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  )
}

describe('ViewMediaPage Stage 3 permalinks', () => {
  beforeEach(() => {
    mocks.queryData = []
    mocks.detailById = {}
    mocks.refetch.mockReset()
    mocks.refetch.mockResolvedValue({ data: mocks.queryData })
    mocks.getSetting.mockReset()
    mocks.getSetting.mockResolvedValue(undefined)
    mocks.setSetting.mockReset()
    mocks.clearSetting.mockReset()
    mocks.bgRequest.mockReset()

    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || '')
      if (path.startsWith('/api/v1/media/?page=')) {
        return { items: [], pagination: { total_pages: 1, total_items: 0 } }
      }
      if (path.startsWith('/api/v1/media/keywords')) {
        return { keywords: [] }
      }
      if (path.startsWith('/api/v1/media/')) {
        const id = path.replace('/api/v1/media/', '').split('?')[0]
        return (
          mocks.detailById[id] || {
            id,
            title: `Media ${id}`,
            type: 'document',
            content: { text: `Content for ${id}` }
          }
        )
      }
      if (path.startsWith('/api/v1/notes')) {
        return { items: [], pagination: { total_items: 0 } }
      }
      return {}
    })
  })

  it('hydrates and selects permalink media id even when not in current results', async () => {
    mocks.queryData = [
      {
        kind: 'media',
        id: 1,
        title: 'First item',
        snippet: 'one',
        keywords: [],
        meta: { type: 'document' },
        raw: {}
      }
    ]
    mocks.detailById['900'] = {
      id: 900,
      title: 'Deep linked item',
      type: 'document',
      content: { text: 'Deep-linked content' }
    }

    renderMediaPage('/media?id=900')

    await waitFor(() => {
      expect(screen.getByTestId('selected-media-id')).toHaveTextContent('900')
    })
    expect(screen.getByTestId('location-search')).toHaveTextContent('?id=900')
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({ path: '/api/v1/media/900', method: 'GET' })
    )
  })

  it('falls back to LAST_MEDIA_ID_SETTING when URL has no id and clears legacy setting', async () => {
    mocks.queryData = [
      {
        kind: 'media',
        id: 42,
        title: 'Stored selection',
        snippet: 'stored',
        keywords: [],
        meta: { type: 'document' },
        raw: {}
      },
      {
        kind: 'media',
        id: 43,
        title: 'Neighbor selection',
        snippet: 'next',
        keywords: [],
        meta: { type: 'document' },
        raw: {}
      }
    ]
    mocks.getSetting.mockResolvedValue('42')

    renderMediaPage('/media')

    await waitFor(() => {
      expect(screen.getByTestId('selected-media-id')).toHaveTextContent('42')
    })
    await waitFor(() => {
      expect(screen.getByTestId('location-search')).toHaveTextContent('?id=42')
    })
    expect(mocks.clearSetting).toHaveBeenCalledWith(
      expect.objectContaining({ key: 'tldw:lastMediaId' })
    )
  })

  it('keeps permalink id synchronized when navigating previous/next from a deep link', async () => {
    mocks.queryData = [
      {
        kind: 'media',
        id: 100,
        title: 'Item 100',
        snippet: '100',
        keywords: [],
        meta: { type: 'document' },
        raw: {}
      },
      {
        kind: 'media',
        id: 200,
        title: 'Item 200',
        snippet: '200',
        keywords: [],
        meta: { type: 'document' },
        raw: {}
      }
    ]

    renderMediaPage('/media?id=100')

    await waitFor(() => {
      expect(screen.getByTestId('selected-media-id')).toHaveTextContent('100')
    })
    expect(screen.getByTestId('location-search')).toHaveTextContent('?id=100')

    fireEvent.click(screen.getByRole('button', { name: 'Next item' }))

    await waitFor(() => {
      expect(screen.getByTestId('selected-media-id')).toHaveTextContent('200')
    })
    expect(screen.getByTestId('location-search')).toHaveTextContent('?id=200')

    fireEvent.click(screen.getByRole('button', { name: 'Previous item' }))

    await waitFor(() => {
      expect(screen.getByTestId('selected-media-id')).toHaveTextContent('100')
    })
    expect(screen.getByTestId('location-search')).toHaveTextContent('?id=100')
  })
})
