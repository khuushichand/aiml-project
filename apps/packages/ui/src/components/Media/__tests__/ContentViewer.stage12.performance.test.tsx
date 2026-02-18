import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import {
  ContentViewer,
  LARGE_PLAIN_CONTENT_CHUNK_CHARS,
  LARGE_PLAIN_CONTENT_THRESHOLD_CHARS
} from '../ContentViewer'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallbackOrOptions?: string | { defaultValue?: string }) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      return fallbackOrOptions?.defaultValue || _key
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

const selectedMedia = {
  kind: 'media' as const,
  id: 512,
  title: 'Large content media',
  raw: {},
  meta: { type: 'document' }
}

const buildContentWithTail = (length: number, tailMarker: string) => {
  const prefixLength = Math.max(0, length - tailMarker.length)
  return `${'x'.repeat(prefixLength)}${tailMarker}`
}

describe('ContentViewer stage 12 large content rendering', () => {
  it('keeps normal-size plain content on the default rendering path', () => {
    render(
      <ContentViewer
        selectedMedia={selectedMedia}
        content={'normal body with a compact footprint'}
        mediaDetail={{ type: 'document' }}
        contentDisplayMode="plain"
      />
    )

    expect(
      screen.getByText('normal body with a compact footprint')
    ).toBeInTheDocument()
    expect(screen.queryByTestId('large-content-window-status')).not.toBeInTheDocument()
  })

  it('chunks large plain content and lets users load the remaining text', async () => {
    const user = userEvent.setup()
    const tailMarker = '__STAGE12_TAIL_MARKER__'
    const longContent = buildContentWithTail(
      LARGE_PLAIN_CONTENT_THRESHOLD_CHARS + LARGE_PLAIN_CONTENT_CHUNK_CHARS + 1024,
      tailMarker
    )

    render(
      <ContentViewer
        selectedMedia={selectedMedia}
        content={longContent}
        mediaDetail={{ type: 'document' }}
        contentDisplayMode="plain"
      />
    )

    expect(screen.getByTestId('large-content-window-status')).toHaveAttribute(
      'data-visible-chars',
      String(LARGE_PLAIN_CONTENT_CHUNK_CHARS)
    )
    expect(screen.queryByText(tailMarker)).not.toBeInTheDocument()

    const clicksNeeded = Math.ceil(
      (longContent.length - LARGE_PLAIN_CONTENT_CHUNK_CHARS) /
        LARGE_PLAIN_CONTENT_CHUNK_CHARS
    )
    for (let i = 0; i < clicksNeeded; i += 1) {
      const loadMoreButton = screen.queryByTestId('large-content-window-load-more')
      if (!loadMoreButton) break
      await user.click(loadMoreButton)
    }

    await waitFor(() => {
      expect(
        screen.getByText((textContent) => textContent.includes(tailMarker))
      ).toBeInTheDocument()
    })
    expect(screen.queryByTestId('large-content-window-status')).not.toBeInTheDocument()
  })

  it('auto-loads another chunk when scrolling near the bottom of long content', async () => {
    const tailMarker = '__AUTO_LOAD_TAIL__'
    const longContent = buildContentWithTail(
      LARGE_PLAIN_CONTENT_THRESHOLD_CHARS + LARGE_PLAIN_CONTENT_CHUNK_CHARS * 2,
      tailMarker
    )

    render(
      <ContentViewer
        selectedMedia={selectedMedia}
        content={longContent}
        mediaDetail={{ type: 'document' }}
        contentDisplayMode="plain"
      />
    )

    const status = screen.getByTestId('large-content-window-status')
    expect(status).toHaveAttribute('data-visible-chars', String(LARGE_PLAIN_CONTENT_CHUNK_CHARS))

    const scrollContainer = screen.getByTestId('content-scroll-container')
    let scrollTop = 0
    Object.defineProperty(scrollContainer, 'clientHeight', {
      configurable: true,
      get: () => 500
    })
    Object.defineProperty(scrollContainer, 'scrollHeight', {
      configurable: true,
      get: () => 900
    })
    Object.defineProperty(scrollContainer, 'scrollTop', {
      configurable: true,
      get: () => scrollTop,
      set: (value: number) => {
        scrollTop = Number(value)
      }
    })

    scrollTop = 420
    fireEvent.scroll(scrollContainer)

    await waitFor(() => {
      expect(screen.getByTestId('large-content-window-status')).toHaveAttribute(
        'data-visible-chars',
        String(LARGE_PLAIN_CONTENT_CHUNK_CHARS * 2)
      )
    })
    expect(
      screen.queryByText((textContent) => textContent.includes(tailMarker))
    ).not.toBeInTheDocument()
  })
})
