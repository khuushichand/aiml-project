import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ContentViewer } from '../ContentViewer'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?:
        | string
        | { defaultValue?: string; count?: number; minutes?: number }
    ) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      return fallbackOrOptions?.defaultValue || key
    }
  })
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

const baseSelectedMedia = {
  kind: 'media' as const,
  id: 404,
  title: 'Metadata test media',
  raw: {},
  meta: {
    type: 'pdf',
    source: 'archive.org'
  }
}

describe('ContentViewer stage 1 metadata bar', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-02-18T12:00:00.000Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders ingestion/modified dates and reading time in metadata bar', () => {
    const content = Array.from({ length: 600 }, () => 'word').join(' ')

    render(
      <ContentViewer
        selectedMedia={baseSelectedMedia}
        content={content}
        mediaDetail={{
          created_at: '2026-02-16T12:00:00.000Z',
          updated_at: '2026-02-17T12:00:00.000Z',
          type: 'pdf'
        }}
      />
    )

    expect(screen.getByTestId('media-ingested-date')).toHaveTextContent('Ingested 2d ago')
    expect(screen.getByTestId('media-last-modified-date')).toHaveTextContent('Updated 1d ago')
    expect(screen.getByTestId('media-reading-time')).toHaveTextContent('3 min read')
  })

  it('omits date badges when date values are unavailable', () => {
    render(
      <ContentViewer
        selectedMedia={baseSelectedMedia}
        content={'single word'}
        mediaDetail={{ type: 'pdf' }}
      />
    )

    expect(screen.queryByTestId('media-ingested-date')).not.toBeInTheDocument()
    expect(screen.queryByTestId('media-last-modified-date')).not.toBeInTheDocument()
    expect(screen.getByTestId('media-reading-time')).toHaveTextContent('1 min read')
  })

  it('matches compact metadata bar snapshot', () => {
    const { container } = render(
      <ContentViewer
        selectedMedia={{
          ...baseSelectedMedia,
          meta: {
            type: 'pdf'
          }
        }}
        content={'compact'}
        mediaDetail={{ type: 'pdf' }}
      />
    )

    const metadataBar = screen.getByTestId('media-metadata-bar')
    expect(metadataBar).toMatchSnapshot()
    expect(container).toBeTruthy()
  })

  it('matches expanded metadata bar snapshot', () => {
    render(
      <ContentViewer
        selectedMedia={{
          ...baseSelectedMedia,
          meta: {
            ...baseSelectedMedia.meta,
            created_at: '2026-02-15T12:00:00.000Z',
            duration: 360
          }
        }}
        content={Array.from({ length: 420 }, () => 'word').join(' ')}
        mediaDetail={{
          created_at: '2026-02-15T12:00:00.000Z',
          last_modified: '2026-02-17T09:00:00.000Z',
          type: 'pdf'
        }}
      />
    )

    const metadataBar = screen.getByTestId('media-metadata-bar')
    expect(metadataBar).toMatchSnapshot()
  })
})
