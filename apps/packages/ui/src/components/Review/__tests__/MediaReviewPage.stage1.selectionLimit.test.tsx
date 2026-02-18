import React from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MediaReviewPage from '../MediaReviewPage'

const mediaItems = Array.from({ length: 31 }).map((_, idx) => ({
  id: idx + 1,
  title: `Item ${idx + 1}`,
  snippet: `Snippet ${idx + 1}`,
  type: 'pdf',
  created_at: '2026-02-17T00:00:00.000Z'
}))

const mocks = vi.hoisted(() => ({
  bgRequest: vi.fn(),
  refetch: vi.fn(),
  messageInfo: vi.fn(),
  messageWarning: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  clipboardWriteText: vi.fn(),
  getSetting: vi.fn(),
  setSetting: vi.fn(),
  clearSetting: vi.fn(),
  setHelpDismissed: vi.fn(),
  setSettingHook: vi.fn(),
  setChatMode: vi.fn(),
  setSelectedKnowledge: vi.fn(),
  setRagMediaIds: vi.fn(),
  navigate: vi.fn(),
  useVirtualizer: vi.fn(({ count }: { count: number }) => ({
    getTotalSize: () => count * 120,
    getVirtualItems: () =>
      Array.from({ length: count }).map((_, index) => ({
        index,
        start: index * 120,
        size: 120,
        key: index
      })),
    scrollToIndex: vi.fn(),
    measureElement: vi.fn()
  }))
}))

const interpolate = (template: string, values?: Record<string, unknown>) =>
  template.replace(/\{\{(\w+)\}\}/g, (_, key) => String(values?.[key] ?? ''))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?:
        | string
        | { defaultValue?: string; selected?: number; limit?: number; count?: number; total?: number; current?: number },
      maybeOptions?: Record<string, unknown>
    ) => {
      if (typeof fallbackOrOptions === 'string') {
        return interpolate(fallbackOrOptions, maybeOptions)
      }
      const template = fallbackOrOptions?.defaultValue || key
      return interpolate(template, fallbackOrOptions as Record<string, unknown> | undefined)
    }
  })
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => mocks.navigate
}))

vi.mock('@/hooks/useMessageOption', () => ({
  useMessageOption: () => ({
    setChatMode: mocks.setChatMode,
    setSelectedKnowledge: mocks.setSelectedKnowledge,
    setRagMediaIds: mocks.setRagMediaIds
  })
}))

vi.mock('@/hooks/useAntdMessage', () => ({
  useAntdMessage: () => ({
    info: mocks.messageInfo,
    warning: mocks.messageWarning,
    success: mocks.messageSuccess,
    error: mocks.messageError
  })
}))

vi.mock('@/services/background-proxy', () => ({
  bgRequest: mocks.bgRequest
}))

vi.mock('@tanstack/react-query', () => ({
  keepPreviousData: {},
  useQuery: () => ({
    data: mediaItems,
    isFetching: false,
    refetch: mocks.refetch
  })
}))

vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: (params: { count: number }) => mocks.useVirtualizer(params)
}))

vi.mock('@/hooks/useServerOnline', () => ({
  useServerOnline: () => true
}))

vi.mock('@/services/note-keywords', () => ({
  getNoteKeywords: vi.fn().mockResolvedValue([]),
  searchNoteKeywords: vi.fn().mockResolvedValue([])
}))

vi.mock('@plasmohq/storage/hook', () => ({
  useStorage: () => [true, mocks.setHelpDismissed, { isLoading: false }]
}))

vi.mock('@/hooks/useSetting', () => {
  const React = require('react') as typeof import('react')
  return {
    useSetting: (setting: { key: string; defaultValue: unknown }) => {
      const [value, setValue] = React.useState(setting.defaultValue)
      const setter = async (next: unknown | ((prev: unknown) => unknown)) => {
        setValue((prev: unknown) => (typeof next === 'function' ? (next as (prev: unknown) => unknown)(prev) : next))
      }
      return [value, setter, { isLoading: false }] as const
    }
  }
})

vi.mock('@/services/settings/registry', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/settings/registry')>()
  return {
    ...actual,
    getSetting: mocks.getSetting,
    setSetting: mocks.setSetting,
    clearSetting: mocks.clearSetting
  }
})

