import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { KeyboardShortcutsOverlay } from '../KeyboardShortcutsOverlay'

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) => options?.defaultValue || key,
  }),
}))

describe('KeyboardShortcutsOverlay', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders nothing when closed', () => {
    render(<KeyboardShortcutsOverlay open={false} onClose={vi.fn()} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders dialog when open', () => {
    render(<KeyboardShortcutsOverlay open={true} onClose={vi.fn()} />)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Keyboard Shortcuts')).toBeInTheDocument()
  })

  it('displays Navigation section', () => {
    render(<KeyboardShortcutsOverlay open={true} onClose={vi.fn()} />)
    expect(screen.getByText('Navigation')).toBeInTheDocument()
    expect(screen.getByText('Next item')).toBeInTheDocument()
    expect(screen.getByText('Previous item')).toBeInTheDocument()
    expect(screen.getByText('Previous page')).toBeInTheDocument()
    expect(screen.getByText('Next page')).toBeInTheDocument()
  })

  it('displays General section', () => {
    render(<KeyboardShortcutsOverlay open={true} onClose={vi.fn()} />)
    expect(screen.getByText('General')).toBeInTheDocument()
    expect(screen.getByText('Focus search')).toBeInTheDocument()
    expect(screen.getByText('Show/hide this help')).toBeInTheDocument()
    expect(screen.getByText('Close overlay')).toBeInTheDocument()
    expect(screen.getByText('Clear large selection in multi-review')).toBeInTheDocument()
  })

  it('displays key indicators', () => {
    const { container } = render(<KeyboardShortcutsOverlay open={true} onClose={vi.fn()} />)
    // Check for keyboard shortcuts shown in kbd elements
    const kbdElements = container.querySelectorAll('kbd')
    expect(kbdElements.length).toBeGreaterThan(0)

    // Check for specific keys
    expect(screen.getByText('j')).toBeInTheDocument()
    expect(screen.getByText('k')).toBeInTheDocument()
    expect(screen.getByText('/')).toBeInTheDocument()
    expect(screen.getByText('?')).toBeInTheDocument()
    expect(screen.getAllByText('Esc').length).toBeGreaterThan(0)
  })

  it('closes on Escape key', () => {
    const handleClose = vi.fn()
    render(<KeyboardShortcutsOverlay open={true} onClose={handleClose} />)

    fireEvent.keyDown(document, { key: 'Escape' })

    expect(handleClose).toHaveBeenCalledTimes(1)
  })

  it('closes on ? key', () => {
    const handleClose = vi.fn()
    render(<KeyboardShortcutsOverlay open={true} onClose={handleClose} />)

    fireEvent.keyDown(document, { key: '?' })

    expect(handleClose).toHaveBeenCalledTimes(1)
  })

  it('closes on backdrop click', () => {
    const handleClose = vi.fn()
    render(<KeyboardShortcutsOverlay open={true} onClose={handleClose} />)

    const backdrop = screen.getByRole('dialog')
    fireEvent.click(backdrop)

    expect(handleClose).toHaveBeenCalledTimes(1)
  })

  it('does not close when clicking inside the dialog content', () => {
    const handleClose = vi.fn()
    render(<KeyboardShortcutsOverlay open={true} onClose={handleClose} />)

    // Click on the title text (inside the dialog)
    const title = screen.getByText('Keyboard Shortcuts')
    fireEvent.click(title)

    expect(handleClose).not.toHaveBeenCalled()
  })

  it('closes on X button click', () => {
    const handleClose = vi.fn()
    render(<KeyboardShortcutsOverlay open={true} onClose={handleClose} />)

    const closeButton = screen.getByRole('button', { name: 'Close' })
    fireEvent.click(closeButton)

    expect(handleClose).toHaveBeenCalledTimes(1)
  })

  it('removes event listener when closed', () => {
    const handleClose = vi.fn()
    const { rerender } = render(
      <KeyboardShortcutsOverlay open={true} onClose={handleClose} />
    )

    // Close the overlay
    rerender(<KeyboardShortcutsOverlay open={false} onClose={handleClose} />)

    // Key events should not trigger onClose anymore
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(handleClose).not.toHaveBeenCalled()
  })

  it('displays footer hint', () => {
    render(<KeyboardShortcutsOverlay open={true} onClose={vi.fn()} />)
    expect(screen.getByText('Press ? or Esc to close')).toBeInTheDocument()
  })

  it('has proper accessibility attributes', () => {
    render(<KeyboardShortcutsOverlay open={true} onClose={vi.fn()} />)

    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAttribute('aria-label', 'Keyboard shortcuts')
  })
})
