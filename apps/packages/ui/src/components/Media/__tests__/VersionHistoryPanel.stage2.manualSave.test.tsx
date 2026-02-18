import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { VersionHistoryPanel } from '../VersionHistoryPanel'

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn(),
  confirmDanger: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  messageInfo: vi.fn(),
  messageWarning: vi.fn()
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?:
        | string
        | { defaultValue?: string; num?: number; current?: number; total?: number }
    ) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      return fallbackOrOptions?.defaultValue || key
    }
  })
}))

vi.mock('@/services/background-proxy', () => ({
  bgRequest: mocks.bgRequest
}))

vi.mock('@/components/Common/confirm-danger', () => ({
  useConfirmDanger: () => mocks.confirmDanger
}))

vi.mock('antd', async (importOriginal) => {
  const actual = await importOriginal<typeof import('antd')>()
  return {
    ...actual,
    Dropdown: ({ menu, children }: any) => (
      <div>
        {children}
        <div>
          {Array.isArray(menu?.items)
            ? menu.items
                .filter((item: any) => item && item.type !== 'divider')
                .map((item: any, idx: number) => (
                  <button
                    key={`${item.key}-${idx}`}
                    type="button"
                    onClick={() => item.onClick?.()}
                  >
                    {typeof item.label === 'string' ? item.label : String(item.key)}
                  </button>
                ))
            : null}
        </div>
      </div>
    ),
    Checkbox: ({ checked, onChange, children }: any) => (
      <label>
        <input
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange?.({ target: { checked: event.target.checked } })}
        />
        {children}
      </label>
    ),
    message: {
      ...actual.message,
      success: mocks.messageSuccess,
      error: mocks.messageError,
      info: mocks.messageInfo,
      warning: mocks.messageWarning
    }
  }
})

const baseVersionsResponse = {
  items: [
    {
      version_number: 4,
      analysis_content: 'Existing analysis',
      prompt: 'Existing prompt',
      created_at: '2026-02-18T00:00:00.000Z'
    }
  ]
}

function createDeferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('VersionHistoryPanel stage 2 manual save', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    mocks.bgRequest.mockReset()
    mocks.confirmDanger.mockReset()
    mocks.messageSuccess.mockReset()
    mocks.messageError.mockReset()
    mocks.messageInfo.mockReset()
    mocks.messageWarning.mockReset()
    mocks.confirmDanger.mockResolvedValue(true)
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it('creates a new version from current snapshot and blocks duplicate in-flight submissions', async () => {
    const deferredPost = createDeferred<any>()
    const onRefresh = vi.fn()

    mocks.bgRequest.mockImplementation(async (request: { path?: string; method?: string }) => {
      const path = String(request?.path || '')
      const method = String(request?.method || 'GET')
      if (path.includes('/versions?include_content=false') && method === 'GET') {
        return baseVersionsResponse
      }
      if (path === '/api/v1/media/55/versions' && method === 'POST') {
        return deferredPost.promise
      }
      return {}
    })

    render(
      <VersionHistoryPanel
        mediaId={55}
        defaultExpanded
        onRefresh={onRefresh}
        currentContent="Current content body"
        currentPrompt="Manual prompt"
        currentAnalysis="Manual analysis"
      />
    )

    await waitFor(() => {
      expect(screen.getByText('v4')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Save Version' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Saving...' })).toBeDisabled()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Saving...' }))

    const postCalls = mocks.bgRequest.mock.calls.filter(([request]) => {
      const path = String((request as { path?: string })?.path || '')
      const method = String((request as { method?: string })?.method || '')
      return path === '/api/v1/media/55/versions' && method === 'POST'
    })
    expect(postCalls).toHaveLength(1)
    expect(postCalls[0]?.[0]).toEqual(
      expect.objectContaining({
        body: {
          content: 'Current content body',
          prompt: 'Manual prompt',
          analysis_content: 'Manual analysis'
        }
      })
    )

    deferredPost.resolve({})

    await waitFor(() => {
      expect(mocks.messageSuccess).toHaveBeenCalledWith('Saved as new version')
    })
    await waitFor(() => {
      expect(onRefresh).toHaveBeenCalledTimes(1)
      expect(screen.getByRole('button', { name: 'Save Version' })).not.toBeDisabled()
    })
  })

  it('shows an error and clears loading state when manual save fails', async () => {
    const onRefresh = vi.fn()

    mocks.bgRequest.mockImplementation(async (request: { path?: string; method?: string }) => {
      const path = String(request?.path || '')
      const method = String(request?.method || 'GET')
      if (path.includes('/versions?include_content=false') && method === 'GET') {
        return baseVersionsResponse
      }
      if (path === '/api/v1/media/55/versions' && method === 'POST') {
        throw new Error('create failed')
      }
      return {}
    })

    render(
      <VersionHistoryPanel
        mediaId={55}
        defaultExpanded
        onRefresh={onRefresh}
        currentContent="Current content body"
        currentPrompt="Manual prompt"
        currentAnalysis="Manual analysis"
      />
    )

    await waitFor(() => {
      expect(screen.getByText('v4')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Save Version' }))

    await waitFor(() => {
      expect(mocks.messageError).toHaveBeenCalledWith('Failed to save version')
      expect(screen.getByRole('button', { name: 'Save Version' })).not.toBeDisabled()
    })
    expect(onRefresh).not.toHaveBeenCalled()
  })

  it('falls back to latest version payload when current snapshot props are missing', async () => {
    mocks.bgRequest.mockImplementation(async (request: { path?: string; method?: string }) => {
      const path = String(request?.path || '')
      const method = String(request?.method || 'GET')

      if (path.includes('/versions?include_content=false') && method === 'GET') {
        return {
          items: [
            {
              version_number: 7,
              prompt: 'Prompt from latest',
              analysis_content: 'Analysis from latest'
            }
          ]
        }
      }

      if (path === '/api/v1/media/55/versions/7?include_content=true' && method === 'GET') {
        return {
          content: 'Content from latest version detail'
        }
      }

      if (path === '/api/v1/media/55/versions' && method === 'POST') {
        return {}
      }
      return {}
    })

    render(<VersionHistoryPanel mediaId={55} defaultExpanded />)

    await waitFor(() => {
      expect(screen.getByText('v7')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Save Version' }))

    await waitFor(() => {
      expect(mocks.bgRequest).toHaveBeenCalledWith(
        expect.objectContaining({
          path: '/api/v1/media/55/versions',
          method: 'POST',
          body: {
            content: 'Content from latest version detail',
            prompt: 'Prompt from latest',
            analysis_content: 'Analysis from latest'
          }
        })
      )
    })
  })
})
