import React from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

interface CollapsibleSectionProps {
  title: string
  badge?: string | number | null
  defaultOpen?: boolean
  storageKey?: string
  testId?: string
  children: React.ReactNode
}

const CollapsibleSection: React.FC<CollapsibleSectionProps> = ({
  title,
  badge,
  defaultOpen = false,
  storageKey,
  testId,
  children,
}) => {
  const [open, setOpen] = React.useState(() => {
    if (storageKey) {
      try {
        const stored = localStorage.getItem(`notes-section-${storageKey}`)
        if (stored !== null) return stored === 'true'
      } catch {
        /* ignore */
      }
    }
    return defaultOpen
  })

  const toggle = React.useCallback(() => {
    setOpen((prev) => {
      const next = !prev
      if (storageKey) {
        try {
          localStorage.setItem(`notes-section-${storageKey}`, String(next))
        } catch {
          /* ignore */
        }
      }
      return next
    })
  }, [storageKey])

  return (
    <div data-testid={testId}>
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center justify-between py-1.5 text-[11px] uppercase tracking-[0.08em] text-text-muted hover:text-text transition-colors"
        aria-expanded={open}
        data-testid={testId ? `${testId}-toggle` : undefined}
      >
        <span className="flex items-center gap-1.5">
          {title}
          {badge != null && !open && (
            <span
              className="inline-flex items-center rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary"
              data-testid={testId ? `${testId}-badge` : undefined}
            >
              {badge}
            </span>
          )}
        </span>
        {open ? (
          <ChevronDown className="w-3.5 h-3.5" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5" />
        )}
      </button>
      {open && <div className="space-y-2 pb-2">{children}</div>}
    </div>
  )
}

export default React.memo(CollapsibleSection)
