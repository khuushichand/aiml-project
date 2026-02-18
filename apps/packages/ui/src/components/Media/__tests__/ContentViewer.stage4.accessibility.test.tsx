import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ContentViewer } from '../ContentViewer'

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

const selectedMedia = {
  kind: 'media' as const,
  id: 202,
  title: 'Accessibility media',
  raw: {},
  meta: { type: 'document' }
}

describe('ContentViewer stage 4 accessibility/keyboard actions', () => {
  it('supports keyboard toggling for content and analysis sections', async () => {
    const user = userEvent.setup()

    render(
      <ContentViewer
        selectedMedia={selectedMedia}
        content={'Body paragraph'}
        mediaDetail={{ processing: { analysis: 'Analysis paragraph' }, type: 'document' }}
      />
    )

    expect(screen.getByText('Body paragraph')).toBeInTheDocument()
    expect(screen.getByText('Analysis paragraph')).toBeInTheDocument()

    const contentToggle = screen.getByRole('button', { name: 'Content' })
    contentToggle.focus()
    await user.keyboard('{Enter}')

    expect(screen.queryByText('Body paragraph')).not.toBeInTheDocument()

    const analysisToggle = screen.getByRole('button', { name: 'Analysis' })
    analysisToggle.focus()
    await user.keyboard('{Enter}')

    expect(screen.queryByText('Analysis paragraph')).not.toBeInTheDocument()

    // Re-open both via keyboard to verify reversible behavior.
    contentToggle.focus()
    await user.keyboard('{Enter}')
    analysisToggle.focus()
    await user.keyboard('{Enter}')

    expect(screen.getByText('Body paragraph')).toBeInTheDocument()
    expect(screen.getByText('Analysis paragraph')).toBeInTheDocument()
  })

  it('keeps key action buttons labeled for assistive tech', () => {
    render(
      <ContentViewer
        selectedMedia={selectedMedia}
        content={'Body paragraph'}
        mediaDetail={{ processing: { analysis: 'Analysis paragraph' }, type: 'document' }}
      />
    )

    expect(screen.getByRole('button', { name: 'Previous' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Actions' })).toBeInTheDocument()

    const analysisCopyButton = screen.getByRole('button', {
      name: 'Copy analysis to clipboard'
    })
    expect(analysisCopyButton).toBeInTheDocument()

    fireEvent.click(analysisCopyButton)
  })
})
