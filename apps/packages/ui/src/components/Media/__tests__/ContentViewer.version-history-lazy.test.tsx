import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
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
  VersionHistoryPanel: ({ defaultExpanded }: { defaultExpanded?: boolean }) => (
    <div
      data-testid="mock-version-history-panel"
      data-default-expanded={String(defaultExpanded)}
    />
  )
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
  id: 707,
  title: 'Versioned media',
  raw: {},
  meta: { type: 'document' }
}

describe('ContentViewer version history lazy host', () => {
  it('shows the collapsed shell first and only mounts version history after opening it', async () => {
    const user = userEvent.setup()

    render(
      <ContentViewer
        selectedMedia={selectedMedia}
        content={'Body paragraph'}
        mediaDetail={{ type: 'document' }}
      />
    )

    const openButton = screen.getByRole('button', { name: 'Version History' })
    expect(openButton).toBeInTheDocument()
    expect(screen.queryByTestId('mock-version-history-panel')).not.toBeInTheDocument()

    await user.click(openButton)

    await waitFor(() => {
      expect(screen.getByTestId('mock-version-history-panel')).toHaveAttribute(
        'data-default-expanded',
        'true'
      )
    })
  })
})
