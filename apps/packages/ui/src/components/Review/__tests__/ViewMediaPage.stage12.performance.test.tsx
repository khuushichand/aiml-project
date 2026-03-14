import React from 'react'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ViewMediaPage from '../ViewMediaPage'
import { MEDIA_TYPES_CACHE_KEY } from '../mediaTypeCache'

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
  showUndoNotification: vi.fn(),
  setChatMode: vi.fn(),
  setSelectedKnowledge: vi.fn(),
  setRagMediaIds: vi.fn()
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
    useStorage: (_key: string, initialValue: unknown) => {
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
  useConnectionState: () => ({ serverUrl: 'http://localhost:8000' }),
  useConnectionUxState: () => ({
    uxState: 'connected_ok',
    hasCompletedFirstRun: true
  }),
  useConnectionActions: () => ({
    checkOnce: vi.fn()
  })
}))

vi.mock('@/hooks/useMessageOption', () => ({
  useMessageOption: () => ({
    setChatMode: mocks.setChatMode,
    setSelectedKnowledge: mocks.setSelectedKnowledge,
    setRagMediaIds: mocks.setRagMediaIds
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
  SearchBar: ({
    value,
    onChange,
    placeholder = 'Search media (title/content)',
    inputRef
  }: {
    value: string
    onChange: (next: string) => void
    placeholder?: string
    inputRef?: React.Ref<HTMLInputElement>
  }) => (
    <input
      data-testid="search-bar"
      ref={inputRef}
      value={value}
      placeholder={placeholder}
      aria-label={placeholder}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}))

vi.mock('@/components/Media/FilterPanel', () => ({
  FilterPanel: ({
    mediaTypes,
    onKeywordSearch,
    onMediaTypesChange
  }: {
    mediaTypes?: string[]
    onKeywordSearch?: (query: string) => void
    onMediaTypesChange?: (types: string[]) => void
  }) => (
    <div data-testid="filter-panel">
      <div data-testid="filter-panel-media-types">
        {(mediaTypes || []).join(',')}
      </div>
      <button
        type="button"
        data-testid="filter-panel-apply-media-type"
        onClick={() => onMediaTypesChange?.(['pdf'])}
      >
        apply-media-type
      </button>
      <button
        type="button"
        data-testid="filter-panel-keyword-search"
        onClick={() => onKeywordSearch?.('retry')}
      >
        keyword-search
      </button>
    </div>
  )
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
  Pagination: ({
    currentPage,
    onPageChange
  }: {
    currentPage: number
    onPageChange?: (page: number) => void
  }) => (
    <div data-testid="pagination">
      <div data-testid="pagination-current-page">{currentPage}</div>
      <button
        type="button"
        data-testid="pagination-next-page"
        onClick={() => onPageChange?.(currentPage + 1)}
      >
        next-page
      </button>
    </div>
  )
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
  ContentViewer: ({ selectedMedia, contentRef }: any) => (
    <div
      data-testid="mock-content-viewer"
      ref={(node) => {
        if (node) {
          Object.defineProperty(node, 'scrollHeight', {
            configurable: true,
            value: 1200
          })
        }
        contentRef?.(node)
      }}
    >
      <div data-testid="selected-media-id">
        {selectedMedia?.id != null ? String(selectedMedia.id) : 'none'}
      </div>
    </div>
  )
}))

const renderMediaPage = (initialEntry: string) => {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/" element={<div data-testid="root-route" />} />
        <Route path="/media" element={<ViewMediaPage />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ViewMediaPage stage 12 performance guardrails', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  beforeEach(() => {
    mocks.queryData = [
      {
        kind: 'media',
        id: 1,
        title: 'Item 1',
        snippet: 'one',
        keywords: [],
        meta: { type: 'document' },
        raw: {}
      }
    ]
    mocks.detailById = {
      '1': {
        id: 1,
        title: 'Item 1',
        type: 'document',
        content: { text: 'Content 1' }
      }
    }
    mocks.refetch.mockReset()
    mocks.refetch.mockResolvedValue({ data: mocks.queryData })
    mocks.getSetting.mockReset()
    mocks.getSetting.mockResolvedValue(undefined)
    mocks.setSetting.mockReset()
    mocks.clearSetting.mockReset()
    mocks.showUndoNotification.mockReset()
    mocks.setChatMode.mockReset()
    mocks.setSelectedKnowledge.mockReset()
    mocks.setRagMediaIds.mockReset()
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
    window.localStorage.removeItem(MEDIA_TYPES_CACHE_KEY)
  })

  it('debounces rapid query changes before triggering refetch with active filters', async () => {
    renderMediaPage('/media')

    const searchInput = await screen.findByRole('textbox', {
      name: 'Search media (title/content)'
    })

    // Ignore initial mount refetches.
    await waitFor(() => {
      expect(mocks.refetch.mock.calls.length).toBeGreaterThan(0)
    })
    mocks.refetch.mockClear()

    fireEvent.click(screen.getByTestId('filter-panel-apply-media-type'))
    await waitFor(() => {
      expect(mocks.refetch.mock.calls.length).toBeGreaterThan(0)
    })
    mocks.refetch.mockClear()

    vi.useFakeTimers()

    fireEvent.change(searchInput, { target: { value: 'a' } })
    fireEvent.change(searchInput, { target: { value: 'ab' } })
    fireEvent.change(searchInput, { target: { value: 'abc' } })

    act(() => {
      vi.advanceTimersByTime(299)
    })
    expect(mocks.refetch).toHaveBeenCalledTimes(0)

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(mocks.refetch).toHaveBeenCalledTimes(1)
  })

  it('keeps explicit pagination changes instead of snapping back to page 1', async () => {
    renderMediaPage('/media')

    await waitFor(() => {
      expect(screen.getByTestId('pagination-current-page')).toHaveTextContent('1')
    })

    fireEvent.click(screen.getByTestId('pagination-next-page'))

    await waitFor(() => {
      expect(screen.getByTestId('pagination-current-page')).toHaveTextContent('2')
    })
    await waitFor(() => {
      expect(screen.getByTestId('pagination-current-page')).toHaveTextContent('2')
    })
  })

  it('issues a single refetch when filters change from a non-first page', async () => {
    renderMediaPage('/media')

    await waitFor(() => {
      expect(screen.getByTestId('pagination-current-page')).toHaveTextContent('1')
    })

    fireEvent.click(screen.getByTestId('pagination-next-page'))
    await waitFor(() => {
      expect(screen.getByTestId('pagination-current-page')).toHaveTextContent('2')
    })

    mocks.refetch.mockClear()

    fireEvent.click(screen.getByTestId('filter-panel-apply-media-type'))

    await waitFor(() => {
      expect(screen.getByTestId('pagination-current-page')).toHaveTextContent('1')
    })
    await waitFor(() => {
      expect(mocks.refetch).toHaveBeenCalledTimes(1)
    })
  })

  it('wires resize observer + animation-frame height stabilization for content area', async () => {
    const observeMock = vi.fn()
    const disconnectMock = vi.fn()
    const cancelAnimationFrameMock = vi.fn()
    const requestAnimationFrameMock = vi.fn(() => 1)
    let resizeCallback: ResizeObserverCallback | null = null

    const originalResizeObserver = window.ResizeObserver
    const originalRequestAnimationFrame = window.requestAnimationFrame
    const originalCancelAnimationFrame = window.cancelAnimationFrame

    class ResizeObserverMock {
      constructor(callback: ResizeObserverCallback) {
        resizeCallback = callback
      }
      observe = observeMock
      unobserve = vi.fn()
      disconnect = disconnectMock
    }

    Object.defineProperty(window, 'ResizeObserver', {
      configurable: true,
      writable: true,
      value: ResizeObserverMock
    })
    Object.defineProperty(window, 'requestAnimationFrame', {
      configurable: true,
      writable: true,
      value: requestAnimationFrameMock
    })
    Object.defineProperty(window, 'cancelAnimationFrame', {
      configurable: true,
      writable: true,
      value: cancelAnimationFrameMock
    })

    const { unmount } = renderMediaPage('/media?id=1')

    await waitFor(() => {
      expect(screen.getByTestId('selected-media-id')).toHaveTextContent('1')
      expect(observeMock).toHaveBeenCalled()
    })

    const beforeResize = requestAnimationFrameMock.mock.calls.length
    expect(beforeResize).toBeGreaterThan(0)

    if (resizeCallback) {
      resizeCallback([], {} as ResizeObserver)
    }

    expect(requestAnimationFrameMock.mock.calls.length).toBeGreaterThan(beforeResize)

    unmount()
    expect(disconnectMock).toHaveBeenCalled()
    expect(cancelAnimationFrameMock).toHaveBeenCalled()

    Object.defineProperty(window, 'ResizeObserver', {
      configurable: true,
      writable: true,
      value: originalResizeObserver
    })
    Object.defineProperty(window, 'requestAnimationFrame', {
      configurable: true,
      writable: true,
      value: originalRequestAnimationFrame
    })
    Object.defineProperty(window, 'cancelAnimationFrame', {
      configurable: true,
      writable: true,
      value: originalCancelAnimationFrame
    })
  })

  it('hydrates media type filters from cache before background sampling resolves', async () => {
    window.localStorage.setItem(
      MEDIA_TYPES_CACHE_KEY,
      JSON.stringify({
        types: ['pdf', 'video'],
        cachedAt: Date.now()
      })
    )

    let resolveSampling: ((value: any) => void) | null = null
    const samplingPromise = new Promise((resolve) => {
      resolveSampling = resolve
    })

    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || '')
      if (path === '/api/v1/media/?page=1&results_per_page=50') {
        return samplingPromise
      }
      if (path.startsWith('/api/v1/media/?page=')) {
        return { items: [], pagination: { total_pages: 1, total_items: 0 } }
      }
      if (path.startsWith('/api/v1/media/keywords')) {
        return { keywords: [] }
      }
      if (path.startsWith('/api/v1/media/')) {
        const id = path.replace('/api/v1/media/', '').split('?')[0]
        return {
          id,
          title: `Media ${id}`,
          type: 'document',
          content: { text: `Content for ${id}` }
        }
      }
      if (path.startsWith('/api/v1/notes')) {
        return { items: [], pagination: { total_items: 0 } }
      }
      return {}
    })

    renderMediaPage('/media')

    await waitFor(() => {
      expect(screen.getByTestId('filter-panel-media-types')).toHaveTextContent('pdf,video')
    })

    resolveSampling?.({
      items: [],
      pagination: { total_pages: 1, total_items: 0 }
    })
  })

  it('falls back to sampled media types when no fresh cache is available', async () => {
    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || '')
      if (path === '/api/v1/media/?page=1&results_per_page=50') {
        return {
          items: [{ id: 10, title: 'Doc 10', type: 'pdf' }],
          pagination: { total_pages: 1, total_items: 1 }
        }
      }
      if (path.startsWith('/api/v1/media/?page=')) {
        return { items: [], pagination: { total_pages: 1, total_items: 0 } }
      }
      if (path.startsWith('/api/v1/media/keywords')) {
        return { keywords: [] }
      }
      if (path.startsWith('/api/v1/media/')) {
        const id = path.replace('/api/v1/media/', '').split('?')[0]
        return {
          id,
          title: `Media ${id}`,
          type: 'document',
          content: { text: `Content for ${id}` }
        }
      }
      if (path.startsWith('/api/v1/notes')) {
        return { items: [], pagination: { total_items: 0 } }
      }
      return {}
    })

    renderMediaPage('/media')

    await waitFor(() => {
      expect(screen.getByTestId('filter-panel-media-types')).toHaveTextContent('pdf')
    })
  })

  it('retries keyword endpoint after cooldown instead of latching fallback forever', async () => {
    const baseNow = new Date('2026-02-18T00:00:00Z').getTime()
    let now = baseNow
    const nowSpy = vi.spyOn(Date, 'now').mockImplementation(() => now)

    let keywordCallCount = 0
    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || '')
      if (path.startsWith('/api/v1/media/keywords')) {
        keywordCallCount += 1
        if (keywordCallCount === 1) {
          throw new Error('temporary keyword endpoint failure')
        }
        return { keywords: ['keyword-from-endpoint'] }
      }
      if (path.startsWith('/api/v1/media/?page=')) {
        return { items: [], pagination: { total_pages: 1, total_items: 0 } }
      }
      if (path.startsWith('/api/v1/media/')) {
        const id = path.replace('/api/v1/media/', '').split('?')[0]
        return {
          id,
          title: `Media ${id}`,
          type: 'document',
          content: { text: `Content for ${id}` }
        }
      }
      if (path.startsWith('/api/v1/notes')) {
        return { items: [], pagination: { total_items: 0 } }
      }
      return {}
    })

    renderMediaPage('/media')

    await waitFor(() => {
      expect(keywordCallCount).toBe(1)
    })

    fireEvent.click(screen.getByTestId('filter-panel-keyword-search'))
    await act(async () => {
      await Promise.resolve()
    })
    expect(keywordCallCount).toBe(1)

    now = baseNow + 31_000
    fireEvent.click(screen.getByTestId('filter-panel-keyword-search'))
    await waitFor(() => {
      expect(keywordCallCount).toBe(2)
    })

    nowSpy.mockRestore()
  })
})
