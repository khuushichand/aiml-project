import React, { useEffect, useRef, useState, useCallback } from "react"
import { useTranslation } from "react-i18next"
import { NavLink, useLocation } from "react-router-dom"
import { useShortcut } from "@/hooks/useKeyboardShortcuts"
import { useSetting } from "@/hooks/useSetting"
import {
  HEADER_SHORTCUTS_EXPANDED_SETTING,
  HEADER_SHORTCUT_SELECTION_SETTING
} from "@/services/settings/ui-settings"
import { ChevronDown, Signpost } from "lucide-react"
import { HEADER_SHORTCUT_GROUPS } from "./header-shortcut-items"

const classNames = (...classes: (string | false | null | undefined)[]) =>
  classes.filter(Boolean).join(" ")

type NavigationItem =
  | {
      type: "link"
      to: string
      icon: React.ComponentType<{ className?: string }>
      label: string
    }
  | {
      type: "component"
      key: string
      node: React.ReactNode
    }

interface HeaderShortcutsProps {
  /** Whether to initially show shortcuts expanded */
  defaultExpanded?: boolean
  /** Additional CSS classes */
  className?: string
  /** Whether to render the toggle button */
  showToggle?: boolean
  /** Controlled expanded state */
  expanded?: boolean
  /** Controlled state updater */
  onExpandedChange?: (next: boolean) => void
}

/**
 * Collapsible shortcuts section for the header.
 * Contains navigation groups for quick access to different features.
 * Extracted from Header.tsx for better maintainability.
 */
