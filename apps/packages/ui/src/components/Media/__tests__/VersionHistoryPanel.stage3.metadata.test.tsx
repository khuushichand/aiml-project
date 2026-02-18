import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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
      info: mocks.messageInfo,
      warning: mocks.messageWarning
    }
  }
})

describe('VersionHistoryPanel stage 3 metadata visibility', () => {
  beforeEach(() => {
    mocks.bgRequest.mockReset()
    mocks.confirmDanger.mockReset()
    mocks.messageSuccess.mockReset()
    mocks.messageError.mockReset()
    mocks.messageInfo.mockReset()
    mocks.messageWarning.mockReset()
    mocks.confirmDanger.mockResolvedValue(true)

    mocks.bgRequest.mockImplementation(async (request: { path?: string; method?: string }) => {
      const path = String(request?.path || '')
      if (path.includes('/versions?include_content=false')) {
        return {
          items: [
            {
              version_number: 3,
              analysis_content: 'Analysis v3',
              prompt: 'Prompt v3',
              safe_metadata: {
                doi: '10.1000/foo',
                journal: 'Journal One',
                license: 'CC-BY'
              }
            },
            {
              version_number: 2,
              analysis_content: 'Analysis v2',
              prompt: 'Prompt v2',
              safe_metadata: {
                doi: '10.1000/bar',
                journal: 'Journal One',
                license: 'CC0'
              }
            }
          ]
        }
      }
      return {}
    })
  })

  it('shows key metadata on each version and includes metadata diff context in compare actions', async () => {
    const onShowDiff = vi.fn()

    render(
      <VersionHistoryPanel mediaId={55} defaultExpanded onShowDiff={onShowDiff} />
    )

    await waitFor(() => {
      expect(screen.getByText('v3')).toBeInTheDocument()
      expect(screen.getByText('v2')).toBeInTheDocument()
    })

    expect(screen.getByText('DOI: 10.1000/foo')).toBeInTheDocument()
    expect(screen.getAllByText('Journal: Journal One').length).toBeGreaterThan(0)
    expect(screen.getByText('License: CC-BY')).toBeInTheDocument()

    fireEvent.click(screen.getAllByRole('button', { name: 'Compare with selected' })[0])

    expect(onShowDiff).toHaveBeenCalledWith(
      'Analysis v3',
      'Analysis v2',
      'Version 3',
      'Version 2',
      expect.objectContaining({
        left: expect.arrayContaining([
          'DOI: 10.1000/foo',
          'Journal: Journal One',
          'License: CC-BY'
        ]),
        right: expect.arrayContaining([
          'DOI: 10.1000/bar',
          'Journal: Journal One',
          'License: CC0'
        ]),
        changed: expect.arrayContaining([
          'DOI: 10.1000/foo → 10.1000/bar',
          'License: CC-BY → CC0'
        ])
      })
    )
  })
})
