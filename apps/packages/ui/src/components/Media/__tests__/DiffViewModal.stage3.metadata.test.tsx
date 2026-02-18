import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { DiffViewModal } from '../DiffViewModal'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallbackOrOptions?: string | { defaultValue?: string }) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      return fallbackOrOptions?.defaultValue || key
    }
  })
}))

vi.mock('antd', async (importOriginal) => {
  const React = await import('react')
  const actual = await importOriginal<typeof import('antd')>()

  const Modal = ({ open, title, onCancel, afterOpenChange, children }: any) => {
    React.useEffect(() => {
      afterOpenChange?.(open)
    }, [open, afterOpenChange])

    if (!open) return null
    return (
      <div data-testid="diff-modal">
        <h2>{title}</h2>
        <button type="button" onClick={onCancel}>
          Close
        </button>
        {children}
      </div>
    )
  }

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
    <div data-testid="diff-view-mode-group">
      {React.Children.map(children, (child: any) =>
        React.cloneElement(child, {
          __groupValue: value,
          __groupOnChange: onChange
        })
      )}
    </div>
  )

  return {
    ...actual,
    Modal,
    Radio: {
      Group: RadioGroup,
      Button: RadioButton
    }
  }
})

describe('DiffViewModal stage 3 metadata summary', () => {
  it('renders metadata diff details alongside content diff', () => {
    render(
      <DiffViewModal
        open
        onClose={vi.fn()}
        leftText={'alpha\nbeta'}
        rightText={'alpha\ngamma'}
        leftLabel="Version 3"
        rightLabel="Version 2"
        metadataDiff={{
          left: ['DOI: 10.1000/foo', 'License: CC-BY'],
          right: ['DOI: 10.1000/bar', 'License: CC0'],
          changed: ['DOI: 10.1000/foo → 10.1000/bar', 'License: CC-BY → CC0']
        }}
      />
    )

    expect(screen.getByText('Metadata changes')).toBeInTheDocument()
    expect(screen.getByText('DOI: 10.1000/foo → 10.1000/bar')).toBeInTheDocument()
    expect(screen.getByText('License: CC-BY → CC0')).toBeInTheDocument()
    expect(screen.getByText('DOI: 10.1000/foo')).toBeInTheDocument()
    expect(screen.getByText('DOI: 10.1000/bar')).toBeInTheDocument()
  })
})
