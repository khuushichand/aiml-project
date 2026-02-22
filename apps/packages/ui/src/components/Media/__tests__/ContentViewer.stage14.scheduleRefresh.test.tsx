import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ContentViewer } from '../ContentViewer'
import { useMediaReadingProgress } from '@/hooks/useMediaReadingProgress'

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  messageWarning: vi.fn()
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?:
        | string
        | {
            defaultValue?: string
            size?: string
            minutes?: number
            percent?: number
            cron?: string
          }
    ) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      if (fallbackOrOptions?.defaultValue) {
        return fallbackOrOptions.defaultValue
          .replace('{{size}}', String(fallbackOrOptions.size ?? ''))
          .replace('{{minutes}}', String(fallbackOrOptions.minutes ?? ''))
          .replace('{{percent}}', String(fallbackOrOptions.percent ?? ''))
          .replace('{{cron}}', String(fallbackOrOptions.cron ?? ''))
      }
      return key
    }
  })
}))

vi.mock('@/services/background-proxy', () => ({
  bgRequest: mocks.bgRequest
}))

vi.mock('antd', async (importOriginal) => {
  const actual = await importOriginal<typeof import('antd')>()
  const renderItems = (items: any[] | undefined): React.ReactNode[] => {
    if (!Array.isArray(items)) return []
    return items.flatMap((item) => {
      if (!item) return []
      if (item.type === 'divider') return []
      if (item.type === 'group' && Array.isArray(item.children)) {
        return renderItems(item.children)
      }
      return [
        <button
          key={String(item.key)}
          type="button"
          data-testid={`menu-item-${String(item.key)}`}
          onClick={() => item.onClick?.()}
        >
          {typeof item.label === 'string' ? item.label : String(item.key)}
        </button>
      ]
    })
  }

  return {
    ...actual,
    Select: () => <div />,
    Dropdown: ({ children, menu }: any) => (
      <div>
        {children}
        <div data-testid="mock-dropdown-menu">{renderItems(menu?.items)}</div>
      </div>
    ),
    Tooltip: ({ children }: any) => <>{children}</>,
    Modal: ({ open, children }: any) =>
      open ? <div data-testid="mock-modal">{children}</div> : null,
    Spin: () => null,
    message: {
      ...actual.message,
      success: mocks.messageSuccess,
      error: mocks.messageError,
      warning: mocks.messageWarning
    }
  }
})

vi.mock('@/hooks/useSetting', async () => {
  const React = await import('react')
  return {
    useSetting: (setting: { defaultValue: unknown }) => {
      const [value, setValue] = React.useState(setting.defaultValue)
      const setAsync = async (next: unknown | ((prev: unknown) => unknown)) => {
        setValue((prev) =>
          typeof next === 'function' ? (next as (prev: unknown) => unknown)(prev) : next
        )
      }
      return [value, setAsync, { isLoading: false }] as const
    }
  }
})

vi.mock('@/hooks/useMediaReadingProgress', () => ({
  useMediaReadingProgress: vi.fn()
}))

vi.mock('../AnalysisModal', () => ({ AnalysisModal: () => null }))
vi.mock('../AnalysisEditModal', () => ({ AnalysisEditModal: () => null }))
vi.mock('../VersionHistoryPanel', () => ({ VersionHistoryPanel: () => null }))
vi.mock('../DeveloperToolsSection', () => ({ DeveloperToolsSection: () => null }))
vi.mock('../DiffViewModal', () => ({ DiffViewModal: () => null }))
vi.mock('@/components/Common/MarkdownPreview', () => ({
  MarkdownPreview: ({ content }: { content: string }) => <div>{content}</div>
}))

const selectedMedia = {
  kind: 'media' as const,
  id: 99,
  title: 'Refresh target',
  raw: {
    url: 'https://example.com/article'
  },
  meta: {
    type: 'document',
    source: 'https://example.com/article'
  }
}

describe('ContentViewer stage 14 scheduled source refresh baseline', () => {
  beforeEach(() => {
    mocks.bgRequest.mockReset()
    mocks.messageSuccess.mockReset()
    mocks.messageError.mockReset()
    mocks.messageWarning.mockReset()
    vi.mocked(useMediaReadingProgress).mockReturnValue({
      saveProgress: vi.fn(),
      clearProgress: vi.fn(),
      progressPercent: null
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('creates watchlist source and scheduled job from source refresh action', async () => {
    mocks.bgRequest.mockImplementation(async (request: { path?: string; method?: string }) => {
      const path = String(request?.path || '')
      if (path === '/api/v1/watchlists/sources' && request?.method === 'POST') {
        return { id: 501 }
      }
      if (path === '/api/v1/watchlists/jobs' && request?.method === 'POST') {
        return { id: 7001 }
      }
      return {}
    })

    render(
      <ContentViewer
        selectedMedia={selectedMedia}
        content={'Body content'}
        mediaDetail={{ type: 'document' }}
      />
    )

    fireEvent.click(screen.getByTestId('menu-item-schedule-refresh'))
    expect(screen.getByTestId('media-schedule-refresh-modal')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('media-schedule-refresh-preset-weekly'))
    fireEvent.click(screen.getByTestId('media-schedule-refresh-confirm'))

    await waitFor(() => {
      expect(mocks.bgRequest).toHaveBeenCalledWith(
        expect.objectContaining({
          path: '/api/v1/watchlists/sources',
          method: 'POST',
          body: expect.objectContaining({
            url: 'https://example.com/article',
            source_type: 'site'
          })
        })
      )
    })

    await waitFor(() => {
      expect(mocks.bgRequest).toHaveBeenCalledWith(
        expect.objectContaining({
          path: '/api/v1/watchlists/jobs',
          method: 'POST',
          body: expect.objectContaining({
            scope: { sources: [501] },
            schedule_expr: '0 9 * * MON',
            active: true
          })
        })
      )
    })

    expect(mocks.messageSuccess).toHaveBeenCalledWith('Scheduled source refresh monitor.')
  })
})
