import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MediaTrashPage from '../MediaTrashPage'

const mocks = vi.hoisted(() => ({
  queryData: null as any,
  refetch: vi.fn(),
  bgRequest: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  confirmDanger: vi.fn(),
  navigate: vi.fn()
}))

const interpolate = (template: string, values?: Record<string, unknown>) =>
  template.replace(/\{\{(\w+)\}\}/g, (_, key) => String(values?.[key] ?? ''))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string; [k: string]: unknown }
    ) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      const template = fallbackOrOptions?.defaultValue || key
      return interpolate(template, fallbackOrOptions as Record<string, unknown> | undefined)
    }
  })
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => mocks.navigate
}))

vi.mock('@tanstack/react-query', () => ({
  keepPreviousData: {},
  useQuery: () => ({
    data: mocks.queryData,
    isLoading: false,
    isFetching: false,
    isError: false,
    refetch: mocks.refetch
  })
}))

vi.mock('@/hooks/useServerOnline', () => ({
  useServerOnline: () => true
}))

vi.mock('@/hooks/useServerCapabilities', () => ({
  useServerCapabilities: () => ({
    capabilities: { hasMedia: true },
    loading: false
  })
}))

vi.mock('@/context/demo-mode', () => ({
  useDemoMode: () => ({ demoEnabled: false })
}))

vi.mock('@/hooks/useAntdMessage', () => ({
  useAntdMessage: () => ({
    success: mocks.messageSuccess,
    error: mocks.messageError,
    warning: vi.fn(),
    info: vi.fn()
  })
}))

vi.mock('@/components/Common/confirm-danger', () => ({
  useConfirmDanger: () => mocks.confirmDanger
}))

vi.mock('@/services/background-proxy', () => ({
  bgRequest: mocks.bgRequest
}))

vi.mock('@/services/tldw/path-utils', () => ({
  toAllowedPath: (path: string) => path
}))

vi.mock('@/components/Common/FeatureEmptyState', () => ({
  default: ({
    title,
    description,
    primaryActionLabel,
    onPrimaryAction
  }: {
    title: string
    description: string
    primaryActionLabel?: string
    onPrimaryAction?: () => void
  }) => (
    <div data-testid="feature-empty-state">
      <div>{title}</div>
      <div>{description}</div>
      {primaryActionLabel ? (
        <button type="button" onClick={onPrimaryAction}>
          {primaryActionLabel}
        </button>
      ) : null}
    </div>
  )
}))

vi.mock('@/components/Media/Pagination', () => ({
  Pagination: ({
    currentPage,
    totalPages,
    currentItemsCount
  }: {
    currentPage: number
    totalPages: number
    currentItemsCount: number
  }) => (
    <div data-testid="pagination-indicator">
      {currentPage}/{totalPages}/{currentItemsCount}
    </div>
  )
}))

