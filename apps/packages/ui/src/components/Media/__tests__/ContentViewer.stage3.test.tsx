import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { ContentViewer } from '../ContentViewer'

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn()
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallbackOrOptions?: string | { defaultValue?: string; timestamp?: string }) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      if (fallbackOrOptions?.defaultValue) {
        return fallbackOrOptions.defaultValue.replace(
          '{{timestamp}}',
          String(fallbackOrOptions.timestamp ?? '')
        )
      }
      return _key
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

const selectedAudio = {
  kind: 'media' as const,
  id: 77,
  title: 'Audio item',
  raw: { has_original_file: true },
  meta: { type: 'audio' }
}

describe('ContentViewer stage 3 playback', () => {
  beforeEach(() => {
    mocks.bgRequest.mockReset()
    mocks.bgRequest.mockResolvedValue(new ArrayBuffer(8))

    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:media-audio')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders an embedded audio player for audio items with original files', async () => {
    render(
      <ContentViewer
        selectedMedia={selectedAudio}
        content={'Transcript content'}
        mediaDetail={{ has_original_file: true, type: 'audio' }}
        contentDisplayMode="plain"
      />
    )

    await waitFor(() => {
      expect(screen.getByTestId('embedded-audio-player')).toBeInTheDocument()
    })

    expect(mocks.bgRequest).toHaveBeenCalledWith(
      expect.objectContaining({
        path: '/api/v1/media/77/file',
        method: 'GET',
        responseType: 'arrayBuffer'
      })
    )
  })

  it('seeks embedded playback when transcript timestamp chips are clicked', async () => {
    render(
      <ContentViewer
        selectedMedia={selectedAudio}
        content={'00:12 Intro line\n00:34 Follow up line'}
        mediaDetail={{ has_original_file: true, type: 'audio' }}
        contentDisplayMode="plain"
      />
    )

    const player = (await screen.findByTestId('embedded-audio-player')) as HTMLAudioElement
    let currentTimeValue = 0
    Object.defineProperty(player, 'currentTime', {
      configurable: true,
      get: () => currentTimeValue,
      set: (value: number) => {
        currentTimeValue = Number(value)
      }
    })
    expect(player.currentTime).toBe(0)

    fireEvent.click(await screen.findByRole('button', { name: 'Seek to 00:12' }))

    expect(player.currentTime).toBe(12)
  })
})