export function HeaderShortcuts({
  defaultExpanded = false,
  className,
  showToggle = true,
  expanded,
  onExpandedChange,
}: HeaderShortcutsProps) {
  const { t } = useTranslation(["option", "common", "settings"])

  const [shortcutsPreference, setShortcutsPreference] = useSetting(
    HEADER_SHORTCUTS_EXPANDED_SETTING
  )
  const [shortcutSelection] = useSetting(HEADER_SHORTCUT_SELECTION_SETTING)

  type DebouncedShortcutsSetter = ((value: boolean) => void) & {
    cancel: () => void
  }

  const debouncedSetShortcutsPreference =
    React.useMemo<DebouncedShortcutsSetter>(() => {
      let timeoutId: number | undefined

      const fn = ((value: boolean) => {
        if (timeoutId !== undefined) {
          window.clearTimeout(timeoutId)
        }
        timeoutId = window.setTimeout(() => {
          timeoutId = undefined
          void setShortcutsPreference(value).catch(() => {
            // ignore storage write failures
          })
        }, 500)
      }) as DebouncedShortcutsSetter

      fn.cancel = () => {
        if (timeoutId !== undefined) {
          window.clearTimeout(timeoutId)
          timeoutId = undefined
        }
      }

      return fn
    }, [setShortcutsPreference])

  const isControlled = typeof expanded === "boolean"
  const [shortcutsExpandedInternal, setShortcutsExpandedInternal] = useState(() =>
    Boolean(shortcutsPreference ?? defaultExpanded)
  )
  const shortcutsExpanded = isControlled ? expanded : shortcutsExpandedInternal
  const location = useLocation()
  const shortcutsToggleRef = useRef<HTMLButtonElement>(null)
  const shortcutsContainerRef = useRef<HTMLDivElement>(null)
  const shortcutsSectionId = "header-shortcuts-section"
  const previousPathRef = useRef(location.pathname)

  // Navigation groups
  const shortcutSelectionSet = React.useMemo(
    () => new Set(shortcutSelection),
    [shortcutSelection]
  )

  const navigationGroups = React.useMemo(() => {
    return HEADER_SHORTCUT_GROUPS.map((group) => {
      const items: NavigationItem[] = group.items
        .filter((item) => shortcutSelectionSet.has(item.id))
        .map((item) => ({
          type: "link" as const,
          to: item.to,
          icon: item.icon,
          label: t(item.labelKey, item.labelDefault)
        }))
      return {
        key: group.id,
        title: t(group.titleKey, group.titleDefault),
        items
      }
    }).filter((group) => group.items.length > 0)
  }, [shortcutSelectionSet, t])

  // Sync with storage preference
  useEffect(() => {
    if (isControlled) return
    setShortcutsExpandedInternal(Boolean(shortcutsPreference))
  }, [isControlled, shortcutsPreference])

  // Cleanup debounced setter
  useEffect(() => {
    return () => {
      debouncedSetShortcutsPreference.cancel()
    }
  }, [debouncedSetShortcutsPreference])

  // Manage focus for accessibility when expanding/collapsing
  useEffect(() => {
    if (shortcutsExpanded) {
      requestAnimationFrame(() => {
        const container = shortcutsContainerRef.current
        if (!container) return
        const firstFocusable = container.querySelector<HTMLElement>(
          'a, button, [tabindex]:not([tabindex="-1"])'
        )
        firstFocusable?.focus()
      })
    } else {
      const container = shortcutsContainerRef.current
      const active = document.activeElement
      if (container && active && container.contains(active)) {
        shortcutsToggleRef.current?.focus()
      }
    }
  }, [shortcutsExpanded])

  const setShortcutsExpanded = useCallback(
    (next: boolean) => {
      if (isControlled) {
        onExpandedChange?.(next)
        return
      }
      setShortcutsExpandedInternal(next)
      debouncedSetShortcutsPreference(next)
    },
    [debouncedSetShortcutsPreference, isControlled, onExpandedChange]
  )

  const handleToggle = useCallback(() => {
    const next = !shortcutsExpanded
    setShortcutsExpanded(next)
  }, [setShortcutsExpanded, shortcutsExpanded])

  const handleShortcutNavigate = useCallback(() => {
    if (!shortcutsExpanded) return
    setShortcutsExpanded(false)
  }, [setShortcutsExpanded, shortcutsExpanded])

  // Register "?" keyboard shortcut to toggle shortcuts
  useShortcut({
    key: "?",
    modifiers: ["shift"],
    action: handleToggle,
    description: "Toggle keyboard shortcuts",
    // Allow global toggle, even when an input is focused.
    allowInInput: true,
  })

  useEffect(() => {
    if (previousPathRef.current !== location.pathname) {
      previousPathRef.current = location.pathname
      if (shortcutsExpanded) {
        setShortcutsExpanded(false)
      }
    }
  }, [location.pathname, shortcutsExpanded, setShortcutsExpanded])

  if (!showToggle && !shortcutsExpanded) {
    return null
  }

  return (
    <div className={`flex flex-col gap-2 ${className || ""}`}>
      {showToggle && (
        <button
          type="button"
          onClick={handleToggle}
          aria-expanded={shortcutsExpanded}
          aria-controls={shortcutsSectionId}
          ref={shortcutsToggleRef}
          title={t(
            "option:header.shortcutsKeyHint",
            "Press ? to toggle shortcuts"
          )}
          className="inline-flex items-center self-start rounded-md border border-transparent px-2 py-1 text-xs font-semibold uppercase tracking-wide text-text-muted transition hover:border-border hover:bg-surface"
        >
          <ChevronDown
            className={classNames(
              "mr-1 h-4 w-4 transition-transform",
              shortcutsExpanded ? "rotate-180" : ""
            )}
          />
          <Signpost className="mr-1 h-4 w-4" aria-hidden="true" />
          {shortcutsExpanded
            ? t("option:header.hideShortcuts", "Hide shortcuts")
            : t("option:header.showShortcuts", "Show shortcuts")}
          {!shortcutsExpanded && (
            <span className="ml-1.5 text-xs font-normal normal-case tracking-normal text-text-subtle">
              {t("option:header.shortcutsKeyHintInline", "(Press ?)")}
            </span>
          )}
        </button>
      )}

      {shortcutsExpanded && (
        <div
          id={shortcutsSectionId}
          ref={shortcutsContainerRef}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.preventDefault()
              setShortcutsExpanded(false)
              debouncedSetShortcutsPreference(false)
              requestAnimationFrame(() => {
                shortcutsToggleRef.current?.focus()
              })
            }
          }}
          className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between"
          role="region"
          aria-label={t("option:header.showShortcuts", "Shortcuts")}
        >
          <div className="flex flex-col gap-4 lg:flex-1">
            {navigationGroups.length === 0 ? (
              <div className="rounded-md border border-dashed border-border px-3 py-2 text-sm text-text-muted">
                {t(
                  "settings:uiCustomization.shortcuts.empty",
                  "No shortcuts selected"
                )}
              </div>
            ) : (
              navigationGroups.map((group, index) => {
                const groupId = `header-shortcuts-group-${index}`
                return (
                  <section
                    key={group.key}
                    className="flex flex-col gap-2"
                    aria-labelledby={groupId}
                  >
                    <h3
                      id={groupId}
                      className="text-xs font-semibold uppercase tracking-wide text-text-subtle"
                    >
                      {group.title}
                    </h3>
                    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                      {group.items.map((item) => {
                        if (item.type === "component") {
                          return (
                            <div key={item.key} className="w-full sm:w-auto">
                              {item.node}
                            </div>
                          )
                        }
                        const Icon = item.icon
                        return (
                          <NavLink
                            key={item.to}
                            to={item.to}
                            onClick={handleShortcutNavigate}
                            className={({ isActive }) =>
                              classNames(
                                "flex w-full items-center gap-2 rounded-md border px-3 py-2 text-sm transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus sm:w-auto",
                                isActive
                                  ? "border-border bg-surface text-text"
                                  : "border-transparent text-text-muted hover:border-border hover:bg-surface"
                              )
                            }
                          >
                            <Icon className="h-4 w-4" aria-hidden="true" />
                            <span className="truncate">{item.label}</span>
                          </NavLink>
                        )
                      })}
                    </div>
                  </section>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default HeaderShortcuts