vi.mock('@/components/Media/DiffViewModal', () => ({
  DiffViewModal: ({
    open,
    leftText,
    rightText,
    leftLabel,
    rightLabel,
    onClose
  }: {
    open: boolean
    leftText: string
    rightText: string
    leftLabel: string
    rightLabel: string
    onClose: () => void
  }) =>
    open ? (
      <div data-testid="compare-diff-modal">
        <div>{leftLabel}</div>
        <div>{rightLabel}</div>
        <div>{leftText}</div>
        <div>{rightText}</div>
        <button type="button" onClick={onClose}>
          Close diff
        </button>
      </div>
    ) : null
}))

vi.mock('antd', async (importOriginal) => {
  const React = await import('react')
  const actual = await importOriginal<typeof import('antd')>()

  const Input = React.forwardRef<HTMLInputElement, any>(
    ({ value, onChange, onPressEnter, placeholder, ...rest }, ref) => (
      <input
        ref={ref}
        value={value || ''}
        onChange={onChange}
        placeholder={placeholder}
        onKeyDown={(event) => {
          if (event.key === 'Enter') onPressEnter?.(event)
        }}
        {...rest}
      />
    )
  )

  const Button = ({ children, onClick, disabled, icon, danger: _danger, iconPlacement: _iconPlacement, ...rest }: any) => (
    <button type="button" onClick={onClick} disabled={disabled} {...rest}>
      {icon}
      {children}
    </button>
  )

  const Tag = ({ children }: any) => <span>{children}</span>
  const Tooltip = ({ children }: any) => <>{children}</>
  const Spin = () => <span>loading</span>
  const Pagination = () => <div>pagination</div>
  const Empty = ({ description }: any) => <div>{description}</div>
  ;(Empty as any).PRESENTED_IMAGE_SIMPLE = null

  const Checkbox = ({ checked, onChange, ...rest }: any) => (
    <input
      type="checkbox"
      checked={checked}
      onChange={(event) => onChange?.({ target: { checked: event.target.checked } })}
      {...rest}
    />
  )

  const SelectComponent = ({ value, onChange, options = [], children, mode, ...rest }: any) => {
    const resolvedOptions = options.length > 0
      ? options
      : React.Children.toArray(children).map((child: any) => ({
          value: child?.props?.value,
          label: child?.props?.children
        }))
    const isMultiple = mode === 'multiple' || mode === 'tags'
    const selected = isMultiple ? (Array.isArray(value) ? value : []) : (value ?? '')
    return (
      <select
        multiple={isMultiple}
        value={selected as any}
        onChange={(event) => {
          if (isMultiple) {
            const values = Array.from(event.currentTarget.selectedOptions).map((opt) => opt.value)
            onChange?.(values)
          } else {
            onChange?.(event.currentTarget.value)
          }
        }}
        aria-label={rest['aria-label']}
      >
        {resolvedOptions.map((opt: any) => (
          <option key={String(opt.value)} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    )
  }
  ;(SelectComponent as any).Option = ({ value, children }: any) => (
    <option value={value}>{children}</option>
  )

  const RadioButton = ({ value, children, __groupValue, __groupOnChange }: any) => (
    <button
      type="button"
      aria-pressed={__groupValue === value}
      onClick={() => __groupOnChange?.({ target: { value } })}
    >
      {children}
    </button>
  )

  const RadioGroup = ({ value, onChange, children }: any) => (
    <div>
      {React.Children.map(children, (child: any) =>
        React.cloneElement(child, {
          __groupValue: value,
          __groupOnChange: onChange
        })
      )}
    </div>
  )

  const Switch = ({ checked, onChange }: any) => (
    <input type="checkbox" checked={checked} onChange={(e) => onChange?.(e.target.checked)} />
  )

  const Typography = {
    Text: ({ children }: any) => <span>{children}</span>
  }

  const Skeleton = () => <div>loading-skeleton</div>

  const Alert = ({ title, action }: any) => (
    <div>
      {title}
      {action}
    </div>
  )

  const Dropdown = ({ menu, children }: any) => (
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
                  disabled={item.disabled}
                  onClick={() => item.onClick?.()}
                >
                  {typeof item.label === 'string' ? item.label : String(item.key)}
                </button>
              ))
          : null}
      </div>
    </div>
  )

  const Modal = ({ open, title, onCancel, footer, children }: any) => {
    if (!open) return null
    return (
      <div>
        <h2>{title}</h2>
        <button type="button" onClick={onCancel}>
          Close
        </button>
        {children}
        {footer}
      </div>
    )
  }

  return {
    ...actual,
    Input,
    Button,
    Spin,
    Tag,
    Tooltip,
    Radio: { Group: RadioGroup, Button: RadioButton },
    Pagination,
    Empty,
    Select: SelectComponent,
    Checkbox,
    Typography,
    Skeleton,
    Switch,
    Alert,
    Collapse: ({ children }: any) => <div>{children}</div>,
    Dropdown,
    Modal
  }
})

