import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AnalysisEditModal } from '../AnalysisEditModal'

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
      fallbackOrOptions?: string | { defaultValue?: string; count?: number }
    ) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      if (key === 'mediaPage.wordCount') {
        return `${fallbackOrOptions?.count ?? 0} words`
      }
      if (key === 'mediaPage.charCount') {
        return `${fallbackOrOptions?.count ?? 0} characters`
      }
      return fallbackOrOptions?.defaultValue || key
    }
  })
}))

vi.mock('antd', async (importOriginal) => {
  const actual = await importOriginal<typeof import('antd')>()

  const Modal = ({ open, title, onCancel, footer, children }: any) => {
    if (!open) return null
    return (
      <div data-testid="analysis-edit-modal">
        <h2>{title}</h2>
        <button type="button" onClick={onCancel}>
          Close
        </button>
        <div>{children}</div>
        <div>{footer}</div>
      </div>
    )
  }

  return {
    ...actual,
    Modal,
    message: {
      ...actual.message,
      success: mocks.messageSuccess,
      error: mocks.messageError,
      warning: mocks.messageWarning
    }
  }
})

vi.mock('@/services/background-proxy', () => ({
  bgRequest: mocks.bgRequest
}))

describe('AnalysisEditModal stage 3 regression coverage', () => {
  beforeEach(() => {
    mocks.bgRequest.mockReset()
    mocks.messageSuccess.mockReset()
    mocks.messageError.mockReset()
    mocks.messageWarning.mockReset()
  })

  it('shows character warning and disables save actions when over limit', async () => {
    const overLimitText = 'a'.repeat(25001)

    render(
      <AnalysisEditModal
        open
        onClose={vi.fn()}
        initialText={overLimitText}
        mediaId={55}
        onSave={vi.fn()}
      />
    )

    expect(screen.getByText('Character limit exceeded')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save as New Version' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  })

  it('keeps send-to-chat and save flows functional', async () => {
    const onClose = vi.fn()
    const onSave = vi.fn()
    const onSendToChat = vi.fn()

    const { rerender } = render(
      <AnalysisEditModal
        open
        onClose={onClose}
        initialText={'analysis text to save'}
        onSave={onSave}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onSave).toHaveBeenCalledWith('analysis text to save')
    expect(onClose).toHaveBeenCalledTimes(1)

    rerender(
      <AnalysisEditModal
        open
        onClose={onClose}
        initialText={'analysis text to chat'}
        onSendToChat={onSendToChat}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Send to Chat' }))
    expect(onSendToChat).toHaveBeenCalledWith('analysis text to chat')
    expect(onClose).toHaveBeenCalledTimes(2)
  })

  it('saves as new version using latest prompt fallback when prompt prop is empty', async () => {
    const onClose = vi.fn()
    const onSaveNewVersion = vi.fn()

    mocks.bgRequest.mockImplementation(async (request: { path?: string; method?: string }) => {
      const path = String(request?.path || '')
      if (path.includes('/versions?include_content=false')) {
        return {
          items: [
            { version_number: 3, prompt: 'Prompt from latest' },
            { version_number: 2, prompt: 'Older prompt' }
          ]
        }
      }
      return {}
    })

    render(
      <AnalysisEditModal
        open
        onClose={onClose}
        initialText={'analysis text'}
        mediaId={55}
        content="media content"
        prompt=""
        onSaveNewVersion={onSaveNewVersion}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Save as New Version' }))

    await waitFor(() => {
      expect(mocks.bgRequest).toHaveBeenCalledWith(
        expect.objectContaining({
          path: '/api/v1/media/55/versions',
          method: 'POST',
          body: {
            content: 'media content',
            analysis_content: 'analysis text',
            prompt: 'Prompt from latest'
          }
        })
      )
    })

    expect(mocks.messageSuccess).toHaveBeenCalledWith('Saved as new version')
    expect(onSaveNewVersion).toHaveBeenCalledWith('analysis text')
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