describe('MediaTrashPage Stage 2 and Stage 3 coverage', () => {
  beforeEach(() => {
    mocks.refetch.mockReset()
    mocks.bgRequest.mockReset()
    mocks.messageSuccess.mockReset()
    mocks.messageError.mockReset()
    mocks.confirmDanger.mockReset()
    mocks.navigate.mockReset()

    mocks.refetch.mockResolvedValue({ data: mocks.queryData })
    mocks.confirmDanger.mockResolvedValue(true)
    mocks.bgRequest.mockResolvedValue({})
  })

  it('shows deletion timestamp when available and explicit fallback when unavailable', () => {
    mocks.queryData = {
      items: [
        {
          id: 1,
          title: 'Alpha doc',
          type: 'pdf',
          trash_date: '2026-02-15T10:30:00.000Z'
        },
        {
          id: 2,
          title: 'Beta clip',
          type: 'video'
        }
      ],
      retention_days: 30,
      pagination: {
        page: 1,
        results_per_page: 20,
        total_pages: 1,
        total_items: 2
      }
    }

    render(<MediaTrashPage />)

    expect(screen.getByTestId('trash-retention-policy')).toHaveTextContent(
      'Auto-purge after 30 days in trash.'
    )
    expect(screen.getByTestId('trash-item-deleted-at-1')).toHaveTextContent('Deleted:')
    expect(screen.getByTestId('trash-item-deleted-at-2')).toHaveTextContent(
      'Deleted date unavailable'
    )
  })

  it('shows explicit retention-policy unknown message when policy is absent', () => {
    mocks.queryData = {
      items: [
        {
          id: 3,
          title: 'Gamma',
          type: 'article'
        }
      ],
      pagination: {
        page: 1,
        results_per_page: 20,
        total_pages: 1,
        total_items: 1
      }
    }

    render(<MediaTrashPage />)

    expect(screen.getByTestId('trash-retention-policy')).toHaveTextContent(
      'Auto-purge policy is not configured or not reported by this server.'
    )
  })

  it('filters trash rows by search input and safely scopes selected state to visible results', async () => {
    mocks.queryData = {
      items: [
        {
          id: 1,
          title: 'Alpha doc',
          type: 'pdf'
        },
        {
          id: 2,
          title: 'Beta clip',
          type: 'video'
        }
      ],
      pagination: {
        page: 1,
        results_per_page: 20,
        total_pages: 1,
        total_items: 2
      }
    }

    render(<MediaTrashPage />)

    fireEvent.click(screen.getByRole('checkbox', { name: 'Select item 1' }))
    expect(screen.getByText('1 selected')).toBeInTheDocument()

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search trash' }), {
      target: { value: 'Beta' }
    })

    await waitFor(() => {
      expect(screen.queryByText('Alpha doc')).not.toBeInTheDocument()
      expect(screen.getByText('Beta clip')).toBeInTheDocument()
      expect(screen.getByText('0 selected')).toBeInTheDocument()
    })
  })

  it('preserves mixed-outcome bulk restore messaging with selected visible rows', async () => {
    mocks.queryData = {
      items: [
        {
          id: 1,
          title: 'Alpha doc',
          type: 'pdf'
        },
        {
          id: 2,
          title: 'Beta clip',
          type: 'video'
        }
      ],
      pagination: {
        page: 1,
        results_per_page: 20,
        total_pages: 1,
        total_items: 2
      }
    }

    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || '')
      if (path.includes('/api/v1/media/2/restore')) {
        throw new Error('restore failed')
      }
      return {}
    })

    render(<MediaTrashPage />)

    fireEvent.click(screen.getByRole('checkbox', { name: 'Select all visible' }))
    fireEvent.click(screen.getByRole('button', { name: 'Restore selected' }))

    await waitFor(() => {
      expect(mocks.messageSuccess).toHaveBeenCalledWith('Restored 1 items')
      expect(mocks.messageError).toHaveBeenCalledWith('Failed to restore 1 items')
    })
  })

  it('aborts in-flight bulk requests on unmount without emitting failure toasts', async () => {
    mocks.queryData = {
      items: Array.from({ length: 12 }).map((_, idx) => ({
        id: idx + 1,
        title: `Item ${idx + 1}`,
        type: 'pdf'
      })),
      pagination: {
        page: 1,
        results_per_page: 20,
        total_pages: 1,
        total_items: 12
      }
    }

    const observedSignals: AbortSignal[] = []
    mocks.bgRequest.mockImplementation(
      (request: { abortSignal?: AbortSignal }) =>
        new Promise((_resolve, reject) => {
          const signal = request.abortSignal
          if (signal) {
            observedSignals.push(signal)
            signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true })
          }
        })
    )

    const { unmount } = render(<MediaTrashPage />)

    fireEvent.click(screen.getByRole('checkbox', { name: 'Select all visible' }))
    fireEvent.click(screen.getByRole('button', { name: 'Restore selected' }))

    unmount()

    await waitFor(() => {
      expect(observedSignals.length).toBeGreaterThan(0)
      expect(observedSignals.some((signal) => signal.aborted)).toBe(true)
    })
    expect(mocks.messageError).not.toHaveBeenCalledWith('Failed to restore selected items')
  })
})
