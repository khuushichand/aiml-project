import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ContentViewer } from '../ContentViewer'
import { useMediaReadingProgress } from '@/hooks/useMediaReadingProgress'

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn()
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
            timestamp?: string
          }
    ) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      if (fallbackOrOptions?.defaultValue) {
        return fallbackOrOptions.defaultValue
          .replace('{{size}}', String(fallbackOrOptions.size ?? ''))
          .replace('{{minutes}}', String(fallbackOrOptions.minutes ?? ''))
          .replace('{{percent}}', String(fallbackOrOptions.percent ?? ''))
          .replace('{{timestamp}}', String(fallbackOrOptions.timestamp ?? ''))
      }
      return key
    }
  })
}))

vi.mock('@/services/background-proxy', () => ({
  bgRequest: mocks.bgRequest
}))

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
  title: 'Intelligence target',
  raw: {},
  meta: {
    type: 'document'
  }
}

describe('ContentViewer stage 14 document intelligence', () => {
  beforeEach(() => {
    mocks.bgRequest.mockReset()
    vi.mocked(useMediaReadingProgress).mockReturnValue({
      saveProgress: vi.fn(),
      clearProgress: vi.fn(),
      progressPercent: null
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('lazily loads document intelligence endpoints when panel opens', async () => {
    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || '')
      if (path.endsWith('/outline')) {
        return {
          media_id: 777,
          has_outline: true,
          entries: [{ level: 1, title: 'Introduction', page: 1 }],
          total_pages: 12
        }
      }
      if (path.endsWith('/insights')) {
        return {
          media_id: 777,
          insights: [{ category: 'summary', title: 'Summary', content: 'Insight content' }],
          model_used: 'test-model',
          cached: true
        }
      }
      if (path.includes('/references')) {
        return {
          media_id: 777,
          has_references: true,
          references: [{ title: 'Paper A', raw_text: 'Paper A citation' }]
        }
      }
      if (path.includes('/figures')) {
        return {
          media_id: 777,
          has_figures: true,
          figures: [{ id: 'fig-1', page: 2, caption: 'Figure 1' }]
        }
      }
      if (path.endsWith('/annotations')) {
        return {
          media_id: 777,
          annotations: [{ id: 'ann-1', text: 'Highlighted text', location: '1' }]
        }
      }
      return {}
    })

    render(
      <ContentViewer
        selectedMedia={selectedMedia}
        content={'Body text'}
        mediaDetail={{ type: 'document' }}
      />
    )

    expect(mocks.bgRequest).not.toHaveBeenCalledWith(
      expect.objectContaining({
        path: '/api/v1/media/777/outline'
      })
    )

    fireEvent.click(screen.getByTestId('media-intelligence-toggle'))

    await waitFor(() => {
      expect(screen.getByTestId('media-intelligence-outline-item')).toHaveTextContent(
        'Introduction'
      )
    })

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({ path: '/api/v1/media/777/outline', method: 'GET' })
    )
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({ path: '/api/v1/media/777/insights', method: 'POST' })
    )
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: '/api/v1/media/777/references?enrich=true&limit=25',
        method: 'GET'
      })
    )
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({ path: '/api/v1/media/777/figures?min_size=50', method: 'GET' })
    )
    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({ path: '/api/v1/media/777/annotations', method: 'GET' })
    )
  })

  it('shows tab-specific empty states when intelligence data is unavailable', async () => {
    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || '')
      if (path.endsWith('/outline')) {
        return { media_id: 777, has_outline: false, entries: [], total_pages: 0 }
      }
      if (path.endsWith('/insights')) {
        return { media_id: 777, insights: [], model_used: 'test-model', cached: false }
      }
      if (path.includes('/references')) {
        return { media_id: 777, has_references: false, references: [] }
      }
      if (path.includes('/figures')) {
        return { media_id: 777, has_figures: false, figures: [] }
      }
      if (path.endsWith('/annotations')) {
        return { media_id: 777, annotations: [] }
      }
      return {}
    })

    render(
      <ContentViewer
        selectedMedia={selectedMedia}
        content={'Body text'}
        mediaDetail={{ type: 'document' }}
      />
    )

    fireEvent.click(screen.getByTestId('media-intelligence-toggle'))

    await waitFor(() => {
      expect(screen.getByTestId('media-intelligence-empty')).toHaveTextContent(
        'No outline available for this item.'
      )
    })

    fireEvent.click(screen.getByTestId('media-intelligence-tab-insights'))
    expect(screen.getByTestId('media-intelligence-empty')).toHaveTextContent(
      'No insights available for this item.'
    )

    fireEvent.click(screen.getByTestId('media-intelligence-tab-references'))
    expect(screen.getByTestId('media-intelligence-empty')).toHaveTextContent(
      'No references available for this item.'
    )
  })

  it('keeps other tabs usable when one tab fails and supports retry', async () => {
    let failReferences = true
    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || '')
      if (path.endsWith('/outline')) {
        return {
          media_id: 777,
          has_outline: true,
          entries: [{ level: 1, title: 'Outline entry', page: 1 }],
          total_pages: 2
        }
      }
      if (path.endsWith('/insights')) {
        return {
          media_id: 777,
          insights: [{ category: 'summary', title: 'Insight', content: 'Insight body' }],
          model_used: 'test-model',
          cached: true
        }
      }
      if (path.includes('/references')) {
        if (failReferences) {
          throw Object.assign(new Error('references unavailable'), { status: 500 })
        }
        return {
          media_id: 777,
          has_references: true,
          references: [{ title: 'Recovered reference', raw_text: 'Recovered reference raw' }]
        }
      }
      if (path.includes('/figures')) {
        return { media_id: 777, has_figures: false, figures: [] }
      }
      if (path.endsWith('/annotations')) {
        return { media_id: 777, annotations: [] }
      }
      return {}
    })

    render(
      <ContentViewer
        selectedMedia={selectedMedia}
        content={'Body text'}
        mediaDetail={{ type: 'document' }}
      />
    )

    fireEvent.click(screen.getByTestId('media-intelligence-toggle'))

    await waitFor(() => {
      expect(screen.getByTestId('media-intelligence-outline-item')).toHaveTextContent(
        'Outline entry'
      )
    })

    fireEvent.click(screen.getByTestId('media-intelligence-tab-references'))
    await waitFor(() => {
      expect(screen.getByTestId('media-intelligence-error')).toHaveTextContent(
        'Unable to load this panel. Try again.'
      )
    })

    fireEvent.click(screen.getByTestId('media-intelligence-tab-outline'))
    expect(screen.getByTestId('media-intelligence-outline-item')).toHaveTextContent(
      'Outline entry'
    )

    failReferences = false
    fireEvent.click(screen.getByTestId('media-intelligence-tab-references'))
    fireEvent.click(screen.getByTestId('media-intelligence-retry'))

    await waitFor(() => {
      expect(screen.getByTestId('media-intelligence-reference-item')).toHaveTextContent(
        'Recovered reference'
      )
    })
  })
})
