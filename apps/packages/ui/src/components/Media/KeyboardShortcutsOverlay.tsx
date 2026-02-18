import { X, Keyboard } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useEffect, useCallback } from 'react'

interface KeyboardShortcutsOverlayProps {
  open: boolean
  onClose: () => void
}

interface ShortcutItem {
  keys: string[]
  description: string
}

interface ShortcutGroup {
  title: string
  shortcuts: ShortcutItem[]
}

export function KeyboardShortcutsOverlay({ open, onClose }: KeyboardShortcutsOverlayProps) {
  const { t } = useTranslation(['review'])

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' || e.key === '?') {
      e.preventDefault()
      onClose()
    }
  }, [onClose])

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleKeyDown)
      return () => document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, handleKeyDown])

  if (!open) return null

  const shortcutGroups: ShortcutGroup[] = [
    {
      title: t('review:shortcuts.navigation', { defaultValue: 'Navigation' }),
      shortcuts: [
        { keys: ['j'], description: t('review:shortcuts.nextItem', { defaultValue: 'Next item' }) },
        { keys: ['k'], description: t('review:shortcuts.previousItem', { defaultValue: 'Previous item' }) },
        { keys: ['\u2190'], description: t('review:shortcuts.previousPage', { defaultValue: 'Previous page' }) },
        { keys: ['\u2192'], description: t('review:shortcuts.nextPage', { defaultValue: 'Next page' }) },
      ]
    },
    {
      title: t('review:shortcuts.general', { defaultValue: 'General' }),
      shortcuts: [
        { keys: ['/'], description: t('review:shortcuts.focusSearch', { defaultValue: 'Focus search' }) },
        { keys: ['?'], description: t('review:shortcuts.showHelp', { defaultValue: 'Show/hide this help' }) },
        { keys: ['Esc'], description: t('review:shortcuts.closeOverlay', { defaultValue: 'Close overlay' }) },
        {
          keys: ['Esc', 'Esc'],
          description: t('review:shortcuts.clearLargeSelection', {
            defaultValue: 'Clear large selection in multi-review'
          })
        },
      ]
    }
  ]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={t('review:shortcuts.title', { defaultValue: 'Keyboard shortcuts' })}
    >
      <div
        className="bg-surface border border-border rounded-lg shadow-xl max-w-md w-full mx-4 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface2">
          <div className="flex items-center gap-2">
            <Keyboard className="w-5 h-5 text-primary" />
            <h2 className="text-base font-semibold text-text">
              {t('review:shortcuts.title', { defaultValue: 'Keyboard Shortcuts' })}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-text-muted hover:text-text hover:bg-surface rounded transition-colors"
            aria-label={t('common:close', { defaultValue: 'Close' })}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4 max-h-[60vh] overflow-y-auto">
          {shortcutGroups.map((group) => (
            <div key={group.title}>
              <h3 className="text-xs font-medium text-text-muted uppercase tracking-wide mb-2">
                {group.title}
              </h3>
              <div className="space-y-2">
                {group.shortcuts.map((shortcut, idx) => (
                  <div key={idx} className="flex items-center justify-between py-1">
                    <span className="text-sm text-text">{shortcut.description}</span>
                    <div className="flex items-center gap-1">
                      {shortcut.keys.map((key, keyIdx) => (
                        <kbd
                          key={keyIdx}
                          className="inline-flex items-center justify-center min-w-[24px] h-6 px-2 text-xs font-mono bg-surface2 border border-border rounded shadow-sm text-text"
                        >
                          {key}
                        </kbd>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer hint */}
        <div className="px-4 py-2 border-t border-border bg-surface2 text-center">
          <span className="text-xs text-text-muted">
            {t('review:shortcuts.pressToClose', { defaultValue: 'Press ? or Esc to close' })}
          </span>
        </div>
      </div>
    </div>
  )
}
