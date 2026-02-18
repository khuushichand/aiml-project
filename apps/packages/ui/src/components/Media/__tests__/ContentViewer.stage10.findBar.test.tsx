import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import {
  ContentViewer,
  findInContentOffsets,
  getNextFindMatchIndex
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

vi.mock('../AnalysisModal', () => ({
  AnalysisModal: () => null
}))

vi.mock('../AnalysisEditModal', () => ({
  AnalysisEditModal: () => null
}))

vi.mock('../VersionHistoryPanel', () => ({
  VersionHistoryPanel: () => null
}))

vi.mock('../DeveloperToolsSection', () => ({
  DeveloperToolsSection: () => null
}))

vi.mock('../DiffViewModal', () => ({
  DiffViewModal: () => null
}))

vi.mock('@/components/Common/MarkdownPreview', () => ({
  MarkdownPreview: ({ content }: { content: string }) => <div>{content}</div>
}))

const baseSelectedMedia = {
  kind: 'media' as const,
  id: 320,
  title: 'Findable media',
  raw: {},
  meta: { type: 'document' }
}

describe('ContentViewer stage 10 find helpers', () => {
  it('finds all case-insensitive match offsets', () => {
    expect(findInContentOffsets('Alpha beta alpha ALPHA', 'alpha')).toEqual([0, 11, 17])
    expect(findInContentOffsets('Alpha beta alpha ALPHA', '  ALPHA  ')).toEqual([
      0, 11, 17
    ])
    expect(findInContentOffsets('abc', '')).toEqual([])
    expect(findInContentOffsets('', 'abc')).toEqual([])
  })

  it('cycles next/previous match indices', () => {
    expect(getNextFindMatchIndex(-1, 3, 1)).toBe(0)
    expect(getNextFindMatchIndex(-1, 3, -1)).toBe(2)
    expect(getNextFindMatchIndex(0, 3, 1)).toBe(1)
    expect(getNextFindMatchIndex(2, 3, 1)).toBe(0)
    expect(getNextFindMatchIndex(0, 3, -1)).toBe(2)
    expect(getNextFindMatchIndex(2, 3, -1)).toBe(1)
    expect(getNextFindMatchIndex(1, 0, 1)).toBe(-1)
  })
})

describe('ContentViewer stage 10 scoped find bar', () => {
  it('opens via Ctrl+F, focuses input, and navigates matches', async () => {
    const user = userEvent.setup()
    render(
      <ContentViewer
        selectedMedia={baseSelectedMedia}
        content={'alpha beta alpha'}
        mediaDetail={{ type: 'document' }}
        contentDisplayMode="plain"
      />
    )

    const openEvent = new KeyboardEvent('keydown', {
      key: 'f',
      ctrlKey: true,
      bubbles: true,
      cancelable: true
    })
    document.body.dispatchEvent(openEvent)

    expect(openEvent.defaultPrevented).toBe(true)
    const findInput = await screen.findByTestId('content-find-input')
    expect(findInput).toHaveFocus()

    await user.type(findInput, 'alpha')

    expect(screen.getByTestId('content-find-count')).toHaveTextContent('1/2')
    expect(screen.getAllByText('alpha').length).toBeGreaterThanOrEqual(2)

    await user.click(screen.getByTestId('content-find-next'))
    expect(screen.getByTestId('content-find-count')).toHaveTextContent('2/2')

    await user.click(screen.getByTestId('content-find-next'))
    expect(screen.getByTestId('content-find-count')).toHaveTextContent('1/2')

    await user.click(screen.getByTestId('content-find-prev'))
    expect(screen.getByTestId('content-find-count')).toHaveTextContent('2/2')
  })

  it('does not hijack Ctrl+F for targets outside the content viewer', () => {
    render(
      <>
        <button type="button" data-testid="outside-control">
          outside
        </button>
        <ContentViewer
          selectedMedia={baseSelectedMedia}
          content={'alpha beta alpha'}
          mediaDetail={{ type: 'document' }}
        />
      </>
    )

    const outside = screen.getByTestId('outside-control')
    const openEvent = new KeyboardEvent('keydown', {
      key: 'f',
      ctrlKey: true,
      bubbles: true,
      cancelable: true
    })
    outside.dispatchEvent(openEvent)

    expect(openEvent.defaultPrevented).toBe(false)
    expect(screen.queryByTestId('content-find-bar')).not.toBeInTheDocument()
  })

  it('closes and resets find state on media switch', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <ContentViewer
        selectedMedia={baseSelectedMedia}
        content={'alpha beta alpha'}
        mediaDetail={{ type: 'document' }}
        contentDisplayMode="plain"
      />
    )

    await user.click(screen.getByTestId('content-find-toggle'))
    const findInput = await screen.findByTestId('content-find-input')
    await user.type(findInput, 'alpha')
    expect(screen.getByTestId('content-find-count')).toHaveTextContent('1/2')

    rerender(
      <ContentViewer
        selectedMedia={{
          ...baseSelectedMedia,
          id: 321,
          title: 'New item'
        }}
        content={'gamma delta'}
        mediaDetail={{ type: 'document' }}
        contentDisplayMode="plain"
      />
    )

    expect(screen.queryByTestId('content-find-bar')).not.toBeInTheDocument()
  })

  it('supports Escape and Enter navigation from find input', async () => {
    const user = userEvent.setup()
    render(
      <ContentViewer
        selectedMedia={baseSelectedMedia}
        content={'alpha beta alpha'}
        mediaDetail={{ type: 'document' }}
        contentDisplayMode="plain"
      />
    )

    await user.click(screen.getByTestId('content-find-toggle'))
    const findInput = await screen.findByTestId('content-find-input')
    await user.type(findInput, 'alpha')
    expect(screen.getByTestId('content-find-count')).toHaveTextContent('1/2')

    fireEvent.keyDown(findInput, { key: 'Enter' })
    expect(screen.getByTestId('content-find-count')).toHaveTextContent('2/2')

    fireEvent.keyDown(findInput, { key: 'Enter', shiftKey: true })
    expect(screen.getByTestId('content-find-count')).toHaveTextContent('1/2')

    fireEvent.keyDown(findInput, { key: 'Escape' })
    expect(screen.queryByTestId('content-find-bar')).not.toBeInTheDocument()
  })
})