describe('MediaReviewPage stage 1 selection limit clarity', () => {
  beforeEach(() => {
    mocks.bgRequest.mockReset()
    mocks.refetch.mockReset()
    mocks.messageInfo.mockReset()
    mocks.messageWarning.mockReset()
    mocks.messageSuccess.mockReset()
    mocks.messageError.mockReset()
    mocks.clipboardWriteText.mockReset()
    mocks.getSetting.mockReset()
    mocks.setSetting.mockReset()
    mocks.clearSetting.mockReset()
    mocks.setHelpDismissed.mockReset()
    mocks.setChatMode.mockReset()
    mocks.setSelectedKnowledge.mockReset()
    mocks.setRagMediaIds.mockReset()
    mocks.navigate.mockReset()
    mocks.useVirtualizer.mockClear()

    mocks.getSetting.mockResolvedValue(null)
    mocks.setSetting.mockResolvedValue(undefined)
    mocks.clearSetting.mockResolvedValue(undefined)

    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || '')
      const idMatch = path.match(/\/api\/v1\/media\/([^?]+)/)
      const id = idMatch ? Number(idMatch[1]) : null
      return {
        id: id ?? 1,
        title: `Item ${id ?? 1}`,
        type: 'pdf',
        content: `Content ${id ?? 1}`
      }
    })

    mocks.clipboardWriteText.mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: mocks.clipboardWriteText
      }
    })

    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: false,
        media: '',
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn()
      }))
    })
  })

  const getResultRowByTitle = (title: string): HTMLElement => {
    const list = screen.getByTestId('media-review-results-list')
    const text = within(list).getByText(title)
    const row = text.closest('[role="button"]')
    if (!row) throw new Error(`Missing row for title: ${title}`)
    return row as HTMLElement
  }

  const setMobileViewport = (isMobile: boolean) => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches:
          query === '(prefers-reduced-motion: reduce)'
            ? false
            : query === '(max-width: 1023px)'
              ? isMobile
              : false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn()
      }))
    })
  }

  it('renders X / 30 selected and updates counter correctly on shift-click range selection', async () => {
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })

    fireEvent.click(getResultRowByTitle('Item 1'))
    fireEvent.click(getResultRowByTitle('Item 5'), { shiftKey: true })

    await waitFor(() => {
      expect(screen.getByText('5 / 30 selected')).toBeInTheDocument()
    })
  })

  it('keeps warning/error threshold behavior predictable as selection nears and hits limit', async () => {
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })

    for (let i = 1; i <= 25; i++) {
      fireEvent.click(getResultRowByTitle(`Item ${i}`))
    }

    await waitFor(() => {
      expect(screen.getByText('25 / 30 selected')).toBeInTheDocument()
      expect(screen.getByText('(5 left)')).toBeInTheDocument()
    })

    for (let i = 26; i <= 30; i++) {
      fireEvent.click(getResultRowByTitle(`Item ${i}`))
    }

    await waitFor(() => {
      expect(screen.getByText('30 / 30 selected')).toBeInTheDocument()
    })

    fireEvent.click(getResultRowByTitle('Item 31'))

    expect(mocks.messageWarning).toHaveBeenCalledWith('Selection limit reached (30 items)')
    expect(screen.getByText('30 / 30 selected')).toBeInTheDocument()
  })

  it('supports keyboard selection and keeps counter in sync', async () => {
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })

    const row = getResultRowByTitle('Item 2')
    row.focus()
    fireEvent.keyDown(row, { key: 'Enter' })

    await waitFor(() => {
      expect(screen.getByText('1 / 30 selected')).toBeInTheDocument()
    })

    const checkbox = within(row).getByRole('checkbox')
    expect(checkbox).toBeChecked()
  })

  it('shows inline double-escape hint when selection exceeds five items', async () => {
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('escape-double-tap-hint-inline')).not.toBeInTheDocument()

    for (let i = 1; i <= 6; i++) {
      fireEvent.click(getResultRowByTitle(`Item ${i}`))
    }

    await waitFor(() => {
      expect(screen.getByText('6 / 30 selected')).toBeInTheDocument()
      expect(screen.getByTestId('escape-double-tap-hint-inline')).toHaveTextContent(
        'Tip: press Escape twice quickly to clear large selections.'
      )
    })
  })

  it('focuses the search field when slash shortcut is pressed outside typing contexts', async () => {
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })

    const searchInput = screen.getByPlaceholderText('Search media (title/content)')
    expect(searchInput).not.toHaveFocus()

    fireEvent.keyDown(document, { key: '/' })

    await waitFor(() => {
      expect(searchInput).toHaveFocus()
    })
  })

  it('shows compare content action only when exactly two items are selected', async () => {
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })
    expect(screen.queryByRole('button', { name: 'Compare content' })).not.toBeInTheDocument()

    fireEvent.click(getResultRowByTitle('Item 1'))
    expect(screen.queryByRole('button', { name: 'Compare content' })).not.toBeInTheDocument()

    fireEvent.click(getResultRowByTitle('Item 2'))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Compare content' })).toBeInTheDocument()
    })

    fireEvent.click(getResultRowByTitle('Item 2'))
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Compare content' })).not.toBeInTheDocument()
    })
  }, 10000)

  it('opens content diff modal with selected item content when compare action is triggered', async () => {
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })

    fireEvent.click(getResultRowByTitle('Item 1'))
    fireEvent.click(getResultRowByTitle('Item 2'))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Compare content' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Compare content' }))

    await waitFor(() => {
      const modal = screen.getByTestId('compare-diff-modal')
      expect(modal).toBeInTheDocument()
      expect(within(modal).getByText('Item 1')).toBeInTheDocument()
      expect(within(modal).getByText('Item 2')).toBeInTheDocument()
      expect(within(modal).getByText('Content 1')).toBeInTheDocument()
      expect(within(modal).getByText('Content 2')).toBeInTheDocument()
    })
  })

  it('shows actionable error when compare content is requested without content payloads', async () => {
    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || '')
      const idMatch = path.match(/\/api\/v1\/media\/([^?]+)/)
      const id = idMatch ? Number(idMatch[1]) : null
      if (id === 2) {
        return {
          id: 2,
          title: 'Item 2',
          type: 'pdf',
          content: ''
        }
      }
      return {
        id: id ?? 1,
        title: `Item ${id ?? 1}`,
        type: 'pdf',
        content: `Content ${id ?? 1}`
      }
    })

    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })

    fireEvent.click(getResultRowByTitle('Item 1'))
    fireEvent.click(getResultRowByTitle('Item 2'))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Compare content' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Compare content' }))

    await waitFor(() => {
      expect(mocks.messageError).toHaveBeenCalledWith('One or both selected items have no content to compare.')
    })
    expect(screen.queryByTestId('compare-diff-modal')).not.toBeInTheDocument()
  })

  it('shows chat-about-selection action only when at least one item is selected', async () => {
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })
    expect(
      screen.queryByRole('button', { name: 'Chat about selection (1)' })
    ).not.toBeInTheDocument()

    fireEvent.click(getResultRowByTitle('Item 1'))

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Chat about selection (1)' })
      ).toBeInTheDocument()
    })
  })

  it('launches media-scoped chat with selected ids and backward-compatible discuss payload', async () => {
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent')
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })

    fireEvent.click(getResultRowByTitle('Item 1'))
    fireEvent.click(getResultRowByTitle('Item 2'))

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Chat about selection (2)' })
      ).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Chat about selection (2)' }))

    await waitFor(() => {
      expect(mocks.setChatMode).toHaveBeenCalledWith('rag')
      expect(mocks.setRagMediaIds).toHaveBeenCalledWith([1, 2])
      expect(mocks.navigate).toHaveBeenCalledWith('/')
    })

    const discussEvent = dispatchSpy.mock.calls
      .map((call) => call[0])
      .find((event) => event.type === 'tldw:discuss-media') as CustomEvent | undefined
    expect(discussEvent).toBeDefined()
    expect(discussEvent?.detail).toEqual(
      expect.objectContaining({
        mediaId: '1',
        mode: 'rag_media',
        mediaIds: [1, 2]
      })
    )
    dispatchSpy.mockRestore()
  })

  it('preserves auto view-mode thresholds for 1, 2-4, and 5+ selections', async () => {
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })

    fireEvent.click(getResultRowByTitle('Item 1'))
    await waitFor(() => {
      expect(screen.getByText('Single item view')).toBeInTheDocument()
    })

    fireEvent.click(getResultRowByTitle('Item 2'))
    await waitFor(() => {
      expect(screen.getByText('2 open')).toBeInTheDocument()
    })

    fireEvent.click(getResultRowByTitle('Item 3'))
    fireEvent.click(getResultRowByTitle('Item 4'))
    fireEvent.click(getResultRowByTitle('Item 5'))
    await waitFor(() => {
      expect(screen.getByText('All items (stacked)')).toBeInTheDocument()
    })
  })

  it('keeps help modal trigger and keyboard j/k navigation behavior available', async () => {
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Multi-Item Review keyboard shortcuts'
      })
    )
    expect(screen.getByText('Keyboard Shortcuts')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByText('Keyboard Shortcuts')).not.toBeInTheDocument()

    fireEvent.click(getResultRowByTitle('Item 1'))
    await waitFor(() => {
      expect(screen.getByText('Item 1 of 31')).toBeInTheDocument()
    })

    fireEvent.keyDown(document, { key: 'j' })
    await waitFor(() => {
      expect(screen.getByText('Item 2 of 31')).toBeInTheDocument()
    })

    fireEvent.keyDown(document, { key: 'k' })
    await waitFor(() => {
      expect(screen.getByText('Item 1 of 31')).toBeInTheDocument()
    })
  })

  it('preserves per-card copy confirmation behavior', async () => {
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })

    fireEvent.click(getResultRowByTitle('Item 1'))

    const copyContentButton = await screen.findByRole('button', { name: 'Copy Content' })
    fireEvent.click(copyContentButton)

    await waitFor(() => {
      expect(mocks.clipboardWriteText).toHaveBeenCalledWith('Content 1')
      expect(mocks.messageSuccess).toHaveBeenCalledWith('Content copied')
    })
  })

  it('preserves failed-item recovery behavior by allowing reselection retry', async () => {
    const attempts = new Map<number, number>()
    mocks.bgRequest.mockImplementation(async (request: { path?: string }) => {
      const path = String(request?.path || '')
      const idMatch = path.match(/\/api\/v1\/media\/([^?]+)/)
      const id = idMatch ? Number(idMatch[1]) : null
      const numericId = id ?? 1
      const attempt = (attempts.get(numericId) ?? 0) + 1
      attempts.set(numericId, attempt)
      if (numericId === 1 && attempt === 1) {
        throw new Error('detail fetch failed')
      }
      return {
        id: numericId,
        title: `Item ${numericId}`,
        type: 'pdf',
        content: `Recovered Content ${numericId}`
      }
    })

    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })

    fireEvent.click(getResultRowByTitle('Item 1'))

    await waitFor(() => {
      expect(attempts.get(1)).toBe(1)
      expect(screen.getByText('Select items on the left to view here.')).toBeInTheDocument()
    })

    fireEvent.click(getResultRowByTitle('Item 1'))
    fireEvent.click(getResultRowByTitle('Item 1'))

    await waitFor(() => {
      expect(screen.getByText('Recovered Content 1')).toBeInTheDocument()
    })
    expect(attempts.get(1)).toBeGreaterThanOrEqual(2)
  })

  it('forces list mode and hides sidebar by default on mobile viewports', async () => {
    setMobileViewport(true)
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Show sidebar' })).toBeInTheDocument()
    })
    expect(screen.getByText('Focus')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Compare' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Stack' })).not.toBeInTheDocument()
  })

  it('keeps mobile viewer in single-item mode for multi-selection', async () => {
    setMobileViewport(true)
    render(<MediaReviewPage />)

    fireEvent.click(await screen.findByRole('button', { name: 'Show sidebar' }))

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })

    fireEvent.click(getResultRowByTitle('Item 1'))
    fireEvent.click(getResultRowByTitle('Item 2'))

    await waitFor(() => {
      expect(screen.getByText('2 / 30 selected')).toBeInTheDocument()
      expect(screen.getByText('Single item view')).toBeInTheDocument()
    })
    expect(screen.getAllByRole('button', { name: 'Copy Content' })).toHaveLength(1)
  })

  it('keeps list and viewer virtualization counts aligned with result/selection state', async () => {
    render(<MediaReviewPage />)

    await waitFor(() => {
      expect(screen.getByText('0 / 30 selected')).toBeInTheDocument()
    })

    expect(
      mocks.useVirtualizer.mock.calls.some(
        (call) => Number((call[0] as { count?: number })?.count) === mediaItems.length
      )
    ).toBe(true)
    expect(
      mocks.useVirtualizer.mock.calls.some(
        (call) => Number((call[0] as { count?: number })?.count) === 0
      )
    ).toBe(true)

    fireEvent.click(getResultRowByTitle('Item 1'))
    fireEvent.click(getResultRowByTitle('Item 2'))

    await waitFor(() => {
      expect(screen.getByText('2 / 30 selected')).toBeInTheDocument()
    })
    expect(
      mocks.useVirtualizer.mock.calls.some(
        (call) => Number((call[0] as { count?: number })?.count) === 2
      )
    ).toBe(true)
  })
})
