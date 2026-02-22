import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { VersionHistoryPanel } from '../VersionHistoryPanel'

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn(),
  confirmDanger: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  messageInfo: vi.fn()
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string; num?: number; current?: number; total?: number }
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
      info: mocks.messageInfo
    }
  }
})

const versionsResponse = {
  items: [
    {
      version_number: 3,
      analysis_content: '',
      prompt: 'Prompt 3',
      created_at: '2026-02-17T12:00:00.000Z'
    },
    {
      version_number: 2,
      analysis: 'Analysis from fallback field',
      prompt: 'Prompt 2',
      created_at: '2026-02-16T12:00:00.000Z'
    },
    {
      version_number: 1,
      analysis_content: 'Analysis from primary field',
      prompt: 'Prompt 1',
      created_at: '2026-02-15T12:00:00.000Z'
    }
  ]
}

describe('VersionHistoryPanel stage 1 regressions', () => {
  beforeEach(() => {
    mocks.confirmDanger.mockReset()
    mocks.confirmDanger.mockResolvedValue(true)
    mocks.bgRequest.mockReset()
    mocks.messageSuccess.mockReset()
    mocks.messageError.mockReset()
    mocks.messageInfo.mockReset()

    mocks.bgRequest.mockImplementation(async (request: { path?: string; method?: string }) => {
      const path = String(request?.path || '')
      if (path.includes('/versions?include_content=false')) {
        return versionsResponse
      }
      if (path.includes('/versions/2?include_content=true')) {
        return {
          content: 'Loaded content v2',
          analysis: 'Loaded analysis v2',
          prompt: 'Loaded prompt v2'
        }
      }
      return {}
    })
  })

  it('loads versions, renders analysis previews, and supports analysis-only filter', async () => {
    render(<VersionHistoryPanel mediaId={55} defaultExpanded />)

    await waitFor(() => {
      expect(mocks.bgRequest).toHaveBeenCalledWith(
        expect.objectContaining({
          path: '/api/v1/media/55/versions?include_content=false&limit=50&page=1',
          method: 'GET'
        })
      )
    })

    expect(screen.getByText('v3')).toBeInTheDocument()
    expect(screen.getByText('v2')).toBeInTheDocument()
    expect(screen.getByText('v1')).toBeInTheDocument()
    expect(screen.getByText('Analysis from fallback field')).toBeInTheDocument()
    expect(screen.getByText('Analysis from primary field')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('checkbox'))

    expect(screen.queryByText('v3')).not.toBeInTheDocument()
    expect(screen.getByText('v2')).toBeInTheDocument()
    expect(screen.getByText('v1')).toBeInTheDocument()
  })

  it('loads selected version content/analysis/prompt via action menu', async () => {
    const onVersionLoad = vi.fn()

    render(
      <VersionHistoryPanel mediaId={55} defaultExpanded onVersionLoad={onVersionLoad} />
    )

    await waitFor(() => {
      expect(screen.getByText('v2')).toBeInTheDocument()
    })

    fireEvent.click(screen.getAllByRole('button', { name: 'Load into editor' })[1])

    await waitFor(() => {
      expect(onVersionLoad).toHaveBeenCalledWith(
        'Loaded content v2',
        'Loaded analysis v2',
        'Loaded prompt v2',
        2
      )
    })
  })

  it('keeps compare, rollback, and delete actions functional', async () => {
    const onShowDiff = vi.fn()

    render(
      <VersionHistoryPanel mediaId={55} defaultExpanded onShowDiff={onShowDiff} />
    )

    await waitFor(() => {
      expect(screen.getByText('v1')).toBeInTheDocument()
    })

    fireEvent.click(screen.getAllByRole('button', { name: 'Compare with selected' })[0])
    expect(onShowDiff).toHaveBeenCalledWith(
      '',
      'Analysis from fallback field',
      'Version 3',
      'Version 2'
    )

    fireEvent.click(screen.getAllByRole('button', { name: 'Rollback to this version' })[0])
    await waitFor(() => {
      expect(mocks.bgRequest).toHaveBeenCalledWith(
        expect.objectContaining({
          path: '/api/v1/media/55/versions/rollback',
          method: 'POST',
          body: { version_number: 3 }
        })
      )
    })

    fireEvent.click(screen.getAllByRole('button', { name: 'Delete version' })[0])
    await waitFor(() => {
      expect(mocks.bgRequest).toHaveBeenCalledWith(
        expect.objectContaining({
          path: '/api/v1/media/55/versions/3',
          method: 'DELETE'
        })
      )
    })
  })
})
