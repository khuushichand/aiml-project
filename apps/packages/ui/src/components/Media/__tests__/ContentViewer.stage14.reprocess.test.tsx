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
        | { defaultValue?: string; size?: string; minutes?: number; percent?: number }
    ) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      if (fallbackOrOptions?.defaultValue) {
        return fallbackOrOptions.defaultValue
          .replace('{{size}}', String(fallbackOrOptions.size ?? ''))
          .replace('{{minutes}}', String(fallbackOrOptions.minutes ?? ''))
          .replace('{{percent}}', String(fallbackOrOptions.percent ?? ''))
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
  id: 777,
  title: 'Reprocess target',
  raw: {},
  meta: {
    type: 'document'
  }
}

describe('ContentViewer stage 14 reprocess action', () => {
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

  it('starts reprocessing from the actions menu and refreshes details on success', async () => {
    const onRefreshMedia = vi.fn()
    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || '')
      if (path === '/api/v1/media/777/reprocess') {
        return { ok: true }
      }
      return {}
    })

    render(
      <ContentViewer
        selectedMedia={selectedMedia}
        content={'Body text'}
        mediaDetail={{ type: 'document' }}
        onRefreshMedia={onRefreshMedia}
      />
    )

    fireEvent.click(screen.getByTestId('menu-item-reprocess-media'))

    await waitFor(() => {
      expect(mocks.bgRequest).toHaveBeenCalledWith(
        expect.objectContaining({
          path: '/api/v1/media/777/reprocess',
          method: 'POST',
          body: {
            perform_chunking: true,
            generate_embeddings: true,
            force_regenerate_embeddings: true
          }
        })
      )
    })
    expect(mocks.messageSuccess).toHaveBeenCalledWith('Reprocessing started.')
    expect(onRefreshMedia).toHaveBeenCalled()
  })

  it('shows an error toast when reprocessing cannot be started', async () => {
    const onRefreshMedia = vi.fn()
    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || '')
      if (path === '/api/v1/media/777/reprocess') {
        throw Object.assign(new Error('boom'), { status: 500 })
      }
      return {}
    })

    render(
      <ContentViewer
        selectedMedia={selectedMedia}
        content={'Body text'}
        mediaDetail={{ type: 'document' }}
        onRefreshMedia={onRefreshMedia}
      />
    )

    fireEvent.click(screen.getByTestId('menu-item-reprocess-media'))

    await waitFor(() => {
      expect(mocks.messageError).toHaveBeenCalledWith(
        'Unable to start reprocessing. Please try again.'
      )
    })
    expect(onRefreshMedia).not.toHaveBeenCalled()
  })
})
